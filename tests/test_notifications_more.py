"""Notifications : piles des détecteurs, résumé de démarrage, maison vide + fenêtre."""

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.electric_heater.const import DOMAIN, ROOM

from .test_init import CENTRAL_DATA
from .test_notifications import _later, _messages


@pytest.fixture(autouse=True)
def instant_ko():
    with patch("custom_components.electric_heater.notifications.KO_CONFIRM", 0):
        yield


async def _setup(hass, central_extra=None, temp="19", window="off"):
    sent = async_mock_service(hass, "notify", "mobile_app_secret")
    other = MockConfigEntry(domain="zha")
    other.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(config_entry_id=other.entry_id, identifiers={("zha", "win")})
    reg = er.async_get(hass)
    reg.async_get_or_create("binary_sensor", "zha", "w", device_id=dev.id, suggested_object_id="fenetre")
    reg.async_get_or_create("sensor", "zha", "b", device_id=dev.id, suggested_object_id="fenetre_battery")
    reg.async_get_or_create("binary_sensor", "zha", "bl", device_id=dev.id, suggested_object_id="fenetre_battery_low")
    hass.states.async_set("sensor.fenetre_battery", "80", {"device_class": "battery"})
    hass.states.async_set("binary_sensor.fenetre_battery_low", "off", {"device_class": "battery"})
    hass.states.async_set("sensor.salon_temp", "19")
    hass.states.async_set("sensor.chambre_temp", temp)
    hass.states.async_set("binary_sensor.fenetre", window, {"friendly_name": "Fenêtre chambre"})
    hass.states.async_set("select.chambre_pilot_wire_mode", "off", {"options": ["comfort", "off"]})
    MockConfigEntry(
        domain=DOMAIN, title="Chambre", unique_id="room_chambre",
        data={"type": ROOM, "name": "Chambre", "fil_pilote_select": "select.chambre_pilot_wire_mode",
              "temperature_sensor": "sensor.chambre_temp", "window_sensors": ["binary_sensor.fenetre"]},
    ).add_to_hass(hass)
    central = MockConfigEntry(domain=DOMAIN, data={**CENTRAL_DATA, **(central_extra or {})},
                              unique_id="electric_heater_central", title="T")
    central.add_to_hass(hass)
    assert await hass.config_entries.async_setup(central.entry_id)
    await hass.async_block_till_done()
    await _later(hass, 3600)
    return sent


async def test_window_batteries(hass: HomeAssistant) -> None:
    sent = await _setup(hass)
    hass.states.async_set("sensor.fenetre_battery", "5", {"device_class": "battery"})
    await hass.async_block_till_done()
    assert any("Pile faible" in m and "(5 %)" in m for m in _messages(sent))
    hass.states.async_set("sensor.fenetre_battery", "90", {"device_class": "battery"})
    await hass.async_block_till_done()
    assert any("Pile du détecteur" in m and "OK" in m for m in _messages(sent))
    hass.states.async_set("binary_sensor.fenetre_battery_low", "on", {"device_class": "battery"})
    await hass.async_block_till_done()
    assert sum("Pile faible" in m for m in _messages(sent)) == 2
    hass.states.async_set("sensor.fenetre_battery", "abc", {"device_class": "battery"})
    await hass.async_block_till_done()


async def test_startup_lists_problems(hass: HomeAssistant) -> None:
    sent = await _setup(hass, temp="unavailable", window="on")
    msg = next(m for m in _messages(sent) if "opérationnel" in m)
    assert "sonde(s) KO : Chambre" in msg and "Fenêtre chambre" in msg


async def test_nobody_home_window_open(hass: HomeAssistant) -> None:
    hass.states.async_set("person.xavier", "not_home")
    sent = await _setup(hass, central_extra={"presence_sensor": "person.xavier"}, window="on")
    await _later(hass, 7200)
    assert any("Personne à la maison" in m for m in _messages(sent))
    hass.states.async_set("binary_sensor.fenetre", "off")
    await hass.async_block_till_done()
    await _later(hass, 7300)
    assert any("Fenêtres fermées" in m for m in _messages(sent))


async def test_notifications_disabled_and_bad_delay(hass: HomeAssistant) -> None:
    sent = await _setup(hass, central_extra={"notifications": False, "window_off_delay": "x"})
    assert not any("opérationnel" in m for m in _messages(sent))
