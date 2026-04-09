from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CONF_INDOOR_SENSOR,
    CONF_NAME,
    CONF_OUTDOOR_SENSOR,
    CONF_WEATHER_ENTITY,
    DATA_CURRENT,
    DATA_DAY,
    DATA_NIGHT,
    DOMAIN,
    FORECAST_DAILY,
    FORECAST_HOURLY,
    FORECAST_TWICE_DAILY,
    UPDATE_INTERVAL,
)
from .logic import RecommendationSnapshot, calculate_recommendation, speed_to_kmh, temperature_to_celsius

LOGGER = logging.getLogger(__name__)


class TogRatingCoordinator(DataUpdateCoordinator[dict[str, RecommendationSnapshot | None]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        self.name = entry.data[CONF_NAME]
        self.indoor_entity_id = entry.data[CONF_INDOOR_SENSOR]
        self.outdoor_entity_id = entry.data[CONF_OUTDOOR_SENSOR]
        self.weather_entity_id = entry.data[CONF_WEATHER_ENTITY]
        self._unsubscribe_state_listener = None

        super().__init__(
            hass,
            logger=LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=UPDATE_INTERVAL,
        )

    def start_listening(self) -> None:
        if self._unsubscribe_state_listener is not None:
            return
        self._unsubscribe_state_listener = async_track_state_change_event(
            self.hass,
            [self.indoor_entity_id, self.outdoor_entity_id, self.weather_entity_id],
            self._handle_source_change,
        )

    def stop_listening(self) -> None:
        if self._unsubscribe_state_listener is None:
            return
        self._unsubscribe_state_listener()
        self._unsubscribe_state_listener = None

    @callback
    def _handle_source_change(self, event: Event) -> None:
        self.hass.async_create_task(self.async_refresh())

    async def _async_update_data(self) -> dict[str, RecommendationSnapshot | None]:
        try:
            indoor_state = self._get_state(self.indoor_entity_id)
            outdoor_state = self._get_state(self.outdoor_entity_id)
            weather_state = self._get_state(self.weather_entity_id)

            indoor_temp_c = temperature_to_celsius(
                _coerce_float(indoor_state.state, self.indoor_entity_id),
                indoor_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            )
            outdoor_temp_c = temperature_to_celsius(
                _coerce_float(outdoor_state.state, self.outdoor_entity_id),
                outdoor_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            )
            wind_speed = self._wind_speed_from_weather(weather_state.attributes)
            precipitation_probability = weather_state.attributes.get("precipitation_probability")

            data: dict[str, RecommendationSnapshot | None] = {
                DATA_CURRENT: calculate_recommendation(
                    indoor_temp_c=indoor_temp_c,
                    outdoor_temp_c=outdoor_temp_c,
                    condition=weather_state.state,
                    source_label="Current conditions",
                    wind_speed_kmh=wind_speed,
                    precipitation_probability=_safe_int(precipitation_probability),
                ),
                DATA_DAY: None,
                DATA_NIGHT: None,
            }

            forecasts = await self._async_get_forecast_sets()
            day_snapshot, night_snapshot = self._build_forecast_snapshots(
                indoor_temp_c=indoor_temp_c,
                forecasts=forecasts,
            )
            data[DATA_DAY] = day_snapshot
            data[DATA_NIGHT] = night_snapshot
            return data
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    def _get_state(self, entity_id: str):
        state = self.hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise UpdateFailed(f"Entity {entity_id} is unavailable")
        return state

    def _wind_speed_from_weather(self, attributes: dict[str, Any]) -> float | None:
        wind_speed = attributes.get("wind_speed")
        if wind_speed is None:
            return None
        try:
            return speed_to_kmh(_coerce_float(wind_speed, "weather wind_speed"), attributes.get("wind_speed_unit"))
        except (UpdateFailed, ValueError):
            return None

    async def _async_get_forecast_sets(self) -> dict[str, Any]:
        for forecast_type in (FORECAST_DAILY, FORECAST_TWICE_DAILY, FORECAST_HOURLY):
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"type": forecast_type, "entity_id": self.weather_entity_id},
                    blocking=True,
                    return_response=True,
                )
            except Exception:
                LOGGER.debug("Forecast lookup failed for %s", forecast_type, exc_info=True)
                continue

            if not response:
                continue

            payload = response.get(self.weather_entity_id)
            if payload and payload.get("forecast"):
                return {"type": forecast_type, "forecast": payload["forecast"]}
        return {"type": FORECAST_DAILY, "forecast": []}

    def _build_forecast_snapshots(
        self,
        *,
        indoor_temp_c: float,
        forecasts: dict[str, Any],
    ) -> tuple[RecommendationSnapshot | None, RecommendationSnapshot | None]:
        forecast_type = forecasts["type"]
        forecast_list = forecasts["forecast"]
        if not forecast_list:
            return None, None

        if forecast_type == FORECAST_TWICE_DAILY:
            return self._from_twice_daily(indoor_temp_c, forecast_list)
        if forecast_type == FORECAST_HOURLY:
            return self._from_hourly(indoor_temp_c, forecast_list)
        return self._from_daily(indoor_temp_c, forecast_list)

    def _from_twice_daily(
        self,
        indoor_temp_c: float,
        forecast_list: list[dict[str, Any]],
    ) -> tuple[RecommendationSnapshot | None, RecommendationSnapshot | None]:
        day_forecast = next((item for item in forecast_list if item.get("is_daytime") is True), None)
        night_forecast = next((item for item in forecast_list if item.get("is_daytime") is False), None)
        return (
            self._snapshot_from_forecast(indoor_temp_c, day_forecast, "Day forecast"),
            self._snapshot_from_forecast(indoor_temp_c, night_forecast, "Night forecast"),
        )

    def _from_hourly(
        self,
        indoor_temp_c: float,
        forecast_list: list[dict[str, Any]],
    ) -> tuple[RecommendationSnapshot | None, RecommendationSnapshot | None]:
        day_forecast = None
        night_forecast = None
        now = dt_util.utcnow()

        for item in forecast_list:
            parsed = self._parse_forecast_datetime(item)
            if parsed is None or parsed < now:
                continue
            local_hour = dt_util.as_local(parsed).hour
            if 7 <= local_hour < 19 and day_forecast is None:
                day_forecast = item
            if (local_hour >= 19 or local_hour < 7) and night_forecast is None:
                night_forecast = item
            if day_forecast and night_forecast:
                break

        return (
            self._snapshot_from_forecast(indoor_temp_c, day_forecast, "Day forecast"),
            self._snapshot_from_forecast(indoor_temp_c, night_forecast, "Night forecast"),
        )

    def _from_daily(
        self,
        indoor_temp_c: float,
        forecast_list: list[dict[str, Any]],
    ) -> tuple[RecommendationSnapshot | None, RecommendationSnapshot | None]:
        daily = next((item for item in forecast_list if item.get("temperature") is not None), None)
        if daily is None:
            return None, None
        day = dict(daily)
        night = dict(daily)
        day["datetime"] = None
        night["datetime"] = None
        if daily.get("templow") is not None:
            night["temperature"] = daily["templow"]
        return (
            self._snapshot_from_forecast(indoor_temp_c, day, "Day high forecast"),
            self._snapshot_from_forecast(indoor_temp_c, night, "Night low forecast"),
        )

    def _snapshot_from_forecast(
        self,
        indoor_temp_c: float,
        item: dict[str, Any] | None,
        source_label: str,
    ) -> RecommendationSnapshot | None:
        if item is None:
            return None

        if item.get("temperature") is None:
            return None

        weather_state = self._get_state(self.weather_entity_id)
        unit = weather_state.attributes.get("temperature_unit")
        outdoor_temp_c = temperature_to_celsius(
            _coerce_float(item["temperature"], f"{source_label} temperature"),
            unit,
        )

        wind_speed = None
        if item.get("wind_speed") is not None:
            try:
                wind_speed = speed_to_kmh(
                    _coerce_float(item["wind_speed"], f"{source_label} wind_speed"),
                    weather_state.attributes.get("wind_speed_unit"),
                )
            except (UpdateFailed, ValueError):
                wind_speed = None

        return calculate_recommendation(
            indoor_temp_c=indoor_temp_c,
            outdoor_temp_c=outdoor_temp_c,
            condition=item.get("condition") or weather_state.state,
            source_label=source_label,
            forecast_time=self._parse_forecast_datetime(item),
            wind_speed_kmh=wind_speed,
            precipitation_probability=_safe_int(item.get("precipitation_probability")),
        )

    def _parse_forecast_datetime(self, item: dict[str, Any]) -> datetime | None:
        raw = item.get("datetime")
        if raw is None:
            return None
        return dt_util.parse_datetime(raw)


def _safe_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        raise UpdateFailed(f"Invalid numeric value for {label}: {value!r}") from err