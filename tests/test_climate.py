"""Central + pièce : ordres fil pilote réellement envoyés."""

from unittest.mock import patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater.const import CENTRAL, DOMAIN, ROOM

from .test_init import CENTRAL_DATA

SELECT = "select.chambre_pilot_wire_mode"
OPTIONS = ["comfort", "eco", "anti_freeze", "off", "comfort_-1", "comfort_-2"]


@pytest.fixture(autouse=True)
def no_grace():
    with patch(
        "custom_components.electric_heater.climate.RoomThermostat._in_startup_grace",
        return_value=False,
    ):
        yield


async def _house(hass: HomeAssistant, room_temp: str):
    calls = []

    async def _select(call):
        # Comme un vrai module : l'option choisie devient l'état du select.
        calls.append(call)
        hass.states.async_set(SELECT, call.data["option"], {"options": OPTIONS})

    hass.services.async_register("select", "select_option", _select)
    hass.states.async_set("sensor.salon_temp", "19.0")
    hass.states.async_set("sensor.chambre_temp", room_temp)
    hass.states.async_set(SELECT, "off", {"options": OPTIONS})
    central = MockConfigEntry(domain=DOMAIN, data=CENTRAL_DATA, unique_id="electric_heater_central", title="T")
    central.add_to_hass(hass)
    room = MockConfigEntry(
        domain=DOMAIN,
        title="Chambre",
        unique_id=f"electric_heater_room_{SELECT}",
        data={"type": ROOM, "name": "Chambre", "fil_pilote_select": SELECT,
              "temperature_sensor": "sensor.chambre_temp"},
    )
    room.add_to_hass(hass)
    assert await hass.config_entries.async_setup(central.entry_id)
    await hass.async_block_till_done()
    central_id = next(e for e in hass.states.async_entity_ids("climate") if "central" in e)
    return calls, central_id


async def _set(hass, central_id, mode, preset=None):
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": central_id, "hvac_mode": mode}, blocking=True)
    if preset:
        await hass.services.async_call("climate", "set_preset_mode", {"entity_id": central_id, "preset_mode": preset}, blocking=True)
    await hass.async_block_till_done()


def _last(calls):
    return calls[-1].data["option"] if calls else None


async def test_cold_room_heats_in_comfort(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert _last(calls) == "comfort"
    assert all(c.data["entity_id"] in (SELECT, [SELECT]) for c in calls)


async def test_warm_room_stops(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "23.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert _last(calls) in (None, "off")


async def test_central_off_turns_radiator_off(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    await _set(hass, central, HVACMode.OFF)
    assert _last(calls) == "off"
    assert hass.states.get(central).state == HVACMode.OFF


async def test_eco_preset_sends_eco(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "eco")
    assert _last(calls) == "eco"


async def test_sensor_ko_never_comfort(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "unavailable")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert _last(calls) != "comfort"
