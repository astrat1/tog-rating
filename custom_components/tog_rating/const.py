from __future__ import annotations

from datetime import timedelta

from homeassistant.const import Platform

DOMAIN = "tog_rating"
PLATFORMS: list[Platform] = [Platform.SENSOR]

CONF_NAME = "name"
CONF_INDOOR_SENSOR = "indoor_temperature_entity"
CONF_OUTDOOR_SENSOR = "outdoor_temperature_entity"
CONF_OUTDOOR_WEIGHT = "outdoor_temperature_weight"
CONF_WEATHER_ENTITY = "weather_entity"

DEFAULT_NAME = "Child TOG"
DEFAULT_OUTDOOR_WEIGHT = 20
UPDATE_INTERVAL = timedelta(minutes=15)

DATA_CURRENT = "current"
DATA_DAY = "day"
DATA_NIGHT = "night"

FORECAST_DAILY = "daily"
FORECAST_HOURLY = "hourly"
FORECAST_TWICE_DAILY = "twice_daily"

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