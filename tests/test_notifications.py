"""Notifications : démarrage, sonde KO puis rétablie, fenêtre ouverte."""

from datetime import timedelta
from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.electric_heater.const import DOMAIN, ROOM

from .test_init import CENTRAL_DATA


async def _later(hass, seconds):
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def _setup(hass: HomeAssistant):
    sent = async_mock_service(hass, "notify", "mobile_app_secret")
    hass.states.async_set("sensor.salon_temp", "19")
    hass.states.async_set("sensor.chambre_temp", "19")
    hass.states.async_set("binary_sensor.fenetre", "off")
    hass.states.async_set("select.chambre_pilot_wire_mode", "off", {"options": ["comfort", "off"]})
    MockConfigEntry(
        domain=DOMAIN, title="Chambre", unique_id="room_chambre",
        data={"type": ROOM, "name": "Chambre", "fil_pilote_select": "select.chambre_pilot_wire_mode",
              "temperature_sensor": "sensor.chambre_temp", "window_sensors": ["binary_sensor.fenetre"]},
    ).add_to_hass(hass)
    central = MockConfigEntry(domain=DOMAIN, data=CENTRAL_DATA, unique_id="electric_heater_central", title="T")
    central.add_to_hass(hass)
    with patch("custom_components.electric_heater.notifications.KO_CONFIRM", 0):
        assert await hass.config_entries.async_setup(central.entry_id)
        await hass.async_block_till_done()
        await _later(hass, 3600)  # fin de la grâce de démarrage
    return sent


def _messages(sent):
    return [c.data["message"] for c in sent]


async def test_startup_message_all_ok(hass: HomeAssistant) -> None:
    sent = await _setup(hass)
    assert any("opérationnel : tout est OK" in m for m in _messages(sent))


async def test_sensor_ko_then_back(hass: HomeAssistant) -> None:
    sent = await _setup(hass)
    with patch("custom_components.electric_heater.notifications.KO_CONFIRM", 0):
        hass.states.async_set("sensor.chambre_temp", "unavailable")
        await hass.async_block_till_done()
        assert any("Sonde de température KO – Chambre" in m for m in _messages(sent))
        count = len(sent)
        hass.states.async_set("sensor.chambre_temp", "unknown")
        await hass.async_block_till_done()
        assert len(sent) == count  # une seule notification par problème
        hass.states.async_set("sensor.chambre_temp", "19.5")
        await hass.async_block_till_done()
        assert any("Sonde de température OK – Chambre" in m for m in _messages(sent))


async def test_window_open_notified_after_delay(hass: HomeAssistant) -> None:
    sent = await _setup(hass)
    hass.states.async_set("binary_sensor.fenetre", "on")
    await hass.async_block_till_done()
    assert not any("Fenêtre ouverte" in m for m in _messages(sent))
    await _later(hass, 3600)
    assert any("Fenêtre ouverte" in m for m in _messages(sent))
