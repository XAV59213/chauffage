"""Sensors pour Chauffage Electrique Fil Pilote FR."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from datetime import timedelta

from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .const import (
    CENTRAL,
    CENTRAL_ENTITY_ID,
    CONF_PRESENCE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WEATHER,
    DOMAIN,
    EVENT_WINDOWS_CHANGED,
)
from .fil_pilote import (
    all_configured_windows,
    entry_windows_open,
    get_central_state,
    house_window_open,
    iter_room_entries,
    open_windows,
    rooms_sensor_ko,
    parse_window_sensors,
)
from .occupancy import occupancy_count
from .weather import outdoor_temperature, weather_condition


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    entities = []
    if entry.data.get("type") == CENTRAL:
        entities.append(CentralTemperatureSensor(hass))
        entities.append(WindowStateSensor(hass, entry, central=True))
        entities.append(WhoIsHomeSensor(hass, entry))
        entities.append(OutdoorWeatherSensor(hass, entry))
        entities.append(OpenWindowsSensor(hass))
        entities.append(SensorKoSensor(hass))
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
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update))
        self.async_on_remove(
            async_track_state_change_event(self.hass, [CENTRAL_ENTITY_ID], self._update)
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


class OutdoorWeatherSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Temperature exterieure"
    _attr_unique_id = "electric_heater_central_exterieur"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_icon = "mdi:weather-partly-cloudy"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._weather = entry.data.get(CONF_WEATHER)
        self._unsub = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def extra_state_attributes(self):
        return {
            "weather": self._weather,
            "condition": weather_condition(self.hass, self._weather),
        }

    async def async_added_to_hass(self):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._weather = self.entry.data.get(CONF_WEATHER)
        if self._weather:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._weather], self._update)
            )
        self._update()

    @callback
    def _update(self, event=None):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._weather = self.entry.data.get(CONF_WEATHER)
        self._attr_native_value = outdoor_temperature(self.hass, self._weather)
        self.async_write_ha_state()


class WhoIsHomeSensor(SensorEntity):
    """Un seul capteur : suit Nombre famille home."""

    _attr_has_entity_name = True
    _attr_name = "Presents"
    _attr_unique_id = "electric_heater_central_presents"
    _attr_icon = "mdi:account-group"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass = hass
        self.entry = entry
        self._sensor = entry.data.get(CONF_PRESENCE_SENSOR)
        self._unsub = None

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def extra_state_attributes(self):
        noms = sorted(
            (st.attributes.get("friendly_name") or st.entity_id)
            for st in self.hass.states.async_all("person")
            if st.state == "home"
            and (st.attributes.get("friendly_name") or "").strip().lower() not in ("maison", "home")
            and st.entity_id not in ("person.maison", "person.home")
        )
        return {
            "source": self._sensor,
            "count": occupancy_count(self.hass, self._sensor),
            "personnes": noms,
            "noms": ", ".join(noms) or "Personne",
        }

    async def async_added_to_hass(self):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._sensor = self.entry.data.get(CONF_PRESENCE_SENSOR)
        if self._sensor:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._sensor], self._update)
            )
        persons = self.hass.states.async_entity_ids("person")
        if persons:
            self.async_on_remove(
                async_track_state_change_event(self.hass, persons, self._update)
            )
        self._update()

    @callback
    def _update(self, event=None):
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._sensor = self.entry.data.get(CONF_PRESENCE_SENSOR)
        if not self._sensor:
            self._attr_native_value = "Non configure"
            self._attr_icon = "mdi:account-question"
        else:
            count = occupancy_count(self.hass, self._sensor)
            if count <= 0:
                self._attr_native_value = "Personne"
                self._attr_icon = "mdi:account-off"
            elif count == 1:
                self._attr_native_value = "1 personne"
                self._attr_icon = "mdi:account"
            else:
                self._attr_native_value = f"{count} personnes"
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
        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._sensor], self._update)
        )
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
    """on = Ouverte, off = Fermee."""

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
            self.async_on_remove(
                async_track_state_change_event(self.hass, sensors, self._update)
            )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._update))
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
        elif not opened and all(
            (st := self.hass.states.get(eid)) is None or st.state in ("unknown", "unavailable")
            for eid in sensors
        ):
            self._attr_native_value = "Indisponible"
            self._attr_icon = "mdi:window-shutter-alert"
        elif opened:
            self._attr_native_value = "Ouverte"
            self._attr_icon = "mdi:window-open-variant"
        else:
            self._attr_native_value = "Fermee"
            self._attr_icon = "mdi:window-closed-variant"
        self.async_write_ha_state()


def _room_temp_sensors(hass: HomeAssistant) -> list[str]:
    return [
        e.data[CONF_TEMPERATURE_SENSOR]
        for e in iter_room_entries(hass)
        if e.data.get(CONF_TEMPERATURE_SENSOR)
    ]


class OpenWindowsSensor(SensorEntity):
    """Nombre de fenêtres ouvertes, avec la liste en attributs."""

    _attr_has_entity_name = True
    _attr_translation_key = "fenetres_ouvertes"
    _attr_unique_id = "electric_heater_central_fenetres_ouvertes"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._open: list[dict] = []

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def icon(self):
        return "mdi:window-open-variant" if self._open else "mdi:window-closed-variant"

    @property
    def extra_state_attributes(self):
        return {
            "fenetres": [w["name"] for w in self._open],
            "entites": [w["entity_id"] for w in self._open],
            "pieces": sorted({w["piece"] for w in self._open if w["piece"]}),
            "liste": ", ".join(w["name"] for w in self._open) or "Aucune",
        }

    async def async_added_to_hass(self):
        sensors = all_configured_windows(self.hass)
        if sensors:
            self.async_on_remove(
                async_track_state_change_event(self.hass, sensors, self._update)
            )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._update))
        self.async_on_remove(
            async_track_time_interval(self.hass, self._update, timedelta(minutes=1))
        )
        self._update()

    @callback
    def _update(self, event=None):
        self._open = open_windows(self.hass)
        self._attr_native_value = len(self._open)
        self.async_write_ha_state()


class SensorKoSensor(SensorEntity):
    """Nombre de sondes de pièce KO (pile à remplacer), avec les pièces en attributs."""

    _attr_has_entity_name = True
    _attr_translation_key = "sondes_ko"
    _attr_unique_id = "electric_heater_central_sondes_ko"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant):
        self.hass = hass
        self._ko: list[dict] = []

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    @property
    def icon(self):
        return "mdi:battery-alert-variant-outline" if self._ko else "mdi:battery-check"

    @property
    def extra_state_attributes(self):
        return {
            "pieces": [r["piece"] for r in self._ko],
            "sondes": [r["sonde"] for r in self._ko],
            "liste": ", ".join(str(r["piece"]) for r in self._ko) or "Aucune",
            "message": "Remplacer la pile de la sonde" if self._ko else None,
        }

    async def async_added_to_hass(self):
        sensors = _room_temp_sensors(self.hass)
        if sensors:
            self.async_on_remove(
                async_track_state_change_event(self.hass, sensors, self._update)
            )
        self.async_on_remove(
            async_track_time_interval(self.hass, self._update, timedelta(minutes=1))
        )
        self._update()

    @callback
    def _update(self, event=None):
        self._ko = rooms_sensor_ko(self.hass)
        self._attr_native_value = len(self._ko)
        self.async_write_ha_state()
