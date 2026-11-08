"""Flux de configuration."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
