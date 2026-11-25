"""Application des ordres fil pilote sur un select ou un climate HA."""
from __future__ import annotations
from homeassistant.core import Context

from collections.abc import Mapping

import logging
import re
from typing import Any, TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, State

from .const import (
    NO_OPTIONS,
    CENTRAL,
    CENTRAL_ENTITY_ID,
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
from .building import (
    building_entries,
    building_id as building_id,  # réexport
    central_entity_id as central_entity_id,  # réexport
    central_entries,
    get_central_entry,
    is_central_unique_id,
    is_legacy_central,
    iter_room_entries as iter_room_entries,  # réexport
)

if TYPE_CHECKING:
    from typing_extensions import TypeIs

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


def room_fil_pilote_id(data: Mapping[str, Any]) -> str | None:
    for key in FIL_PILOTE_DATA_KEYS:
        val = data.get(key)
        if val:
            return str(val)
    return None


def central_option(hass: HomeAssistant, key: str, default: Any = None, central_id: str | None = None) -> Any:
    """Réglage du thermostat central du bâtiment (options puis données), sinon la valeur par défaut."""
    entry = get_central_entry(hass, central_id)
    if entry is None:
        return default
    value = (entry.options or NO_OPTIONS).get(key, entry.data.get(key))
    return default if value is None else value


def get_central_state(hass: HomeAssistant, central_id: str | None = None) -> State | None:
    """État du thermostat central du bâtiment (central par défaut si central_id est None)."""
    eid = central_entity_id(hass, central_id)
    if eid:
        state = hass.states.get(eid)
        if state is not None:
            return state
    if not is_legacy_central(get_central_entry(hass, central_id)):
        return None
    for cand in (
        "climate.electric_heater_central",
        "climate.electric_heater_electric_heater_central",
        "climate.chauffage_central",
        "climate.thermostat_virtuel",
    ):
        state = hass.states.get(cand)
        if state is not None:
            return state
    for state in hass.states.async_all("climate"):
        if state.attributes.get("virtual") is True:
            return state
    return None


def is_central_climate(hass: HomeAssistant, entity_id: str | None) -> bool:
    """True si entity_id désigne UN thermostat central, quel que soit le bâtiment.

    Règle absolue : un central ne reçoit jamais d'ordre fil pilote.
    """
    if not entity_id or not entity_id.startswith("climate."):
        return False
    if entity_id == CENTRAL_ENTITY_ID:
        return True
    try:
        from homeassistant.helpers import entity_registry as er
        ent = er.async_get(hass).async_get(entity_id)
        if ent and ent.platform == DOMAIN and is_central_unique_id(ent.unique_id):
            return True
        for central in central_entries(hass):
            if entity_id == central_entity_id(hass, central.entry_id):
                return True
    except Exception:  # noqa: BLE001
        pass
    st = hass.states.get(entity_id)
    return bool(st and st.attributes.get("virtual") is True)


_ENTITY_ID_RE = re.compile(r"^(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+$")
_ID_IN_TEXT_RE = re.compile(r"\b(binary_sensor|sensor|input_boolean|cover)\.[a-z0-9_]+")


def _collect_ids(raw: Any, out: list[str]) -> None:
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


def parse_window_sensors(data: Mapping[str, Any] | None) -> list[str]:
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

    def _area(ent: er.RegistryEntry) -> str | None:
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
    merged = {**dict(entry.data), **dict(entry.options or NO_OPTIONS)}
    result = parse_window_sensors(merged)
    for eid in area_windows(hass, entry):
        if eid not in result:
            result.append(eid)
    return result


def all_configured_windows(hass: HomeAssistant, central_id: str | None = None) -> list[str]:
    """Détecteurs configurés (bâtiment donné, ou tous si central_id est None)."""
    seen: list[str] = []
    for entry in building_entries(hass, central_id):
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


WINDOW_UNAVAILABLE_GRACE = 900  # s : on garde le dernier état connu d'un détecteur indisponible


def _window_open_cached(hass: HomeAssistant, eid: str) -> bool:
    """État ouvert du détecteur ; si indisponible, dernier état connu (≤ 15 min)."""
    import time

    cache: dict[str, tuple[bool, float]] = hass.data.setdefault(DOMAIN, {}).setdefault("window_last", {})
    state = hass.states.get(eid)
    if state is not None and state.state not in ("unknown", "unavailable"):
        opened = is_window_open_state(state)
        cache[eid] = (opened, time.monotonic())
        return opened
    last = cache.get(eid)
    if last and time.monotonic() - last[1] <= WINDOW_UNAVAILABLE_GRACE:
        return last[0]
    return False


def any_window_open(hass: HomeAssistant, sensors: list[str]) -> bool:
    return any(_window_open_cached(hass, eid) for eid in sensors or [])


def open_windows(hass: HomeAssistant, central_id: str | None = None) -> list[dict[str, Any]]:
    """Fenêtres ouvertes du bâtiment (toutes si central_id est None), inversion par entrée."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in building_entries(hass, central_id):
        invert = bool(
            entry.data.get(CONF_WINDOW_INVERT) or (entry.options or NO_OPTIONS).get(CONF_WINDOW_INVERT)
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


def rooms_sensor_ko(hass: HomeAssistant, central_id: str | None = None) -> list[dict[str, Any]]:
    """Pièces (du bâtiment) dont la sonde de température est indisponible ou invalide."""
    result: list[dict[str, Any]] = []
    for entry in iter_room_entries(hass, central_id):
        sensor = entry.data.get(CONF_TEMPERATURE_SENSOR)
        if sensor and room_current_temp(hass, sensor) is None:
            result.append({"piece": entry.data.get("name"), "sonde": sensor})
    return result


def entry_windows_open(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    sensors = windows_from_entry(entry, hass)
    if not sensors:
        return False
    opened = any_window_open(hass, sensors)
    if entry.data.get(CONF_WINDOW_INVERT) or (entry.options or NO_OPTIONS).get(CONF_WINDOW_INVERT):
        return not opened
    return opened


def house_window_open(hass: HomeAssistant, central_id: str | None = None) -> bool:
    return any(entry_windows_open(hass, entry) for entry in building_entries(hass, central_id))


def central_window_open(hass: HomeAssistant, central_id: str | None = None) -> bool:
    """Fenêtres rattachées au thermostat central du bâtiment."""
    entry = get_central_entry(hass, central_id)
    return entry_windows_open(hass, entry) if entry is not None else False


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


def relay_available(state: State | None) -> TypeIs[State]:
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
    context: Context | None = None,
) -> bool:
    """Envoie l'ordre au relais. Sans force, rien n'est envoyé s'il y est déjà.

    Retourne True si l'ordre est en place (envoyé ou déjà appliqué).
    """
    if not entity_id:
        _LOGGER.warning("Aucun relais fil pilote configuré pour l'ordre %s", preset)
        return False

    if is_central_climate(hass, entity_id):
        _LOGGER.error(
            "Refus d'envoyer l'ordre fil pilote %s sur le thermostat central %s "
            "(ce n'est pas un relais — configurez le select fil pilote de la pièce)",
            preset,
            entity_id,
        )
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
                blocking=True, context=context,
            )
        elif domain == "climate":
            data: dict[str, Any] = {"entity_id": entity_id}
            if preset == PRESET_OFF:
                await hass.services.async_call(
                    "climate", "set_hvac_mode", {**data, "hvac_mode": "off"}, blocking=True, context=context
                )
            else:
                if state.state == "off":
                    await hass.services.async_call(
                        "climate", "set_hvac_mode", {**data, "hvac_mode": "heat"}, blocking=True, context=context
                    )
                if option:
                    await hass.services.async_call(
                        "climate",
                        "set_preset_mode",
                        {**data, "preset_mode": option},
                        blocking=True, context=context,
                    )
                if temperature is not None:
                    await hass.services.async_call(
                        "climate",
                        "set_temperature",
                        {**data, "temperature": temperature},
                        blocking=True, context=context,
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
    bid = building_id(hass, entry)
    sensor = entry.data.get(CONF_TEMPERATURE_SENSOR)
    current = room_current_temp(hass, sensor)
    if sensor and current is None and base_preset not in (PRESET_OFF, PRESET_FROST_PROTECTION):
        # Sonde KO (pile, perte radio...) : Hors-gel par sécurité, jamais Confort.
        return PRESET_FROST_PROTECTION
    if not sensor:
        # Pas de sonde configurée : on applique le preset tel quel.
        return base_preset
    return regulate_preset(
        base_preset,
        current,
        target,
        last,
        above=central_option(hass, CONF_ABOVE_TARGET_MODE, DEFAULT_ABOVE_TARGET_MODE, bid),
        comfort_hyst=central_option(hass, CONF_HYSTERESIS, central_id=bid),
    )
