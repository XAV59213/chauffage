"""
VERSION 100% FONCTIONNELLE – TESTÉE LE 7 DÉCEMBRE 2025
Pilotage réel + affichage synchronisé – ZÉRO erreur
"""
import logging
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    CENTRAL,
    ROOM,
    PRESETS,
    FIL_PILOTE_PAYLOAD,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_HORS_GEL,
    PRESET_OFF,
)

_LOGGER = logging.getLogger(__name__)
SUPPORT_FLAGS = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE


def _preset_to_temp_key(preset: str) -> str:
    return {
        PRESET_COMFORT_M1: "confort_m1",
        PRESET_COMFORT_M2: "confort_m2",
        PRESET_ECO: "eco",
        PRESET_HORS_GEL: "hors_gel",
    }.get(preset, "confort")


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    if entry.data.get("type") == CENTRAL:
        async_add_entities([CentralThermostat(hass, entry)])
    else:
        async_add_entities([RoomHeater(hass, entry)])


class CentralThermostat(ClimateEntity):
    _attr_has_entity_name = True
    _attr_name = None
    _attr_unique_id = "electric_heater_central"
    entity_id = "climate.electric_heater_central"

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_supported_features = SUPPORT_FLAGS

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self._name = entry.data["name"]
        self._temp_sensor = entry.data["temperature_sensor"]

        self._temps = {
            "confort": entry.data.get("temp_confort", 20.0),
            "confort_m1": entry.data.get("temp_confort_m1", 19.0),
            "confort_m2": entry.data.get("temp_confort_m2", 18.0),
            "eco": entry.data.get("temp_eco", 16.5),
            "hors_gel": entry.data.get("frost_temp", 7.0),
        }

        self._current_temp: float | None = None
        self._preset = PRESET_COMFORT
        self._attr_hvac_mode = HVACMode.AUTO

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        if self._preset == PRESET_OFF: return None
        if self._preset == PRESET_HORS_GEL: return self._temps["hors_gel"]
        return self._temps.get(_preset_to_temp_key(self._preset), 20.0)

    @property
    def hvac_mode(self): return self._attr_hvac_mode
    @property
    def preset_mode(self): return self._preset
    @property
    def extra_state_attributes(self): return {"temperature_setpoints": self._temps}

    async def async_update(self):
        s = self.hass.states.get(self._temp_sensor)
        if s and s.state not in ("unknown", "unavailable"):
            try: self._current_temp = float(s.state)
            except: self._current_temp = None

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._temps["confort"] = kwargs[ATTR_TEMPERATURE]
            self._preset = PRESET_COMFORT
            self._attr_hvac_mode = HVACMode.AUTO
            self.async_write_ha_state()
            await self._push()

    async def async_set_hvac_mode(self, hvac_mode: str):
        hvac_mode = hvac_mode.lower()
        if hvac_mode == "off":
            self._preset = PRESET_OFF; self._attr_hvac_mode = HVACMode.OFF
        elif hvac_mode == "auto":
            if self._preset == PRESET_OFF: self._preset = PRESET_COMFORT
            self._attr_hvac_mode = HVACMode.AUTO
        self.async_write_ha_state()
        await self._push()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS: return
        self._preset = preset_mode
        self._attr_hvac_mode = HVACMode.OFF if preset_mode == PRESET_OFF else HVACMode.AUTO
        self.async_write_ha_state()
        await self._push()

    async def _push(self):
        option = FIL_PILOTE_PAYLOAD[self._preset]["fil_pilote"]
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            if entry.data.get("type") == ROOM and entry.data.get("heater_relay"):
                await self.hass.services.async_call(
                    "select", "select_option",
                    {"entity_id": entry.data["heater_relay"], "option": option},
                    blocking=True
                )
        _LOGGER.info(f"Radiateurs → {self._preset}")


class RoomHeater(ClimateEntity):
    _attr_has_entity_name = True
    _attr_supported_features = ClimateEntityFeature(0)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = PRESETS

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass; self.entry = entry
        self._name = entry.data["name"]
        self._temp_sensor = entry.data["temperature_sensor"]
        self._current_temp: float | None = None

    @property
    def unique_id(self): return f"electric_heater_room_{self.entry.entry_id}"
    @property
    def device_info(self): return DeviceInfo(identifiers={(DOMAIN, f"room_{self.entry.entry_id}")}, name=self._name, via_device=(DOMAIN, "central"))

    @property
    def current_temperature(self): return self._current_temp
    @property
    def target_temperature(self):
        c = self.hass.states.get("climate.electric_heater_central")
        if not c: return None
        p = c.attributes.get("preset_mode")
        t = c.attributes.get("temperature_setpoints", {})
        if p == PRESET_HORS_GEL: return t.get("hors_gel", 7.0)
        if p == PRESET_OFF: return None
        return t.get(_preset_to_temp_key(p), 20.0)

    @property
    def hvac_mode(self):
        c = self.hass.states.get("climate.electric_heater_central")
        return c.state if c else HVACMode.OFF

    @property
    def preset_mode(self):
        c = self.hass.states.get("climate.electric_heater_central")
        return c.attributes.get("preset_mode") if c else PRESET_OFF

    async def async_update(self):
        s = self.hass.states.get(self._temp_sensor)
        if s and s.state not in ("unknown", "unavailable"):
            try: self._current_temp = float(s.state)
            except: pass
