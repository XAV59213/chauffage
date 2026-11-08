"""Chargement, diagnostics, réparations, appareils."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater.const import CENTRAL, DOMAIN, ROOM
from custom_components.electric_heater.diagnostics import (
    async_get_config_entry_diagnostics,
)

CENTRAL_DATA = {
    "type": CENTRAL,
    "name": "Thermostat virtuel",
    "temp_method": "reference",
    "temperature_sensor": "sensor.salon_temp",
    "notify_service": ["notify.mobile_app_secret"],
    "comfort_temp": 20.0,
    "comfort_m1_temp": 19.0,
    "comfort_m2_temp": 18.0,
    "eco_temp": 17.0,
    "frost_temp": 7.0,
    "min_temp": 7.0,
    "max_temp": 25.0,
    "temp_step": 0.1,
}


async def _setup(hass: HomeAssistant, data: dict, unique_id: str) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=data, unique_id=unique_id, title=data["name"])
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_central_setup_unload(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.salon_temp", "19.5", {"unit_of_measurement": "°C"})
    entry = await _setup(hass, CENTRAL_DATA, "electric_heater_central")
    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.async_entity_ids("climate")
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED


async def test_diagnostics_redacts_notify(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.salon_temp", "19.5")
    entry = await _setup(hass, CENTRAL_DATA, "electric_heater_central")
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["entry"]["data"]["notify_service"] == "**REDACTED**"
    assert "mobile_app_secret" not in str(diag)
    assert diag["entities"]


async def test_repair_missing_sensor(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.salon_temp", "19.5")
    await _setup(hass, CENTRAL_DATA, "electric_heater_central")
    room = {
        "type": ROOM,
        "name": "Chambre",
        "fil_pilote_select": "select.chambre_pilot_wire_mode",
        "temperature_sensor": "sensor.inexistant",
    }
    entry = await _setup(hass, room, "electric_heater_room_select.chambre_pilot_wire_mode")
    issues = ir.async_get(hass)
    assert issues.async_get_issue(DOMAIN, f"missing_temperature_sensor_{entry.entry_id}")
    assert issues.async_get_issue(DOMAIN, f"missing_fil_pilote_select_{entry.entry_id}")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not issues.async_get_issue(DOMAIN, f"missing_temperature_sensor_{entry.entry_id}")
