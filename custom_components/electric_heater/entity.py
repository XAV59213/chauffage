"""Base commune des entités : appareil central / appareil radiateur, nom d'entité."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device_link import via_central

CENTRAL_DEVICE_ID = "electric_heater_central"


def central_device_info(**extra) -> DeviceInfo:
    """Appareil du thermostat virtuel central."""
    return DeviceInfo(identifiers={(DOMAIN, CENTRAL_DEVICE_ID)}, **extra)


def room_device_info(hass: HomeAssistant | None, entry: ConfigEntry, **extra) -> DeviceInfo:
    """Appareil d'un radiateur, rattaché au central (via_device)."""
    return DeviceInfo(
        identifiers={(DOMAIN, f"room_{entry.entry_id}")},
        **extra,
        **via_central(hass),
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
