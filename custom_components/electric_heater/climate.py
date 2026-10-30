"""Climate : thermostat virtuel + radiateurs fil pilote."""
from __future__ import annotations

import asyncio
from datetime import timedelta
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
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CENTRAL_ENTITY_ID,
    CONF_CALENDAR_OFF_MODE,
    CONF_CALENDAR_ON_MODE,
    CONF_HEATING_CALENDAR,
    CONF_PRESENCE_AWAY_MODE,
    CONF_PRESENCE_SENSOR,
    CONF_TEMP_METHOD,
    CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMPERATURE_SENSOR,
    CONF_HYSTERESIS,
    CONF_RESYNC_INTERVAL,
    CONF_WINDOW_MODE,
    CONF_WINDOW_OFF_DELAY,
    DEFAULT_CALENDAR_OFF_MODE,
    DEFAULT_WINDOW_MODE,
    DOMAIN,
    EVENT_CENTRAL_CHANGED,
    EVENT_CENTRAL_COMMAND,
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
    RELAY_CHECK_DELAY,
    RESYNC_INTERVAL_MIN,
    SENSOR_KO_MESSAGE,
    SIGNAL_SETPOINTS_UPDATED,
    VERSION,
    WINDOW_MODES,
    WINDOW_OFF_DELAY,
)
from .fil_pilote import (
    apply_fil_pilote,
    central_window_open,
    entry_windows_open,
    expected_option,
    central_option,
    get_central_state,
    iter_room_entries,
    relay_available,
    relay_matches,
    room_fil_pilote_id,
    room_order,
    windows_from_entry,
)
from .hysteresis import hysteresis_for, order_heats, should_heat
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
# Du plus froid au plus chaud : une fenêtre ouverte ne peut que baisser l'ordre.
_PRESET_RANK = {
    PRESET_OFF: 0,
    PRESET_FROST_PROTECTION: 1,
    PRESET_ECO: 2,
    PRESET_COMFORT_M2: 3,
    PRESET_COMFORT_M1: 4,
    PRESET_COMFORT: 5,
}


def window_preset(preset: str, window_mode: str) -> str:
    """Ordre avec une fenêtre ouverte : le plus bas des deux."""
    if _PRESET_RANK.get(window_mode, 1) < _PRESET_RANK.get(preset, 5):
        return window_mode
    return preset


def _consignes(temps: dict) -> dict[str, float]:
    return {
        PRESET_LABELS[PRESET_COMFORT]: temps.get("comfort"),
        PRESET_LABELS[PRESET_COMFORT_M1]: temps.get("comfort_m1"),
        PRESET_LABELS[PRESET_COMFORT_M2]: temps.get("comfort_m2"),
        PRESET_LABELS[PRESET_ECO]: temps.get("eco"),
        PRESET_LABELS[PRESET_FROST_PROTECTION]: temps.get("frost_protection"),
    }



class _TunablesMixin:
    """Réglages avancés lus sur le thermostat central (défauts = const.py)."""

    hass: HomeAssistant

    def _comfort_hyst(self) -> float:
        return float(central_option(self.hass, CONF_HYSTERESIS, HYSTERESIS[PRESET_COMFORT]))

    def _window_off_delay(self) -> float:
        return float(central_option(self.hass, CONF_WINDOW_OFF_DELAY, WINDOW_OFF_DELAY))

    def _resync_interval(self) -> float:
        return max(1.0, float(central_option(self.hass, CONF_RESYNC_INTERVAL, RESYNC_INTERVAL_MIN)))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    if entry.data.get("type") == "central":
        async_add_entities([CentralThermostat(hass, entry)])
    else:
        async_add_entities([RoomThermostat(hass, entry)])


class CentralThermostat(_TunablesMixin, ClimateEntity, RestoreEntity):
    """Thermostat virtuel : consigne visible en Auto et suivie par les radiateurs."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_translation_key = "central"
    _attr_unique_id = "electric_heater_central"
    entity_id = CENTRAL_ENTITY_ID
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
        self._have_mode = False
        self._hvac_mode = HVACMode.AUTO
        self._hvac_action = HVACAction.IDLE
        self._heating = False
        self._last_manual_preset = PRESET_COMFORT
        self._auto_eco_active = False
        # None = état du calendrier encore jamais connu
        self._calendar_active: bool | None = None
        self._manual_hold = False
        self._window_open = False
        self._window_delay = None
        self._unsub_temp = None
        self._unsub_presence = None
        self._unsub_calendar = None
        self._unsub_windows = None

    def _load_from_entry(self) -> None:
        data = self.entry.data
        self._load_temps()
        self._attr_min_temp = data["min_temp"]
        self._attr_max_temp = data["max_temp"]
        self._attr_target_temperature_step = data["temp_step"]
        self._temp_method = data.get(CONF_TEMP_METHOD, "reference")
        self._reference_sensor = data.get(CONF_TEMPERATURE_SENSOR)
        self._presence_sensor = data.get(CONF_PRESENCE_SENSOR)
        self._calendar = data.get(CONF_HEATING_CALENDAR)
        on_mode = data.get(CONF_CALENDAR_ON_MODE, PRESET_COMFORT)
        off_mode = data.get(CONF_CALENDAR_OFF_MODE, DEFAULT_CALENDAR_OFF_MODE)
        away_mode = data.get(CONF_PRESENCE_AWAY_MODE, PRESET_ECO)
        window_mode = data.get(CONF_WINDOW_MODE, DEFAULT_WINDOW_MODE)
        self._calendar_on_mode = on_mode if on_mode in PRESETS else PRESET_COMFORT
        self._calendar_off_mode = off_mode if off_mode in PRESETS else DEFAULT_CALENDAR_OFF_MODE
        self._presence_away_mode = away_mode if away_mode in PRESETS else PRESET_ECO
        self._window_mode = window_mode if window_mode in WINDOW_MODES else DEFAULT_WINDOW_MODE

    def _load_temps(self) -> None:
        data = self.entry.data
        self._temps = {
            "comfort": data["comfort_temp"],
            "comfort_m1": data["comfort_m1_temp"],
            "comfort_m2": data["comfort_m2_temp"],
            "eco": data["eco_temp"],
            "frost_protection": data["frost_temp"],
        }

    def _windows_live_open(self) -> bool:
        return central_window_open(self.hass) or entry_windows_open(self.hass, self.entry)

    def _cancel_window_delay(self) -> None:
        if self._window_delay:
            self._window_delay()
            self._window_delay = None

    def _temp_for_preset(self, preset: str) -> float:
        key = PRESET_TO_TEMP_KEY.get(preset, "comfort")
        return self._temps.get(key, self._temps["comfort"])

    def _effective_preset(self) -> str:
        """Ordre réellement suivi : mode fenêtre si une fenêtre est ouverte."""
        if self._hvac_mode == HVACMode.OFF:
            return PRESET_OFF
        if self._window_open:
            return window_preset(self._preset_mode, self._window_mode)
        return self._preset_mode

    def _persist_temps(self) -> None:
        # Consignes seules : l'écouteur de mise à jour ne recharge pas l'entrée.
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
    def _on_setpoints_updated(self) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._load_temps()
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        self._notify_rooms()

    @callback
    def _on_window_delay(self, _now=None):
        self._window_delay = None
        if self._windows_live_open() and not self._window_open:
            self._window_open = True
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            self._notify_rooms()

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
            return self._effective_preset()
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode = self._effective_preset()
        mode_label = PRESET_LABELS.get(mode, mode)
        return {
            "virtual": True,
            "fil_pilote_mode": mode,
            "fil_pilote_modes": PRESETS,
            "base_preset": self._preset_mode,
            "manual_hold": self._manual_hold,
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
            "window_mode": self._window_mode,
            "fenetre": "Ouverte" if self._window_open else "Fermee",
            "hysteresis": hysteresis_for(self._preset_mode, self._comfort_hyst()),
            "rooms": [e.title for e in iter_room_entries(self.hass)],
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        previous_calendar: bool | None = None
        if last_state := await self.async_get_last_state():
            attrs = last_state.attributes
            if last_state.state in ("heat", "off", "auto"):
                self._hvac_mode = HVACMode(last_state.state)
            preset = attrs.get("base_preset", attrs.get("preset_mode"))
            if preset in PRESETS:
                self._preset_mode = preset
                self._have_mode = True
            if self._preset_mode == PRESET_OFF and self._hvac_mode != HVACMode.OFF:
                self._preset_mode = PRESET_COMFORT
            self._manual_hold = bool(attrs.get("manual_hold", False))
            self._auto_eco_active = bool(attrs.get("auto_eco_active", False))
            if isinstance(attrs.get("calendar_active"), bool):
                previous_calendar = attrs["calendar_active"]
            self._last_manual_preset = (
                self._preset_mode if self._preset_mode in COMFORT_PRESETS else PRESET_COMFORT
            )
        self._subscribe_sensors()
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_ROOMS_CHANGED, self._on_rooms_changed)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._handle_windows)
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                SIGNAL_SETPOINTS_UPDATED.format(self.entry.entry_id),
                self._on_setpoints_updated,
            )
        )
        self.async_on_remove(self._unsubscribe_sensors)
        self.async_on_remove(self._cancel_window_delay)
        now_calendar = self._calendar_state()
        if self._manual_hold and None not in (now_calendar, previous_calendar) and (
            now_calendar != previous_calendar
        ):
            # Le calendrier a changé pendant l'arrêt : fin du maintien manuel.
            self._manual_hold = False
        self._calendar_active = now_calendar if now_calendar is not None else previous_calendar
        self._handle_windows()
        if self._hvac_mode == HVACMode.AUTO and not self._window_open:
            self._apply_auto_from_calendar(push=False)
        self._handle_presence_change()
        self._update_central_temperature()
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        self._notify_rooms()

    def _unsubscribe_sensors(self) -> None:
        for name in ("_unsub_temp", "_unsub_presence", "_unsub_calendar", "_unsub_windows"):
            unsub = getattr(self, name)
            if unsub:
                unsub()
            setattr(self, name, None)

    @callback
    def _on_rooms_changed(self, event=None):
        self._subscribe_sensors()
        self._update_central_temperature()

    def _subscribe_sensors(self):
        self._unsubscribe_sensors()
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
                    self._notify_rooms()
                return
            self.async_write_ha_state()
            return
        if self._window_open:
            return
        if not self._window_delay:
            self._window_delay = async_call_later(
                self.hass, self._window_off_delay(), self._on_window_delay
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

    def _calendar_state(self) -> bool | None:
        """True/False selon le calendrier, None s'il est indisponible."""
        if not self._calendar:
            return True
        state = self.hass.states.get(self._calendar)
        if not state or state.state in ("unknown", "unavailable"):
            return None
        return state.state.lower() in ACTIVE_CALENDAR_STATES

    def _apply_auto_from_calendar(self, push: bool = True) -> None:
        if self._hvac_mode != HVACMode.AUTO:
            return
        if self._window_open:
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            if push:
                self._notify_rooms()
            return
        active = self._calendar_state()
        if active is not None:
            self._calendar_active = active
        if self._manual_hold:
            # Mode choisi à la main : gardé jusqu'au prochain changement du calendrier.
            pass
        elif self._calendar_active is None:
            # Calendrier jamais connu (indisponible) : dernier mode, sinon Eco.
            if not self._have_mode:
                self._preset_mode = PRESET_ECO
                self._auto_eco_active = False
        elif self._calendar_active:
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
            self._preset_mode = preset
        else:
            self._preset_mode = self._calendar_off_mode
            self._auto_eco_active = False
        self._have_mode = True
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        if push:
            self._notify_rooms()

    @callback
    def _handle_calendar_change(self, event=None):
        new = self._calendar_state()
        if new is None:
            # Calendrier indisponible : on garde le dernier mode.
            self.async_write_ha_state()
            return
        if self._calendar_active is not None and new != self._calendar_active:
            self._manual_hold = False
        if self._window_open or self._hvac_mode != HVACMode.AUTO:
            self._calendar_active = new
            self.async_write_ha_state()
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
        if self._window_open or self._hvac_mode != HVACMode.AUTO or self._manual_hold:
            return
        if not self._has_occupancy_source():
            return
        if self._calendar_active is not True:
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
            self._notify_rooms()

    def _update_target_temp(self):
        if self._hvac_mode == HVACMode.OFF:
            self._target_temp = None
            return
        preset = self._effective_preset()
        if preset == PRESET_OFF:
            self._target_temp = self._temps["comfort"]
            return
        self._target_temp = self._temp_for_preset(preset)

    def _update_hvac_action(self):
        preset = self._effective_preset()
        if preset == PRESET_OFF:
            self._heating = False
            self._hvac_action = HVACAction.OFF
            return
        self._heating = should_heat(
            self._current_temp, self._target_temp, preset, self._heating, self._comfort_hyst()
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
        self._notify_rooms()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        self._hvac_mode = hvac_mode
        self._manual_hold = False
        if hvac_mode == HVACMode.OFF:
            self._preset_mode = PRESET_OFF
        elif hvac_mode == HVACMode.AUTO:
            if self._preset_mode == PRESET_OFF:
                self._preset_mode = self._last_manual_preset or PRESET_COMFORT
            self._apply_auto_from_calendar(push=False)
        elif self._preset_mode == PRESET_OFF:
            self._preset_mode = self._last_manual_preset or PRESET_COMFORT
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        self._notify_rooms(command=True)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset_mode = preset_mode
        self._have_mode = True
        if preset_mode in COMFORT_PRESETS:
            self._last_manual_preset = preset_mode
        self._auto_eco_active = False
        if preset_mode == PRESET_OFF:
            self._hvac_mode = HVACMode.OFF
            self._manual_hold = False
        elif self._hvac_mode == HVACMode.OFF:
            self._hvac_mode = HVACMode.HEAT
            self._manual_hold = False
        elif self._hvac_mode == HVACMode.AUTO:
            # En Auto : mode maintenu jusqu'au prochain changement du calendrier.
            self._manual_hold = True
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        self._notify_rooms(command=True)

    @callback
    def _notify_rooms(self, command: bool = False) -> None:
        """Les radiateurs lisent l'état du thermostat et appliquent eux-mêmes l'ordre."""
        if command:
            self.hass.bus.async_fire(EVENT_CENTRAL_COMMAND)
        self.hass.bus.async_fire(EVENT_CENTRAL_CHANGED)


class RoomThermostat(_TunablesMixin, ClimateEntity, RestoreEntity):
    """Radiateur : suit le thermostat virtuel, ou garde un réglage manuel."""

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
        self._central_window_open = False
        self._window_mode = DEFAULT_WINDOW_MODE
        self._temp_sensor = entry.data[CONF_TEMPERATURE_SENSOR]
        self._sensor_ko = False
        self._fil_pilote_select = room_fil_pilote_id(entry.data)
        self._window_sensors = windows_from_entry(entry)
        self._unsub_windows = None
        self._lock = asyncio.Lock()
        self._expected_preset: str | None = None
        self._relay_check = None
        self._relay_unavailable_logged = False

    def _cancel_window_delay(self) -> None:
        if self._window_delay:
            self._window_delay()
            self._window_delay = None

    def _cancel_relay_check(self) -> None:
        if self._relay_check:
            self._relay_check()
            self._relay_check = None

    @callback
    def _on_window_delay(self, _now=None):
        self._window_delay = None
        if entry_windows_open(self.hass, self.entry) and not self._window_open:
            self._window_open = True
            self.async_write_ha_state()
            self._schedule_apply()

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
        if self._any_window_open():
            base = self._order_base()
            if base != PRESET_OFF:
                return self._order_target(base)
        return self._target_temp

    @property
    def hvac_mode(self) -> HVACMode:
        return self._hvac_mode

    def _any_window_open(self) -> bool:
        return self._window_open or self._central_window_open

    def _order_base(self) -> str:
        if self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF:
            return PRESET_OFF
        if self._any_window_open():
            return window_preset(self._preset_mode, self._window_mode)
        return self._preset_mode

    def _order_target(self, base: str) -> float | None:
        if base == PRESET_OFF:
            return None
        if self._any_window_open():
            return self._temps.get(PRESET_TO_TEMP_KEY.get(base, "comfort"))
        return self._target_temp

    @property
    def hvac_action(self) -> HVACAction:
        # Déduit de l'ordre réellement envoyé au radiateur.
        order = self._expected_preset or self._order_base()
        if order == PRESET_OFF:
            return HVACAction.OFF
        return HVACAction.HEATING if order_heats(order) else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        return self._order_base() if self._any_window_open() else self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        mode = self._order_base()
        return {
            "window_open": self._window_open,
            "fenetre": "Ouverte" if self._window_open else "Fermee",
            "follow_central": self._follow_central,
            "manual_preset": None if self._follow_central else self._preset_mode,
            "fil_pilote_mode": mode,
            "fil_pilote_ordre": self._expected_preset,
            "ordre_envoye": PRESET_LABELS.get(self._expected_preset, self._expected_preset),
            "sonde_ko": self._sensor_ko,
            "alerte": "pile_sonde" if self._sensor_ko else None,
            "message": SENSOR_KO_MESSAGE if self._sensor_ko else None,
            "consigne": self._target_temp,
            "consigne_mode": PRESET_LABELS.get(mode, mode),
            "consignes": _consignes(self._temps) if self._temps else {},
            "temperature_sensor": self._temp_sensor,
            "fil_pilote": self._fil_pilote_select,
            "hysteresis": hysteresis_for(self._preset_mode, self._comfort_hyst()),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if (last_state := await self.async_get_last_state()) and (
            last_state.attributes.get("follow_central") is False
        ):
            # Réglage manuel du radiateur conservé après un redémarrage.
            attrs = last_state.attributes
            self._follow_central = False
            if last_state.state in ("heat", "off"):
                self._hvac_mode = HVACMode(last_state.state)
            else:
                self._hvac_mode = HVACMode.HEAT
            preset = attrs.get("manual_preset")
            if preset in PRESETS:
                self._preset_mode = preset
            if isinstance(attrs.get("consigne"), (int, float)):
                self._target_temp = attrs["consigne"]
        self.async_on_remove(self._cancel_window_delay)
        self.async_on_remove(self._cancel_relay_check)
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CENTRAL_CHANGED, self._sync_from_central)
        )
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_CENTRAL_COMMAND, self._on_central_command)
        )
        self.async_on_remove(
            async_track_state_change_event(self.hass, [CENTRAL_ENTITY_ID], self._sync_from_central)
        )
        if self._temp_sensor:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._temp_sensor], self._update_room_temp
                )
            )
        if self._window_sensors:
            self._unsub_windows = async_track_state_change_event(
                self.hass, self._window_sensors, self._check_windows
            )
            self.async_on_remove(lambda: self._unsub_windows and self._unsub_windows())
        if self._fil_pilote_select:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._fil_pilote_select], self._on_relay_change
                )
            )
        self.async_on_remove(
            self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._check_windows)
        )
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._periodic_resync, timedelta(minutes=self._resync_interval())
            )
        )
        self.async_on_remove(lambda: self.hass.bus.async_fire(EVENT_ROOMS_CHANGED))
        self._update_room_temp(apply=False)
        self._check_windows(apply=False)
        self._sync_from_central(apply=False)
        self.async_write_ha_state()
        self._schedule_apply()
        self.hass.bus.async_fire(EVENT_ROOMS_CHANGED)

    def _central_state(self):
        return self.hass.states.get(CENTRAL_ENTITY_ID) or get_central_state(self.hass)

    @callback
    def _on_central_command(self, event=None):
        """Commande manuelle sur le thermostat virtuel : le radiateur le suit de nouveau."""
        self._follow_central = True
        self._sync_from_central()

    @callback
    def _sync_from_central(self, event=None, apply: bool = True):
        central = self._central_state()
        if not central or central.state in ("unknown", "unavailable"):
            return
        attrs = central.attributes
        self._temps = attrs.get("temperatures") or self._temps
        self._central_window_open = bool(attrs.get("window_open"))
        mode = attrs.get("window_mode")
        self._window_mode = mode if mode in WINDOW_MODES else DEFAULT_WINDOW_MODE
        if self._follow_central:
            if central.state in ("heat", "off", "auto"):
                self._hvac_mode = HVACMode(central.state)
            preset = attrs.get("base_preset") or attrs.get("preset_mode") or PRESET_COMFORT
            if self._hvac_mode == HVACMode.OFF:
                preset = PRESET_OFF
            self._preset_mode = preset
            key = PRESET_TO_TEMP_KEY.get(self._preset_mode, "comfort")
            self._target_temp = attrs.get("consigne")
            if self._target_temp is None or self._central_window_open:
                self._target_temp = self._temps.get(key) or self._temps.get("comfort")
            self._hysteresis = hysteresis_for(self._preset_mode, self._comfort_hyst())
        if apply:
            self.async_write_ha_state()
            self._schedule_apply()

    @callback
    def _update_room_temp(self, event=None, apply: bool = True):
        if not self._temp_sensor:
            self._current_temp = None
        else:
            state = self.hass.states.get(self._temp_sensor)
            try:
                self._current_temp = (
                    float(state.state)
                    if state and state.state not in ("unknown", "unavailable")
                    else None
                )
            except (ValueError, TypeError):
                self._current_temp = None
        ko = bool(self._temp_sensor) and self._current_temp is None
        if ko and not self._sensor_ko:
            _LOGGER.warning(
                "Sonde %s indisponible pour %s : radiateur en Hors-gel par sécurité. %s",
                self._temp_sensor,
                self.entry.data.get("name"),
                SENSOR_KO_MESSAGE,
            )
        elif not ko and self._sensor_ko:
            _LOGGER.info("Sonde %s de nouveau disponible : régulation normale", self._temp_sensor)
        self._sensor_ko = ko
        if apply:
            self.async_write_ha_state()
            self._schedule_apply()

    @callback
    def _check_windows(self, event=None, apply: bool = True):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._window_sensors = windows_from_entry(self.entry)
        live = entry_windows_open(self.hass, self.entry)
        if not live:
            self._cancel_window_delay()
            if self._window_open:
                self._window_open = False
                if apply:
                    self._schedule_apply()
            if apply:
                self.async_write_ha_state()
            return
        if self._window_open:
            return
        if not self._window_delay:
            self._window_delay = async_call_later(
                self.hass, self._window_off_delay(), self._on_window_delay
            )
        if apply:
            self.async_write_ha_state()

    @callback
    def _on_relay_change(self, event):
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if not relay_available(new):
            return
        if old is None or old.state in ("unknown", "unavailable"):
            # Relais de retour : on renvoie l'ordre attendu.
            if self._relay_unavailable_logged:
                _LOGGER.info("Relais %s de nouveau disponible : ordre renvoyé", self._fil_pilote_select)
            self._relay_unavailable_logged = False
            self._schedule_apply(force=True)
            return
        if self._expected_preset is None:
            return
        option = expected_option(self.hass, self._fil_pilote_select, self._expected_preset)
        if relay_matches(new, self._expected_preset, option):
            self._cancel_relay_check()
            return
        if not self._relay_check:
            self._relay_check = async_call_later(
                self.hass, RELAY_CHECK_DELAY, self._on_relay_check
            )

    @callback
    def _on_relay_check(self, _now=None):
        self._relay_check = None
        if self._expected_preset is None:
            return
        state = self.hass.states.get(self._fil_pilote_select)
        option = expected_option(self.hass, self._fil_pilote_select, self._expected_preset)
        if relay_available(state) and not relay_matches(state, self._expected_preset, option):
            _LOGGER.info(
                "Relais %s sur %s au lieu de %s : ordre renvoyé",
                self._fil_pilote_select,
                state.state,
                option,
            )
            self._schedule_apply(force=True)

    async def _periodic_resync(self, _now=None):
        await self._apply_fil_pilote(force=True)

    @callback
    def _schedule_apply(self, force: bool = False) -> None:
        self.hass.async_create_task(self._apply_fil_pilote(force=force))

    async def _apply_fil_pilote(self, force: bool = False):
        async with self._lock:
            # Ordre calculé au moment de l'envoi : toujours l'état le plus récent.
            base = self._order_base()
            target = self._order_target(base)
            exact = self._any_window_open()
            preset = room_order(
                self.hass, self.entry, base, target, exact=exact, last=self._expected_preset
            )
            changed = preset != self._expected_preset
            self._expected_preset = preset
            if changed:
                self.async_write_ha_state()
            state = self.hass.states.get(self._fil_pilote_select) if self._fil_pilote_select else None
            if self._fil_pilote_select and not relay_available(state):
                if not self._relay_unavailable_logged:
                    _LOGGER.warning(
                        "Relais fil pilote %s indisponible : l'ordre %s sera envoyé à son retour",
                        self._fil_pilote_select,
                        preset,
                    )
                    self._relay_unavailable_logged = True
                return
            await apply_fil_pilote(
                self.hass, self._fil_pilote_select, preset, temperature=target, force=force
            )

    async def async_set_temperature(self, **kwargs):
        if temp := kwargs.get("temperature"):
            self._target_temp = temp
            self._preset_mode = PRESET_COMFORT
            self._hvac_mode = HVACMode.HEAT
            self._follow_central = False
        self.async_write_ha_state()
        await self._apply_fil_pilote()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        if hvac_mode == HVACMode.AUTO:
            # Auto : le radiateur suit de nouveau le thermostat virtuel.
            self._follow_central = True
            self._sync_from_central(apply=False)
        else:
            self._follow_central = False
            self._hvac_mode = hvac_mode
            if hvac_mode == HVACMode.OFF:
                self._preset_mode = PRESET_OFF
            elif self._preset_mode == PRESET_OFF:
                self._preset_mode = PRESET_COMFORT
                self._target_temp = self._temps.get("comfort", self._target_temp)
        self.async_write_ha_state()
        await self._apply_fil_pilote()

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._follow_central = False
        self._preset_mode = preset_mode
        if preset_mode in PRESET_TO_TEMP_KEY and self._temps:
            self._target_temp = self._temps.get(PRESET_TO_TEMP_KEY[preset_mode])
        self._hvac_mode = HVACMode.OFF if preset_mode == PRESET_OFF else HVACMode.HEAT
        self.async_write_ha_state()
        await self._apply_fil_pilote()
