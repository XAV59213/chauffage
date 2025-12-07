# custom_components/electric_heater/config_flow.py
from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol
from .const import DOMAIN, CENTRAL, ROOM, DEFAULT_FROST_TEMP

class ElectricHeaterFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 2

    async def async_step_user(self, user_input=None):
        if not any(e.data.get("type") == CENTRAL for e in self.hass.config_entries.async_entries(DOMAIN)):
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        if user_input is not None:
            # Valeurs par défaut si non définies
            data = {
                "type": CENTRAL,
                "name": user_input.get("name", "Thermostat Central"),
                "temperature_sensor": user_input["temperature_sensor"],
                "master_switch": user_input["master_switch"],
                # Températures par défaut (peuvent être modifiées dans les options après)
                "temp_confort": user_input.get("temp_confort", 20.0),
                "temp_confort_m1": user_input.get("temp_confort_m1", 19.0),
                "temp_confort_m2": user_input.get("temp_confort_m2", 18.0),
                "temp_eco": user_input.get("temp_eco", 16.5),
                "frost_temp": user_input.get("frost_temp", DEFAULT_FROST_TEMP),
            }
            return self.async_create_entry(title="Thermostat Central", data=data)

        return self.async_show_form(
            step_id="central",
            data_schema=vol.Schema({
                vol.Required("name", default="Thermostat Central"): str,
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Required("master_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
                ),
                vol.Optional("temp_confort", default=20.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=15.0, max=30.0, step=0.5, unit_of_measurement="°C", mode="box")
                ),
                vol.Optional("temp_confort_m1", default=19.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=25.0, step=0.5, unit_of_measurement="°C", mode="box")
                ),
                vol.Optional("temp_confort_m2", default=18.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=25.0, step=0.5, unit_of_measurement="°C", mode="box")
                ),
                vol.Optional("temp_eco", default=16.5): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10.0, max=22.0, step=0.5, unit_of_measurement="°C", mode="box")
                ),
                vol.Optional("frost_temp", default=DEFAULT_FROST_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=7.0, max=10.0, step=0.5, unit_of_measurement="°C", mode="slider")
                ),
            }),
            description_placeholders={"title": "Configuration du thermostat principal"}
        )

    async def async_step_room(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=user_input["name"], data=user_input)

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("heater_zigbee_id"): str,
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("window_sensors"): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="binary_sensor", device_class="window")
                ),
            }),
            description_placeholders={"title": "Ajouter un radiateur fil pilote"}
        )
