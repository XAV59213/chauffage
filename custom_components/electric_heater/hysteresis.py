"""Seuil de chauffage et régulation par consigne."""
from __future__ import annotations

from .const import (
    HYSTERESIS,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
)

_HOLD = {PRESET_OFF, PRESET_FROST_PROTECTION}


def should_heat(
    current: float | None,
    target: float | None,
    preset: str | None,
    heating: bool,
) -> bool:
    if current is None or target is None:
        return False
    hyst = HYSTERESIS.get(preset or PRESET_COMFORT, 0.3)
    if current <= target - hyst:
        return True
    if current >= target:
        return False
    return heating


def regulate_preset(
    base: str,
    current: float | None,
    target: float | None,
) -> str:
    """Adapte l'ordre fil pilote à l'écart consigne / pièce."""
    if base in _HOLD:
        return base
    if current is None or target is None:
        return base
    hyst = HYSTERESIS.get(base, 0.3)
    if current >= target:
        return PRESET_ECO if base == PRESET_ECO else PRESET_COMFORT_M1
    if current <= target - hyst:
        return PRESET_COMFORT
    return base
