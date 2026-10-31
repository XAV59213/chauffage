"""Lien appareil radiateur → thermostat central (via_device / via_device_id)."""
from __future__ import annotations

import inspect

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

CENTRAL_IDENTIFIER = (DOMAIN, "electric_heater_central")

try:
    _HAS_VIA_ID = "via_device_id" in inspect.signature(
        dr.DeviceRegistry.async_get_or_create
    ).parameters
except (TypeError, ValueError):  # pragma: no cover
    _HAS_VIA_ID = False


def via_central(hass: HomeAssistant | None) -> dict:
    """Clé de liaison vers l'appareil central, compatible anciennes/nouvelles versions HA.

    HA récent : ``via_device_id`` (id du registre) ; ``via_device`` est déprécié (2027.8).
    Si le central n'est pas encore enregistré, rien n'est renvoyé (le lien existant est conservé).
    """
    if not _HAS_VIA_ID:
        return {"via_device": CENTRAL_IDENTIFIER}
    if hass is None:
        return {}
    device = dr.async_get(hass).async_get_device(identifiers={CENTRAL_IDENTIFIER})
    return {"via_device_id": device.id} if device else {}
