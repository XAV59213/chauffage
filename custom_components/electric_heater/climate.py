"""
Chauffage Électrique Fil Pilote Français - v1.3.0
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
    DOMAIN, CENTRAL, ROOM, PRESETS, OFFSET, FIL_PILOTE_PAYLOAD,
    PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2,
    PRESET_ECO, PRESET_HORS_GEL, PRESET_OFF, DEFAULT_FROST_TEMP
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
        self._frost_temp = entry.data.get("frost_temp", DEFAULT_FROST_TEMP)

        self._current_temp = None
        self._target_temp = 20.0
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
            return self._frost_temp
        base = self._target_temp
        return base + OFFSET.get(self._preset, 0)

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
            self._preset = PRESET_COMFORT
            self.async_write_ha_state()
            await self._push_to_rooms()

    async def async_set_preset_mode(self, preset_mode):
        if preset_mode in PRESETS:
            self._preset = preset_mode
            self._hvac_mode = HVAC_MODE_OFF if preset_mode == PRESET_OFF else HVAC_MODE_AUTO

            # Valeurs par défaut intelligentes au premier changement de mode
            if self._target_temp <= 15:
                defaults = {
                    PRESET_COMFORT: 20.0,
                    PRESET_COMFORT_M1: 19.0,
                    PRESET_COMFORT_M2: 18.0,
                    PRESET_ECO: 19.5,
                }
                self._target_temp = defaults.get(preset_mode, 20.0)

            self.async_write_ha_state()
            await self._push_to_rooms()

    async def _push_to_rooms(self):
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("type") == ROOM:
                await RoomHeater(self.hass, entry).apply_central_order(
                    self._preset, self._target_temp, self._frost_temp
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
        base = float(c.attributes.get("temperature", 20))
        frost = float(c.attributes.get("frost_temp", 7.0))
        if preset == PRESET_HORS_GEL: return frost
        if preset == PRESET_OFF: return 0
        return base + OFFSET.get(preset, 0)

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

    async def apply_central_order(self, preset, base_temp, frost_temp):
        if any(self.hass.states.get(w) and self.hass.states.get(w).state == STATE_ON for w in self._windows):
            payload = FIL_PILOTE_PAYLOAD[PRESET_OFF]
        else:
            payload = FIL_PILOTE_PAYLOAD.get(preset, FIL_PILOTE_PAYLOAD[PRESET_OFF])

        await self.hass.services.async_call(
            "zigbee2mqtt",
            "publish",
            {"topic": f"{self._zigbee_id}/set", "payload_json": payload}
        )
