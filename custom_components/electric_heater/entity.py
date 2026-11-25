"""Base commune des entités : appareil central / appareil radiateur, nom d'entité."""
from __future__ import annotations
from typing import Any, cast

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .building import building_id, central_entity_id, central_uid
from .const import LEGACY_CENTRAL_UID
from .const import DOMAIN
from .device_link import via_central

_LOGGER = logging.getLogger("custom_components.electric_heater")

CENTRAL_DEVICE_ID = "electric_heater_central"


def central_device_info(entry: ConfigEntry | None = None, **extra: Any) -> DeviceInfo:
    """Appareil du thermostat virtuel central du bâtiment (historique : identifiant inchangé)."""
    return cast(DeviceInfo, {"identifiers": {(DOMAIN, central_uid(entry))}, **extra})


def scoped_central_uid(entry: ConfigEntry | None, legacy_uid: str) -> str:
    """unique_id historique (``electric_heater_central_x``) → celui du bâtiment de ``entry``.

    Central historique : identique. Autre bâtiment : ``electric_heater_central_<entry_id>_x``.
    """
    if legacy_uid == LEGACY_CENTRAL_UID:
        return central_uid(entry)
    prefix = f"{LEGACY_CENTRAL_UID}_"
    if legacy_uid.startswith(prefix):
        return central_uid(entry, legacy_uid[len(prefix):])
    return legacy_uid


def room_device_info(hass: HomeAssistant | None, entry: ConfigEntry, **extra: Any) -> DeviceInfo:
    """Appareil d'un radiateur, rattaché au central de son bâtiment (via_device)."""
    return cast(
        DeviceInfo,
        {
            "identifiers": {(DOMAIN, f"room_{entry.entry_id}")},
            **extra,
            **via_central(hass, building_id(hass, entry)),
        },
    )


class CentralEntity(Entity):
    """Entité rattachée à l'appareil central (``self.entry`` = entrée du central, si connue)."""

    _attr_has_entity_name = True
    entry: ConfigEntry | None = None

    @property
    def central_id(self) -> str | None:
        """entry_id du central de ce bâtiment (None = central par défaut)."""
        return self.entry.entry_id if self.entry is not None else None

    @property
    def unique_id(self) -> str | None:
        # Les sous-classes déclarent l'id historique ; il est préfixé pour un autre bâtiment.
        uid = self._attr_unique_id
        return scoped_central_uid(self.entry, uid) if uid else uid

    @property
    def device_info(self) -> DeviceInfo:
        return central_device_info(self.entry)

    def _central_eids(self) -> list[str]:
        """entity_id du thermostat central de ce bâtiment (liste vide s'il n'est pas encore enregistré)."""
        eid = central_entity_id(getattr(self, "hass", None), self.central_id)
        return [eid] if eid else []


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
