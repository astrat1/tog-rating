from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "tog_rating"
PLATFORMS: list[Platform] = [Platform.SENSOR]

# Core config keys
CONF_NAME = "name"
CONF_INDOOR_SENSOR = "indoor_temperature_entity"
CONF_WEATHER_ENTITY = "weather_entity"

# New config keys
CONF_INDOOR_HUMIDITY_SENSOR = "indoor_humidity_entity"
CONF_OPENING_SENSORS = "opening_sensors"
CONF_CHILD_MODE = "child_mode"
CONF_BASE_LAYER_TOG = "base_layer_tog"

# Kept for backward compat with existing config entries (no longer in UI)
CONF_OUTDOOR_SENSOR = "outdoor_temperature_entity"
CONF_OUTDOOR_WEIGHT = "outdoor_temperature_weight"

# Defaults
DEFAULT_NAME = "Child TOG"
DEFAULT_CHILD_MODE = "baby"
DEFAULT_BASE_LAYER_TOG = 0.5

# Dynamic outdoor weighting (fractions, not percent)
OUTDOOR_WEIGHT_OPEN = 0.35      # any opening sensor open > threshold
OUTDOOR_WEIGHT_DEFAULT = 0.10   # house closed, HVAC running
OPEN_THRESHOLD_MINUTES = 60

# Child modes
CHILD_MODE_BABY = "baby"
CHILD_MODE_TODDLER = "toddler"
CHILD_MODE_CHILD = "child"
CHILD_MODE_OPTIONS = [CHILD_MODE_BABY, CHILD_MODE_TODDLER, CHILD_MODE_CHILD]

# Data keys
DATA_CURRENT = "current"
DATA_DAY = "day"
DATA_NIGHT = "night"

# Forecast types
FORECAST_DAILY = "daily"
FORECAST_HOURLY = "hourly"
FORECAST_TWICE_DAILY = "twice_daily"

UPDATE_INTERVAL = timedelta(minutes=15)

RECOMMENDATION_OPTIONS = [
    "very_light",
    "light",
    "balanced",
    "warm",
    "extra_warm",
]

WET_CONDITIONS = {
    "hail",
    "lightning-rainy",
    "pouring",
    "rainy",
    "snowy",
    "snowy-rainy",
}

WINDY_CONDITIONS = {
    "windy",
    "windy-variant",
}
