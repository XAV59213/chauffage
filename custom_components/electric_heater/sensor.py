"""Sensors pour Chauffage Electrique Fil Pilote FR."""
from __future__ import annotations

from .history import DecisionHistory

from datetime import datetime

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.core import Event
from typing import Any, TYPE_CHECKING
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.const import EntityCategory
from datetime import timedelta

from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval

from .entity import CentralEntity, RoomEntity, SourceAvailabilityMixin, central_device_info, room_device_info
from .const import (
    NO_OPTIONS,
    CENTRAL,
    CENTRAL_ENTITY_ID,
    CONF_PERSONS,
    CONF_PRESENCE_SENSOR,
    CONF_TEMPERATURE_SENSOR,
    CONF_WEATHER,
    DOMAIN,
    EVENT_WINDOWS_CHANGED,
)
from .fil_pilote import (
    central_entity_id,

    all_configured_windows,
    entry_windows_open,
    get_central_state,
    house_window_open,
    iter_room_entries,
    open_windows,
    rooms_sensor_ko,
    windows_from_entry,
)
from .history import ATTR_ENTRIES, CHANGE_LABELS, MERGED_ID, entry_summary, get_history, signal as history_signal
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from .occupancy import occupancy_count, present_names
from .stats import CentralMeterDailySensor, CentralMeteredEnergySensor, RoomMeterDailySensor, CentralStatSensor, RoomHeatingTimeSensor
from .weather import outdoor_temperature, weather_condition

if TYPE_CHECKING:
    from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

# Ordres envoyés via les services HA ; pas de limite de parallélisme nécessaire.
PARALLEL_UPDATES = 0


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback) -> None:
    entities: list[SensorEntity] = []
    if entry.data.get("type") == CENTRAL:
        entities.append(CentralTemperatureSensor(hass))
        entities.append(WindowStateSensor(hass, entry, central=True))
        entities.append(WhoIsHomeSensor(hass, entry))
        entities.append(OutdoorWeatherSensor(hass, entry))
        entities.append(OpenWindowsSensor(hass))
        entities.append(SensorKoSensor(hass))
        for kind in ("time", "energy"):
            for daily in (True, False):
                entities.append(CentralStatSensor(hass, daily=daily, kind=kind))
        entities.append(CentralMeteredEnergySensor(hass))
        entities.append(CentralMeterDailySensor(hass))
        entities.append(LastChangeSensor(hass, entry))
        entities.append(CentralLastDecisionSensor(hass, entry))
    else:
        entities.append(RoomTemperatureSensor(hass, entry))
        entities.append(WindowStateSensor(hass, entry, central=False))
        for kind in ("time", "energy"):
            for daily in (True, False):
                entities.append(RoomHeatingTimeSensor(hass, entry, daily=daily, kind=kind))
        entities.append(RoomMeterDailySensor(hass, entry))
        entities.append(LastDecisionSensor(hass, entry))
    async_add_entities(entities)


class CentralTemperatureSensor(SourceAvailabilityMixin, CentralEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "temperature_centrale"
    # Doublon de current_temperature du thermostat central : désactivé par défaut.
    _attr_entity_registry_enabled_default = False
    _attr_unique_id = "electric_heater_central_temperature"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._unsub = None

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.hass.bus.async_listen(f"{DOMAIN}_central_changed", self._update))
        self.async_on_remove(
            async_track_state_change_event(self.hass, [central_entity_id(self.hass) or CENTRAL_ENTITY_ID], self._update)
        )
        self._update()

    @callback
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
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
        self._set_source_available(value is not None, central.entity_id if central else "thermostat central")
        self.async_write_ha_state()


class OutdoorWeatherSensor(CentralEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "temperature_exterieure"
    # Doublon de l'entité météo choisie : désactivé par défaut.
    _attr_entity_registry_enabled_default = False
    _attr_unique_id = "electric_heater_central_exterieur"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._weather = entry.data.get(CONF_WEATHER)
        self._unsub = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "weather": self._weather,
            "condition": weather_condition(self.hass, self._weather),
        }

    async def async_added_to_hass(self) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._weather = self.entry.data.get(CONF_WEATHER)
        if self._weather:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._weather], self._update)
            )
        self._update()

    @callback
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._weather = self.entry.data.get(CONF_WEATHER)
        self._attr_native_value = outdoor_temperature(self.hass, self._weather)
        self.async_write_ha_state()


class WhoIsHomeSensor(CentralEntity, SensorEntity):
    """Un seul capteur : suit Nombre famille home."""

    _attr_has_entity_name = True
    _attr_translation_key = "presents"
    _attr_unique_id = "electric_heater_central_presents"
    _attr_icon = "mdi:account-group"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._sensor = entry.data.get(CONF_PRESENCE_SENSOR)
        self._unsub = None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        noms = present_names(self.hass, {**dict(self.entry.data), **dict(self.entry.options or NO_OPTIONS)})
        return {
            "source": self._sensor,
            "count": len(noms) if self.entry.data.get(CONF_PERSONS) else occupancy_count(self.hass, self._sensor),
            "personnes_suivies": self.entry.data.get(CONF_PERSONS) or "auto",
            "personnes": noms,
            "noms": ", ".join(noms) or "Personne",
        }

    async def async_added_to_hass(self) -> None:
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
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id)
        self.entry = current or self.entry
        self._sensor = self.entry.data.get(CONF_PRESENCE_SENSOR)
        chosen = self.entry.data.get(CONF_PERSONS) or []
        if not self._sensor and not chosen:
            self._attr_native_value = "Non configure"
            self._attr_icon = "mdi:account-question"
        else:
            count = (
                len(present_names(self.hass, dict(self.entry.data)))
                if chosen
                else occupancy_count(self.hass, self._sensor)
            )
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


class RoomTemperatureSensor(SourceAvailabilityMixin, RoomEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "temperature_piece"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._sensor = entry.data[CONF_TEMPERATURE_SENSOR]
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_temperature"

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_state_change_event(self.hass, [self._sensor], self._update)
        )
        self._update()

    @callback
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
        state = self.hass.states.get(self._sensor)
        try:
            self._attr_native_value = (
                round(float(state.state), 1)
                if state and state.state not in ("unknown", "unavailable")
                else None
            )
        except (ValueError, TypeError):
            self._attr_native_value = None
        self._set_source_available(self._attr_native_value is not None, self._sensor)
        self.async_write_ha_state()


class WindowStateSensor(SensorEntity):
    """on = Ouverte, off = Fermee."""

    _attr_has_entity_name = True
    _attr_translation_key = "etat_fenetre"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, central: bool) -> None:
        self.hass = hass
        self.entry = entry
        self._central = central
        self._unsub = None
        if central:
            self._attr_unique_id = "electric_heater_central_etat_fenetre"
        else:
            self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_etat_fenetre"

    @property
    def device_info(self) -> DeviceInfo:
        if self._central:
            return central_device_info()
        return room_device_info(getattr(self, "hass", None), self.entry)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        sensors = (
            all_configured_windows(self.hass)
            if self._central
            else windows_from_entry(self.entry, self.hass)
        )
        sources = {}
        for eid in sensors:
            st = self.hass.states.get(eid)
            sources[eid] = st.state if st else "inconnu"
        return {"windows": sensors, "sources": sources}

    async def async_added_to_hass(self) -> None:
        sensors = (
            all_configured_windows(self.hass)
            if self._central
            else windows_from_entry(self.entry, self.hass)
        )
        if sensors:
            self.async_on_remove(
                async_track_state_change_event(self.hass, sensors, self._update)
            )
        self.async_on_remove(self.hass.bus.async_listen(EVENT_WINDOWS_CHANGED, self._update))
        self._update()

    @callback
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
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
            else windows_from_entry(self.entry, self.hass)
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


class OpenWindowsSensor(CentralEntity, SensorEntity):
    """Nombre de fenêtres ouvertes, avec la liste en attributs."""

    _attr_has_entity_name = True
    _attr_translation_key = "fenetres_ouvertes"
    _attr_unique_id = "electric_heater_central_fenetres_ouvertes"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._open: list[dict[str, Any]] = []

    @property
    def icon(self) -> str:
        return "mdi:window-open-variant" if self._open else "mdi:window-closed-variant"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "fenetres": [w["name"] for w in self._open],
            "entites": [w["entity_id"] for w in self._open],
            "pieces": sorted({w["piece"] for w in self._open if w["piece"]}),
            "liste": ", ".join(w["name"] for w in self._open) or "Aucune",
        }

    async def async_added_to_hass(self) -> None:
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
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
        self._open = open_windows(self.hass)
        self._attr_native_value = len(self._open)
        self.async_write_ha_state()


class SensorKoSensor(CentralEntity, SensorEntity):
    """Nombre de sondes de pièce KO (pile à remplacer), avec les pièces en attributs."""

    _attr_has_entity_name = True
    _attr_translation_key = "sondes_ko"
    _attr_unique_id = "electric_heater_central_sondes_ko"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._ko: list[dict[str, Any]] = []

    @property
    def icon(self) -> str:
        return "mdi:battery-alert-variant-outline" if self._ko else "mdi:battery-check"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "pieces": [r["piece"] for r in self._ko],
            "sondes": [r["sonde"] for r in self._ko],
            "liste": ", ".join(str(r["piece"]) for r in self._ko) or "Aucune",
            "message": "Remplacer la pile de la sonde" if self._ko else None,
        }

    async def async_added_to_hass(self) -> None:
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
    def _update(self, event: Event[Any] | datetime | None = None) -> None:
        self._ko = rooms_sensor_ko(self.hass)
        self._attr_native_value = len(self._ko)
        self.async_write_ha_state()


class LastDecisionSensor(SensorEntity):
    """Dernière décision de régulation du radiateur (visible dans Activité)."""

    _attr_has_entity_name = True
    _attr_translation_key = "derniere_decision"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_derniere_decision"
        self._history = get_history(hass, entry.entry_id, entry.data.get("name", ""))

    @property
    def device_info(self) -> DeviceInfo:
        return room_device_info(getattr(self, "hass", None), self.entry, name=self.entry.data["name"])

    def _last(self) -> dict[str, Any] | None:
        last = self._history.last(1)
        return last[0] if last else None

    @property
    def native_value(self) -> Any:
        return entry_summary(self._last())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        e = self._last() or {}
        return {
            "raison": e.get("reason"),
            "temperature": e.get("current_temp"),
            "consigne": e.get("target"),
            "ordre": e.get("new_order"),
            "ordre_precedent": e.get("previous_order"),
            "puissance_w": e.get("power_W"),
            "heure": e.get("time"),
            "dernier_changement": _last_change(self._history),
            "historique": self._history.last(ATTR_ENTRIES),
        }

    async def async_added_to_hass(self) -> None:
        await self._history.async_load()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, history_signal(self.entry.entry_id), self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()


def _change_entries(history: DecisionHistory, count: int) -> list[dict[str, Any]]:
    return [e for e in reversed(history.entries) if e.get("reason") in CHANGE_LABELS][:count]


def _last_change(history: DecisionHistory) -> str | None:
    found = _change_entries(history, 1)
    return entry_summary(found[0]) if found else None


class LastChangeSensor(CentralEntity, SensorEntity):
    """Dernier changement de consigne / mode / preset du thermostat central (Activité)."""

    _attr_has_entity_name = True
    _attr_translation_key = "dernier_changement"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_unique_id = "electric_heater_central_dernier_changement"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._history = get_history(hass, "central", "Thermostat central")

    def _last(self) -> dict[str, Any] | None:
        found = _change_entries(self._history, 1)
        return found[0] if found else None

    @property
    def native_value(self) -> Any:
        e = self._last()
        return entry_summary(e) if e else "Aucun changement"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        e = self._last() or {}
        return {
            "type": e.get("reason"),
            "ancien": e.get("ancien"),
            "nouveau": e.get("nouveau"),
            "par": e.get("par"),
            "heure": e.get("time"),
            "historique": _change_entries(self._history, 50),
        }

    async def async_added_to_hass(self) -> None:
        await self._history.async_load()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, history_signal("central"), self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()


class CentralLastDecisionSensor(CentralEntity, SensorEntity):
    """Dernière décision toutes pièces confondues (appareil central)."""

    _attr_has_entity_name = True
    _attr_translation_key = "derniere_decision"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_unique_id = "electric_heater_central_derniere_decision"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._history = get_history(hass, MERGED_ID, "Toutes les pièces")

    def _last(self) -> dict[str, Any] | None:
        return self._history.entries[-1] if self._history.entries else None

    @property
    def native_value(self) -> Any:
        e = self._last()
        if not e:
            return "Aucune décision"
        return f"{e.get('piece', '?')} · {entry_summary(e)}"[:255]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        e = self._last() or {}
        par_piece = {}
        for x in reversed(self._history.entries):
            p = x.get("piece")
            if p and p not in par_piece:
                par_piece[p] = entry_summary(x)
        return {
            "piece": e.get("piece"),
            "raison": e.get("reason"),
            "ordre": e.get("new_order"),
            "temperature": e.get("current_temp"),
            "consigne": e.get("target"),
            "puissance_w": e.get("power_W"),
            "heure": e.get("time"),
            "par_piece": par_piece,
            "historique": list(reversed(self._history.entries))[:50],
        }

    async def async_added_to_hass(self) -> None:
        await self._history.async_load()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, history_signal(MERGED_ID), self._updated)
        )

    @callback
    def _updated(self) -> None:
        self.async_write_ha_state()
