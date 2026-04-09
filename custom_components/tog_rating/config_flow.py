from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT
from homeassistant.helpers import selector

from .const import (
    CONF_INDOOR_SENSOR,
    CONF_NAME,
    CONF_OUTDOOR_SENSOR,
    CONF_WEATHER_ENTITY,
    DEFAULT_NAME,
    DOMAIN,
)


class TogRatingConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate_input(user_input)
            if not errors:
                return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema_with_defaults(user_input),
            errors=errors,
        )

    def _schema_with_defaults(self, user_input: dict[str, Any] | None) -> vol.Schema:
        user_input = user_input or {}
        return vol.Schema(
            {
                vol.Required(CONF_NAME, default=user_input.get(CONF_NAME, DEFAULT_NAME)): selector.TextSelector(),
                vol.Required(
                    CONF_INDOOR_SENSOR,
                    default=user_input.get(CONF_INDOOR_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_OUTDOOR_SENSOR,
                    default=user_input.get(CONF_OUTDOOR_SENSOR),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    CONF_WEATHER_ENTITY,
                    default=user_input.get(CONF_WEATHER_ENTITY),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="weather")
                ),
            }
        )

    def _validate_input(self, user_input: dict[str, Any]) -> dict[str, str]:
        if user_input[CONF_INDOOR_SENSOR] == user_input[CONF_OUTDOOR_SENSOR]:
            return {"base": "same_temperature_entity"}

        for key in (CONF_INDOOR_SENSOR, CONF_OUTDOOR_SENSOR):
            entity_id = user_input[key]
            state = self.hass.states.get(entity_id)
            if state is None or state.state in {"unknown", "unavailable"}:
                return {"base": "sensor_unavailable"}
            try:
                float(state.state)
            except (TypeError, ValueError):
                return {"base": "invalid_temperature_sensor"}

            if state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) not in {"°C", "°F"}:
                return {"base": "invalid_temperature_sensor"}

        weather_state = self.hass.states.get(user_input[CONF_WEATHER_ENTITY])
        if weather_state is None or weather_state.state in {"unknown", "unavailable"}:
            return {"base": "weather_unavailable"}

        return {}