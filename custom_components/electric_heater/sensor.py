"""Sensors pour Chauffage Électrique Fil Pilote FR."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, CENTRAL, ROOM, CONF_PRESENCE_SENSOR


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.append(CentralTemperatureSensor(hass, entry))
        if entry.data.get(CONF_PRESENCE_SENSOR):
            entities.append(CentralPersonsSensor(hass, entry))
    else:
        entities.append(RoomTemperatureSensor(hass, entry))
    async_add_entities(entities)


class CentralTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Température Centrale"
    _attr_unique_id = "electric_heater_central_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update)
        await self._update()

    @callback
    def _update(self, event=None):
        central = self.hass.states.get("climate.electric_heater_central")
        self._attr_native_value = central.attributes.get("current_temperature") if central else None
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
        await self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(self._sensor)
        self._attr_native_value = int(float(state.state)) if state and state.state not in ("unknown", "unavailable") else 0
        self.async_write_ha_state()


class RoomTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Température Pièce"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._sensor = entry.data["temperature_sensor"]
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_temperature"

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")}, "via_device": (DOMAIN, "electric_heater_central")}

    async def async_added_to_hass(self):
        async_track_state_change_event(self.hass, [self._sensor], self._update)
        await self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(self._sensor)
        self._attr_native_value = round(float(state.state), 1) if state and state.state not in ("unknown", "unavailable") else None
        self.async_write_ha_state()
