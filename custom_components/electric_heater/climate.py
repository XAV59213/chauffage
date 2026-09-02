"""Climate : thermostat virtuel + radiateurs fil pilote."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CALENDAR_OFF_MODE,
    CONF_CALENDAR_ON_MODE,
    CONF_HEATING_CALENDAR,
    CONF_PRESENCE_AWAY_MODE,
    CONF_PRESENCE_SENSOR,
    CONF_TEMP_METHOD,
    CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    EVENT_CENTRAL_CHANGED,
    EVENT_ROOMS_CHANGED,
    EVENT_WINDOWS_CHANGED,
    HYSTERESIS,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_LABELS,
    PRESET_OFF,
    PRESETS,
    VERSION,
    WINDOW_OFF_DELAY,
)
from .fil_pilote import (
    apply_room_order,
    central_window_open,
    entry_windows_open,
    get_central_state,
    iter_room_entries,
    room_fil_pilote_id,
    windows_from_entry,
)
from .hysteresis import should_heat
from .occupancy import occupancy_count

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)

PRESET_TO_TEMP_KEY = {
    PRESET_COMFORT: "comfort",
    PRESET_COMFORT_M1: "comfort_m1",
    PRESET_COMFORT_M2: "comfort_m2",
    PRESET_ECO: "eco",
    PRESET_FROST_PROTECTION: "frost_protection",
}

ACTIVE_CALENDAR_STATES = {"on", "active", "true", "home"}
COMFORT_PRESETS = {PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2}


def _consignes(temps: dict) -> dict[str, float]:
    return {
        PRESET_LABELS[PRESET_COMFORT]: temps.get("comfort"),
        PRESET_LABELS[PRESET_COMFORT_M1]: temps.get("comfort_m1"),
        PRESET_LABELS[PRESET_COMFORT_M2]: temps.get("comfort_m2"),
        PRESET_LABELS[PRESET_ECO]: temps.get("eco"),
        PRESET_LABELS[PRESET_FROST_PROTECTION]: temps.get("frost_protection"),
    }


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("type") == "central":
        async_add_entities([CentralThermostat(hass, entry)])
    else:
        async_add_entities([RoomThermostat(hass, entry)])


class CentralThermostat(ClimateEntity, RestoreEntity):
    """Thermostat virtuel : consigne visible en Auto et envoyee aux radiateurs."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "central"
    _attr_unique_id = "electric_heater_central"
    entity_id = "climate.electric_heater_central"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_precision = PRECISION_TENTHS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._load_from_entry()
        self._current_temp: float | None = None
        self._target_temp: float | None = None
        self._preset_mode = PRESET_COMFORT
        self._hvac_mode = HVACMode.AUTO
        self._hvac_action = HVACAction.IDLE
        self._heating = False
        self._last_manual_preset = PRESET_COMFORT
        self._auto_eco_active = False
        self._calendar_active = False
        self._window_open = False
        self._window_delay = None
        self._unsub_temp = None
        self._unsub_presence = None
        self._unsub_calendar = None
        self._unsub_rooms = None
        self._unsub_windows = None

    def _load_from_entry(self) -> None:
        data = self.entry.data
        self._temps = {
            "comfort": data["comfort_temp"],
            "comfort_m1": data["comfort_m1_temp"],
            "comfort_m2": data["comfort_m2_temp"],
            "eco": data["eco_temp"],
            "frost_protection": data["frost_temp"],
        }
        self._attr_min_temp = data["min_temp"]
        self._attr_max_temp = data["max_temp"]
        self._attr_target_temperature_step = data["temp_step"]
        self._temp_method = data.get(CONF_TEMP_METHOD, "reference")
        self._reference_sensor = data.get(CONF_TEMPERATURE_SENSOR)
        self._presence_sensor = data.get(CONF_PRESENCE_SENSOR)
        self._calendar = data.get(CONF_HEATING_CALENDAR)
        on_mode = data.get(CONF_CALENDAR_ON_MODE, PRESET_COMFORT)
        off_mode = data.get(CONF_CALENDAR_OFF_MODE, PRESET_OFF)
        away_mode = data.get(CONF_PRESENCE_AWAY_MODE, PRESET_ECO)
        self._calendar_on_mode = on_mode if on_mode in PRESETS else PRESET_COMFORT
        self._calendar_off_mode = off_mode if off_mode in PRESETS else PRESET_OFF
        self._presence_away_mode = away_mode if away_mode in PRESETS else PRESET_ECO

    def _windows_live_open(self) -> bool:
        return central_window_open(self.hass) or entry_windows_open(self.hass, self.entry)

    def _cancel_window_delay(self) -> None:
        if self._window_delay:
            self._window_delay()
            self._window_delay = None

    def _temp_for_preset(self, preset: str) -> float:
        key = PRESET_TO_TEMP_KEY.get(preset, "comfort")
        return self._temps.get(key, self._temps["comfort"])

    def _persist_temps(self) -> None:
        self.hass.config_entries.async_update_entry(
            self.entry,
            data={
                **self.entry.data,
                "comfort_temp": self._temps["comfort"],
                "comfort_m1_temp": self._temps["comfort_m1"],
                "comfort_m2_temp": self._temps["comfort_m2"],
                "eco_temp": self._temps["eco"],
                "frost_temp": self._temps["frost_protection"],
            },
        )

    @callback
    def _on_window_delay(self, _now=None):
        self._window_delay = None
        if self._windows_live_open() and not self._window_open:
            self._window_open = True
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            self.hass.create_task(self._push_to_all_rooms())

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "electric_heater_central")},
            "name": self.entry.data.get("name", "Thermostat virtuel"),
            "manufacturer": "XAV59213",
            "model": "Thermostat virtuel 6 ordres",
            "sw_version": VERSION,
        }

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        return self._hvac_action

    @property
    def preset_mode(self) -> str | None:
        if self._window_open:
            return PRESET_OFF
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode = PRESET_OFF if self._window_open or self._hvac_mode == HVACMode.OFF else self._preset_mode
        mode_label = PRESET_LABELS.get(mode, mode)
        return {
            "virtual": True,
            "fil_pilote_mode": mode,
            "fil_pilote_modes": PRESETS,
            "consigne": self._target_temp,
            "consigne_mode": mode_label,
            "consignes": _consignes(self._temps),
            "calendar": self._calendar,
            "calendar_active": self._calendar_active,
            "calendar_on_mode": self._calendar_on_mode,
            "calendar_off_mode": self._calendar_off_mode,
            "presence_away_mode": self._presence_away_mode,
            "presence_sensor": self._presence_sensor,
            "temperatures": self._temps,
            "auto_eco_active": self._auto_eco_active,
            "occupants": self._occupancy_count() if self._has_occupancy_source() else None,
            "current_temperature": self._current_temp,
            "temp_method": self._temp_method,
            "temperature_sensor": self._reference_sensor,
            "window_open": self._window_open,
            "fenetre": "Ouverte" if self._window_open else "Fermee",
            "hysteresis": HYSTERESIS.get(self._preset_mode, 0.3),
            "rooms": [e.title for e in iter_room_entries(self.hass)],
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if last_state := await self.async_get_last_state():
            if last_state.state in ("heat", "off", "auto"):
                self._hvac_mode = HVACMode(last_state.state)
            self._preset_mode = last_state.attributes.get("preset_mode", PRESET_COMFORT)
            if self._preset_mode == PRESET_OFF:
                self._preset_mode = PRESET_COMFORT
            self._last_manual_preset = (
                self._preset_mode if self._preset_mode in COMFORT_PRESETS else PRESET_COMFORT
            )
        self._subscribe_sensors()
        self._unsub_rooms = self.hass.bus.async_listen(EVENT_ROOMS_CHANGED, self._on_rooms_changed)
        self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._handle_windows)
        self._refresh_calendar()
        self._handle_windows()
        if self._hvac_mode == HVACMode.AUTO and not self._window_open:
            self._apply_auto_from_calendar(push=False)
        self._handle_presence_change()
        self._update_central_temperature()
        self._update_target_temp()
        self._update_hvac_action()
        if self._window_open or self._hvac_mode == HVACMode.OFF or (
            self._hvac_mode == HVACMode.AUTO and self._preset_mode == PRESET_OFF
        ):
            self.hass.create_task(self._push_to_all_rooms())

    async def async_will_remove_from_hass(self):
        self._cancel_window_delay()
        for unsub in (
            self._unsub_temp,
            self._unsub_presence,
            self._unsub_calendar,
            self._unsub_rooms,
            self._unsub_windows,
        ):
            if unsub:
                unsub()
        self._unsub_temp = self._unsub_presence = self._unsub_calendar = None
        self._unsub_rooms = self._unsub_windows = None

    @callback
    def _on_rooms_changed(self, event=None):
        self._subscribe_sensors()
        self._update_central_temperature()

    def _subscribe_sensors(self):
        if self._unsub_temp:
            self._unsub_temp()
            self._unsub_temp = None
        if self._unsub_presence:
            self._unsub_presence()
            self._unsub_presence = None
        if self._unsub_calendar:
            self._unsub_calendar()
            self._unsub_calendar = None
        if self._unsub_windows:
            self._unsub_windows()
            self._unsub_windows = None
        sensors = self._get_temperature_sensors()
        if sensors:
            self._unsub_temp = async_track_state_change_event(
                self.hass, sensors, self._update_central_temperature
            )
        if self._presence_sensor:
            self._unsub_presence = async_track_state_change_event(
                self.hass, [self._presence_sensor], self._handle_presence_change
            )
        if self._calendar:
            self._unsub_calendar = async_track_state_change_event(
                self.hass, [self._calendar], self._handle_calendar_change
            )
        windows = windows_from_entry(self.entry)
        if windows:
            self._unsub_windows = async_track_state_change_event(
                self.hass, windows, self._handle_windows
            )

    def _has_occupancy_source(self) -> bool:
        return bool(self._presence_sensor)

    def _occupancy_count(self) -> int:
        return occupancy_count(self.hass, self._presence_sensor)

    @callback
    def _handle_windows(self, event=None):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        live = self._windows_live_open()
        if not live:
            self._cancel_window_delay()
            if self._window_open:
                self._window_open = False
                self._update_target_temp()
                self._update_hvac_action()
                self.async_write_ha_state()
                if self._hvac_mode == HVACMode.AUTO:
                    self._apply_auto_from_calendar(push=True)
                else:
                    self.hass.create_task(self._push_to_all_rooms())
                return
            self.async_write_ha_state()
            return
        if self._window_open:
            return
        if not self._window_delay:
            self._window_delay = async_call_later(
                self.hass, WINDOW_OFF_DELAY, self._on_window_delay
            )
        self.async_write_ha_state()

    def _get_temperature_sensors(self):
        if self._temp_method == CONF_TEMP_METHOD_AVERAGE:
            sensors = [
                e.data.get(CONF_TEMPERATURE_SENSOR)
                for e in iter_room_entries(self.hass)
                if e.data.get(CONF_TEMPERATURE_SENSOR)
            ]
            if self._reference_sensor:
                sensors.append(self._reference_sensor)
            return [s for s in sensors if s]
        return [self._reference_sensor] if self._reference_sensor else []

    def _is_calendar_active(self) -> bool:
        if not self._calendar:
            return True
        state = self.hass.states.get(self._calendar)
        if not state or state.state in ("unknown", "unavailable"):
            return False
        return state.state.lower() in ACTIVE_CALENDAR_STATES

    def _refresh_calendar(self) -> None:
        self._calendar_active = self._is_calendar_active()

    def _apply_auto_from_calendar(self, push: bool = True) -> None:
        if self._hvac_mode != HVACMode.AUTO:
            return
        if self._window_open:
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            if push:
                self.hass.create_task(self._push_to_all_rooms())
            return
        self._refresh_calendar()
        if self._calendar_active:
            preset = self._calendar_on_mode
            if self._last_manual_preset in COMFORT_PRESETS and preset in COMFORT_PRESETS:
                preset = self._last_manual_preset
            if self._has_occupancy_source() and self._occupancy_count() == 0:
                if preset in COMFORT_PRESETS:
                    self._last_manual_preset = preset
                preset = self._presence_away_mode
                self._auto_eco_active = True
            else:
                self._auto_eco_active = False
        else:
            preset = self._calendar_off_mode
            self._auto_eco_active = False
        self._preset_mode = preset
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        if push:
            self.hass.create_task(self._push_to_all_rooms())

    @callback
    def _handle_calendar_change(self, event=None):
        if self._window_open or self._hvac_mode != HVACMode.AUTO:
            return
        was_active = self._calendar_active
        self._refresh_calendar()
        if self._calendar_active and not was_active:
            self._apply_auto_from_calendar(push=True)
            return
        self._apply_auto_from_calendar(push=True)

    @callback
    def _update_central_temperature(self, event=None):
        temps = []
        for entity_id in self._get_temperature_sensors():
            state = self.hass.states.get(entity_id)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    temps.append(float(state.state))
                except ValueError:
                    pass
        self._current_temp = round(sum(temps) / len(temps), 1) if temps else None
        self._update_hvac_action()
        self.async_write_ha_state()

    @callback
    def _handle_presence_change(self, event=None):
        if self._window_open or self._hvac_mode != HVACMode.AUTO:
            return
        if not self._has_occupancy_source():
            return
        if not self._is_calendar_active():
            return
        persons = self._occupancy_count()
        changed = False
        if persons == 0 and not self._auto_eco_active:
            if self._preset_mode in COMFORT_PRESETS:
                self._last_manual_preset = self._preset_mode
            self._preset_mode = self._presence_away_mode
            self._auto_eco_active = True
            changed = True
        elif persons > 0 and self._auto_eco_active:
            self._auto_eco_active = False
            self._apply_auto_from_calendar(push=True)
            return
        if changed:
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            self.hass.create_task(self._push_to_all_rooms())

    def _update_target_temp(self):
        if self._hvac_mode == HVACMode.OFF:
            self._target_temp = None
            return
        if self._preset_mode == PRESET_OFF:
            self._target_temp = self._temps["comfort"]
            return
        self._target_temp = self._temp_for_preset(self._preset_mode)

    def _update_hvac_action(self):
        if self._window_open or self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF:
            self._heating = False
            self._hvac_action = HVACAction.OFF
            return
        self._heating = should_heat(
            self._current_temp, self._target_temp, self._preset_mode, self._heating
        )
        self._hvac_action = HVACAction.HEATING if self._heating else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs):
        if self._window_open:
            return
        if temp := kwargs.get("temperature"):
            key = PRESET_TO_TEMP_KEY.get(self._preset_mode, "comfort")
            if self._preset_mode == PRESET_OFF:
                key = "comfort"
            self._temps[key] = temp
            self._persist_temps()
            if self._preset_mode in COMFORT_PRESETS:
                self._last_manual_preset = self._preset_mode
                self._auto_eco_active = False
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            self._preset_mode = PRESET_OFF
        elif hvac_mode == HVACMode.AUTO:
            self._apply_auto_from_calendar(push=False)
        elif self._preset_mode == PRESET_OFF:
            self._preset_mode = self._last_manual_preset or PRESET_COMFORT
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset_mode = preset_mode
        if preset_mode in COMFORT_PRESETS:
            self._last_manual_preset = preset_mode
        self._auto_eco_active = False
        if preset_mode == PRESET_OFF:
            self._hvac_mode = HVACMode.OFF
        elif self._hvac_mode == HVACMode.OFF:
            self._hvac_mode = HVACMode.HEAT
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def _push_to_all_rooms(self):
        base = (
            PRESET_OFF
            if self._window_open or self._hvac_mode == HVACMode.OFF
            else self._preset_mode
        )
        target = None if base == PRESET_OFF else self._target_temp
        exact = self._hvac_mode == HVACMode.HEAT
        rooms = iter_room_entries(self.hass)
        if not rooms:
            _LOGGER.warning("Aucun radiateur a commander pour l'ordre %s", base)
        for entry in rooms:
            await apply_room_order(self.hass, entry, base, target, exact=exact)
        self.hass.bus.async_fire(EVENT_CENTRAL_CHANGED)


class RoomThermostat(ClimateEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "room"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_precision = PRECISION_TENTHS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_name = f"Chauffage {entry.data['name']}"
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}"
        self._current_temp: float | None = None
        self._target_temp: float | None = None
        self._temps: dict[str, float] = {}
        self._preset_mode = PRESET_COMFORT
        self._hvac_mode = HVACMode.AUTO
        self._heating = False
        self._window_open = False
        self._window_delay = None
        self._hysteresis = 0.3
        self._follow_central = True
        self._temp_sensor = entry.data[CONF_TEMPERATURE_SENSOR]
        self._fil_pilote_select = room_fil_pilote_id(entry.data)
        self._window_sensors = windows_from_entry(entry)
        self._unsub_temp = None
        self._unsub_windows = None
        self._unsub_central = None
        self._unsub_central_state = None

    def _cancel_window_delay(self) -> None:
        if self._window_delay:
            self._window_delay()
            self._window_delay = None

    @callback
    def _on_window_delay(self, _now=None):
        self._window_delay = None
        if entry_windows_open(self.hass, self.entry) and not self._window_open:
            self._window_open = True
            self.hass.create_task(self._apply_fil_pilote())
            self.async_write_ha_state()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "name": self.entry.data["name"],
            "manufacturer": "XAV59213",
            "model": "Radiateur fil pilote",
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    @property
    def current_temperature(self) -> float | None:
        return self._current_temp

    @property
    def target_temperature(self) -> float | None:
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        if self._window_open or self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF:
            return HVACAction.OFF
        if self._current_temp is None or self._target_temp is None:
            return HVACAction.IDLE
        self._heating = should_heat(
            self._current_temp, self._target_temp, self._preset_mode, self._heating
        )
        return HVACAction.HEATING if self._heating else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        return PRESET_OFF if self._window_open else self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        off = self._window_open or self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF
        mode = PRESET_OFF if off else self._preset_mode
        return {
            "window_open": self._window_open,
            "fenetre": "Ouverte" if self._window_open else "Fermee",
            "follow_central": self._follow_central,
            "fil_pilote_mode": mode,
            "consigne": self._target_temp,
            "consigne_mode": PRESET_LABELS.get(mode, mode),
            "consignes": _consignes(self._temps) if self._temps else {},
            "temperature_sensor": self._temp_sensor,
            "fil_pilote": self._fil_pilote_select,
            "hysteresis": HYSTERESIS.get(self._preset_mode, 0.3),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._sync_from_central()
        self._unsub_central = self.hass.bus.async_listen(EVENT_CENTRAL_CHANGED, self._sync_from_central)
        central = get_central_state(self.hass)
        if central:
            self._unsub_central_state = async_track_state_change_event(
                self.hass, [central.entity_id], self._sync_from_central
            )
        if self._temp_sensor:
            self._unsub_temp = async_track_state_change_event(
                self.hass, [self._temp_sensor], self._update_room_temp
            )
        if self._window_sensors:
            self._unsub_windows = async_track_state_change_event(
                self.hass, self._window_sensors, self._check_windows
            )
        self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._check_windows)
        self._update_room_temp()
        self._check_windows()
        self.hass.bus.async_fire(EVENT_ROOMS_CHANGED)

    async def async_will_remove_from_hass(self):
        self._cancel_window_delay()
        for unsub in (self._unsub_temp, self._unsub_windows, self._unsub_central, self._unsub_central_state):
            if unsub:
                unsub()
        self.hass.bus.async_fire(EVENT_ROOMS_CHANGED)

    @callback
    def _sync_from_central(self, event=None):
        central = get_central_state(self.hass)
        if not central:
            return
        if central.state == "heat":
            self._follow_central = True
        if not self._follow_central:
            return
        if central.state in ("heat", "off", "auto"):
            self._hvac_mode = HVACMode(central.state)
        self._preset_mode = central.attributes.get("preset_mode", PRESET_COMFORT)
        self._temps = central.attributes.get("temperatures") or {}
        key = PRESET_TO_TEMP_KEY.get(self._preset_mode, "comfort")
        self._target_temp = central.attributes.get("consigne")
        if self._target_temp is None:
            self._target_temp = self._temps.get(key) or self._temps.get("comfort")
        self._hysteresis = HYSTERESIS.get(self._preset_mode, 0.3)
        self.hass.create_task(self._apply_fil_pilote())
        self.async_write_ha_state()

    @callback
    def _update_room_temp(self, event=None):
        if not self._temp_sensor:
            self._current_temp = None
            self.async_write_ha_state()
            return
        state = self.hass.states.get(self._temp_sensor)
        try:
            self._current_temp = (
                float(state.state)
                if state and state.state not in ("unknown", "unavailable")
                else None
            )
        except (ValueError, TypeError):
            self._current_temp = None
        if self._hvac_mode != HVACMode.HEAT:
            self.hass.create_task(self._apply_fil_pilote())
        self.async_write_ha_state()

    @callback
    def _check_windows(self, event=None):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._window_sensors = windows_from_entry(self.entry)
        live = entry_windows_open(self.hass, self.entry)
        if not live:
            self._cancel_window_delay()
            if self._window_open:
                self._window_open = False
                self.hass.create_task(self._apply_fil_pilote())
            self.async_write_ha_state()
            return
        if self._window_open:
            return
        if not self._window_delay:
            self._window_delay = async_call_later(
                self.hass, WINDOW_OFF_DELAY, self._on_window_delay
            )
        self.async_write_ha_state()

    async def _apply_fil_pilote(self):
        base = (
            PRESET_OFF
            if self._window_open or self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF
            else self._preset_mode
        )
        target = None if base == PRESET_OFF else self._target_temp
        exact = self._hvac_mode == HVACMode.HEAT
        await apply_room_order(self.hass, self.entry, base, target, exact=exact)

    async def async_set_temperature(self, **kwargs):
        if temp := kwargs.get("temperature"):
            self._target_temp = temp
            self._preset_mode = PRESET_COMFORT
            self._hvac_mode = HVACMode.HEAT
            self._follow_central = False
        self.async_write_ha_state()
        await self._apply_fil_pilote()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            self._preset_mode = PRESET_OFF
        elif self._preset_mode == PRESET_OFF:
            self._preset_mode = PRESET_COMFORT
        self.async_write_ha_state()
        await self._apply_fil_pilote()

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        self._follow_central = True
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset_mode = preset_mode
        if preset_mode in PRESET_TO_TEMP_KEY and self._temps:
            self._target_temp = self._temps.get(PRESET_TO_TEMP_KEY[preset_mode])
        self._hvac_mode = HVACMode.OFF if preset_mode == PRESET_OFF else HVACMode.HEAT
        self.async_write_ha_state()
        await self._apply_fil_pilote()
