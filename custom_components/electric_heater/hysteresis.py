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


HEATING_ORDERS = {PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2}


def order_heats(order: str | None) -> bool:
    """Vrai si l'ordre fil pilote fait chauffer le radiateur (Confort, -1, -2)."""
    return order in HEATING_ORDERS


def regulate_preset(
    base: str,
    current: float | None,
    target: float | None,
    last: str | None = None,
) -> str:
    """Adapte l'ordre fil pilote à l'écart consigne / pièce.

    - au-dessus de la consigne : Eco (non chauffant) ;
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
    hyst = HYSTERESIS.get(base, 0.3)
    if current >= target:
        return PRESET_ECO
    if current <= target - hyst:
        return base
    if last == PRESET_ECO:
        return PRESET_ECO
    return base
