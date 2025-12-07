"""
Chauffage Électrique Fil Pilote Français - v1.4.0
Auteur : XAV59213
100 % local - Décembre 2025
"""

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVAC_MODE_AUTO, HVAC_MODE_OFF,
    SUPPORT_TARGET_TEMPERATURE, SUPPORT_PRESET_MODE
)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE, STATE_ON
from .const import (
    DOMAIN, CENTRAL, ROOM, PRESETS, FIL_PILOTE_PAYLOAD,
    PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2,
    PRESET_ECO, PRESET_HORS_GEL, PRESET_OFF
)

SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

async def async_setup_entry(hass, config_entry, async_add_entities):
    if config_entry.data.get("type") == CENTRAL:
        async_add_entities([CentralThermostat(hass, config_entry)])
    else:
        async_add_entities([RoomHeater(hass, config_entry)])

# ====================== THERMOSTAT CENTRAL ======================
class CentralThermostat(ClimateEntity):
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self._name = entry.data["name"]
        self._temp_sensor = entry.data["temperature_sensor"]
        self._master_switch = entry.data["master_switch"]
        self._calendar = entry.data.get("heating_calendar")
        self._temps = {
            "confort": entry.data.get("temp_confort", 20.0),
            "confort_m1": entry.data.get("temp_confort_m1", 19.0),
            "confort_m2": entry.data.get("temp_confort_m2", 18.0),
            "eco": entry.data.get("temp_eco", 16.5),
            "hors_gel": entry.data.get("frost_temp", 7.0),
        }

        self._current_temp = None
        self._target_temp = self._temps["confort"]
        self._preset = PRESET_COMFORT
        self._hvac_mode = HVAC_MODE_AUTO

    @property
    def name(self): return self._name
    @property
    def unique_id(self): return "electric_heater_central"
    @property
    def temperature_unit(self): return TEMP_CELSIUS
    @property
    def current_temperature(self): return self._current_temp
    @property
    def target_temperature(self):
        if self._preset == PRESET_OFF:
            return None
        if self._preset == PRESET_HORS_GEL:
            return self._temps["hors_gel"]
        return self._temps.get(self._preset.replace("_", ""), self._temps["confort"])

    @property
    def hvac_mode(self): return self._hvac_mode
    @property
    def hvac_modes(self): return [HVAC_MODE_AUTO, HVAC_MODE_OFF]
    @property
    def preset_mode(self): return self._preset
    @property
    def preset_modes(self): return PRESETS
    @property
    def supported_features(self): return SUPPORT_FLAGS

    def update(self):
        state = self.hass.states.get(self._temp_sensor)
        if state and state.state not in ["unknown", "unavailable"]:
            try: self._current_temp = float(state.state)
            except: self._current_temp = None
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            self._temps["confort"] = self._target_temp
            self._preset = PRESET_COMFORT
            self.async_write_ha_state()
            await self._push_to_rooms()

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode in PRESETS:
            self._preset = preset_mode
            self._hvac_mode = HVAC_MODE_OFF if preset_mode == PRESET_OFF else HVAC_MODE_AUTO
            self.async_write_ha_state()
            await self._push_to_rooms()

    async def _push_to_rooms(self):
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("type") == ROOM:
                await RoomHeater(self.hass, entry).apply_central_order(
                    self._preset, self._temps, self._calendar
                )

# ====================== RADIATEUR PAR PIÈCE ======================
class RoomHeater(ClimateEntity):
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self._name = entry.data["name"]
        self._zigbee_id = entry.data["heater_zigbee_id"]
        self._temp_sensor = entry.data["temperature_sensor"]
        self._windows = [s.strip() for s in entry.data.get("window_sensors", "").split(",") if s.strip()]
        self._current_temp = None

    @property
    def name(self): return self._name
    @property
    def unique_id(self): return f"electric_heater_{self.entry.entry_id}"
    @property
    def temperature_unit(self): return TEMP_CELSIUS
    @property
    def current_temperature(self): return self._current_temp
    @property
    def supported_features(self): return SUPPORT_FLAGS

    def _central_state(self):
        return self.hass.states.get("climate.electric_heater_central")

    @property
    def preset_mode(self):
        c = self._central_state()
        return c.attributes.get("preset_mode") if c else PRESET_OFF

    @property
    def target_temperature(self):
        c = self._central_state()
        if not c: return 0
        preset = c.attributes.get("preset_mode")
        temps = c.attributes.get("temperature_setpoints", {})
        if preset == PRESET_HORS_GEL:
            return temps.get("hors_gel", 7.0)
        if preset == PRESET_OFF:
            return 0
        return temps.get(preset.replace("_", ""), 20.0)

    @property
    def hvac_mode(self):
        c = self._central_state()
        return c.state if c else HVAC_MODE_OFF

    @property
    def hvac_modes(self): return [HVAC_MODE_AUTO, HVAC_MODE_OFF]
    @property
    def preset_modes(self): return PRESETS

    def update(self):
        state = self.hass.states.get(self._temp_sensor)
        if state and state.state not in ["unknown", "unavailable"]:
            try: self._current_temp = float(state.state)
            except: self._current_temp = None
        self.async_write_ha_state()

    def _is_heating_allowed(self, calendar_id):
        if not calendar_id:
            return True
        state = self.hass.states.get(calendar_id)
        return state and state.state == "on"

    async def apply_central_order(self, preset, temps_dict, calendar_id):
        # 1. Calendrier chauffage désactivé → Hors-gel
        if not self._is_heating_allowed(calendar_id):
            payload = FIL_PILOTE_PAYLOAD[PRESET_HORS_GEL]
        # 2. Fenêtre ouverte → Arrêt
        elif any(self.hass.states.get(w) and self.hass.states.get(w).state == STATE_ON for w in self._windows):
            payload = FIL_PILOTE_PAYLOAD[PRESET_OFF]
        # 3. Mode normal
        else:
            payload = FIL_PILOTE_PAYLOAD.get(preset, FIL_PILOTE_PAYLOAD[PRESET_OFF])

        await self.hass.services.async_call(
            "zigbee2mqtt",
            "publish",
            {"topic": f"{self._zigbee_id}/set", "payload_json": payload}
        )
