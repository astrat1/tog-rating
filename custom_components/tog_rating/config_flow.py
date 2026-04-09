from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import selector

from .const import (
    CONF_INDOOR_SENSOR,
    CONF_NAME,
    CONF_OUTDOOR_SENSOR,
    CONF_OUTDOOR_WEIGHT,
    CONF_WEATHER_ENTITY,
    DEFAULT_NAME,
    DEFAULT_OUTDOOR_WEIGHT,
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
            data_schema=_build_schema(user_input),
            errors=errors,
        )


class TogRatingOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}

        if user_input is not None:
            user_input = _normalize_input(user_input)
            merged_input = {
                CONF_NAME: self.config_entry.title,
                CONF_INDOOR_SENSOR: self.config_entry.data[CONF_INDOOR_SENSOR],
                CONF_OUTDOOR_SENSOR: self.config_entry.data.get(CONF_OUTDOOR_SENSOR),
                CONF_WEATHER_ENTITY: self.config_entry.data[CONF_WEATHER_ENTITY],
                CONF_OUTDOOR_WEIGHT: self.config_entry.data.get(
                    CONF_OUTDOOR_WEIGHT,
                    DEFAULT_OUTDOOR_WEIGHT,
                ),
                **self.config_entry.options,
                **user_input,
            }
            errors = _validate_input(self.hass, merged_input)
            if not errors:
                return self.async_create_entry(title="", data=user_input)

        defaults = {
            CONF_OUTDOOR_SENSOR: self.config_entry.options.get(
                CONF_OUTDOOR_SENSOR,
                self.config_entry.data.get(CONF_OUTDOOR_SENSOR),
            ),
            CONF_WEATHER_ENTITY: self.config_entry.options.get(
                CONF_WEATHER_ENTITY,
                self.config_entry.data[CONF_WEATHER_ENTITY],
            ),
            CONF_OUTDOOR_WEIGHT: self.config_entry.options.get(
                CONF_OUTDOOR_WEIGHT,
                self.config_entry.data.get(CONF_OUTDOOR_WEIGHT, DEFAULT_OUTDOOR_WEIGHT),
            ),
        }
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults, include_name=False, include_indoor=False),
            errors=errors,
        )


def _build_schema(
    user_input: dict[str, Any] | None,
    *,
    include_name: bool = True,
    include_indoor: bool = True,
) -> vol.Schema:
    user_input = user_input or {}
    schema: dict[Any, Any] = {}

    if include_name:
        schema[vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME))] = selector.TextSelector()

    if include_indoor:
        schema[
            vol.Required(
                CONF_INDOOR_SENSOR,
                default=user_input.get(CONF_INDOOR_SENSOR),
            )
        ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))

    schema[
        vol.Optional(
            CONF_OUTDOOR_SENSOR,
            default=user_input.get(CONF_OUTDOOR_SENSOR),
        )
    ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor"))
    schema[
        vol.Required(
            CONF_WEATHER_ENTITY,
            default=user_input.get(CONF_WEATHER_ENTITY),
        )
    ] = selector.EntitySelector(selector.EntitySelectorConfig(domain="weather"))
    schema[
        vol.Required(
            CONF_OUTDOOR_WEIGHT,
            default=user_input.get(CONF_OUTDOOR_WEIGHT, DEFAULT_OUTDOOR_WEIGHT),
        )
    ] = selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0,
            max=100,
            step=5,
            unit_of_measurement="%",
        )
    )
    return vol.Schema(schema)


def _normalize_input(user_input: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(user_input)
    if not normalized.get(CONF_OUTDOOR_SENSOR):
        normalized.pop(CONF_OUTDOOR_SENSOR, None)
    normalized[CONF_OUTDOOR_WEIGHT] = int(normalized.get(CONF_OUTDOOR_WEIGHT, DEFAULT_OUTDOOR_WEIGHT))
    return normalized


def _validate_input(hass: HomeAssistant, user_input: dict[str, Any]) -> dict[str, str]:
    outdoor_sensor = user_input.get(CONF_OUTDOOR_SENSOR)
    if outdoor_sensor and user_input[CONF_INDOOR_SENSOR] == outdoor_sensor:
        return {"base": "same_temperature_entity"}

    for key in (CONF_INDOOR_SENSOR, CONF_OUTDOOR_SENSOR):
        entity_id = user_input.get(key)
        if not entity_id:
            continue
        state = hass.states.get(entity_id)
        if state is None or state.state in {"unknown", "unavailable"}:
            return {"base": "sensor_unavailable"}
        try:
            float(state.state)
        except (TypeError, ValueError):
            return {"base": "invalid_temperature_sensor"}

        if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) not in {"°C", "°F"}:
            return {"base": "invalid_temperature_sensor"}

    weather_state = hass.states.get(user_input[CONF_WEATHER_ENTITY])
    if weather_state is None or weather_state.state in {"unknown", "unavailable"}:
        return {"base": "weather_unavailable"}

    if not outdoor_sensor:
        try:
            float(weather_state.attributes.get("temperature"))
        except (TypeError, ValueError):
            return {"base": "invalid_weather_temperature"}

        if weather_state.attributes.get("temperature_unit") not in {"°C", "°F"}:
            return {"base": "invalid_weather_temperature"}

    if not 0 <= user_input[CONF_OUTDOOR_WEIGHT] <= 100:
        return {"base": "invalid_outdoor_weight"}

    return {}