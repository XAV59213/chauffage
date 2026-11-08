"""Statistiques : temps de chauffe, conso estimée, compteurs kWh détectés."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.sensor import DATA_COMPONENT as SENSOR
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import area_registry as ar, device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from custom_components.electric_heater import stats
from custom_components.electric_heater.const import DOMAIN

from .test_climate import SELECT, _house, _set


@pytest.fixture(autouse=True)
def no_grace():
    with patch(
        "custom_components.electric_heater.climate.RoomThermostat._in_startup_grace",
        return_value=False,
    ):
        yield


def _relay_device(hass):
    other = MockConfigEntry(domain="zha")
    other.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={("zha", "rad")})
    reg = er.async_get(hass)
    reg.async_get_or_create("select", "zha", "rad_sel", device_id=dev.id, suggested_object_id="chambre_pilot_wire_mode")
    reg.async_get_or_create("sensor", "zha", "rad_en", device_id=dev.id, suggested_object_id="radiateur_energy",
                            original_device_class="energy")
    return dev


def _sensor(hass, uid):
    eid = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, uid)
    return hass.data[SENSOR].get_entity(eid)


async def test_meter_on_relay_device(hass: HomeAssistant) -> None:
    _relay_device(hass)
    hass.states.async_set("sensor.radiateur_energy", "100.0", {"unit_of_measurement": "kWh"})
    calls, central = await _house(hass, "16.0", room_extra={"power": 1500})
    room = next(e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") != "central")
    assert stats.room_energy_sensor(hass, room) == "sensor.radiateur_energy"
    daily = _sensor(hass, f"electric_heater_room_{room.entry_id}_compteur_jour")
    hass.states.async_set("sensor.radiateur_energy", "101.5", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    assert daily.native_value == 1.5
    # Remise à zéro du compteur : le cumul est conservé
    hass.states.async_set("sensor.radiateur_energy", "0.5", {"unit_of_measurement": "kWh"})
    await hass.async_block_till_done()
    assert daily.native_value == 1.5
    hass.states.async_set("sensor.radiateur_energy", "1000", {"unit_of_measurement": "Wh"})
    await hass.async_block_till_done()
    assert daily.native_value == 2.0
    daily._midnight()
    assert daily.native_value == 0.0
    assert daily.extra_state_attributes["compteur"] == "sensor.radiateur_energy"
    metered = _sensor(hass, "electric_heater_central_conso_compteurs")
    metered._update()
    assert metered.native_value == 1.0
    hass.states.async_set("sensor.radiateur_energy", "x")
    metered._update()
    assert metered.native_value is None
    assert stats._kwh(None) is None and stats._kwh(State("sensor.a", "x")) is None
    # Option explicite prioritaire, puis compteur perdu
    assert stats.room_energy_sensor(hass, SimpleNamespace(data={}, options={"energy_sensor": "sensor.autre"})) == "sensor.autre"
    daily._meter = "sensor.ancien"
    daily._relink()
    assert daily._meter == "sensor.radiateur_energy"


async def test_meter_by_area(hass: HomeAssistant) -> None:
    area = ar.async_get(hass).async_create("Chambre")
    reg = er.async_get(hass)
    reg.async_get_or_create("select", "zha", "sel2", suggested_object_id="chambre_pilot_wire_mode")
    reg.async_update_entity(SELECT, area_id=area.id)
    e = reg.async_get_or_create("sensor", "shelly", "pm", suggested_object_id="prise_radiateur_chambre")
    reg.async_update_entity(e.entity_id, area_id=area.id)
    hass.states.async_set(e.entity_id, "3", {"unit_of_measurement": "kWh"})
    calls, central = await _house(hass, "16.0")
    room = next(x for x in hass.config_entries.async_entries(DOMAIN) if x.data.get("type") != "central")
    assert stats.room_energy_sensor(hass, room) == e.entity_id
    reg.async_update_entity(SELECT, area_id=None)
    climate = stats.room_climate_id(hass, room)
    reg.async_update_entity(climate, area_id=None)
    assert stats.room_energy_sensor(hass, room) is None


async def test_heating_time_and_energy(hass: HomeAssistant) -> None:
    clock = [1000.0]
    with patch.object(stats, "time", SimpleNamespace(monotonic=lambda: clock[0])):
        calls, central = await _house(hass, "16.0", room_extra={"power": "2000"})
        await _set(hass, central, HVACMode.HEAT, "comfort")
        room = next(x for x in hass.config_entries.async_entries(DOMAIN) if x.data.get("type") != "central")
        t = _sensor(hass, stats.stat_uid(room.entry_id, "time", True))
        en = _sensor(hass, stats.stat_uid(room.entry_id, "energy", False))
        # Ordre de chargement des plateformes : le capteur peut démarrer avant le climate (voir rapport).
        t._climate = en._climate = stats.room_climate_id(hass, room)
        t._on_change(); en._on_change()
        st = hass.states.get(stats.room_climate_id(hass, room))
        assert t.extra_state_attributes["en_chauffe"], (t._climate, st.attributes.get("hvac_action"), st.attributes.get("current_temperature"), st.attributes.get("temperature"), st.attributes.get("preset_mode"))
        clock[0] += 3600
        t._tick()
        en._tick()
        assert t.native_value == 1.0
        assert en.native_value == 2.0
        hass.states.async_set("sensor.chambre_temp", "25.0")
        await hass.async_block_till_done()
        clock[0] += 3600
        t._on_change()
        t._midnight()
        assert t.native_value == 0.0
        total = _sensor(hass, "electric_heater_central_chauffe_jour")
        total._update()
        assert "Chambre" in total.extra_state_attributes["par_radiateur"]
    bad = SimpleNamespace(options={"power": "x"}, data={})
    assert stats._power(bad) == 0.0


async def test_restore_stats(hass: HomeAssistant) -> None:
    from homeassistant.util import dt as dt_util

    room_uid = "R1"
    mock_restore_cache_with_extra_data(hass, [
        (State("sensor.chambre_temps_de_chauffe_total", "5"),
         {"native_value": "abc", "native_unit_of_measurement": "h"}),
        (State("sensor.chambre_consommation_compteur_aujourd_hui", "1",
               {"jour": dt_util.now().date().isoformat(), "index_minuit": "x"}), {}),
    ])
    calls, central = await _house(hass, "16.0")
    assert hass.states.get("sensor.chambre_temps_de_chauffe_total") is not None
