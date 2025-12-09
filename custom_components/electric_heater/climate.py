"""Climate entities for Chauffage Électrique Fil Pilote FR."""
import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature, PRECISION_TENTHS
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity
from .const import (
    DOMAIN,
    CENTRAL,
    ROOM,
    PRESETS,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
    FIL_PILOTE_PAYLOAD,
    HYSTERESIS,
    CONF_TEMP_METHOD,
    CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMP_METHOD_REFERENCE,
    CONF_PRESENCE_SENSOR,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up climate entities."""
    if entry.data.get("type") == CENTRAL:
        async_add_entities([CentralThermostat(hass, entry)])
    else:
        async_add_entities([RoomThermostat(hass, entry)])


class CentralThermostat(ClimateEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_unique_id = "electric_heater_central"
    entity_id = "climate.electric_heater_central"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_supported_features = SUPPORTED_FEATURES
    _attr_precision = PRECISION_TENTHS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry

        self._temps = {
            "comfort": entry.data["comfort_temp"],
            "comfort_m1": entry.data["comfort_m1_temp"],
            "comfort_m2": entry.data["comfort_m2_temp"],
            "eco": entry.data["eco_temp"],
            "frost_protection": entry.data["frost_temp"],
        }

        self._attr_min_temp = entry.data["min_temp"]
        self._attr_max_temp = entry.data["max_temp"]
        self._attr_target_temperature_step = entry.data["temp_step"]

        self._current_temp: float | None = None
        self._target_temp: float | None = None
        self._preset_mode = PRESET_COMFORT
        self._hvac_mode = HVACMode.HEAT
        self._hvac_action = HVACAction.IDLE
        self._last_manual_preset = PRESET_COMFORT
        self._auto_eco_active = False

        self._temp_method = entry.data.get(CONF_TEMP_METHOD, CONF_TEMP_METHOD_AVERAGE)
        self._reference_sensor = (
            entry.data.get("temperature_sensor")
            if self._temp_method == CONF_TEMP_METHOD_REFERENCE
            else None
        )
        self._presence_sensor = entry.data.get(CONF_PRESENCE_SENSOR)

        self._unsub_temp = None
        self._unsub_presence = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "electric_heater_central")},
            "name": "Chauffage Central",
            "manufacturer": "XAV59213",
            "model": "Fil Pilote FR",
            "sw_version": "1.0.0",
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
        return self._preset_mode

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "temperatures": self._temps,
            "auto_eco_active": self._auto_eco_active,
            "current_temperature": self._current_temp,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if last_state := await self.async_get_last_state():
            self._hvac_mode = HVACMode(last_state.state) if last_state.state in ("heat", "off") else HVACMode.HEAT
            self._preset_mode = last_state.attributes.get("preset_mode", PRESET_COMFORT)
            self._last_manual_preset = self._preset_mode if self._preset_mode != PRESET_ECO else PRESET_COMFORT

        sensors = self._get_temperature_sensors()
        if sensors:
            self._unsub_temp = async_track_state_change_event(
                self.hass, sensors, self._update_central_temperature
            )

        if self._presence_sensor:
            self._unsub_presence = async_track_state_change_event(
                self.hass, [self._presence_sensor], self._handle_presence_change
            )

        self._update_central_temperature()
        self._update_target_temp()
        self._update_hvac_action()

    async def async_will_remove_from_hass(self):
        if self._unsub_temp:
            self._unsub_temp()
        if self._unsub_presence:
            self._unsub_presence()

    def _get_temperature_sensors(self):
        if self._temp_method == CONF_TEMP_METHOD_AVERAGE:
            return [
                e.data["temperature_sensor"]
                for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.data.get("type") == ROOM
            ]
        return [self._reference_sensor] if self._reference_sensor else []

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
    def _handle_presence_change(self, event):
        state = event.data.get("new_state")
        if not state or state.state in ("unknown", "unavailable"):
            return
        try:
            persons = int(float(state.state))
        except (ValueError, TypeError):
            persons = 0

        changed = False
        if persons == 0 and not self._auto_eco_active:
            self._last_manual_preset = self._preset_mode
            self._preset_mode = PRESET_ECO
            self._auto_eco_active = True
            changed = True
        elif persons > 0 and self._auto_eco_active:
            self._preset_mode = self._last_manual_preset
            self._auto_eco_active = False
            changed = True

        if changed:
            self._update_target_temp()
            self._update_hvac_action()
            self.async_write_ha_state()
            self.hass.bus.async_fire(f"{DOMAIN}_central_changed")

    def _update_target_temp(self):
        if self._hvac_mode == HVACMode.OFF or self._preset_mode == PRESET_OFF:
            self._target_temp = None
            return
        key = {
            PRESET_COMFORT: "comfort",
            PRESET_COMFORT_M1: "comfort_m1",
            PRESET_COMFORT_M2: "comfort_m2",
            PRESET_ECO: "eco",
            PRESET_FROST_PROTECTION: "frost_protection",
        }.get(self._preset_mode, "comfort")
        self._target_temp = self._temps[key]

    def _update_hvac_action(self):
        if self._hvac_mode == HVACMode.OFF:
            self._hvac_action = HVACAction.OFF
        elif self._current_temp is None or self._target_temp is None:
            self._hvac_action = HVACAction.IDLE
        else:
            hysteresis = HYSTERESIS.get(self._preset_mode, 0.3)
            self._hvac_action = HVACAction.HEATING if self._current_temp < self._target_temp - hysteresis else HVACAction.IDLE

    async def async_set_temperature(self, **kwargs):
        if temp := kwargs.get("temperature"):
            self._temps["comfort"] = temp
            self._preset_mode = PRESET_COMFORT
            self._last_manual_preset = PRESET_COMFORT
            self._auto_eco_active = False
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode):
        self._hvac_mode = hvac_mode
        if hvac_mode == HVACMode.OFF:
            self._preset_mode = PRESET_OFF
        elif self._preset_mode == PRESET_OFF:
            self._preset_mode = self._last_manual_preset or PRESET_COMFORT
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset_mode = preset_mode
        if preset_mode != PRESET_ECO:
            self._last_manual_preset = preset_mode
        self._auto_eco_active = False
        self._hvac_mode = HVACMode.OFF if preset_mode == PRESET_OFF else HVACMode.HEAT
        self._update_target_temp()
        self._update_hvac_action()
        self.async_write_ha_state()
        await self._push_to_all_rooms()

    async def _push_to_all_rooms(self):
        preset = PRESET_OFF if self._hvac_mode == HVACMode.OFF else self._preset_mode
        option = FIL_PILOTE_PAYLOAD[preset]["fil_pilote"]
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("type") == ROOM and (select_id := entry.data.get("fil_pilote_select")):
                await self.hass.services.async_call("select", "select_option", {"entity_id": select_id, "option": option})
        self.hass.bus.async_fire(f"{DOMAIN}_central_changed")


class RoomThermostat(ClimateEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
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
        self._preset_mode = PRESET_COMFORT
        self._hvac_mode = HVACMode.HEAT
        self._hvac_action = HVACAction.IDLE
        self._window_open = False
        self._hysteresis = 0.3

        self._temp_sensor = entry.data["temperature_sensor"]
        self._fil_pilote_select = entry.data["fil_pilote_select"]
        self._window_sensors = [s.strip() for s in entry.data.get("window_sensors", "").split(",") if s.strip()]

        self._unsub_temp = None
        self._unsub_windows = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "name": self.entry.data["name"],
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
        if self._window_open or self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        if self._current_temp is None or self._target_temp is None:
            return HVACAction.IDLE
        return HVACAction.HEATING if self._current_temp < self._target_temp - self._hysteresis else HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        return self._preset_mode

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._sync_from_central()
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._sync_from_central)

        self._unsub_temp = async_track_state_change_event(self.hass, [self._temp_sensor], self._update_room_temp)
        if self._window_sensors:
            self._unsub_windows = async_track_state_change_event(self.hass, self._window_sensors, self._check_windows)

        self._update_room_temp()
        self._check_windows()

    async def async_will_remove_from_hass(self):
        if self._unsub_temp:
            self._unsub_temp()
        if self._unsub_windows:
            self._unsub_windows()

    @callback
    def _sync_from_central(self, event=None):
        central = self.hass.states.get("climate.electric_heater_central")
        if not central:
            return
        self._hvac_mode = HVACMode(central.state)
        self._preset_mode = central.attributes.get("preset_mode", PRESET_COMFORT)
        temps = central.attributes.get("temperatures", {})
        key = {"comfort": "comfort", "comfort_-1": "comfort_m1", "comfort_-2": "comfort_m2", "eco": "eco", "frost_protection": "frost_protection"}.get(self._preset_mode, "comfort")
        self._target_temp = temps.get(key)
        self._hysteresis = HYSTERESIS.get(self._preset_mode, 0.3)
        self.hass.create_task(self._apply_fil_pilote())
        self.async_write_ha_state()

    @callback
    def _update_room_temp(self, event=None):
        state = self.hass.states.get(self._temp_sensor)
        self._current_temp = float(state.state) if state and state.state not in ("unknown", "unavailable") else None
        self.async_write_ha_state()

    @callback
    def _check_windows(self, event=None):
        self._window_open = any(self.hass.states.get(eid) and self.hass.states.get(eid).state == "on" for eid in self._window_sensors)
        self.hass.create_task(self._apply_fil_pilote())
        self.async_write_ha_state()

    async def _apply_fil_pilote(self):
        option = "off" if self._window_open or self._hvac_mode == HVACMode.OFF else FIL_PILOTE_PAYLOAD[self._preset_mode]["fil_pilote"]
        await self.hass.services.async_call("select", "select_option", {"entity_id": self._fil_pilote_select, "option": option})

    async def async_set_temperature(self, **kwargs): pass
    async def async_set_hvac_mode(self, hvac_mode: HVACMode): pass
    async def async_set_preset_mode(self, preset_mode: str): pass
