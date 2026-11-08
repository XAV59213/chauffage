"""Base commune des entités : appareil central / appareil radiateur, nom d'entité."""
from __future__ import annotations
from typing import Any, cast

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device_link import via_central

_LOGGER = logging.getLogger("custom_components.electric_heater")

CENTRAL_DEVICE_ID = "electric_heater_central"


def central_device_info(**extra: Any) -> DeviceInfo:
    """Appareil du thermostat virtuel central."""
    return cast(DeviceInfo, {"identifiers": {(DOMAIN, CENTRAL_DEVICE_ID)}, **extra})


def room_device_info(hass: HomeAssistant | None, entry: ConfigEntry, **extra: Any) -> DeviceInfo:
    """Appareil d'un radiateur, rattaché au central (via_device)."""
    return cast(
        DeviceInfo,
        {"identifiers": {(DOMAIN, f"room_{entry.entry_id}")}, **extra, **via_central(hass)},
    )


class CentralEntity(Entity):
    """Entité rattachée à l'appareil central."""

    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        return central_device_info()


class RoomEntity(Entity):
    """Entité rattachée à l'appareil d'un radiateur (``self.entry`` = entrée de la pièce)."""

    _attr_has_entity_name = True
    entry: ConfigEntry

    @property
    def device_info(self) -> DeviceInfo:
        return room_device_info(getattr(self, "hass", None), self.entry)


class SourceAvailabilityMixin:
    """Entité qui recopie une source : indisponible avec elle, journalisé une seule fois."""

    _attr_available: bool

    def _set_source_available(self, ok: bool, source: str | None) -> None:
        if ok == self._attr_available:
            return
        self._attr_available = ok
        if ok:
            _LOGGER.info("Source %s de nouveau disponible (%s)", source, getattr(self, "entity_id", None))
        else:
            _LOGGER.info("Source %s indisponible : %s passe en indisponible", source, getattr(self, "entity_id", None))
