"""Central (calendrier, saison, fenêtres, restauration) et pièce (manuel, relais, sécurité)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.climate import DATA_COMPONENT, HVACMode
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import mock_restore_cache

from custom_components.electric_heater import climate as climate_mod
from custom_components.electric_heater.safety import alerts

from .test_climate import SELECT, OPTIONS, _house, _last, _later, _set

ROOM_ID = "climate.chambre"


@pytest.fixture(autouse=True)
def no_grace():
    with patch(
        "custom_components.electric_heater.climate.RoomThermostat._in_startup_grace",
        return_value=False,
    ):
        yield


def _ent(hass, eid):
    return hass.data[DATA_COMPONENT].get_entity(eid)


def _room_id(hass, central):
    return next(e for e in hass.states.async_entity_ids("climate") if e != central)


async def _svc(hass, service, eid, **data):
    await hass.services.async_call("climate", service, {"entity_id": eid, **data}, blocking=True)
    await hass.async_block_till_done()


async def test_calendar_inactive_eco_then_active(hass: HomeAssistant) -> None:
    hass.states.async_set("calendar.chauffage", "off")
    calls, central = await _house(hass, "16.0", central_extra={"heating_calendar": "calendar.chauffage"})
    await _set(hass, central, HVACMode.AUTO)
    assert hass.states.get(central).attributes["preset_mode"] == "eco"
    assert _last(calls) == "eco"
    hass.states.async_set("calendar.chauffage", "on")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls) == "comfort"
    # Choix manuel en Auto : maintenu jusqu'au prochain changement du calendrier
    await _svc(hass, "set_preset_mode", central, preset_mode="comfort_-1")
    assert _ent(hass, central)._manual_hold
    hass.states.async_set("calendar.chauffage", "unavailable")
    await hass.async_block_till_done()
    hass.states.async_set("calendar.chauffage", "off")
    await hass.async_block_till_done()
    assert not _ent(hass, central)._manual_hold
    assert hass.states.get(central).attributes["preset_mode"] == "eco"
    # Calendrier changé hors Auto : mémorisé seulement
    await _set(hass, central, HVACMode.HEAT)
    hass.states.async_set("calendar.chauffage", "on")
    await hass.async_block_till_done()
    assert _ent(hass, central)._calendar_active is True


async def test_central_services(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    # Consigne au-delà de la limite de sécurité (23 °C) : bornée
    await _ent(hass, central).async_set_temperature(temperature=30)
    await hass.async_block_till_done()
    assert hass.states.get(central).attributes["temperature"] == 23.0
    await _svc(hass, "set_preset_mode", central, preset_mode="eco")
    await _svc(hass, "set_temperature", central, temperature=16.5)
    assert hass.states.get(central).attributes["temperature"] == 16.5
    await _svc(hass, "turn_off", central)
    assert hass.states.get(central).state == "off"
    assert _ent(hass, central)._user_off
    assert _last(calls) == "off"
    # Preset choisi depuis l'arrêt → chauffe
    await _svc(hass, "set_preset_mode", central, preset_mode="comfort")
    assert hass.states.get(central).state == "heat"
    await _svc(hass, "set_preset_mode", central, preset_mode="off")
    assert hass.states.get(central).state == "off"
    await _svc(hass, "turn_on", central)
    assert hass.states.get(central).state == "auto"
    assert not _ent(hass, central)._user_off


async def test_season_off_and_back(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.AUTO)
    ent = _ent(hass, central)
    out = {"in_season": False, "raison": "hors_periode"}
    with patch.object(climate_mod.season_mod.SeasonController, "evaluate", return_value=out):
        ent._season_tick()
        await hass.async_block_till_done()
        assert hass.states.get(central).state == "off"
        assert ent._hors_saison
        ent._season_tick()  # déjà aligné : rien
    with patch.object(climate_mod.season_mod.SeasonController, "evaluate",
                      return_value={"in_season": True, "raison": "en_saison"}):
        ent._season_tick()
        await hass.async_block_till_done()
    assert hass.states.get(central).state == "auto"
    # Off manuel conservé au retour de saison
    await _set(hass, central, HVACMode.OFF)
    with patch.object(climate_mod.season_mod.SeasonController, "evaluate", return_value=out):
        ent._season_tick()
    with patch.object(climate_mod.season_mod.SeasonController, "evaluate",
                      return_value={"in_season": True}):
        ent._season_tick()
        assert hass.states.get(central).state == "off"
        # Remise en marche manuelle hors saison recalculée
        ent._hors_saison = True
        await _set(hass, central, HVACMode.HEAT)
        assert not ent._hors_saison


async def test_central_window(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.porte", "off")
    calls, central = await _house(hass, "16.0", central_extra={"window_sensors": ["binary_sensor.porte"]})
    await _set(hass, central, HVACMode.AUTO)
    hass.states.async_set("binary_sensor.porte", "on")
    await hass.async_block_till_done()
    await _later(hass, 900)
    ent = _ent(hass, central)
    assert ent._window_open
    await _svc(hass, "set_temperature", central, temperature=21)  # ignoré fenêtre ouverte
    hass.states.async_set("binary_sensor.porte", "off")
    await hass.async_block_till_done()
    await _later(hass, 60)
    assert not ent._window_open
    await _set(hass, central, HVACMode.HEAT)
    hass.states.async_set("binary_sensor.porte", "on")
    await hass.async_block_till_done()
    await _later(hass, 900)
    hass.states.async_set("binary_sensor.porte", "off")
    await hass.async_block_till_done()
    await _later(hass, 60)
    assert not ent._window_open


async def test_average_temperature(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "17.0", central_extra={"temp_method": "average"})
    hass.states.async_set("sensor.salon_temp", "21.0")
    await hass.async_block_till_done()
    assert hass.states.get(central).attributes["current_temperature"] == 19.0
    hass.states.async_set("sensor.salon_temp", "bad")
    await hass.async_block_till_done()
    assert hass.states.get(central).attributes["current_temperature"] == 17.0


async def test_restore_central(hass: HomeAssistant) -> None:
    mock_restore_cache(hass, [State("climate.electric_heater_central", "off",
                                    {"preset_mode": "off", "manual_hold": True, "calendar_active": True})])
    calls, central = await _house(hass, "16.0")
    st = hass.states.get(central)
    assert st.state == "off"
    assert _ent(hass, central)._user_off


async def test_room_manual_then_auto(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    room = _room_id(hass, central)
    await _svc(hass, "set_preset_mode", room, preset_mode="eco")
    assert _last(calls) == "eco"
    await _ent(hass, room).async_set_temperature(temperature=40)
    await hass.async_block_till_done()
    assert hass.states.get(room).attributes["temperature"] == 23.0
    await _svc(hass, "turn_off", room)
    assert _last(calls) == "off"
    await _svc(hass, "set_hvac_mode", room, hvac_mode="heat")
    assert _last(calls) == "comfort"
    await _svc(hass, "turn_on", room)  # Auto : suit de nouveau le central
    assert _ent(hass, room)._follow_central
    for eid in (room, central):
        with pytest.raises(ServiceValidationError) as err:
            await _ent(hass, eid).async_set_preset_mode("nope")
        assert err.value.translation_key == "invalid_preset"


async def test_relay_changed_externally(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.HEAT, "comfort")
    room = _ent(hass, _room_id(hass, central))
    room._sending_until = 0
    n = len(calls)
    hass.states.async_set(SELECT, "eco", {"options": OPTIONS})
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert len(calls) > n and _last(calls) == "comfort"
    # Relais indisponible puis de retour : ordre renvoyé
    hass.states.async_set(SELECT, "unavailable", {"options": OPTIONS})
    await hass.async_block_till_done()
    await room._apply_fil_pilote()
    n = len(calls)
    hass.states.async_set(SELECT, "comfort", {"options": OPTIONS})
    await hass.async_block_till_done()
    assert len(calls) > n


async def test_unstable_window_detector(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.fen", "off")
    calls, central = await _house(hass, "16.0", room_extra={"window_sensors": ["binary_sensor.fen"]})
    await _set(hass, central, HVACMode.HEAT, "comfort")
    room = _ent(hass, _room_id(hass, central))
    for _ in range(5):
        hass.states.async_set("binary_sensor.fen", "unavailable")
        await hass.async_block_till_done()
        hass.states.async_set("binary_sensor.fen", "off")
        await hass.async_block_till_done()
    assert room._unstable
    assert alerts(hass)[room.entry.entry_id]["instable"]
    room._unavail_times = []
    room._safety_tick()
    assert not room._unstable


async def test_disobeying_radiator(hass: HomeAssistant) -> None:
    calls, central = await _house(hass, "16.0")
    await _set(hass, central, HVACMode.OFF)
    room = _ent(hass, _room_id(hass, central))
    room._sending_until = 0
    clock = [10000.0]
    with patch.object(climate_mod, "read_power", return_value=800.0), \
         patch.object(climate_mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
        room._check_obeying()
        assert room._not_obeying
        room._safety_tick()
        clock[0] += 200
        room._safety_tick()
        await hass.async_block_till_done()
        assert room._safety_off
        clock[0] += 200
        room._safety_tick()  # toujours désobéissant : ordre renvoyé
        await hass.async_block_till_done()
    with patch.object(climate_mod, "read_power", return_value=0.0):
        room._safety_tick()
        await hass.async_block_till_done()
    assert not room._safety_off
