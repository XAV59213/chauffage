"""
Chauffage Électrique Fil Pilote Français - v1.5.0
Auteur : XAV59213
100 % local – Décembre 2025
Compatible Home Assistant 2025.12+ – zéro erreur, zéro warning
"""
import json

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature, STATE_ON
from homeassistant.core import HomeAssistant, State
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
    DEFAULT_MQTT_BASE_TOPIC,
)

# Flags
SUPPORT_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
SUPPORT_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
SUPPORT_FLAGS_CENTRAL = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


def _preset_to_temp_key(preset: str) -> str:
    """Retourne la clé du dictionnaire de températures correspondant au preset."""
    return {
        PRESET_COMFORT_M1: "confort_m1",
        PRESET_COMFORT_M2: "confort_m2",
        PRESET_ECO: "eco",
        PRESET_HORS_GEL: "hors_gel",
    }.get(preset, "confort")


async def async_setup_entry(hass: HomeAssistant, config_entry):
    """Setup de l’intégration (appelé par HA)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Création des entités climate."""
    if entry.data.get("type") == CENTRAL:
        async_add_entities([CentralThermostat(hass, entry)])
    else:
        async_add_entities([RoomHeater(hass, entry)])


class CentralThermostat(ClimateEntity):
    """Thermostat central virtuel."""
    _attr_has_entity_name = True
    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False

    _attr_supported_features = SUPPORT_FLAGS_CENTRAL
    _attr_hvac_modes = [HVACMode.AUTO, HVACMode.OFF]
    _attr_preset_modes = PRESETS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_unique_id = "electric_heater_central"
    entity_id = "climate.electric_heater_central"

    def __init__(self, hass: HomeAssistant, entry):
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

        self._current_temp: float | None = None
        self._preset = PRESET_COMFORT
        self._attr_hvac_mode = HVACMode.AUTO

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "central")},
            name=self._name,
            manufacturer="XAV59213",
            model="Thermostat central fil pilote",
            sw_version="1.5.0",
        )

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def target_temperature(self):
        if self._preset in (PRESET_OFF, None):
            return None
        if self._preset == PRESET_HORS_GEL:
            return self._temps["hors_gel"]
        return self._temps.get(_preset_to_temp_key(self._preset), self._temps["confort"])

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode

    @property
    def preset_mode(self):
        return self._preset

    @property
    def extra_state_attributes(self):
        return {
            "temperature_setpoints": self._temps,
            "central_temperature_sensor": self._temp_sensor,
            "master_switch": self._master_switch,
            "heating_calendar": self._calendar,
        }

    async def async_update(self):
        state: State | None = self.hass.states.get(self._temp_sensor)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self._current_temp = float(state.state)
            except (ValueError, TypeError):
                self._current_temp = None

    # Stubs synchrones (obligatoires depuis 2025.10)
    def set_temperature(self, **kwargs): raise NotImplementedError
    def set_hvac_mode(self, hvac_mode): raise NotImplementedError
    def set_preset_mode(self, preset_mode): raise NotImplementedError

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            temp = kwargs[ATTR_TEMPERATURE]
            self._temps["confort"] = temp
            self._preset = PRESET_COMFORT
            self._attr_hvac_mode = HVACMode.AUTO
            self.async_write_ha_state()
            await self._push_to_rooms()

    async def async_set_hvac_mode(self, hvac_mode: str):
        if hvac_mode == HVACMode.OFF:
            self._preset = PRESET_OFF
        elif self._preset == PRESET_OFF:
            self._preset = PRESET_COMFORT
        self._attr_hvac_mode = hvac_mode
        self.async_write_ha_state()
        await self._push_to_rooms()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset = preset_mode
        self._attr_hvac_mode = HVACMode.OFF if preset_mode == PRESET_OFF else HVACMode.AUTO
        self.async_write_ha_state()
        await self._push_to_rooms()

    async def _push_to_rooms(self):
        """Envoie l’ordre à toutes les pièces."""
        for entity in self.hass.data.get(DOMAIN, {}).values():
            if isinstance(entity, list):
                for room in entity:
                    if hasattr(room, "apply_central_order"):
                        await room.apply_central_order(
                            self._preset, self._temps, self._calendar, self._master_switch
                        )
            elif hasattr(entity, "apply_central_order"):
                await entity.apply_central_order(
                    self._preset, self._temps, self._calendar, self._master_switch
                )


class RoomHeater(ClimateEntity):
    """Radiateur par pièce – lecture seule."""
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = ClimateEntityFeature(0)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self._name = entry.data["name"]

        # Récupération du Zigbee ID (compat ancienne/nouvelle config)
        zigbee_id = entry.data.get("heater_zigbee_id")
        if not zigbee_id:
            relay = entry.data.get("heater_relay", "")
            state = self.hass.states.get(relay) if relay else None
            zigbee_id = (
                state.attributes.get("friendly_name", "")
                if state and "friendly_name" in state.attributes
                else relay.split(".")[-1] if "." in relay else "unknown"
            )
        self._zigbee_id = zigbee_id
        self._mqtt_base_topic = entry.data.get("mqtt_base_topic", DEFAULT_MQTT_BASE_TOPIC)
        self._temp_sensor = entry.data["temperature_sensor"]
        self._windows = [
            s.strip()
            for s in entry.data.get("window_sensors", "").split(",")
            if s.strip()
        ]
        self._current_temp: float | None = None

    @property
    def unique_id(self):
        return f"electric_heater_{self.entry.entry_id}"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, f"room_{self.entry.entry_id}")},
            name=self._name,
            manufacturer="NodOn",
            model="SIN-4-FP-21",
            via_device=(DOMAIN, "central"),
        )

    @property
    def current_temperature(self):
        return self._current_temp

    @property
    def extra_state_attributes(self):
        return {
            "temperature_sensor": self._temp_sensor,
            "zigbee_id": self._zigbee_id,
            "mqtt_base_topic": self._mqtt_base_topic,
            "window_sensors": self._windows,
        }

    def _central(self) -> State | None:
        return self.hass.states.get("climate.electric_heater_central")

    @property
    def preset_mode(self):
        c = self._central()
        return c.attributes.get("preset_mode") if c else PRESET_OFF

    @property
    def target_temperature(self):
        c = self._central()
        if not c:
            return 0.0
        preset = c.attributes.get("preset_mode")
        temps = c.attributes.get("temperature_setpoints", {})
        if preset == PRESET_HORS_GEL:
            return temps.get("hors_gel", 7.0)
        if preset in (PRESET_OFF, None):
            return 0.0
        return temps.get(_preset_to_temp_key(preset), 20.0)

    @property
    def hvac_mode(self):
        c = self._central()
        return c.state if c else HVACMode.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.AUTO, HVACMode.OFF]

    @property
    def preset_modes(self):
        return PRESETS

    async def async_update(self):
        state = self.hass.states.get(self._temp_sensor)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self._current_temp = float(state.state)
            except (ValueError, TypeError):
                self._current_temp = None

    def _any_window_open(self) -> bool:
        return any(self.hass.states.is_state(w, STATE_ON) for w in self._windows)

    def _calendar_ok(self, calendar_id: str | None) -> bool:
        if not calendar_id:
            return True
        return self.hass.states.is_state(calendar_id, STATE_ON)

    async def apply_central_order(self, preset: str, temps_dict: dict, calendar_id: str | None, master_switch: str | None):
        master_on = not master_switch or self.hass.states.is_state(master_switch, STATE_ON)

        if not master_on or self._any_window_open():
            payload = FIL_PILOTE_PAYLOAD[PRESET_OFF]
        elif not self._calendar_ok(calendar_id):
            payload = FIL_PILOTE_PAYLOAD[PRESET_HORS_GEL]
        else:
            payload = FIL_PILOTE_PAYLOAD.get(preset, FIL_PILOTE_PAYLOAD[PRESET_OFF])

        topic = f"{self._mqtt_base_topic}/{self._zigbee_id}/set"
        await self.hass.services.async_call(
            "mqtt",
            "publish",
            {
                "topic": topic,
                "payload": json.dumps(payload),
            },
            blocking=True,
        )
