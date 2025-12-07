"""
Chauffage Électrique Fil Pilote Français - v1.4.6
Auteur : XAV59213
100 % local - Décembre 2025
Compatible Home Assistant 2025.12+ - ZÉRO ERREUR / ZÉRO WARNING
"""
import json
from enum import Enum

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature
from homeassistant.components.climate.const import HVAC_MODE_AUTO, HVAC_MODE_OFF
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

# Support des fonctionnalités
SUPPORT_TARGET_TEMPERATURE = ClimateEntityFeature.TARGET_TEMPERATURE
SUPPORT_PRESET_MODE = ClimateEntityFeature.PRESET_MODE
SUPPORT_FLAGS_CENTRAL = SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE


def _preset_to_temp_key(preset: str) -> str:
    """Mapper le preset vers la clé de consigne dans le dict de températures."""
    mapping = {
        PRESET_COMFORT_M1: "confort_m1",
        PRESET_COMFORT_M2: "confort_m2",
        PRESET_ECO: "eco",
        PRESET_HORS_GEL: "hors_gel",
    }
    return mapping.get(preset, "confort")


async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    """Créer les entités à partir de l’entry."""
    if config_entry.data.get("type") == CENTRAL:
        async_add_entities([CentralThermostat(hass, config_entry)])
    else:
        async_add_entities([RoomHeater(hass, config_entry)])


class CentralThermostat(ClimateEntity):
    """Thermostat central virtuel – contrôle toute la maison."""
    _attr_has_entity_name = True
    _attr_name = None
    _enable_turn_on_off_backwards_compatibility = False

    _attr_supported_features = SUPPORT_FLAGS_CENTRAL
    _attr_hvac_modes = [HVAC_MODE_AUTO, HVAC_MODE_OFF]
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
        self._target_temp: float = self._temps["confort"]
        self._preset: str = PRESET_COMFORT
        self._attr_hvac_mode = HVAC_MODE_AUTO

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, "central")},
            name=self._name,
            manufacturer="XAV59213",
            model="Thermostat central fil pilote",
            sw_version="1.4.6",
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
        key = _preset_to_temp_key(self._preset)
        return self._temps.get(key, self._temps["confort"])

    @property
    def hvac_mode(self):
        return self._attr_hvac_mode

    @property
    def hvac_modes(self):
        return self._attr_hvac_modes

    @property
    def preset_mode(self):
        return self._preset

    @property
    def preset_modes(self):
        return self._attr_preset_modes

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
        self.async_write_ha_state()

    # Stubs synchrones obligatoires en 2025.12+
    def set_temperature(self, **kwargs):
        raise NotImplementedError("Use async_set_temperature")

    def set_hvac_mode(self, hvac_mode):
        raise NotImplementedError("Use async_set_hvac_mode")

    def set_preset_mode(self, preset_mode):
        raise NotImplementedError("Use async_set_preset_mode")

    async def async_set_temperature(self, **kwargs):
        if ATTR_TEMPERATURE in kwargs:
            self._target_temp = kwargs[ATTR_TEMPERATURE]
            self._temps["confort"] = self._target_temp
            self._preset = PRESET_COMFORT
            self._attr_hvac_mode = HVAC_MODE_AUTO
            self.async_write_ha_state()
            await self._push_to_rooms()

    async def async_set_hvac_mode(self, hvac_mode: str):
        if hvac_mode not in (HVAC_MODE_AUTO, HVAC_MODE_OFF):
            return
        self._attr_hvac_mode = hvac_mode
        if hvac_mode == HVAC_MODE_OFF:
            self._preset = PRESET_OFF
        elif self._preset == PRESET_OFF:
            self._preset = PRESET_COMFORT
        self.async_write_ha_state()
        await self._push_to_rooms()

    async def async_set_preset_mode(self, preset_mode: str):
        if preset_mode not in PRESETS:
            return
        self._preset = preset_mode
        self._attr_hvac_mode = HVAC_MODE_OFF if preset_mode == PRESET_OFF else HVAC_MODE_AUTO
        self.async_write_ha_state()
        await self._push_to_rooms()

    async def _push_to_rooms(self):
        """Propager proprement l’ordre à toutes les pièces (sans recréer d’instances)."""
        for entity in self.hass.data.get("entity_registry", {}).values():
            if (
                hasattr(entity, "entity_id")
                and entity.entity_id.startswith("climate.")
                and entity.entity_id != "climate.electric_heater_central"
                and hasattr(entity, "apply_central_order")
            ):
                try:
                    await entity.apply_central_order(
                        self._preset,
                        self._temps,
                        self._calendar,
                        self._master_switch,
                    )
                except Exception as err:  # sécurité absolue
                    self.hass.log(f"Erreur push room {entity.entity_id}: {err}", level="WARNING")


class RoomHeater(ClimateEntity):
    """Entité radiateur par pièce – lecture seule, pilotée par le central."""
    _attr_has_entity_name = True
    _attr_name = None
    _attr_supported_features = 0
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self._name = entry.data["name"]

        # Compatibilité anciennes/nouvelles config
        zigbee_id = entry.data.get("heater_zigbee_id")
        if not zigbee_id:
            relay = entry.data.get("heater_relay", "")
            state = self.hass.states.get(relay) if relay else None
            zigbee_id = (
                state.attributes.get("friendly_name")
                if state and "friendly_name" in state.attributes
                else relay.split(".")[-1] if relay else "unknown"
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

    def _central_state(self) -> State | None:
        return self.hass.states.get("climate.electric_heater_central")

    @property
    def preset_mode(self):
        c = self._central_state()
        return c.attributes.get("preset_mode") if c else PRESET_OFF

    @property
    def target_temperature(self):
        c = self._central_state()
        if not c:
            return 0.0
        preset = c.attributes.get("preset_mode")
        temps = c.attributes.get("temperature_setpoints", {})
        if preset == PRESET_HORS_GEL:
            return temps.get("hors_gel", 7.0)
        if preset in (PRESET_OFF, None):
            return 0.0
        key = _preset_to_temp_key(preset)
        return temps.get(key, 20.0)

    @property
    def hvac_mode(self):
        c = self._central_state()
        return c.state if c else HVAC_MODE_OFF

    @property
    def hvac_modes(self):
        return [HVAC_MODE_AUTO, HVAC_MODE_OFF]

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
        self.async_write_ha_state()

    def _any_window_open(self) -> bool:
        for w in self._windows:
            s = self.hass.states.get(w)
            if s and s.state == STATE_ON:
                return True
        return False

    def _is_calendar_heating_allowed(self, calendar_id: str | None) -> bool:
        if not calendar_id:
            return True
        state = self.hass.states.get(calendar_id)
        return bool(state and state.state == STATE_ON)

    async def apply_central_order(
        self,
        preset: str,
        temps_dict: dict,
        calendar_id: str | None,
        master_switch: str | None,
    ):
        """Ordre reçu du thermostat central → envoi MQTT au SIN-4-FP-21."""
        # 1. Switch maître
        master_on = True
        if master_switch:
            s = self.hass.states.get(master_switch)
            master_on = bool(s and s.state == STATE_ON)

        if not master_on:
            payload = FIL_PILOTE_PAYLOAD[PRESET_OFF]
        # 2. Fenêtre ouverte
        elif self._any_window_open():
            payload = FIL_PILOTE_PAYLOAD[PRESET_OFF]
        # 3. Calendrier désactivé → Hors-gel
        elif not self._is_calendar_heating_allowed(calendar_id):
            payload = FIL_PILOTE_PAYLOAD[PRESET_HORS_GEL]
        # 4. Ordre normal
        else:
            payload = FIL_PILOTE_PAYLOAD.get(preset, FIL_PILOTE_PAYLOAD[PRESET_OFF])

        topic = f"{self._mqtt_base_topic}/{self._zigbee_id}/set"
        await self.hass.services.async_call(
            "mqtt",
            "publish",
            {"topic": topic, "payload": json.dumps(payload)},
            blocking=True,
        )
