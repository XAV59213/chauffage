"""Presence : uniquement le capteur choisi sur le thermostat."""
from __future__ import annotations

from homeassistant.core import HomeAssistant


def occupancy_count(hass: HomeAssistant, sensor_id: str | None) -> int:
    if not sensor_id:
        return 0
    state = hass.states.get(sensor_id)
    if not state or state.state in ("unknown", "unavailable"):
        return 0
    try:
        return int(float(state.state))
    except (TypeError, ValueError):
        return 0 if str(state.state).lower() in ("off", "false", "not_home", "personne") else 1
