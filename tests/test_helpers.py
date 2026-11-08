"""Fonctions utilitaires : météo, présence, sécurité, fil pilote, fenêtres."""

from homeassistant.core import HomeAssistant, State

from custom_components.electric_heater.const import (
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
)
from custom_components.electric_heater.fil_pilote import (
    is_window_open_state,
    parse_window_sensors,
    resolve_fil_pilote_option,
)
from custom_components.electric_heater.occupancy import (
    is_real_person,
    occupancy_count,
    present_names,
)
from custom_components.electric_heater.safety import (
    DEFAULT_MAX_SAFE_TEMP,
    EVENT_ALERT,
    alerts,
    clamp_target,
    max_safe_temp,
    send_alert,
    set_alert,
)
from custom_components.electric_heater.weather import (
    adjust_preset_for_weather,
    outdoor_temperature,
    weather_condition,
)


async def test_weather(hass: HomeAssistant) -> None:
    assert outdoor_temperature(hass, None) is None
    assert outdoor_temperature(hass, "weather.absent") is None
    hass.states.async_set("weather.maison", "sunny", {"temperature": "12.34"})
    assert outdoor_temperature(hass, "weather.maison") == 12.3
    assert weather_condition(hass, "weather.maison") == "sunny"
    hass.states.async_set("weather.ko", "unavailable")
    assert weather_condition(hass, "weather.ko") is None
    hass.states.async_set("weather.bad", "sunny", {"temperature": "x"})
    assert outdoor_temperature(hass, "weather.bad") is None
    assert adjust_preset_for_weather(PRESET_COMFORT, None) == PRESET_COMFORT
    assert adjust_preset_for_weather(PRESET_ECO, 30) == PRESET_ECO
    assert adjust_preset_for_weather(PRESET_COMFORT, 30) == PRESET_COMFORT_M2
    assert adjust_preset_for_weather(PRESET_COMFORT, -5) == PRESET_COMFORT


async def test_occupancy(hass: HomeAssistant) -> None:
    assert occupancy_count(hass, None) == 0
    for value, expected in (("2", 2), ("off", 0), ("on", 1), ("not_home", 0), ("unavailable", 0)):
        hass.states.async_set("sensor.occ", value)
        assert occupancy_count(hass, "sensor.occ") == expected
    assert not is_real_person(None)
    assert not is_real_person(State("person.ipad_papa", "home", {"friendly_name": "iPad Papa"}))
    assert is_real_person(State("person.xavier", "home", {"friendly_name": "Xavier"}))
    hass.states.async_set("person.xavier", "home", {"friendly_name": "Xavier"})
    hass.states.async_set("person.anais", "not_home", {"friendly_name": "Anais"})
    assert present_names(hass, None) == ["Xavier"]
    assert present_names(hass, {"persons": ["person.anais"]}) == []


async def test_safety(hass: HomeAssistant) -> None:
    assert max_safe_temp(hass) == DEFAULT_MAX_SAFE_TEMP
    assert clamp_target(hass, 99) == DEFAULT_MAX_SAFE_TEMP
    assert clamp_target(hass, None) is None
    assert set_alert(hass, "e1", "Chambre", "surchauffe", True, "40 °C")
    assert not set_alert(hass, "e1", "Chambre", "surchauffe", True, "40 °C")
    assert alerts(hass)["e1"]["surchauffe_detail"] == "40 °C"
    assert set_alert(hass, "e1", "Chambre", "surchauffe", False)
    events = []
    hass.bus.async_listen(EVENT_ALERT, events.append)
    send_alert(hass, "k", "Surchauffe Chambre", 3600, {"piece": "Chambre"})
    send_alert(hass, "k", "Surchauffe Chambre", 3600, {"piece": "Chambre"})
    await hass.async_block_till_done()
    # Événement à chaque fois, notification limitée à une par heure.
    assert len(events) == 2
    assert events[0].data["message"] == "Surchauffe Chambre"


def test_resolve_fil_pilote_option() -> None:
    zigbee = ["comfort", "eco", "anti_freeze", "off", "comfort_-1", "comfort_-2"]
    assert resolve_fil_pilote_option(PRESET_COMFORT, zigbee) == "comfort"
    assert resolve_fil_pilote_option(PRESET_FROST_PROTECTION, zigbee) == "anti_freeze"
    assert resolve_fil_pilote_option(PRESET_COMFORT_M1, zigbee) == "comfort_-1"
    assert resolve_fil_pilote_option(PRESET_COMFORT, ["Confort", "Arrêt"]) == "Confort"
    assert resolve_fil_pilote_option(PRESET_COMFORT, None) == "comfort"
    assert resolve_fil_pilote_option(PRESET_ECO, ["x", "y"]) is None


def test_windows() -> None:
    assert parse_window_sensors(None) == []
    assert parse_window_sensors({"window_sensors": ["binary_sensor.a", "binary_sensor.a", "binary_sensor.b"]}) == [
        "binary_sensor.a", "binary_sensor.b"]
    assert parse_window_sensors({"window_sensors": "binary_sensor.a, binary_sensor.b"}) == [
        "binary_sensor.a", "binary_sensor.b"]
    assert parse_window_sensors({"window_sensors": "{'window_sensors': ['binary_sensor.c']}"}) == ["binary_sensor.c"]
    assert is_window_open_state(State("binary_sensor.a", "on"))
    assert not is_window_open_state(State("binary_sensor.a", "off"))
    assert not is_window_open_state(State("binary_sensor.a", "unavailable"))
    assert is_window_open_state(State("sensor.a", "x", {"contact": False}))
    assert not is_window_open_state(None)
