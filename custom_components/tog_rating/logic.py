from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .const import (
    CHILD_MODE_BABY,
    CHILD_MODE_CHILD,
    CHILD_MODE_TODDLER,
    CHILD_MODE_OPTIONS,
    WET_CONDITIONS,
    WINDY_CONDITIONS,
)


# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------

def _c_to_f(val: float | None) -> float | None:
    if val is None:
        return None
    return round(val * 9 / 5 + 32, 1)


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


# ---------------------------------------------------------------------------
# Clothing recommendation tables
# ---------------------------------------------------------------------------

_BABY: dict[str, dict] = {
    "very_light": {
        "tog_rating": 0.2,
        "headline": "Very light layers",
        "clothing_items": [
            "Short-sleeve cotton onesie",
            "0.2 TOG sleep sack",
        ],
        "general_message": "Room's warm — keep it minimal.",
        "risk": "warm",
    },
    "light": {
        "tog_rating": 0.5,
        "headline": "Light layers",
        "clothing_items": [
            "Short-sleeve cotton onesie",
            "0.5 TOG sleep sack",
        ],
        "general_message": "Warm room, light sack.",
        "risk": "comfortable",
    },
    "balanced": {
        "tog_rating": 1.0,
        "headline": "Balanced layers",
        "clothing_items": [
            "Light cotton onesie",
            "1.0 TOG sleep sack",
        ],
        "general_message": "Room's in the sweet spot.",
        "risk": "comfortable",
    },
    "warm": {
        "tog_rating": 2.5,
        "headline": "Warmer setup",
        "clothing_items": [
            "Light cotton onesie",
            "2.5 TOG sleep sack",
        ],
        "general_message": "Room's on the cooler side — reach for the heavier sack.",
        "risk": "cool",
    },
    "extra_warm": {
        "tog_rating": 2.5,
        "headline": "Extra warm layers",
        "clothing_items": [
            "Light cotton onesie",
            "Footed sleepsuit over onesie",
            "2.5 TOG sleep sack — skip weighted sacks",
        ],
        "general_message": "Cold room — layer up, but check he's not too warm after settling.",
        "risk": "cold",
    },
}

_TODDLER: dict[str, dict] = {
    "very_light": {
        "tog_rating": 0.5,
        "headline": "Very light layers",
        "clothing_items": [
            "Short-sleeve cotton PJs or shorts and tee",
            "0.5 TOG sleep sack, or skip the sack if the room stays warm",
        ],
        "general_message": "Too warm for the standard sack.",
        "risk": "warm",
    },
    "light": {
        "tog_rating": 1.0,
        "headline": "Light layers",
        "clothing_items": [
            "Light short-sleeve cotton pajamas",
            "1.0 TOG sleep sack",
        ],
        "general_message": "Warm room, standard sack.",
        "risk": "comfortable",
    },
    "balanced": {
        "tog_rating": 1.0,
        "headline": "Standard setup",
        "clothing_items": [
            "Long-sleeve cotton or jersey pajamas",
            "1.0 TOG sleep sack",
        ],
        "general_message": "Room's comfortable — the 1.0 TOG sack will do the work.",
        "risk": "comfortable",
    },
    "warm": {
        "tog_rating": 1.0,
        "headline": "Warmer setup",
        "clothing_items": [
            "Footed cotton or jersey knit pajamas",
            "1.0 TOG sleep sack",
        ],
        "general_message": "Clothing carries the warmth, sack stays the same.",
        "risk": "cool",
    },
    "extra_warm": {
        "tog_rating": 2.5,
        "headline": "Cold night — extra warm",
        "clothing_items": [
            "Footed fleece pajamas or a thermal base layer under cotton PJs",
            "2.5 TOG sleep sack",
        ],
        "general_message": "Cold enough to step up to the heavier sack.",
        "risk": "cold",
    },
}

_CHILD: dict[str, dict] = {
    "very_light": {
        "tog_rating": 0.0,
        "headline": "Very light layers",
        "clothing_items": [
            "Light cotton shorts and short-sleeve top",
            "Sheet only",
        ],
        "general_message": "Warm room — keep bedding minimal.",
        "risk": "warm",
    },
    "light": {
        "tog_rating": 0.0,
        "headline": "Light layers",
        "clothing_items": [
            "Light cotton long pajamas",
            "Thin blanket",
        ],
        "general_message": "Mild temps, light blanket.",
        "risk": "comfortable",
    },
    "balanced": {
        "tog_rating": 0.0,
        "headline": "Standard setup",
        "clothing_items": [
            "Long-sleeve cotton or jersey pajamas",
            "Light blanket",
        ],
        "general_message": "Comfortable room — standard pajamas and a light blanket.",
        "risk": "comfortable",
    },
    "warm": {
        "tog_rating": 0.0,
        "headline": "Warmer setup",
        "clothing_items": [
            "Flannel or jersey knit footed pajamas",
            "Warm blanket",
        ],
        "general_message": "Cooler room — warmer PJs and a heavier blanket.",
        "risk": "cool",
    },
    "extra_warm": {
        "tog_rating": 0.0,
        "headline": "Cold night — extra warm",
        "clothing_items": [
            "Thermal base layer under fleece or flannel pajamas",
            "Heavy blanket or down throw — no pillow yet, no weighted blankets",
        ],
        "general_message": "Cold room — layer up and check he's comfortable after settling.",
        "risk": "cold",
    },
}

_MODE_TABLES: dict[str, dict[str, dict]] = {
    CHILD_MODE_BABY: _BABY,
    CHILD_MODE_TODDLER: _TODDLER,
    CHILD_MODE_CHILD: _CHILD,
}


# ---------------------------------------------------------------------------
# Snapshot dataclass
# ---------------------------------------------------------------------------

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
    child_mode: str
    forecast_time: datetime | None = None
    condition: str | None = None
    indoor_temp_c: float | None = None
    outdoor_temp_c: float | None = None
    outdoor_temperature_source: str | None = None
    outdoor_weight_percent: int | None = None
    wind_speed_kmh: float | None = None
    precipitation_probability: int | None = None
    indoor_humidity: float | None = None
    outdoor_humidity: float | None = None
    humidity_adjustment_c: float | None = None

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
            "effective_temperature_c": _rounded(self.effective_temp_c),
            "effective_temperature_f": _c_to_f(self.effective_temp_c),
            "risk": self.risk,
            "source_label": self.source_label,
            "child_mode": self.child_mode,
            "forecast_time": self.forecast_time_iso,
            "condition": self.condition,
            "indoor_temperature_c": _rounded(self.indoor_temp_c),
            "indoor_temperature_f": _c_to_f(self.indoor_temp_c),
            "outdoor_temperature_c": _rounded(self.outdoor_temp_c),
            "outdoor_temperature_f": _c_to_f(self.outdoor_temp_c),
            "outdoor_temperature_source": self.outdoor_temperature_source,
            "outdoor_temperature_weight_percent": self.outdoor_weight_percent,
            "wind_speed_kmh": _rounded(self.wind_speed_kmh),
            "precipitation_probability": self.precipitation_probability,
            "indoor_humidity": _rounded(self.indoor_humidity),
            "outdoor_humidity": _rounded(self.outdoor_humidity),
            "humidity_adjustment_c": _rounded(self.humidity_adjustment_c),
        }


# ---------------------------------------------------------------------------
# Core calculation
# ---------------------------------------------------------------------------

def calculate_recommendation(
    *,
    indoor_temp_c: float,
    outdoor_temp_c: float,
    outdoor_weight: float,
    child_mode: str = CHILD_MODE_BABY,
    indoor_humidity: float | None = None,
    outdoor_humidity: float | None = None,
    condition: str | None,
    source_label: str,
    outdoor_temperature_source: str,
    forecast_time: datetime | None = None,
    wind_speed_kmh: float | None = None,
    precipitation_probability: int | None = None,
    temp_offset: float = 0.0,
) -> RecommendationSnapshot:
    condition = condition or "unknown"
    indoor_weight = 1 - outdoor_weight
    effective_temp = (indoor_temp_c * indoor_weight) + (outdoor_temp_c * outdoor_weight)
    adjustments: list[str] = []

    # Humidity adjustment: indoor dominates, outdoor scaled by outdoor weight
    humidity_adjustment = 0.0
    if indoor_humidity is not None:
        humidity_adjustment += (indoor_humidity - 50) * 0.06
    if outdoor_humidity is not None and outdoor_weight > 0:
        humidity_adjustment += (outdoor_humidity - 50) * 0.04 * outdoor_weight
    if humidity_adjustment != 0.0:
        effective_temp += humidity_adjustment
        direction = "warmer" if humidity_adjustment > 0 else "cooler"
        adjustments.append(f"humidity ({direction})")

    # Weather condition adjustments
    if condition in WET_CONDITIONS:
        effective_temp -= 1.5
        adjustments.append("wet weather")
    elif condition in WINDY_CONDITIONS:
        effective_temp -= 0.5
        adjustments.append("wind")

    if wind_speed_kmh is not None:
        if wind_speed_kmh >= 40:
            effective_temp -= 2
            adjustments.append("strong wind")
        elif wind_speed_kmh >= 25:
            effective_temp -= 1
            adjustments.append("breezy")

    if precipitation_probability is not None and precipitation_probability >= 60:
        effective_temp -= 0.5
        adjustments.append("high rain chance")

    # Bucket selection (temp_offset shifts all thresholds uniformly)
    adjusted = effective_temp + temp_offset
    if adjusted >= 24:
        bucket = "very_light"
    elif adjusted >= 22:
        bucket = "light"
    elif adjusted >= 20:
        bucket = "balanced"
    elif adjusted >= 17:
        bucket = "warm"
    else:
        bucket = "extra_warm"

    # Mode-specific clothing/sack/blanket lookup
    mode_key = child_mode if child_mode in _MODE_TABLES else CHILD_MODE_BABY
    rec = _MODE_TABLES[mode_key][bucket]

    # Reasoning string in °F
    indoor_f = _c_to_f(indoor_temp_c)
    outdoor_f = _c_to_f(outdoor_temp_c)
    effective_f = _c_to_f(effective_temp)
    weight_pct = round(outdoor_weight * 100)
    reasoning = f"{indoor_f}°F indoors, {outdoor_f}°F out ({weight_pct}% influence) → {effective_f}°F effective"
    if adjustments:
        reasoning = f"{reasoning}; adjusted for {', '.join(adjustments)}"

    return RecommendationSnapshot(
        bucket=bucket,
        tog_rating=rec["tog_rating"],
        headline=rec["headline"],
        clothing_items=list(rec["clothing_items"]),
        general_message=rec["general_message"],
        reasoning=reasoning,
        effective_temp_c=effective_temp,
        risk=rec["risk"],
        source_label=source_label,
        child_mode=mode_key,
        forecast_time=forecast_time,
        condition=condition,
        indoor_temp_c=indoor_temp_c,
        outdoor_temp_c=outdoor_temp_c,
        outdoor_temperature_source=outdoor_temperature_source,
        outdoor_weight_percent=weight_pct,
        wind_speed_kmh=wind_speed_kmh,
        precipitation_probability=precipitation_probability,
        indoor_humidity=indoor_humidity,
        outdoor_humidity=outdoor_humidity,
        humidity_adjustment_c=round(humidity_adjustment, 3) if humidity_adjustment != 0.0 else None,
    )
