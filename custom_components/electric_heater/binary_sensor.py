"""Binary sensors pour Chauffage Electrique Fil Pilote FR."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event

from .const import CENTRAL, CONF_HEATING_CALENDAR, CONF_PRESENCE_SENSOR, DOMAIN
from .fil_pilote import get_central_state

ACTIVE_CALENDAR_STATES = {"on", "active", "true", "home"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.extend(
            [
                CentralHeatingActive(hass),
                CentralPresence(hass, entry),
                CentralAutoEcoMode(hass),
                CentralCalendarActive(hass, entry),
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
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
    _attr_name = "Presence"
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
    _attr_name = "Mode Eco Auto"
    _attr_unique_id = "electric_heater_central_mode_eco_auto"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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


class CentralCalendarActive(BinarySensorEntity):
    """Etat du calendrier / planning de chauffage (on = creneau actif)."""

    _attr_has_entity_name = True
    _attr_name = "Calendrier chauffage"
    _attr_unique_id = "electric_heater_central_calendrier"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_is_on = False

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._calendar = entry.data.get(CONF_HEATING_CALENDAR)
        self._unsub = None
        self._event = None
        self._start = None
        self._end = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def available(self) -> bool:
        return bool(self._calendar)

    @property
    def extra_state_attributes(self):
        return {
            "calendar": self._calendar,
            "event": self._event,
            "start": self._start,
            "end": self._end,
        }

    async def async_added_to_hass(self):
        self._refresh_calendar_id()
        if self._calendar:
            self._unsub = async_track_state_change_event(
                self.hass, [self._calendar], self._update
            )
        self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update)
        self._update()

    def _refresh_calendar_id(self) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        data = current.data if current else self.entry.data
        self._calendar = data.get(CONF_HEATING_CALENDAR)

    @callback
    def _update(self, event=None):
        previous = self._calendar
        self._refresh_calendar_id()
        if self._calendar and self._calendar != previous:
            if self._unsub:
                self._unsub()
            self._unsub = async_track_state_change_event(
                self.hass, [self._calendar], self._update
            )
        state = self.hass.states.get(self._calendar) if self._calendar else None
        if not state or state.state in ("unknown", "unavailable"):
            self._attr_is_on = False
            self._event = None
            self._start = None
            self._end = None
        else:
            self._attr_is_on = state.state.lower() in ACTIVE_CALENDAR_STATES
            self._event = state.attributes.get("message")
            self._start = state.attributes.get("start_time")
            self._end = state.attributes.get("end_time")
        self.async_write_ha_state()


class RoomWindowOpen(BinarySensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Fenetre Ouverte"
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
    _attr_name = "Securite Fenetre"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
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
