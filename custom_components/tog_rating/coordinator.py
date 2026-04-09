from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    CHILD_MODE_BABY,
    CONF_BASE_LAYER_TOG,
    CONF_CHILD_MODE,
    CONF_INDOOR_HUMIDITY_SENSOR,
    CONF_INDOOR_SENSOR,
    CONF_NAME,
    CONF_OPENING_SENSORS,
    CONF_WEATHER_ENTITY,
    DATA_CURRENT,
    DATA_DAY,
    DATA_NIGHT,
    DEFAULT_BASE_LAYER_TOG,
    DEFAULT_CHILD_MODE,
    DOMAIN,
    FORECAST_DAILY,
    FORECAST_HOURLY,
    FORECAST_TWICE_DAILY,
    OPEN_THRESHOLD_MINUTES,
    OUTDOOR_WEIGHT_DEFAULT,
    OUTDOOR_WEIGHT_OPEN,
    UPDATE_INTERVAL,
)
from .logic import RecommendationSnapshot, calculate_recommendation, speed_to_kmh, temperature_to_celsius

LOGGER = logging.getLogger(__name__)


class TogRatingCoordinator(DataUpdateCoordinator[dict[str, RecommendationSnapshot | None]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.config_entry = entry
        self.name = entry.data[CONF_NAME]
        self.indoor_entity_id = _entry_value(entry, CONF_INDOOR_SENSOR)
        self.weather_entity_id = _entry_value(entry, CONF_WEATHER_ENTITY)
        self.indoor_humidity_entity_id = _entry_value(entry, CONF_INDOOR_HUMIDITY_SENSOR)
        self.opening_sensor_ids: list[str] = _entry_value(entry, CONF_OPENING_SENSORS) or []
        self.child_mode: str = _entry_value(entry, CONF_CHILD_MODE, DEFAULT_CHILD_MODE)
        self.base_layer_tog: float = _entry_value(entry, CONF_BASE_LAYER_TOG, DEFAULT_BASE_LAYER_TOG)
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
        tracked = [self.indoor_entity_id, self.weather_entity_id]
        if self.indoor_humidity_entity_id:
            tracked.append(self.indoor_humidity_entity_id)
        tracked.extend(self.opening_sensor_ids)
        self._unsubscribe_state_listener = async_track_state_change_event(
            self.hass, tracked, self._handle_source_change,
        )

    def stop_listening(self) -> None:
        if self._unsubscribe_state_listener is None:
            return
        self._unsubscribe_state_listener()
        self._unsubscribe_state_listener = None

    @callback
    def _handle_source_change(self, event: Event) -> None:
        self.hass.async_create_task(self.async_refresh())

    # ------------------------------------------------------------------
    # Dynamic outdoor weight
    # ------------------------------------------------------------------

    def _get_outdoor_weight(self) -> float:
        """35% if any opening sensor has been open > 60 min, else 10%."""
        threshold = timedelta(minutes=OPEN_THRESHOLD_MINUTES)
        for entity_id in self.opening_sensor_ids:
            state = self.hass.states.get(entity_id)
            if state is None or state.state not in ("on", "open"):
                continue
            if (dt_util.utcnow() - state.last_changed) > threshold:
                return OUTDOOR_WEIGHT_OPEN
        return OUTDOOR_WEIGHT_DEFAULT

    # ------------------------------------------------------------------
    # Humidity helpers
    # ------------------------------------------------------------------

    def _get_indoor_humidity(self) -> float | None:
        if not self.indoor_humidity_entity_id:
            return None
        state = self.hass.states.get(self.indoor_humidity_entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return None
        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _get_outdoor_humidity(self, weather_state) -> float | None:
        try:
            return float(weather_state.attributes.get("humidity"))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Main update
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, RecommendationSnapshot | None]:
        try:
            indoor_state = self._get_state(self.indoor_entity_id)
            weather_state = self._get_state(self.weather_entity_id)

            indoor_temp_c = temperature_to_celsius(
                _coerce_float(indoor_state.state, self.indoor_entity_id),
                indoor_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT),
            )
            outdoor_temp_c = self._current_outdoor_temperature(weather_state)
            outdoor_weight = self._get_outdoor_weight()
            wind_speed = self._wind_speed_from_weather(weather_state.attributes)
            precipitation_probability = weather_state.attributes.get("precipitation_probability")
            indoor_humidity = self._get_indoor_humidity()
            outdoor_humidity = self._get_outdoor_humidity(weather_state)

            data: dict[str, RecommendationSnapshot | None] = {
                DATA_CURRENT: calculate_recommendation(
                    indoor_temp_c=indoor_temp_c,
                    outdoor_temp_c=outdoor_temp_c,
                    outdoor_weight=outdoor_weight,
                    child_mode=self.child_mode,
                    indoor_humidity=indoor_humidity,
                    outdoor_humidity=outdoor_humidity,
                    condition=weather_state.state,
                    source_label="Current conditions",
                    outdoor_temperature_source="weather",
                    wind_speed_kmh=wind_speed,
                    precipitation_probability=_safe_int(precipitation_probability),
                ),
                DATA_DAY: None,
                DATA_NIGHT: None,
            }

            forecasts = await self._async_get_forecast_sets()
            day_snapshot, night_snapshot = self._build_forecast_snapshots(
                indoor_temp_c=indoor_temp_c,
                indoor_humidity=indoor_humidity,
                forecasts=forecasts,
                weather_state=weather_state,
            )
            data[DATA_DAY] = day_snapshot
            data[DATA_NIGHT] = night_snapshot
            return data
        except Exception as err:
            raise UpdateFailed(str(err)) from err

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

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
            return speed_to_kmh(
                _coerce_float(wind_speed, "weather wind_speed"),
                attributes.get("wind_speed_unit"),
            )
        except (UpdateFailed, ValueError):
            return None

    def _current_outdoor_temperature(self, weather_state) -> float:
        weather_temp = weather_state.attributes.get("temperature")
        if weather_temp is None:
            raise UpdateFailed(
                f"Weather entity {self.weather_entity_id} does not expose a current temperature"
            )
        return temperature_to_celsius(
            _coerce_float(weather_temp, f"{self.weather_entity_id} temperature"),
            weather_state.attributes.get("temperature_unit"),
        )

    # ------------------------------------------------------------------
    # Forecast handling
    # ------------------------------------------------------------------

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
        indoor_humidity: float | None,
        forecasts: dict[str, Any],
        weather_state,
    ) -> tuple[RecommendationSnapshot | None, RecommendationSnapshot | None]:
        forecast_type = forecasts["type"]
        forecast_list = forecasts["forecast"]
        if not forecast_list:
            return None, None

        if forecast_type == FORECAST_TWICE_DAILY:
            return self._from_twice_daily(indoor_temp_c, indoor_humidity, forecast_list, weather_state)
        if forecast_type == FORECAST_HOURLY:
            return self._from_hourly(indoor_temp_c, indoor_humidity, forecast_list, weather_state)
        return self._from_daily(indoor_temp_c, indoor_humidity, forecast_list, weather_state)

    def _from_twice_daily(self, indoor_temp_c, indoor_humidity, forecast_list, weather_state):
        day = next((i for i in forecast_list if i.get("is_daytime") is True), None)
        night = next((i for i in forecast_list if i.get("is_daytime") is False), None)
        return (
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, day, "Day forecast", weather_state),
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, night, "Night forecast", weather_state),
        )

    def _from_hourly(self, indoor_temp_c, indoor_humidity, forecast_list, weather_state):
        day_item = night_item = None
        now = dt_util.utcnow()
        for item in forecast_list:
            parsed = self._parse_forecast_datetime(item)
            if parsed is None or parsed < now:
                continue
            local_hour = dt_util.as_local(parsed).hour
            if 7 <= local_hour < 19 and day_item is None:
                day_item = item
            if (local_hour >= 19 or local_hour < 7) and night_item is None:
                night_item = item
            if day_item and night_item:
                break
        return (
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, day_item, "Day forecast", weather_state),
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, night_item, "Night forecast", weather_state),
        )

    def _from_daily(self, indoor_temp_c, indoor_humidity, forecast_list, weather_state):
        daily = next((i for i in forecast_list if i.get("temperature") is not None), None)
        if daily is None:
            return None, None
        day = {**daily, "datetime": None}
        night = {**daily, "datetime": None}
        if daily.get("templow") is not None:
            night["temperature"] = daily["templow"]
        return (
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, day, "Day high forecast", weather_state),
            self._snapshot_from_forecast(indoor_temp_c, indoor_humidity, night, "Night low forecast", weather_state),
        )

    def _snapshot_from_forecast(
        self,
        indoor_temp_c: float,
        indoor_humidity: float | None,
        item: dict[str, Any] | None,
        source_label: str,
        weather_state,
    ) -> RecommendationSnapshot | None:
        if item is None or item.get("temperature") is None:
            return None

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

        # Forecasts assume windows closed overnight — use default weight
        outdoor_weight = OUTDOOR_WEIGHT_DEFAULT

        # Outdoor humidity from forecast item if available, else current weather
        outdoor_humidity: float | None = None
        if item.get("humidity") is not None:
            try:
                outdoor_humidity = float(item["humidity"])
            except (TypeError, ValueError):
                pass
        if outdoor_humidity is None:
            outdoor_humidity = self._get_outdoor_humidity(weather_state)

        return calculate_recommendation(
            indoor_temp_c=indoor_temp_c,
            outdoor_temp_c=outdoor_temp_c,
            outdoor_weight=outdoor_weight,
            child_mode=self.child_mode,
            indoor_humidity=indoor_humidity,
            outdoor_humidity=outdoor_humidity,
            condition=item.get("condition") or weather_state.state,
            source_label=source_label,
            outdoor_temperature_source="forecast",
            forecast_time=self._parse_forecast_datetime(item),
            wind_speed_kmh=wind_speed,
            precipitation_probability=_safe_int(item.get("precipitation_probability")),
        )

    def _parse_forecast_datetime(self, item: dict[str, Any]) -> datetime | None:
        raw = item.get("datetime")
        if raw is None:
            return None
        return dt_util.parse_datetime(raw)


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------

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


def _entry_value(entry: ConfigEntry, key: str, default: Any | None = None) -> Any:
    return entry.options.get(key, entry.data.get(key, default))
