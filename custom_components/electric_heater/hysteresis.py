"""Seuil de chauffage : on coupe à la consigne, on relance sous consigne - hyst."""
from __future__ import annotations

from .const import HYSTERESIS, PRESET_COMFORT


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
