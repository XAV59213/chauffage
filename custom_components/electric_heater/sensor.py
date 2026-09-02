"""Sensors pour Chauffage Electrique Fil Pilote FR."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event

from .const import CENTRAL, CONF_PRESENCE_SENSOR, CONF_TEMPERATURE_SENSOR, DOMAIN
from .fil_pilote import get_central_state


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.append(CentralTemperatureSensor(hass))
        if entry.data.get(CONF_PRESENCE_SENSOR):
            entities.append(CentralPersonsSensor(hass, entry))
    else:
        entities.append(RoomTemperatureSensor(hass, entry))
    async_add_entities(entities)


class CentralTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Temperature Centrale"
    _attr_unique_id = "electric_heater_central_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._unsub = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update)
        central = get_central_state(self.hass)
        if central:
            self._unsub = async_track_state_change_event(
                self.hass, [central.entity_id], self._update
            )
        self._update()

    @callback
    def _update(self, event=None):
        central = get_central_state(self.hass)
        value = None
        if central:
            raw = central.attributes.get("current_temperature")
            if raw is not None:
                try:
                    value = round(float(raw), 1)
                except (TypeError, ValueError):
                    value = None
        self._attr_native_value = value
        self.async_write_ha_state()


class CentralPersonsSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Nombre de Personnes"
    _attr_unique_id = "electric_heater_central_personnes"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "personnes"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._sensor = entry.data[CONF_PRESENCE_SENSOR]

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._sensor], self._update)
        self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(self._sensor)
        try:
            self._attr_native_value = (
                int(float(state.state))
                if state and state.state not in ("unknown", "unavailable")
                else 0
            )
        except (ValueError, TypeError):
            self._attr_native_value = 0
        self.async_write_ha_state()


class RoomTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Temperature Piece"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._sensor = entry.data[CONF_TEMPERATURE_SENSOR]
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_temperature"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._sensor], self._update)
        self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(self._sensor)
        try:
            self._attr_native_value = (
                round(float(state.state), 1)
                if state and state.state not in ("unknown", "unavailable")
                else None
            )
        except (ValueError, TypeError):
            self._attr_native_value = None
        self.async_write_ha_state()
