import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import selector
from .const import (
    DOMAIN, CENTRAL, ROOM, CONF_TEMP_METHOD, CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMP_METHOD_REFERENCE, CONF_PRESENCE_SENSOR
)

class ElectricHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        central_exists = any(e.data.get("type") == CENTRAL for e in self.hass.config_entries.async_entries(DOMAIN))
        if not central_exists:
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(CONF_NAME, "Chauffage Central"),
                data={
                    "type": CENTRAL,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_TEMP_METHOD: user_input[CONF_TEMP_METHOD],
                    "temperature_sensor": user_input.get("temperature_sensor"),
                    CONF_PRESENCE_SENSOR: user_input.get(CONF_PRESENCE_SENSOR),
                    "comfort_temp": user_input["comfort_temp"],
                    "comfort_m1_temp": user_input["comfort_m1_temp"],
                    "comfort_m2_temp": user_input["comfort_m2_temp"],
                    "eco_temp": user_input["eco_temp"],
                    "frost_temp": user_input["frost_temp"],
                    "min_temp": user_input["min_temp"],
                    "max_temp": user_input["max_temp"],
                    "temp_step": user_input["temp_step"],
                }
            )

        return self.async_show_form(
            step_id="central",
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default="Chauffage Central"): str,
                vol.Required(CONF_TEMP_METHOD, default=CONF_TEMP_METHOD_AVERAGE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=[
                        {"value": CONF_TEMP_METHOD_AVERAGE, "label": "Moyenne des pièces"},
                        {"value": CONF_TEMP_METHOD_REFERENCE, "label": "Pièce de référence"}
                    ], mode="dropdown")
                ),
                vol.Optional("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_PRESENCE_SENSOR): selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor")),
                vol.Required("comfort_temp", default=20.0): selector.NumberSelector(selector.NumberSelectorConfig(min=15, max=30, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("comfort_m1_temp", default=19.0): selector.NumberSelector(selector.NumberSelectorConfig(min=15, max=30, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("comfort_m2_temp", default=18.0): selector.NumberSelector(selector.NumberSelectorConfig(min=15, max=30, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("eco_temp", default=16.5): selector.NumberSelector(selector.NumberSelectorConfig(min=10, max=25, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("frost_temp", default=7.0): selector.NumberSelector(selector.NumberSelectorConfig(min=5, max=10, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("min_temp", default=7.0): selector.NumberSelector(selector.NumberSelectorConfig(min=5, max=15, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("max_temp", default=30.0): selector.NumberSelector(selector.NumberSelectorConfig(min=20, max=35, step=0.1, mode="box", unit_of_measurement="°C")),
                vol.Required("temp_step", default=0.1): selector.NumberSelector(selector.NumberSelectorConfig(min=0.1, max=1.0, step=0.1, mode="box")),
            }),
            errors=errors,
        )

    async def async_step_room(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    "type": ROOM,
                    CONF_NAME: user_input[CONF_NAME],
                    "fil_pilote_select": user_input["fil_pilote_select"],
                    "temperature_sensor": user_input["temperature_sensor"],
                    "window_sensors": ",".join(user_input.get("window_sensors", [])),
                }
            )

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME): str,
                vol.Required("fil_pilote_select"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select", integration="mqtt")
                ),
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("window_sensors"): selector.EntitySelector(
                    selector.EntitySelectorConfig(multiple=True, domain="binary_sensor", device_class="window")
                ),
            })
        )
