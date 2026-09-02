"""Binary sensors pour Chauffage Électrique Fil Pilote FR."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import CENTRAL, CONF_PRESENCE_SENSOR, DOMAIN
from .fil_pilote import get_central_state


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.extend(
            [
                CentralHeatingActive(hass),
                CentralPresence(hass, entry),
                CentralAutoEcoMode(hass),
            ]
        )
    elif entry.data.get("window_sensors", "").strip():
        entities.extend([RoomWindowOpen(hass, entry), RoomWindowSecurity(hass, entry)])
    async_add_entities(entities)


class CentralHeatingActive(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Chauffage Actif"
    _attr_unique_id = "electric_heater_central_chauffage_actif"
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_is_on = False

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
        if not central:
            self._attr_is_on = False
        else:
            action = central.attributes.get("hvac_action")
            self._attr_is_on = action == "heating" or (
                central.state in ("heat", "auto") and action != "off"
            )
        self.async_write_ha_state()


class CentralPresence(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Présence"
    _attr_unique_id = "electric_heater_central_presence"
    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    _attr_is_on = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self._sensor = entry.data.get(CONF_PRESENCE_SENSOR)

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
        is_on = False
        if state and state.state not in ("unknown", "unavailable"):
            try:
                is_on = int(float(state.state)) > 0
            except (TypeError, ValueError):
                is_on = state.state.lower() in ("on", "home", "true")
        self._attr_is_on = is_on
        self.async_write_ha_state()


class CentralAutoEcoMode(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Mode Éco Auto"
    _attr_unique_id = "electric_heater_central_mode_eco_auto"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_is_on = False

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
        self._attr_is_on = bool(central and central.attributes.get("auto_eco_active"))
        self.async_write_ha_state()


class RoomWindowOpen(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Fenêtre Ouverte"
    _attr_device_class = BinarySensorDeviceClass.WINDOW
    _attr_is_on = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_fenetre_ouverte"
        self._sensors = [
            s.strip()
            for s in entry.data.get("window_sensors", "").split(",")
            if s.strip()
        ]

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    async def async_added_to_hass(self):
        if self._sensors:
            async_track_state_change_event(self.hass, self._sensors, self._update)
            self._update()

    @callback
    def _update(self, event=None):
        self._attr_is_on = any(
            (st := self.hass.states.get(eid)) is not None and st.state == "on"
            for eid in self._sensors
        )
        self.async_write_ha_state()


class RoomWindowSecurity(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Sécurité Fenêtre"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_is_on = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_securite_fenetre"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    async def async_added_to_hass(self):
        self.hass.bus.async_listen(f"{DOMAIN}_rooms_changed", self._update)
        self._update()

    @callback
    def _update(self, event=None):
        sensors = [
            s.strip()
            for s in self.entry.data.get("window_sensors", "").split(",")
            if s.strip()
        ]
        self._attr_is_on = any(
            (st := self.hass.states.get(eid)) is not None and st.state == "on"
            for eid in sensors
        )
        self.async_write_ha_state()
