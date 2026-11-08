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


async def _house(hass: HomeAssistant, room_temp: str, central_extra=None, room_extra=None):
    calls = []

    async def _select(call):
        # Comme un vrai module : l'option choisie devient l'état du select.
        calls.append(call)
        hass.states.async_set(SELECT, call.data["option"], {"options": OPTIONS})

    hass.services.async_register("select", "select_option", _select)
    hass.states.async_set("sensor.salon_temp", "19.0")
    hass.states.async_set("sensor.chambre_temp", room_temp)
    hass.states.async_set(SELECT, "off", {"options": OPTIONS})
    central = MockConfigEntry(domain=DOMAIN, data={**CENTRAL_DATA, **(central_extra or {})}, unique_id="electric_heater_central", title="T")
    central.add_to_hass(hass)
    room = MockConfigEntry(
        domain=DOMAIN,
        title="Chambre",
        unique_id=f"electric_heater_room_{SELECT}",
        data={"type": ROOM, "name": "Chambre", "fil_pilote_select": SELECT,
              "temperature_sensor": "sensor.chambre_temp", **(room_extra or {})},
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
    assert _last(calls) == "anti_freeze"


async def _later(hass, seconds):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_open_window_frost_then_back(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.fenetre_chambre", "off")
    calls, central = await _house(
        hass, "16.0", room_extra={"window_sensors": ["binary_sensor.fenetre_chambre"]}
    )
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert _last(calls) == "comfort"
    hass.states.async_set("binary_sensor.fenetre_chambre", "on")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls) == "anti_freeze"
    hass.states.async_set("binary_sensor.fenetre_chambre", "off")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls) == "comfort"


async def test_nobody_home_goes_eco(hass: HomeAssistant) -> None:
    """Auto + calendrier actif : maison vide -> Eco, retour -> Confort."""
    hass.states.async_set("binary_sensor.presence", "on")
    hass.states.async_set("calendar.chauffage", "on")
    calls, central = await _house(
        hass, "16.0",
        central_extra={"presence_sensor": "binary_sensor.presence", "presence_away_mode": "eco",
                       "heating_calendar": "calendar.chauffage"},
    )
    await _set(hass, central, HVACMode.AUTO)
    assert _last(calls) == "comfort"
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls) == "eco"
    hass.states.async_set("binary_sensor.presence", "on")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls) == "comfort"


async def test_manual_heat_ignores_presence(hass: HomeAssistant) -> None:
    """Mode Chauffe manuel : l'absence ne change pas l'ordre (choix de l'utilisateur)."""
    hass.states.async_set("binary_sensor.presence", "on")
    calls, central = await _house(hass, "16.0", central_extra={"presence_sensor": "binary_sensor.presence"})
    await _set(hass, central, HVACMode.HEAT, "comfort")
    hass.states.async_set("binary_sensor.presence", "off")
    await hass.async_block_till_done()
    assert _last(calls) == "comfort"


async def test_room_follows_central_preset_change(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    await _set(hass, central, HVACMode.HEAT, "frost_protection")
    assert _last(calls) == "anti_freeze"
    await _set(hass, central, HVACMode.HEAT, "comfort_-1")
    assert _last(calls) == "comfort_-1"


async def test_central_never_receives_fil_pilote(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert not any(central in str(c.data.get("entity_id")) for c in calls)


async def test_overheat_cuts_radiator(hass: HomeAssistant) -> None:
    """Pièce au-delà de la température max de sécurité : Arrêt même en Confort."""
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    assert _last(calls) == "comfort"
    hass.states.async_set("sensor.chambre_temp", "40.0")
    await hass.async_block_till_done()
    await _later(hass, 120)
    assert _last(calls) == "off"
