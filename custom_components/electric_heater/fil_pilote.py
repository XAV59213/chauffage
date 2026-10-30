"""Application des ordres fil pilote sur un select ou un climate HA."""
from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State

from .const import (
    CENTRAL,
    CONF_ABOVE_TARGET_MODE,
    CONF_HYSTERESIS,
    DEFAULT_ABOVE_TARGET_MODE,
    CONF_TEMPERATURE_SENSOR,
    CONF_WINDOW_INVERT,
    CONF_WINDOW_SENSORS,
    DOMAIN,
    FIL_PILOTE_ALIASES,
    FIL_PILOTE_DATA_KEYS,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
)
from .hysteresis import regulate_preset

_LOGGER = logging.getLogger(__name__)

_OFF_HINTS = ("off", "stop", "arret", "arrêt")
_OPEN_STATES = {
    "on", "open", "opened", "opening", "true", "1",
    "ouvert", "ouverte", "ouverts", "ouvertes", "ouvrir",
}
_CLOSED_STATES = {
    "off", "closed", "closing", "false", "0",
    "ferme", "fermé", "fermee", "fermée", "fermes", "fermés", "fermees", "fermées",
}


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


def central_option(hass: HomeAssistant, key: str, default: Any = None) -> Any:
    """Réglage du thermostat central (options puis données), sinon la valeur par défaut."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.data.get("type") == CENTRAL:
            value = (entry.options or {}).get(key, entry.data.get(key))
            return default if value is None else value
    return default


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


_ENTITY_ID_RE = re.compile(r"^(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+$")
_ID_IN_TEXT_RE = re.compile(r"\b(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+")


def _collect_ids(raw, out: list[str]) -> None:
    if not raw:
        return
    if isinstance(raw, dict):
        # Config sérialisée par erreur : seule la clé window_sensors compte.
        _collect_ids(raw.get(CONF_WINDOW_SENSORS), out)
        return
    if isinstance(raw, (list, tuple, set)):
        for item in raw:
            _collect_ids(item, out)
        return
    text = str(raw).strip()
    if "{" in text or ":" in text:
        # Texte de config brute ('window_sensors': [...], {'fil_pilote_select': ...})
        m = re.search(r"window_sensors['\"]?\s*:\s*(\[[^\]]*\]|['\"][^'\"]*['\"])", text)
        if m:
            out.extend(x.group(0) for x in _ID_IN_TEXT_RE.finditer(m.group(1)))
        return
    for part in text.split(","):
        part = part.strip().strip("'\"[] ")
        if _ENTITY_ID_RE.match(part):
            out.append(part)


def parse_window_sensors(data: dict | None) -> list[str]:
    """Vrais entity_id de détecteurs de fenêtre, sans doublon (ignore les dicts / config brute)."""
    if not data:
        return []
    raw = data.get(CONF_WINDOW_SENSORS) if isinstance(data, dict) else data
    found: list[str] = []
    _collect_ids(raw, found)
    result: list[str] = []
    for eid in found:
        if eid not in result:
            result.append(eid)
    return result


_AREA_WINDOW_CLASSES = {"window", "door", "opening"}
_AREA_EXCLUDE_HINTS = ("batter", "pile", "tamper", "alarm", "alarme", "garage", "vibration", "occupancy", "motion", "mouvement")


def area_windows(hass: HomeAssistant | None, entry: ConfigEntry) -> list[str]:
    """Détecteurs porte/fenêtre rangés dans la même pièce HA que le radiateur."""
    if hass is None or entry.data.get("type") == CENTRAL:
        return []
    try:
        from homeassistant.helpers import device_registry as dr, entity_registry as er
        ent_reg = er.async_get(hass)
        dev_reg = dr.async_get(hass)
    except Exception:  # noqa: BLE001
        return []

    def _area(ent) -> str | None:
        if ent.area_id:
            return ent.area_id
        if ent.device_id:
            dev = dev_reg.async_get(ent.device_id)
            return dev.area_id if dev else None
        return None

    areas = {
        a for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
        if ent.domain == "climate" and (a := _area(ent))
    }
    if not areas:
        return []
    found: list[str] = []
    for ent in ent_reg.entities.values():
        if ent.domain != "binary_sensor" or ent.disabled_by or ent.platform == DOMAIN:
            continue
        if _area(ent) not in areas:
            continue
        state = hass.states.get(ent.entity_id)
        dclass = ent.device_class or ent.original_device_class or (
            state.attributes.get("device_class") if state else None
        )
        if dclass not in _AREA_WINDOW_CLASSES:
            continue
        if any(h in ent.entity_id.lower() for h in _AREA_EXCLUDE_HINTS):
            continue
        found.append(ent.entity_id)
    return found


def windows_from_entry(entry: ConfigEntry, hass: HomeAssistant | None = None) -> list[str]:
    """Fenêtres configurées + (radiateur) détecteurs de la même pièce HA."""
    merged = {**dict(entry.data), **dict(entry.options or {})}
    result = parse_window_sensors(merged)
    for eid in area_windows(hass, entry):
        if eid not in result:
            result.append(eid)
    return result


def all_configured_windows(hass: HomeAssistant) -> list[str]:
    seen: list[str] = []
    for entry in hass.config_entries.async_entries(DOMAIN):
        for eid in windows_from_entry(entry, hass):
            if eid not in seen:
                seen.append(eid)
    return seen


def is_window_open_state(state: State | None) -> bool:
    if state is None or state.state in ("unknown", "unavailable", None):
        return False
    value = str(state.state).strip().lower()
    if value in _OPEN_STATES:
        return True
    if value in _CLOSED_STATES:
        return False
    # Capteurs type Zigbee2MQTT exposés en sensor : attribut contact (False = ouvert).
    contact = state.attributes.get("contact")
    if isinstance(contact, bool):
        return not contact
    return False


def any_window_open(hass: HomeAssistant, sensors: list[str]) -> bool:
    return any(is_window_open_state(hass.states.get(eid)) for eid in sensors or [])


def open_windows(hass: HomeAssistant) -> list[dict]:
    """Fenêtres ouvertes (toutes entrées), en tenant compte de l'inversion par entrée."""
    result: list[dict] = []
    seen: set[str] = set()
    for entry in hass.config_entries.async_entries(DOMAIN):
        invert = bool(
            entry.data.get(CONF_WINDOW_INVERT) or (entry.options or {}).get(CONF_WINDOW_INVERT)
        )
        for eid in windows_from_entry(entry, hass):
            if eid in seen:
                continue
            state = hass.states.get(eid)
            if state is None or state.state in ("unknown", "unavailable"):
                continue
            if is_window_open_state(state) != invert:
                seen.add(eid)
                name = state.attributes.get("friendly_name") or eid
                result.append({"entity_id": eid, "name": name, "piece": entry.data.get("name")})
    return result


def rooms_sensor_ko(hass: HomeAssistant) -> list[dict]:
    """Pièces dont la sonde de température configurée est indisponible ou invalide."""
    result: list[dict] = []
    for entry in iter_room_entries(hass):
        sensor = entry.data.get(CONF_TEMPERATURE_SENSOR)
        if sensor and room_current_temp(hass, sensor) is None:
            result.append({"piece": entry.data.get("name"), "sonde": sensor})
    return result


def entry_windows_open(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    sensors = windows_from_entry(entry, hass)
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


def room_current_temp(hass: HomeAssistant, sensor_id: str | None) -> float | None:
    if not sensor_id:
        return None
    state = hass.states.get(sensor_id)
    if not state or state.state in ("unknown", "unavailable"):
        return None
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return None


def relay_available(state: State | None) -> bool:
    return state is not None and state.state != "unavailable"


def relay_matches(state: State | None, preset: str, option: str | None) -> bool:
    """Le relais est-il déjà dans l'ordre attendu ?"""
    if state is None or state.state in ("unknown", "unavailable"):
        return False
    domain = state.entity_id.split(".", 1)[0]
    if domain == "select":
        return option is not None and state.state == option
    if domain == "climate":
        if preset == PRESET_OFF:
            return state.state == "off"
        if state.state == "off":
            return False
        return option is None or state.attributes.get("preset_mode") == option
    return False


def expected_option(hass: HomeAssistant, entity_id: str | None, preset: str) -> str | None:
    state = hass.states.get(entity_id) if entity_id else None
    if state is None:
        return None
    available = state.attributes.get("options") or state.attributes.get("preset_modes")
    return resolve_fil_pilote_option(preset, available)


async def apply_fil_pilote(
    hass: HomeAssistant,
    entity_id: str | None,
    preset: str,
    temperature: float | None = None,
    force: bool = False,
) -> bool:
    """Envoie l'ordre au relais. Sans force, rien n'est envoyé s'il y est déjà.

    Retourne True si l'ordre est en place (envoyé ou déjà appliqué).
    """
    if not entity_id:
        _LOGGER.warning("Aucun relais fil pilote configuré pour l'ordre %s", preset)
        return False

    state = hass.states.get(entity_id)
    if not relay_available(state):
        return False

    domain = entity_id.split(".", 1)[0]
    available = state.attributes.get("options") or state.attributes.get("preset_modes")
    option = resolve_fil_pilote_option(preset, available)
    if option is None and domain != "climate":
        _LOGGER.warning(
            "Aucun mode fil pilote correspondant à %s sur %s (dispo: %s)",
            preset,
            entity_id,
            available,
        )
        return False

    if not force and relay_matches(state, preset, option) and (
        domain != "climate"
        or preset == PRESET_OFF
        or temperature is None
        or state.attributes.get("temperature") == temperature
    ):
        return True

    _LOGGER.debug(
        "Fil pilote %s -> %s (demande=%s, consigne=%s, force=%s)",
        entity_id,
        option,
        preset,
        temperature,
        force,
    )
    try:
        if domain == "select":
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": option},
                blocking=True,
            )
        elif domain == "climate":
            data: dict[str, Any] = {"entity_id": entity_id}
            if preset == PRESET_OFF:
                await hass.services.async_call(
                    "climate", "set_hvac_mode", {**data, "hvac_mode": "off"}, blocking=True
                )
            else:
                if state.state == "off":
                    await hass.services.async_call(
                        "climate", "set_hvac_mode", {**data, "hvac_mode": "heat"}, blocking=True
                    )
                if option:
                    await hass.services.async_call(
                        "climate",
                        "set_preset_mode",
                        {**data, "preset_mode": option},
                        blocking=True,
                    )
                if temperature is not None:
                    await hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {**data, "temperature": temperature},
                        blocking=True,
                    )
        else:
            _LOGGER.warning("Type d'entité fil pilote non supporté: %s", entity_id)
            return False
    except Exception as err:  # noqa: BLE001
        _LOGGER.error("Impossible d'appliquer le mode %s sur %s : %s", preset, entity_id, err)
        return False
    return True


def room_order(
    hass: HomeAssistant,
    entry: ConfigEntry,
    base_preset: str,
    target: float | None,
    exact: bool = False,
    last: str | None = None,
) -> str:
    """Ordre à envoyer au radiateur (régulation par la sonde sauf en mode exact)."""
    if exact:
        return base_preset
    sensor = entry.data.get(CONF_TEMPERATURE_SENSOR)
    current = room_current_temp(hass, sensor)
    if sensor and current is None and base_preset not in (PRESET_OFF, PRESET_FROST_PROTECTION):
        # Sonde KO (pile, perte radio...) : Hors-gel par sécurité, jamais Confort.
        return PRESET_FROST_PROTECTION
    return regulate_preset(
        base_preset,
        current,
        target,
        last,
        above=central_option(hass, CONF_ABOVE_TARGET_MODE, DEFAULT_ABOVE_TARGET_MODE),
        comfort_hyst=central_option(hass, CONF_HYSTERESIS),
    )
