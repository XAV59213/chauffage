"""Bâtiments : un thermostat central et ses pièces.

Le central historique (unique_id d'entrée ``electric_heater_central`` ou absent) garde
exactement ses identifiants. Un central ajouté ensuite utilise des identifiants
préfixés par son entry_id. Une pièce est rattachée à un central par
``data["central_entry_id"]`` ; à défaut, au central par défaut (historique, sinon le premier).
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CENTRAL,
    CENTRAL_ENTITY_ID,
    CONF_CENTRAL_ENTRY_ID,
    DOMAIN,
    LEGACY_CENTRAL_UID,
    NO_OPTIONS,
)


def is_legacy_central(entry: ConfigEntry | None) -> bool:
    """Central historique : identifiants inchangés (unique_id fixe ou ancienne entrée sans unique_id)."""
    return entry is None or entry.unique_id in (None, "", LEGACY_CENTRAL_UID)


def central_uid(entry: ConfigEntry | None, suffix: str = "") -> str:
    """unique_id d'une entité (ou identifiant d'appareil) du central de ce bâtiment."""
    if entry is None or is_legacy_central(entry):
        base = LEGACY_CENTRAL_UID
    else:
        base = f"{LEGACY_CENTRAL_UID}_{entry.entry_id}"
    return f"{base}_{suffix}" if suffix else base


def central_history_id(entry: ConfigEntry | None) -> str:
    """Clé de l'historique des décisions du central (« central » pour l'historique)."""
    if entry is None or is_legacy_central(entry):
        return "central"
    return f"central_{entry.entry_id}"


def central_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    """Thermostats centraux : l'historique d'abord, puis dans l'ordre de création."""
    entries = [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") == CENTRAL]
    return sorted(entries, key=lambda e: not is_legacy_central(e))


def default_central(hass: HomeAssistant) -> ConfigEntry | None:
    entries = central_entries(hass)
    return entries[0] if entries else None


def get_central_entry(hass: HomeAssistant, central_id: str | None = None) -> ConfigEntry | None:
    """Central demandé ; s'il n'existe pas (ou id absent), le central par défaut."""
    if central_id:
        entry = hass.config_entries.async_get_entry(central_id)
        if entry is not None and entry.domain == DOMAIN and entry.data.get("type") == CENTRAL:
            return entry
    return default_central(hass)


def _configured_central_id(entry: ConfigEntry) -> Any:
    return (entry.options or NO_OPTIONS).get(CONF_CENTRAL_ENTRY_ID) or entry.data.get(CONF_CENTRAL_ENTRY_ID)


def building_id(hass: HomeAssistant | None, entry: ConfigEntry | None) -> str | None:
    """entry_id du central du bâtiment de cette entrée (central lui-même ou pièce)."""
    if entry is None:
        return None
    if entry.data.get("type") == CENTRAL:
        return entry.entry_id
    if hass is None:
        configured = _configured_central_id(entry)
        return str(configured) if configured else None
    central = get_central_entry(hass, _configured_central_id(entry))
    return central.entry_id if central else None


def iter_room_entries(hass: HomeAssistant, central_id: str | None = None) -> list[ConfigEntry]:
    """Pièces ; avec central_id, uniquement celles de ce bâtiment."""
    rooms = [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") != CENTRAL]
    if central_id is None:
        return rooms
    return [e for e in rooms if building_id(hass, e) == central_id]


def building_entries(hass: HomeAssistant, central_id: str | None) -> list[ConfigEntry]:
    """Entrées d'un bâtiment : son central puis ses pièces (toutes si central_id est None)."""
    if central_id is None:
        return list(hass.config_entries.async_entries(DOMAIN))
    central = hass.config_entries.async_get_entry(central_id)
    head = [central] if central is not None else []
    return head + iter_room_entries(hass, central_id)


def central_entity_id(hass: HomeAssistant | None, central_id: str | None = None) -> str | None:
    """entity_id réel du thermostat central de ce bâtiment (registre).

    Central historique : repli sur ``climate.electric_heater_central``. Autre central pas
    encore enregistré : None.
    """
    if hass is None:
        return CENTRAL_ENTITY_ID
    entry = get_central_entry(hass, central_id)
    try:
        from homeassistant.helpers import entity_registry as er

        ent = er.async_get(hass).async_get_entity_id("climate", DOMAIN, central_uid(entry))
        if ent:
            return ent
    except Exception:  # noqa: BLE001
        pass
    return CENTRAL_ENTITY_ID if is_legacy_central(entry) else None


def is_central_unique_id(unique_id: str | None) -> bool:
    """unique_id d'un climate thermostat central (historique ou bâtiment ajouté)."""
    return bool(unique_id) and (
        unique_id == LEGACY_CENTRAL_UID or str(unique_id).startswith(f"{LEGACY_CENTRAL_UID}_")
    )
