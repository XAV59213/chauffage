"""Lien appareil radiateur → thermostat central (via_device / via_device_id)."""
from __future__ import annotations
from typing import Any, cast

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


def _central_device(registry: dr.DeviceRegistry) -> dr.DeviceEntry | None:
    """Retrouve l'appareil central (API HA récente, avec repli anciennes versions)."""
    by_ident = getattr(registry, "async_get_device_by_identifier", None)
    if callable(by_ident):
        try:
            return cast("dr.DeviceEntry | None", by_ident(CENTRAL_IDENTIFIER))
        except TypeError:
            # Certaines versions attendent (domain, ident) séparés
            try:
                return cast("dr.DeviceEntry | None", by_ident(*CENTRAL_IDENTIFIER))
            except TypeError:
                pass
    devices_fn = getattr(registry, "async_get_devices", None)
    if callable(devices_fn):
        for device in devices_fn():
            if CENTRAL_IDENTIFIER in device.identifiers:
                return cast(dr.DeviceEntry, device)
        return None
    # Très anciennes versions HA
    return registry.async_get_device(identifiers={CENTRAL_IDENTIFIER})


def via_central(hass: HomeAssistant | None) -> dict[str, Any]:
    """Clé de liaison vers l'appareil central, compatible anciennes/nouvelles versions HA.

    HA récent : ``via_device_id`` (id du registre) ; ``via_device`` est déprécié (2027.8).
    Si le central n'est pas encore enregistré, rien n'est renvoyé (le lien existant est conservé).
    """
    if not _HAS_VIA_ID:
        return {"via_device": CENTRAL_IDENTIFIER}
    if hass is None:
        return {}
    device = _central_device(dr.async_get(hass))
    return {"via_device_id": device.id} if device else {}
