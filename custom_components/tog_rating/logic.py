from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import WET_CONDITIONS, WINDY_CONDITIONS


@dataclass(frozen=True)
class RecommendationSnapshot:
    bucket: str
    tog_rating: float
    headline: str
    clothing_items: list[str]
    general_message: str
    reasoning: str
    effective_temp_c: float
    risk: str
    source_label: str
    forecast_time: datetime | None = None
    condition: str | None = None
    indoor_temp_c: float | None = None
    outdoor_temp_c: float | None = None
    outdoor_temperature_source: str | None = None
    outdoor_weight_percent: int | None = None
    wind_speed_kmh: float | None = None
    precipitation_probability: int | None = None

    @property
    def forecast_time_iso(self) -> str | None:
        if self.forecast_time is None:
            return None
        return dt_util.as_local(self.forecast_time).isoformat()

    def as_attributes(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "tog_rating": self.tog_rating,
            "clothing_items": self.clothing_items,
            "general_message": self.general_message,
            "reasoning": self.reasoning,
            "effective_temperature_c": round(self.effective_temp_c, 1),
            "risk": self.risk,
            "source_label": self.source_label,
            "forecast_time": self.forecast_time_iso,
            "condition": self.condition,
            "indoor_temperature_c": _rounded(self.indoor_temp_c),
            "outdoor_temperature_c": _rounded(self.outdoor_temp_c),
            "outdoor_temperature_source": self.outdoor_temperature_source,
            "outdoor_temperature_weight_percent": self.outdoor_weight_percent,
            "wind_speed_kmh": _rounded(self.wind_speed_kmh),
            "precipitation_probability": self.precipitation_probability,
        }


def _rounded(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 1)


def temperature_to_celsius(value: float, unit: str | None) -> float:
    if unit in (None, "°C", "C"):
        return value
    if unit in ("°F", "F"):
        return (value - 32) * 5 / 9
    raise ValueError(f"Unsupported temperature unit: {unit}")


def speed_to_kmh(value: float, unit: str | None) -> float:
    if unit in (None, "km/h", "kmh"):
        return value
    if unit in ("m/s", "mps"):
        return value * 3.6
    if unit in ("mph", "mi/h"):
        return value * 1.609344
    if unit == "ft/s":
        return value * 1.09728
    if unit == "kn":
        return value * 1.852
    if unit == "Beaufort":
        return value * 5
    raise ValueError(f"Unsupported wind speed unit: {unit}")


def calculate_recommendation(
    *,
    indoor_temp_c: float,
    outdoor_temp_c: float,
    outdoor_weight: float,
    condition: str | None,
    source_label: str,
    outdoor_temperature_source: str,
    forecast_time: datetime | None = None,
    wind_speed_kmh: float | None = None,
    precipitation_probability: int | None = None,
) -> RecommendationSnapshot:
    condition = condition or "unknown"
    indoor_weight = 1 - outdoor_weight
    effective_temp = (indoor_temp_c * indoor_weight) + (outdoor_temp_c * outdoor_weight)
    adjustments: list[str] = []

    if condition in WET_CONDITIONS:
        effective_temp -= 1.5
        adjustments.append("wet weather cool-down")
    elif condition in WINDY_CONDITIONS:
        effective_temp -= 0.5
        adjustments.append("wind exposure")

    if wind_speed_kmh is not None:
        if wind_speed_kmh >= 40:
            effective_temp -= 2
            adjustments.append("strong wind")
        elif wind_speed_kmh >= 25:
            effective_temp -= 1
            adjustments.append("breezy conditions")

    if precipitation_probability is not None and precipitation_probability >= 60:
        effective_temp -= 0.5
        adjustments.append("high rain chance")

    if effective_temp >= 24:
        bucket = "very_light"
        tog_rating = 0.2
        headline = "Very light layers"
        clothing_items = [
            "Short-sleeve bodysuit or vest",
            "Light short-leg romper or nappy-only sleep setup",
            "Skip the sleep bag or use a very light 0.2 TOG layer",
        ]
        general_message = "Best for hot rooms and warm weather when overheating is the main concern."
        risk = "warm"
    elif effective_temp >= 22:
        bucket = "light"
        tog_rating = 0.5
        headline = "Light sleepwear"
        clothing_items = [
            "Short-sleeve bodysuit or singlet",
            "Light full sleepsuit",
            "0.5 TOG sleep bag if the room cools later",
        ]
        general_message = "A lighter setup that works well for warm-but-not-hot rooms and milder evenings."
        risk = "comfortable"
    elif effective_temp >= 20:
        bucket = "balanced"
        tog_rating = 1.0
        headline = "Balanced layers"
        clothing_items = [
            "Long-sleeve bodysuit or singlet",
            "Full sleepsuit",
            "1.0 TOG sleep bag",
        ]
        general_message = "A good all-round option for mild weather and cooler rooms overnight."
        risk = "comfortable"
    elif effective_temp >= 17:
        bucket = "warm"
        tog_rating = 2.5
        headline = "Warmer overnight setup"
        clothing_items = [
            "Long-sleeve bodysuit or vest",
            "Warm full sleepsuit",
            "2.5 TOG sleep bag",
        ]
        general_message = "Better for cooler bedrooms where a standard sleep bag may not be enough through the night."
        risk = "cool"
    else:
        bucket = "extra_warm"
        tog_rating = 3.5
        headline = "Extra warm layers"
        clothing_items = [
            "Long-sleeve thermal bodysuit or vest",
            "Warm full sleepsuit",
            "3.5 TOG sleep bag",
        ]
        general_message = "Use this for genuinely cold rooms and re-check regularly so the child does not become too hot after settling."
        risk = "cold"

    reasoning = (
        f"Effective temperature {effective_temp:.1f}°C based on indoor {indoor_temp_c:.1f}°C "
        f"and outdoor {outdoor_temp_c:.1f}°C with {outdoor_weight * 100:.0f}% outdoor weighting"
    )
    if adjustments:
        reasoning = f"{reasoning}; adjusted for {', '.join(adjustments)}"

    return RecommendationSnapshot(
        bucket=bucket,
        tog_rating=tog_rating,
        headline=headline,
        clothing_items=clothing_items,
        general_message=general_message,
        reasoning=reasoning,
        effective_temp_c=effective_temp,
        risk=risk,
        source_label=source_label,
        forecast_time=forecast_time,
        condition=condition,
        indoor_temp_c=indoor_temp_c,
        outdoor_temp_c=outdoor_temp_c,
        outdoor_temperature_source=outdoor_temperature_source,
        outdoor_weight_percent=round(outdoor_weight * 100),
        wind_speed_kmh=wind_speed_kmh,
        precipitation_probability=precipitation_probability,
    )