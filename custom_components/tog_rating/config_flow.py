from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CHILD_MODE_OPTIONS,
    CONF_BASE_LAYER_TOG,
    CONF_CHILD_MODE,
    CONF_INDOOR_HUMIDITY_SENSOR,
    CONF_INDOOR_SENSOR,
    CONF_NAME,
    CONF_OPENING_SENSORS,
    CONF_WEATHER_ENTITY,
    DEFAULT_BASE_LAYER_TOG,
    DEFAULT_CHILD_MODE,
    DEFAULT_NAME,
    DOMAIN,
)


class TogRatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        return TogRatingOptionsFlow(config_entry)

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_input(user_input)
            errors = _validate_input(self.hass, user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(user_input, include_name=True, include_indoor=True),
            errors=errors,
        )


class TogRatingOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_input(user_input)
            merged = {
                CONF_NAME: self.config_entry.title,
                CONF_INDOOR_SENSOR: self.config_entry.data[CONF_INDOOR_SENSOR],
                CONF_WEATHER_ENTITY: self.config_entry.data[CONF_WEATHER_ENTITY],
                **self.config_entry.options,
                **user_input,
            }
            errors = _validate_input(self.hass, merged)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_WEATHER_ENTITY: _entry_default(self.config_entry, CONF_WEATHER_ENTITY),
            CONF_INDOOR_HUMIDITY_SENSOR: _entry_default(self.config_entry, CONF_INDOOR_HUMIDITY_SENSOR),
            CONF_OPENING_SENSORS: _entry_default(self.config_entry, CONF_OPENING_SENSORS, []),
            CONF_CHILD_MODE: _entry_default(self.config_entry, CONF_CHILD_MODE, DEFAULT_CHILD_MODE),
            CONF_BASE_LAYER_TOG: _entry_default(self.config_entry, CONF_BASE_LAYER_TOG, DEFAULT_BASE_LAYER_TOG),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults, include_name=False, include_indoor=False),
            errors=errors,
        )


def _build_schema(
    user_input: dict[str, Any] | None,
    *,
    include_name: bool,
    include_indoor: bool,
) -> vol.Schema:
    user_input = user_input or {}
    schema: dict[Any, Any] = {}

    if include_name:
        schema[vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME))] = (
            selector.TextSelector()
        )

    if include_indoor:
        schema[vol.Required(CONF_INDOOR_SENSOR, default=user_input.get(CONF_INDOOR_SENSOR))] = (
            selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
        )

    schema[vol.Required(CONF_WEATHER_ENTITY, default=user_input.get(CONF_WEATHER_ENTITY))] = (
        selector.EntitySelector(selector.EntitySelectorConfig(domain="weather"))
    )

    schema[vol.Optional(CONF_INDOOR_HUMIDITY_SENSOR, default=user_input.get(CONF_INDOOR_HUMIDITY_SENSOR))] = (
        selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    )

    schema[vol.Optional(CONF_OPENING_SENSORS, default=user_input.get(CONF_OPENING_SENSORS, []))] = (
        selector.EntitySelector(
            selector.EntitySelectorConfig(
                domain=["binary_sensor", "group"],
                multiple=True,
            )
        )
    )

    schema[vol.Required(CONF_CHILD_MODE, default=user_input.get(CONF_CHILD_MODE, DEFAULT_CHILD_MODE))] = (
        selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=CHILD_MODE_OPTIONS,
                mode=selector.SelectSelectorMode.LIST,
                translation_key=CONF_CHILD_MODE,
            )
        )
    )

    schema[vol.Required(CONF_BASE_LAYER_TOG, default=user_input.get(CONF_BASE_LAYER_TOG, DEFAULT_BASE_LAYER_TOG))] = (
        selector.NumberSelector(
            selector.NumberSelectorConfig(min=0.0, max=1.0, step=0.1, unit_of_measurement="TOG")
        )
    )

    return vol.Schema(schema)


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    if not normalized.get(CONF_INDOOR_HUMIDITY_SENSOR):
        normalized.pop(CONF_INDOOR_HUMIDITY_SENSOR, None)
    if not normalized.get(CONF_OPENING_SENSORS):
        normalized[CONF_OPENING_SENSORS] = []
    normalized[CONF_BASE_LAYER_TOG] = float(normalized.get(CONF_BASE_LAYER_TOG, DEFAULT_BASE_LAYER_TOG))
    return normalized


def _validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    # Indoor temperature sensor
    indoor_id = user_input.get(CONF_INDOOR_SENSOR)
    if indoor_id:
        state = hass.states.get(indoor_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return {"base": "sensor_unavailable"}
        try:
            float(state.state)
        except (TypeError, ValueError):
            return {"base": "invalid_temperature_sensor"}
        if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) not in {"°C", "°F"}:
            return {"base": "invalid_temperature_sensor"}

    # Humidity sensor (optional)
    humidity_id = user_input.get(CONF_INDOOR_HUMIDITY_SENSOR)
    if humidity_id:
        state = hass.states.get(humidity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return {"base": "sensor_unavailable"}
        try:
            float(state.state)
        except (TypeError, ValueError):
            return {"base": "invalid_humidity_sensor"}

    # Weather entity
    weather_state = hass.states.get(user_input[CONF_WEATHER_ENTITY])
    if weather_state is None or weather_state.state in {"unknown", "unavailable"}:
        return {"base": "weather_unavailable"}
    try:
        float(weather_state.attributes.get("temperature"))
    except (TypeError, ValueError):
        return {"base": "invalid_weather_temperature"}
    if weather_state.attributes.get("temperature_unit") not in {"°C", "°F"}:
        return {"base": "invalid_weather_temperature"}

    return {}


def _entry_default(entry: config_entries.ConfigEntry, key: str, default: Any = None) -> Any:
    return entry.options.get(key, entry.data.get(key, default))
