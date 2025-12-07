from homeassistant import config_entries
import voluptuous as vol
from .const import DOMAIN, CENTRAL, ROOM, PRESETS, DEFAULT_FROST_TEMP

class ElectricHeaterFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if not any(e.data.get("type") == CENTRAL for e in self.hass.config_entries.async_entries(DOMAIN)):
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Thermostat Central", data=user_input)

        return self.async_show_form(
            step_id="central",
            data_schema=vol.Schema({
                vol.Required("name", default="Thermostat Central"): str,
                vol.Required("temperature_sensor"): str,
                vol.Required("master_switch"): str,
                vol.Optional("frost_temp", default=DEFAULT_FROST_TEMP): vol.In([7.0, 7.5, 8.0, 8.5, 9.0, 9.5, 10.0]),
            }),
        )

    async def async_step_room(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("heater_zigbee_id"): str,
                vol.Required("temperature_sensor"): str,
                vol.Optional("window_sensors", default=""): str,
            }),
        )
