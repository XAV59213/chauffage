"""Bâtiments : une entrée « bâtiment », au plus un thermostat central, ses radiateurs.

- Entrée bâtiment (``type: building``) : le nom du bâtiment, rien d'autre.
- Thermostat central (``type: central``) : ``data["building_entry_id"]`` ; il porte tous les
  réglages du bâtiment (saison, sécurité, notifications, présence, hystérésis…).
- Radiateur (``type: room``) : ``data["building_entry_id"]`` et ``data["central_entry_id"]``.

En interne, un bâtiment est identifié par l'entry_id de son thermostat (``building_id``) :
c'est lui qui commande, les radiateurs suivent.

Le central historique (unique_id d'entrée ``electric_heater_central`` ou absent) garde
exactement ses identifiants. Un central ajouté ensuite utilise des identifiants
préfixés par son entry_id.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    BUILDING,
    CENTRAL,
    CONF_BUILDING_ENTRY_ID,
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


def _conf(entry: ConfigEntry, key: str) -> Any:
    return (entry.options or NO_OPTIONS).get(key) or entry.data.get(key)


def is_room(entry: ConfigEntry) -> bool:
    return entry.data.get("type") not in (CENTRAL, BUILDING)


def building_entries_list(hass: HomeAssistant) -> list[ConfigEntry]:
    """Entrées bâtiment, dans l'ordre de création."""
    return [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") == BUILDING]


def thermostat_of(hass: HomeAssistant, building_entry_id: str | None) -> ConfigEntry | None:
    """Thermostat central du bâtiment (au plus un)."""
    if not building_entry_id:
        return None
    for central in central_entries(hass):
        if central.data.get(CONF_BUILDING_ENTRY_ID) == building_entry_id:
            return central
    return None


def building_of(hass: HomeAssistant, entry: ConfigEntry | None) -> ConfigEntry | None:
    """Entrée bâtiment d'un thermostat ou d'un radiateur (None si absente / supprimée)."""
    if entry is None:
        return None
    if entry.data.get("type") == BUILDING:
        return entry
    bid = _conf(entry, CONF_BUILDING_ENTRY_ID)
    if not bid and is_room(entry):
        central = get_central_entry(hass, _conf(entry, CONF_CENTRAL_ENTRY_ID))
        bid = central.data.get(CONF_BUILDING_ENTRY_ID) if central else None
    found = hass.config_entries.async_get_entry(bid) if bid else None
    return found if found is not None and found.data.get("type") == BUILDING else None


def building_name(hass: HomeAssistant, central: ConfigEntry | None) -> str:
    """Nom affiché du bâtiment d'un thermostat (repli : titre du thermostat)."""
    if central is None:
        return "?"
    building = building_of(hass, central)
    source = building if building is not None else central
    return str(source.title or source.data.get("name") or "?")


def free_buildings(hass: HomeAssistant, keep: str | None = None) -> list[ConfigEntry]:
    """Bâtiments sans thermostat (plus celui du thermostat ``keep``) : 1 thermostat max par bâtiment."""
    used = {
        c.data.get(CONF_BUILDING_ENTRY_ID) for c in central_entries(hass) if c.entry_id != keep
    }
    return [b for b in building_entries_list(hass) if b.entry_id not in used]


def building_id(hass: HomeAssistant | None, entry: ConfigEntry | None) -> str | None:
    """Bâtiment d'une entrée = entry_id de son thermostat central (central lui-même ou radiateur).

    Radiateur : le thermostat de son bâtiment, sinon le thermostat enregistré, sinon le
    thermostat par défaut (historique, sinon le premier).
    """
    if entry is None:
        return None
    if entry.data.get("type") == CENTRAL:
        return entry.entry_id
    if hass is None:
        configured = _conf(entry, CONF_CENTRAL_ENTRY_ID)
        return str(configured) if configured else None
    thermostat = thermostat_of(hass, _conf(entry, CONF_BUILDING_ENTRY_ID))
    if thermostat is not None:
        return thermostat.entry_id
    central = get_central_entry(hass, _conf(entry, CONF_CENTRAL_ENTRY_ID))
    return central.entry_id if central else None


def iter_room_entries(hass: HomeAssistant, central_id: str | None = None) -> list[ConfigEntry]:
    """Radiateurs ; avec central_id, uniquement ceux de ce bâtiment."""
    rooms = [e for e in hass.config_entries.async_entries(DOMAIN) if is_room(e)]
    if central_id is None:
        return rooms
    return [e for e in rooms if building_id(hass, e) == central_id]


def building_entries(hass: HomeAssistant, central_id: str | None) -> list[ConfigEntry]:
    """Entrées d'un bâtiment : son central puis ses pièces (toutes si central_id est None)."""
    if central_id is None:
        return [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") != BUILDING]
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
