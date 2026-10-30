"""Statistiques : temps de chauffe par radiateur (statistiques long terme HA)."""
from __future__ import annotations

import time
from datetime import timedelta

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_track_state_change_event,
    async_track_time_change,
    async_track_time_interval,
)
from homeassistant.util import dt as dt_util

from .const import CONF_POWER, DOMAIN
from .fil_pilote import iter_room_entries

_TICK = timedelta(minutes=1)


def room_climate_id(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    return er.async_get(hass).async_get_entity_id(
        "climate", DOMAIN, f"electric_heater_room_{entry.entry_id}"
    )


def room_energy_sensor(hass: HomeAssistant, entry: ConfigEntry) -> str | None:
    """Compteur d'énergie réel du radiateur (sensor.*_energy en kWh), détecté automatiquement.

    Ordre : option « energy_sensor » > même appareil que le relais fil pilote >
    même pièce HA que le radiateur (nom contenant radiateur / chauffage / nom de la pièce).
    """
    data = {**dict(entry.data), **dict(entry.options or {})}
    if data.get("energy_sensor"):
        return data["energy_sensor"]
    from homeassistant.helpers import device_registry as dr

    ent_reg = er.async_get(hass)
    dev_reg = dr.async_get(hass)

    def _is_energy(ent) -> bool:
        if ent.domain != "sensor" or ent.platform == DOMAIN or ent.disabled_by:
            return False
        st = hass.states.get(ent.entity_id)
        dclass = ent.device_class or ent.original_device_class or (st and st.attributes.get("device_class"))
        unit = (st and st.attributes.get("unit_of_measurement")) or ent.unit_of_measurement
        return dclass == "energy" or unit in ("kWh", "Wh")

    def _area(ent):
        if ent.area_id:
            return ent.area_id
        dev = dev_reg.async_get(ent.device_id) if ent.device_id else None
        return dev.area_id if dev else None

    def _best(cands):
        cands = sorted(cands, key=lambda e: (not e.entity_id.endswith("_energy"), e.entity_id))
        return cands[0].entity_id if cands else None

    relay = ent_reg.async_get(data.get("fil_pilote_select") or "")
    if relay and relay.device_id:
        found = _best([e for e in er.async_entries_for_device(ent_reg, relay.device_id) if _is_energy(e)])
        if found:
            return found
    climate = ent_reg.async_get(room_climate_id(hass, entry) or "")
    areas = {a for a in (_area(climate) if climate else None, _area(relay) if relay else None) if a}
    if not areas:
        return None
    name = str(data.get("name") or "").lower().split()
    hints = ("radiateur", "chauffage", "heater", "radiator")
    cands = [
        e for e in ent_reg.entities.values()
        if _is_energy(e) and _area(e) in areas
        and (any(h in e.entity_id for h in hints) or any(w in e.entity_id for w in name if len(w) > 3))
    ]
    return _best(cands)


def _heating(hass: HomeAssistant, eid: str | None) -> bool:
    st = hass.states.get(eid) if eid else None
    return bool(st and st.attributes.get("hvac_action") == "heating")


def _power(entry: ConfigEntry) -> float:
    try:
        return float((entry.options or {}).get(CONF_POWER, entry.data.get(CONF_POWER)) or 0)
    except (TypeError, ValueError):
        return 0.0


def stat_uid(entry_id: str, kind: str, daily: bool) -> str:
    suffix = "jour" if daily else "total"
    return f"electric_heater_room_{entry_id}_{'chauffe' if kind == 'time' else 'conso'}_{suffix}"


_NAMES = {
    ("time", True): "Temps de chauffe aujourd'hui",
    ("time", False): "Temps de chauffe total",
    ("energy", True): "Consommation aujourd'hui",
    ("energy", False): "Consommation totale",
}


class RoomHeatingTimeSensor(RestoreSensor):
    """Temps de chauffe (h) ou consommation estimée (kWh = h x puissance) d'un radiateur."""

    _attr_has_entity_name = True
    _attr_suggested_display_precision = 2

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, daily: bool, kind: str = "time") -> None:
        self.hass = hass
        self.entry = entry
        self._daily = daily
        self._kind = kind
        self._attr_name = _NAMES[(kind, daily)]
        self._attr_unique_id = stat_uid(entry.entry_id, kind, daily)
        if kind == "time":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS
            self._attr_icon = "mdi:radiator"
        else:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_icon = "mdi:lightning-bolt"
        self._attr_state_class = SensorStateClass.TOTAL if daily else SensorStateClass.TOTAL_INCREASING
        self._hours = 0.0
        self._since: float | None = None
        self._climate: str | None = None
        if daily:
            self._attr_last_reset = dt_util.start_of_local_day()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    @property
    def native_value(self) -> float:
        return round(self._hours + self._running(), 3)

    def _factor(self) -> float:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id) or self.entry
        return 1.0 if self._kind == "time" else _power(current) / 1000

    def _running(self) -> float:
        hours = (time.monotonic() - self._since) / 3600 if self._since is not None else 0.0
        return hours * self._factor()

    def _flush(self) -> None:
        self._hours += self._running()
        if self._since is not None:
            self._since = time.monotonic()

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_sensor_data()
        last_state = await self.async_get_last_state()
        if last and last.native_value is not None:
            try:
                value = float(last.native_value)
            except (TypeError, ValueError):
                value = 0.0
            same_day = (
                not self._daily
                or (last_state and dt_util.as_local(last_state.last_updated).date() == dt_util.now().date())
            )
            self._hours = value if same_day else 0.0
        self._climate = room_climate_id(self.hass, self.entry)
        if self._climate:
            self.async_on_remove(
                async_track_state_change_event(self.hass, [self._climate], self._on_change)
            )
        self.async_on_remove(async_track_time_interval(self.hass, self._tick, _TICK))
        if self._daily:
            self.async_on_remove(
                async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=0)
            )
        self._on_change()

    @callback
    def _on_change(self, _event=None) -> None:
        heating = _heating(self.hass, self._climate)
        if heating and self._since is None:
            self._since = time.monotonic()
        elif not heating and self._since is not None:
            self._hours += self._running()
            self._since = None
        self.async_write_ha_state()

    @callback
    def _tick(self, _now=None) -> None:
        self._flush()
        self.async_write_ha_state()

    @callback
    def _midnight(self, _now=None) -> None:
        self._hours = 0.0
        if self._since is not None:
            self._since = time.monotonic()
        self._attr_last_reset = dt_util.start_of_local_day()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"en_chauffe": self._since is not None, "radiateur": self._climate}


class CentralStatSensor(SensorEntity):
    """Somme de tous les radiateurs (temps de chauffe ou consommation)."""

    _attr_has_entity_name = True
    _attr_suggested_display_precision = 2

    def __init__(self, hass: HomeAssistant, daily: bool, kind: str) -> None:
        self.hass = hass
        self._daily = daily
        self._kind = kind
        self._attr_name = {
            ("time", True): "Temps de chauffe maison aujourd'hui",
            ("time", False): "Temps de chauffe maison total",
            ("energy", True): "Consommation maison aujourd'hui",
            ("energy", False): "Consommation maison totale",
        }[(kind, daily)]
        self._attr_unique_id = f"electric_heater_central_{'chauffe' if kind == 'time' else 'conso'}_{'jour' if daily else 'total'}"
        self._attr_state_class = SensorStateClass.TOTAL if daily else SensorStateClass.TOTAL_INCREASING
        if kind == "time":
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.HOURS
            self._attr_icon = "mdi:radiator"
        else:
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_icon = "mdi:lightning-bolt"
        if daily:
            self._attr_last_reset = dt_util.start_of_local_day()
        self._detail: dict[str, float] = {}

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    def _sources(self) -> dict[str, str]:
        reg = er.async_get(self.hass)
        out = {}
        for entry in iter_room_entries(self.hass):
            eid = reg.async_get_entity_id("sensor", DOMAIN, stat_uid(entry.entry_id, self._kind, self._daily))
            if eid:
                out[eid] = entry.data.get("name") or entry.title
        return out

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_track_time_interval(self.hass, self._update, _TICK))
        self._update()

    @callback
    def _update(self, _now=None) -> None:
        detail: dict[str, float] = {}
        for eid, name in self._sources().items():
            st = self.hass.states.get(eid)
            try:
                detail[name] = round(float(st.state), 3)
            except (AttributeError, TypeError, ValueError):
                continue
        self._detail = detail
        self._attr_native_value = round(sum(detail.values()), 3)
        if self._daily:
            self._attr_last_reset = dt_util.start_of_local_day()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"par_radiateur": self._detail}


class CentralMeteredEnergySensor(SensorEntity):
    """Somme des compteurs d'énergie réels liés aux radiateurs (kWh)."""

    _attr_has_entity_name = True
    _attr_name = "Consommation radiateurs (compteurs)"
    _attr_unique_id = "electric_heater_central_conso_compteurs"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:meter-electric"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._detail: dict[str, float] = {}
        self._links: dict[str, str] = {}

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_track_time_interval(self.hass, self._update, _TICK))
        self._update()

    @callback
    def _update(self, _now=None) -> None:
        detail: dict[str, float] = {}
        links: dict[str, str] = {}
        for entry in iter_room_entries(self.hass):
            eid = room_energy_sensor(self.hass, entry)
            if not eid:
                continue
            name = entry.data.get("name") or entry.title
            links[name] = eid
            st = self.hass.states.get(eid)
            try:
                value = float(st.state)
            except (AttributeError, TypeError, ValueError):
                continue
            if (st.attributes.get("unit_of_measurement") or "") == "Wh":
                value /= 1000
            detail[name] = round(value, 3)
        self._detail, self._links = detail, links
        self._attr_native_value = round(sum(detail.values()), 3) if detail else None
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"par_radiateur": self._detail, "compteurs": self._links}


def _kwh(state) -> float | None:
    if state is None or state.state in ("unknown", "unavailable"):
        return None
    try:
        value = float(state.state)
    except (TypeError, ValueError):
        return None
    return value / 1000 if (state.attributes.get("unit_of_measurement") or "") == "Wh" else value


class RoomMeterDailySensor(RestoreSensor):
    """Consommation du jour lue sur le compteur kWh réel du radiateur."""

    _attr_has_entity_name = True
    _attr_name = "Consommation compteur aujourd'hui"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:meter-electric"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._attr_unique_id = f"electric_heater_room_{entry.entry_id}_compteur_jour"
        self._meter: str | None = None
        self._base: float | None = None
        self._acc = 0.0
        self._value: float | None = None
        self._unsub = None
        self._attr_last_reset = dt_util.start_of_local_day()

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"room_{self.entry.entry_id}")},
            "via_device": (DOMAIN, "electric_heater_central"),
        }

    @property
    def available(self) -> bool:
        return self._meter is not None

    @property
    def native_value(self):
        return None if self._value is None else round(self._value, 3)

    @property
    def extra_state_attributes(self):
        return {
            "compteur": self._meter,
            "index_minuit": self._base,
            "cumul_avant_remise": round(self._acc, 3),
            "jour": dt_util.now().date().isoformat(),
        }

    async def async_added_to_hass(self) -> None:
        last = await self.async_get_last_state()
        if last and last.attributes.get("jour") == dt_util.now().date().isoformat():
            try:
                self._base = float(last.attributes.get("index_minuit"))
                self._acc = float(last.attributes.get("cumul_avant_remise") or 0)
            except (TypeError, ValueError):
                self._base = None
        self.async_on_remove(
            async_track_time_change(self.hass, self._midnight, hour=0, minute=0, second=0)
        )
        self.async_on_remove(async_track_time_interval(self.hass, self._relink, timedelta(minutes=5)))
        self.async_on_remove(lambda: self._unsub and self._unsub())
        self._relink()

    @callback
    def _relink(self, _now=None) -> None:
        current = self.hass.config_entries.async_get_entry(self.entry.entry_id) or self.entry
        meter = room_energy_sensor(self.hass, current)
        if meter != self._meter:
            if self._unsub:
                self._unsub()
                self._unsub = None
            if self._meter is not None:
                self._base, self._acc = None, 0.0
            self._meter = meter
            if meter:
                self._unsub = async_track_state_change_event(self.hass, [meter], self._on_meter)
        self._on_meter()

    @callback
    def _on_meter(self, _event=None) -> None:
        cur = _kwh(self.hass.states.get(self._meter)) if self._meter else None
        if cur is not None:
            if self._base is None:
                self._base = cur
            elif cur < self._base - 0.001:
                # Compteur remis à zéro : on garde ce qui a déjà été compté aujourd'hui.
                self._acc += (self._value or 0) - self._acc
                self._base = cur
            self._value = self._acc + max(cur - self._base, 0.0)
        self.async_write_ha_state()

    @callback
    def _midnight(self, _now=None) -> None:
        cur = _kwh(self.hass.states.get(self._meter)) if self._meter else None
        self._base = cur
        self._acc = 0.0
        self._value = 0.0 if cur is not None else None
        self._attr_last_reset = dt_util.start_of_local_day()
        self.async_write_ha_state()


class CentralMeterDailySensor(SensorEntity):
    """Somme des consommations du jour lues sur les compteurs réels."""

    _attr_has_entity_name = True
    _attr_name = "Consommation compteurs aujourd'hui"
    _attr_unique_id = "electric_heater_central_compteurs_jour"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_suggested_display_precision = 2
    _attr_icon = "mdi:meter-electric"

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._detail: dict[str, float] = {}
        self._attr_last_reset = dt_util.start_of_local_day()

    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, "electric_heater_central")}}

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(async_track_time_interval(self.hass, self._update, _TICK))
        self._update()

    @callback
    def _update(self, _now=None) -> None:
        reg = er.async_get(self.hass)
        detail: dict[str, float] = {}
        for entry in iter_room_entries(self.hass):
            eid = reg.async_get_entity_id("sensor", DOMAIN, f"electric_heater_room_{entry.entry_id}_compteur_jour")
            st = self.hass.states.get(eid) if eid else None
            try:
                detail[entry.data.get("name") or entry.title] = round(float(st.state), 3)
            except (AttributeError, TypeError, ValueError):
                continue
        self._detail = detail
        self._attr_native_value = round(sum(detail.values()), 3) if detail else None
        self._attr_last_reset = dt_util.start_of_local_day()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {"par_radiateur": self._detail}
