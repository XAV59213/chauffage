"""Binary sensors pour Chauffage Électrique Fil Pilote FR."""
from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from .const import DOMAIN, CENTRAL, ROOM, CONF_PRESENCE_SENSOR


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.extend([CentralHeatingActive(hass), CentralPresence(hass, entry), CentralAutoEcoMode(hass)])
    else:
        if entry.data.get("window_sensors", "").strip():
            entities.extend([RoomWindowOpen(hass, entry), RoomWindowSecurity(hass, entry)])
    async_add_entities(entities)


class CentralHeatingActive(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Chauffage Actif"
    _attr_unique_id = "electric_heater_central_chauffage_actif"
    _attr_device_class = BinarySensorDeviceClass.HEAT

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_is_on = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update)
        self._update()

    @callback
    def _update(self, event=None):
        central = self.hass.states.get("climate.electric_heater_central")
        self._attr_is_on = central and central.state == "heat"
        self.async_write_ha_state()


class CentralPresence(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Présence"
    _attr_unique_id = "electric_heater_central_presence"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._sensor = entry.data.get(CONF_PRESENCE_SENSOR)
        self._attr_is_on = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        if self._sensor:
            async_track_state_change_event(self.hass, [self._sensor], self._update)
            self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(self._sensor) if self._sensor else None
        self._attr_is_on = bool(state and state.state not in ("unknown", "unavailable") and int(float(state.state or 0)) > 0)
        self.async_write_ha_state()


class CentralAutoEcoMode(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Mode Éco Auto"
    _attr_unique_id = "electric_heater_central_mode_eco_auto"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._attr_is_on = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self):
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update)
        self._update()

    @callback
    def _update(self, event=None):
        central = self.hass.states.get("climate.electric_heater_central")
        self._attr_is_on = bool(central and central.attributes.get("auto_eco_active"))
        self.async_write_ha_state()


class RoomWindowOpen(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Fenêtre Ouverte"
    _attr_device_class = BinarySensorDeviceClass.WINDOW

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_fenetre_ouverte"
        self._sensors = [s.strip() for s in entry.data.get("window_sensors", "").split(",") if s.strip()]
        self._attr_is_on = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")}, "via_device": (DOMAIN, "electric_heater_central")}

    async def async_added_to_hass(self):
        if self._sensors:
            async_track_state_change_event(self.hass, self._sensors, self._update)
            self._update()

    @callback
    def _update(self, event=None):
        self._attr_is_on = any(self.hass.states.get(eid) and self.hass.states.get(eid).state == "on" for eid in self._sensors)
        self.async_write_ha_state()


class RoomWindowSecurity(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sécurité Fenêtre"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_securite_fenetre"
        self._attr_is_on = False

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")}, "via_device": (DOMAIN, "electric_heater_central")}

    async def async_added_to_hass(self):
        eid = f"binary_sensor.electric_heater_room_{self.entry.entry_id}_fenetre_ouverte"
        async_track_state_change_event(self.hass, [eid], self._update)
        self._update()

    @callback
    def _update(self, event=None):
        state = self.hass.states.get(f"binary_sensor.electric_heater_room_{self.entry.entry_id}_fenetre_ouverte")
        self._attr_is_on = bool(state and state.state == "on")
        self.async_write_ha_state()
