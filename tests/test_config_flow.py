"""Flux de configuration."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import pytest
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater.const import CENTRAL, DOMAIN


async def test_first_flow_is_central(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "central"


async def test_central_requires_sensor_in_reference_mode(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_central(
        {"name": "T", "temp_method": "reference", "temperature_sensor": None}
    )
    assert result["errors"] == {"temperature_sensor": "sensor_required"}


async def test_room_flow_after_central(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, data={"type": CENTRAL, "name": "T"}, unique_id="electric_heater_central"
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["step_id"] == "room"


CENTRAL_INPUT = {
    "name": "Thermostat virtuel",
    "temp_method": "reference",
    "temperature_sensor": "sensor.salon_temp",
    "comfort_temp": 20.199999999999998,
    "comfort_m1_temp": 19,
    "comfort_m2_temp": 18,
    "eco_temp": 17,
    "frost_temp": 7,
    "min_temp": 7,
    "max_temp": 25,
    "temp_step": 0.1,
}


async def _flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return hass.config_entries.flow._progress[result["flow_id"]]


async def test_central_created_and_rounded(hass: HomeAssistant) -> None:
    flow = await _flow(hass)
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["type"] == CENTRAL
    assert result["data"]["comfort_temp"] == 20.2


async def test_room_created_then_duplicate_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, data={"type": CENTRAL, "name": "T"}, unique_id="electric_heater_central"
    ).add_to_hass(hass)
    room = {
        "name": "Chambre",
        "fil_pilote_select": "select.chambre_pilot_wire_mode",
        "temperature_sensor": "sensor.chambre_temp",
    }
    flow = await _flow(hass)
    result = await flow.async_step_room(dict(room))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    MockConfigEntry(
        domain=DOMAIN, data=result["data"],
        unique_id="electric_heater_room_select.chambre_pilot_wire_mode",
    ).add_to_hass(hass)
    flow = await _flow(hass)
    with pytest.raises(AbortFlow):
        await flow.async_step_room(dict(room))


async def test_options_room_updates_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chambre",
        data={"type": "room", "name": "Chambre",
              "fil_pilote_select": "select.chambre_pilot_wire_mode",
              "temperature_sensor": "sensor.a"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "room"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Chambre 2", "fil_pilote_select": "select.chambre_pilot_wire_mode",
         "temperature_sensor": "sensor.b"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["temperature_sensor"] == "sensor.b"
    assert entry.title == "Chambre 2"


async def test_options_central_sensor_required(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="T", data={"type": CENTRAL, "name": "T"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "central"
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await flow.async_step_central({"temp_method": "reference", "temperature_sensor": None})
    assert result["errors"] == {"temperature_sensor": "sensor_required"}
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["temperature_sensor"] == "sensor.salon_temp"
