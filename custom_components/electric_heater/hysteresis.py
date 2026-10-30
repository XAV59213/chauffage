"""Seuil de chauffage et régulation par consigne."""
from __future__ import annotations

from .const import (
    HYSTERESIS,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
)

_HOLD = {PRESET_OFF, PRESET_FROST_PROTECTION}


def hysteresis_for(preset: str | None, comfort_hyst: float | None = None) -> float:
    """Hystérésis du preset ; la valeur réglable s'applique aux presets Confort."""
    preset = preset or PRESET_COMFORT
    if comfort_hyst is not None and preset in (PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2):
        return float(comfort_hyst)
    return HYSTERESIS.get(preset, 0.3)


def should_heat(
    current: float | None,
    target: float | None,
    preset: str | None,
    heating: bool,
    comfort_hyst: float | None = None,
) -> bool:
    if current is None or target is None:
        return False
    hyst = hysteresis_for(preset, comfort_hyst)
    if current <= target - hyst:
        return True
    if current >= target:
        return False
    return heating


HEATING_ORDERS = {PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2}


def order_heats(order: str | None) -> bool:
    """Vrai si l'ordre fil pilote fait chauffer le radiateur (Confort, -1, -2)."""
    return order in HEATING_ORDERS


def regulate_preset(
    base: str,
    current: float | None,
    target: float | None,
    last: str | None = None,
    above: str = PRESET_ECO,
    comfort_hyst: float | None = None,
) -> str:
    """Adapte l'ordre fil pilote à l'écart consigne / pièce.

    - au-dessus de la consigne : ordre non chauffant réglable (Eco par défaut) ;
    - sous consigne - hystérésis : l'ordre de base, jamais plus chaud que lui ;
    - entre les deux : on garde le dernier ordre envoyé (hystérésis avec mémoire).
    """
    if base in _HOLD:
        return base
    if current is None or target is None:
        return base
    if base not in HEATING_ORDERS:
        # Eco (absence, nuit...) : jamais remonter en Confort.
        return base
    if above not in (PRESET_ECO, PRESET_FROST_PROTECTION, PRESET_OFF):
        above = PRESET_ECO
    hyst = hysteresis_for(base, comfort_hyst)
    if current >= target:
        return above
    if current <= target - hyst:
        return base
    if last == above:
        return above
    return base
