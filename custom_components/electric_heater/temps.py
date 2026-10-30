"""Arrondi fiable des consignes à 0,1 °C (évite 20.199999999999998)."""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SETPOINT_DATA_KEYS = (
    "comfort_temp",
    "comfort_m1_temp",
    "comfort_m2_temp",
    "eco_temp",
    "frost_temp",
    "min_temp",
    "max_temp",
)


def round_temp(value) -> float | None:
    """Arrondi décimal à 0,1 : 20.199999999999998 -> 20.2, 11.600000000000001 -> 11.6."""
    if value is None or isinstance(value, bool):
        return None
    try:
        dec = Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None
    return float(dec)


def clean_setpoints(data: dict) -> dict | None:
    """Données avec consignes arrondies, ou None si rien à corriger."""
    changed = False
    new = dict(data)
    for key in SETPOINT_DATA_KEYS:
        if key in new and isinstance(new[key], (int, float)) and not isinstance(new[key], bool):
            rounded = round_temp(new[key])
            if rounded != new[key]:
                new[key] = rounded
                changed = True
    return new if changed else None
