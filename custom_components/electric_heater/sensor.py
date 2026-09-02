"""Sensors pour Chauffage Electrique Fil Pilote FR."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    CENTRAL,
    CONF_PRESENCE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    EVENT_WINDOWS_CHANGED,
)
from .fil_pilote import (
    all_configured_windows,
    entry_windows_open,
    get_central_state,
    house_window_open,
    parse_window_sensors,
)

HOME_STATES = {"home", "on"}


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.append(CentralTemperatureSensor(hass))
        entities.append(WindowStateSensor(hass, entry, central=True))
        entities.append(WhoIsHomeSensor(hass, entry))
        if entry.data.get(CONF_PRESENCE_SENSOR):
            entities.append(CentralPersonsSensor(hass, entry))
    else:
        entities.append(RoomTemperatureSensor(hass, entry))
        entities.append(WindowStateSensor(hass, entry, central=False))
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


class WhoIsHomeSensor(SensorEntity):
    """Noms des personnes a la maison (person.* et zone.home)."""

    _attr_has_entity_name = True
    _attr_name = "Presents"
    _attr_unique_id = "electric_heater_central_presents"
    _attr_icon = "mdi:account-group"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._unsub = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def extra_state_attributes(self):
        names, entity_ids = self._who()
        return {
            "count": len(names),
            "persons": entity_ids,
            "names": names,
        }

    def _who(self) -> tuple[list[str], list[str]]:
        names: list[str] = []
        entity_ids: list[str] = []
        zone = self.hass.states.get("zone.home")
        listed = []
        if zone and isinstance(zone.attributes.get("persons"), list):
            listed = [eid for eid in zone.attributes["persons"] if eid]
        if listed:
            for eid in listed:
                state = self.hass.states.get(eid)
                entity_ids.append(eid)
                names.append(state.name if state else eid.split(".", 1)[-1].replace("_", " ").title())
        else:
            for state in self.hass.states.async_all("person"):
                if str(state.state).lower() in HOME_STATES:
                    entity_ids.append(state.entity_id)
                    names.append(state.name)
        return names, entity_ids

    async def async_added_to_hass(self):
        tracked = ["zone.home"]
        tracked.extend(state.entity_id for state in self.hass.states.async_all("person"))
        self._unsub = async_track_state_change_event(self.hass, tracked, self._update)
        self._update()

    @callback
    def _update(self, event=None):
        names, _entity_ids = self._who()
        if not names:
            self._attr_native_value = "Personne"
            self._attr_icon = "mdi:account-off"
        else:
            self._attr_native_value = ", ".join(names)
            self._attr_icon = "mdi:account-group"
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


class WindowStateSensor(SensorEntity):
    """on = Ouverte, off = Fermee. Meme ecoute que la temperature."""

    _attr_has_entity_name = True
    _attr_name = "Etat fenetre"
    _attr_icon = "mdi:window-closed-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, central: bool):
        self.hass = hass
        self.entry = entry
        self._central = central
        self._unsub = None
        if central:
            self._attr_unique_id = "electric_heater_central_etat_fenetre"
        else:
            self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_etat_fenetre"

    @property
    def device_info(self):
        if self._central:
            return {"identifiers": {(DOMAIN, "electric_heater_central")}}
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    @property
    def extra_state_attributes(self):
        sensors = (
            all_configured_windows(self.hass)
            if self._central
            else parse_window_sensors(self.entry.data)
        )
        sources = {}
        for eid in sensors:
            st = self.hass.states.get(eid)
            sources[eid] = st.state if st else "inconnu"
        return {"windows": sensors, "sources": sources}

    async def async_added_to_hass(self):
        sensors = (
            all_configured_windows(self.hass)
            if self._central
            else parse_window_sensors(self.entry.data)
        )
        if sensors:
            self._unsub = async_track_state_change_event(
                self.hass, sensors, self._update
            )
        self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._update)
        self._update()

    @callback
    def _update(self, event=None):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        opened = (
            house_window_open(self.hass)
            if self._central
            else entry_windows_open(self.hass, self.entry)
        )
        sensors = (
            all_configured_windows(self.hass)
            if self._central
            else parse_window_sensors(self.entry.data)
        )
        if not sensors:
            self._attr_native_value = "Non configuree"
            self._attr_icon = "mdi:window-closed-variant"
        elif opened:
            self._attr_native_value = "Ouverte"
            self._attr_icon = "mdi:window-open-variant"
        else:
            self._attr_native_value = "Fermee"
            self._attr_icon = "mdi:window-closed-variant"
        self.async_write_ha_state()
