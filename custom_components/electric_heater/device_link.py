"""Lien appareil radiateur → thermostat central (via_device / via_device_id)."""
from __future__ import annotations
from typing import Any, cast

import inspect

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .building import central_uid, get_central_entry
from .const import DOMAIN

CENTRAL_IDENTIFIER = (DOMAIN, "electric_heater_central")


def central_identifier(hass: HomeAssistant | None, central_id: str | None = None) -> tuple[str, str]:
    """Identifiant d'appareil du central du bâtiment (historique : inchangé)."""
    entry = get_central_entry(hass, central_id) if hass is not None else None
    return (DOMAIN, central_uid(entry))

try:
    _HAS_VIA_ID = "via_device_id" in inspect.signature(
        dr.DeviceRegistry.async_get_or_create
    ).parameters
except (TypeError, ValueError):  # pragma: no cover
    _HAS_VIA_ID = False


def _accepts_entry_id(func: Any) -> bool:
    try:
        return "config_entry_id" in inspect.signature(func).parameters
    except (TypeError, ValueError):  # pragma: no cover
        return False


def _central_device(
    registry: dr.DeviceRegistry,
    ident: tuple[str, str] = CENTRAL_IDENTIFIER,
    config_entry_id: str | None = None,
) -> dr.DeviceEntry | None:
    """Retrouve l'appareil central (API HA récente, avec repli anciennes versions)."""
    by_ident = getattr(registry, "async_get_device_by_identifier", None)
    if callable(by_ident):
        if config_entry_id and _accepts_entry_id(by_ident):
            # HA 2026.x : identifiants uniques par entrée, l'entrée du central est requise.
            return cast("dr.DeviceEntry | None", by_ident(ident, config_entry_id))
        try:
            return cast("dr.DeviceEntry | None", by_ident(ident))
        except TypeError:
            # Certaines versions attendent (domain, ident) séparés
            try:
                return cast("dr.DeviceEntry | None", by_ident(*ident))
            except TypeError:
                pass
    devices_fn = getattr(registry, "async_get_devices", None)
    if callable(devices_fn):
        for device in devices_fn():
            if ident in device.identifiers:
                return cast(dr.DeviceEntry, device)
        return None
    # Très anciennes versions HA
    return registry.async_get_device(identifiers={ident})


def via_central(hass: HomeAssistant | None, central_id: str | None = None) -> dict[str, Any]:
    """Clé de liaison vers l'appareil central du bâtiment, compatible anciennes/nouvelles versions HA.

    HA récent : ``via_device_id`` (id du registre) ; ``via_device`` est déprécié (2027.8).
    Si le central n'est pas encore enregistré, rien n'est renvoyé (le lien existant est conservé).
    """
    ident = central_identifier(hass, central_id)
    if not _HAS_VIA_ID:
        return {"via_device": ident}
    if hass is None:
        return {}
    central = get_central_entry(hass, central_id)
    device = _central_device(dr.async_get(hass), ident, central.entry_id if central else None)
    return {"via_device_id": device.id} if device else {}
