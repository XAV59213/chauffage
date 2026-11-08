"""Silver : entités indisponibles avec leur source, journalisation unique."""

import logging
from unittest.mock import patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant

from .test_climate import _house, _last, _set


@pytest.fixture(autouse=True)
def no_grace():
    with patch(
        "custom_components.electric_heater.climate.RoomThermostat._in_startup_grace",
        return_value=False,
    ):
        yield


async def test_room_temperature_follows_source(hass: HomeAssistant, caplog) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    temp = "sensor.chambre_temperature_piece"
    room = next(e for e in hass.states.async_entity_ids("climate") if e != central)
    assert hass.states.get(temp).state == "16.0"
    caplog.set_level(logging.INFO, logger="custom_components.electric_heater")
    caplog.clear()
    hass.states.async_set("sensor.chambre_temp", "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set("sensor.chambre_temp", "unknown")
    await hass.async_block_till_done()
    assert hass.states.get(temp).state == "unavailable"
    assert sum("Source sensor.chambre_temp indisponible" in r.message for r in caplog.records) == 1
    # Le radiateur reste disponible pour appliquer la sécurité Hors-gel
    assert hass.states.get(room).state != "unavailable"
    assert hass.states.get(room).attributes["sonde_ko"] is True
    assert _last(calls) == "anti_freeze"
    hass.states.async_set("sensor.chambre_temp", "18.0")
    await hass.async_block_till_done()
    assert hass.states.get(temp).state == "18.0"
    assert sum("Source sensor.chambre_temp de nouveau disponible" in r.message for r in caplog.records) == 1


async def test_central_temperature_follows_central(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    temp = "sensor.thermostat_virtuel_temperature_centrale"
    assert hass.states.get(temp).state == "19.0"
    hass.states.async_set("sensor.salon_temp", "unavailable")
    await hass.async_block_till_done()
    assert hass.states.get(temp).state == "unavailable"
    hass.states.async_set("sensor.salon_temp", "20.0")
    await hass.async_block_till_done()
    assert hass.states.get(temp).state == "20.0"
