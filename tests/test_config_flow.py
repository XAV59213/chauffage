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


@pytest.fixture
def no_setup():
    from unittest.mock import AsyncMock, patch

    with patch("custom_components.electric_heater.async_setup_entry", AsyncMock(return_value=True)):
        yield


def _room_entry(hass, fil="select.chambre_pilot_wire_mode"):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chambre", unique_id=f"electric_heater_room_{fil}",
        data={"type": "room", "name": "Chambre", "fil_pilote_select": fil, "temperature_sensor": "sensor.a"},
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_central(hass: HomeAssistant, no_setup) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="T", unique_id="electric_heater_central",
                            data={"type": CENTRAL, "name": "T"})
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_central"
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(fid, {k: v for k, v in CENTRAL_INPUT.items() if k != "temperature_sensor"})
    assert result["errors"] == {"temperature_sensor": "sensor_required"}
    result = await hass.config_entries.flow.async_configure(fid, {**CENTRAL_INPUT, "name": "Maison", "notify_service": ["mobile"]})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.title == "Maison" and entry.data["comfort_temp"] == 20.2
    assert entry.data["notify_service"] == ["notify.mobile"] and entry.data["type"] == CENTRAL


async def test_reconfigure_room(hass: HomeAssistant, no_setup) -> None:
    entry = _room_entry(hass)
    _room_entry(hass, "select.salon_pilot_wire_mode")
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_room"
    fid = result["flow_id"]
    # Même relais, nouvelle sonde
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre", "fil_pilote_select": "select.chambre_pilot_wire_mode", "temperature_sensor": "sensor.b",
         "power": 1500})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["temperature_sensor"] == "sensor.b" and entry.data["power"] == 1500
    assert entry.data["type"] == "room"
    # Relais déjà utilisé par une autre pièce : refusé
    result = await entry.start_reconfigure_flow(hass)
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre", "fil_pilote_select": "select.salon_pilot_wire_mode", "temperature_sensor": "sensor.b"})
    assert result["reason"] == "already_configured"
    # Nouveau relais libre : unique_id mis à jour
    result = await entry.start_reconfigure_flow(hass)
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre 2", "fil_pilote_select": "select.neuf", "temperature_sensor": "sensor.b"})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "electric_heater_room_select.neuf" and entry.title == "Chambre 2"
