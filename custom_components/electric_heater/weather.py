"""Météo locale Home Assistant pour adapter le chauffage."""
from __future__ import annotations

from homeassistant.core import HomeAssistant

from .const import (
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    WEATHER_MILD,
    WEATHER_WARM,
)

_COMFORT = {PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2}


def outdoor_temperature(hass: HomeAssistant, weather_id: str | None) -> float | None:
    if not weather_id:
        return None
    state = hass.states.get(weather_id)
    if not state or state.state in ("unknown", "unavailable"):
        return None
    raw = state.attributes.get("temperature")
    if raw is None:
        return None
    try:
        return round(float(raw), 1)
    except (TypeError, ValueError):
        return None


def weather_condition(hass: HomeAssistant, weather_id: str | None) -> str | None:
    if not weather_id:
        return None
    state = hass.states.get(weather_id)
    if not state or state.state in ("unknown", "unavailable"):
        return None
    return state.state


def adjust_preset_for_weather(preset: str, outdoor: float | None) -> str:
    if outdoor is None or preset not in _COMFORT:
        return preset
    if outdoor >= WEATHER_WARM:
        return PRESET_COMFORT_M2
    if outdoor >= WEATHER_MILD:
        return PRESET_COMFORT_M1
    return preset
