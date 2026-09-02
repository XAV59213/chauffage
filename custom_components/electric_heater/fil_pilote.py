"""Application des ordres fil pilote sur un select ou un climate HA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State

from .const import (
    CENTRAL,
    CONF_WINDOW_INVERT,
    CONF_WINDOW_SENSORS,
    DOMAIN,
    FIL_PILOTE_ALIASES,
    FIL_PILOTE_DATA_KEYS,
    PRESET_OFF,
)

_LOGGER = logging.getLogger(__name__)

_OFF_HINTS = ("off", "stop", "arret", "arrêt")
_OPEN_STATES = {"on", "open", "opened", "opening", "true", "1"}


def room_fil_pilote_id(data: dict) -> str | None:
    for key in FIL_PILOTE_DATA_KEYS:
        val = data.get(key)
        if val:
            return val
    return None


def iter_room_entries(hass: HomeAssistant) -> list[ConfigEntry]:
    rooms = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("type") == CENTRAL:
            continue
        rooms.append(entry)
    return rooms


def get_central_state(hass: HomeAssistant) -> State | None:
    for eid in (
        "climate.electric_heater_central",
        "climate.chauffage_central",
        "climate.thermostat_virtuel",
    ):
        state = hass.states.get(eid)
        if state is not None:
            return state
    for state in hass.states.async_all("climate"):
        if state.attributes.get("virtual") is True:
            return state
    return None


def parse_window_sensors(data: dict | None) -> list[str]:
    if not data:
        return []
    raw = data.get(CONF_WINDOW_SENSORS) if isinstance(data, dict) else data
    if not raw:
        return []
    items: list[str] = []
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            if isinstance(item, (list, tuple)):
                items.extend(str(s).strip() for s in item if str(s).strip())
            elif item:
                items.append(str(item).strip())
    else:
        items.extend(s.strip() for s in str(raw).split(",") if s.strip())
    return [s for s in items if "." in s]


def windows_from_entry(entry: ConfigEntry) -> list[str]:
    merged = {**dict(entry.data), **dict(entry.options or {})}
    return parse_window_sensors(merged)


def all_configured_windows(hass: HomeAssistant) -> list[str]:
    seen: list[str] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for eid in windows_from_entry(entry):
            if eid not in seen:
                seen.append(eid)
    return seen


def is_window_open_state(state: State | None) -> bool:
    if state is None or state.state in ("unknown", "unavailable", None):
        return False
    return str(state.state).strip().lower() in _OPEN_STATES


def any_window_open(hass: HomeAssistant, sensors: list[str]) -> bool:
    return any(is_window_open_state(hass.states.get(eid)) for eid in sensors or [])


def entry_windows_open(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    sensors = windows_from_entry(entry)
    if not sensors:
        return False
    opened = any_window_open(hass, sensors)
    if entry.data.get(CONF_WINDOW_INVERT) or (entry.options or {}).get(CONF_WINDOW_INVERT):
        return not opened
    return opened


def house_window_open(hass: HomeAssistant) -> bool:
    return any(
        entry_windows_open(hass, entry)
        for entry in hass.config_entries.async_entries(DOMAIN)
    )


def central_window_open(hass: HomeAssistant) -> bool:
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("type") == CENTRAL:
            return entry_windows_open(hass, entry)
    return False


def resolve_fil_pilote_option(preset: str, available: list[str] | None) -> str | None:
    aliases = FIL_PILOTE_ALIASES.get(preset, [preset])
    if not available:
        return aliases[0]

    available_map = {opt.casefold(): opt for opt in available}
    for alias in aliases:
        if alias.casefold() in available_map:
            return available_map[alias.casefold()]

    for alias in aliases:
        needle = alias.replace("_", " ").replace("-", " ").casefold()
        for key, original in available_map.items():
            cleaned = key.replace("_", " ").replace("-", " ")
            if needle == cleaned or needle in cleaned:
                return original

    if preset == PRESET_OFF:
        for key, original in available_map.items():
            if any(hint in key for hint in _OFF_HINTS):
                return original
    return None


async def apply_fil_pilote(hass: HomeAssistant, entity_id: str | None, preset: str) -> None:
    if central_window_open(hass):
        preset = PRESET_OFF
    if not entity_id:
        _LOGGER.warning("Aucun relais fil pilote configuré pour l'ordre %s", preset)
        return

    state = hass.states.get(entity_id)
    if state is None:
        _LOGGER.warning("Entité fil pilote introuvable: %s", entity_id)
        return

    domain = entity_id.split(".", 1)[0]
    available = state.attributes.get("options") or state.attributes.get("preset_modes")
    option = resolve_fil_pilote_option(preset, available)
    _LOGGER.debug(
        "Fil pilote %s -> %s (demande=%s, dispo=%s)",
        entity_id,
        option,
        preset,
        available,
    )
    if option is None and domain != "climate":
        _LOGGER.warning(
            "Aucun mode fil pilote correspondant à %s sur %s (dispo: %s)",
            preset,
            entity_id,
            available,
        )
        return

    try:
        if domain == "select":
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": option},
                blocking=False,
            )
        elif domain == "climate":
            data: dict[str, Any] = {"entity_id": entity_id}
            if preset == PRESET_OFF:
                await hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {**data, "hvac_mode": "off"},
                    blocking=False,
                )
            else:
                if state.state == "off":
                    await hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {**data, "hvac_mode": "heat"},
                        blocking=False,
                    )
                if option:
                    await hass.services.async_call(
                        "climate",
                        "set_preset_mode",
                        {**data, "preset_mode": option},
                        blocking=False,
                    )
        else:
            _LOGGER.warning("Type d'entité fil pilote non supporté: %s", entity_id)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Impossible d'appliquer le mode %s sur %s", preset, entity_id)
