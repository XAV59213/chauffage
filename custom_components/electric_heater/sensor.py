# custom_components/electric_heater/sensor.py
"""
Sensors température pour chaque pièce – Chauffage Électrique Fil Pilote FR
"""

import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    """Création du sensor température pour chaque pièce"""
    if entry.data.get("type") == "central":
        return

    sensor = RoomTemperatureSensor(hass, entry)
    async_add_entities([sensor])


class RoomTemperatureSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Température"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:thermometer"

    def __init__(self, hass: HomeAssistant, entry):
        self.hass = hass
        self.entry = entry
        self._temp_sensor = entry.data["temperature_sensor"]
        self._attr_unique_id = f"{entry.entry_id}_temperature"
        self._attr_native_value = None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "name": self.entry.data["name"],
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        async_track_state_change_event(
            self.hass, [self._temp_sensor], self._sensor_changed
        )
        await self._update_from_source()

    @callback
    def _sensor_changed(self, _):
        self.hass.create_task(self._update_from_source())

    async def _update_from_source(self):
        state = self.hass.states.get(self._temp_sensor)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                self._attr_native_value = round(float(state.state), 1)
            except (ValueError, TypeError):
                self._attr_native_value = None
        else:
            self._attr_native_value = None
        self.async_write_ha_state()
