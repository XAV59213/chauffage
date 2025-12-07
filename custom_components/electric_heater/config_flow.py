# custom_components/electric_heater/config_flow.py
from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol
from .const import DOMAIN, CENTRAL, ROOM, DEFAULT_FROST_TEMP


# LE SEUL ET UNIQUE BON ENDROIT POUR LE HANDLER EN HA 2025
@config_entries.HANDLERS.register(DOMAIN)
async def async_migrate_entry(hass, config_entry: config_entries.ConfigEntry):
    """Migration automatique des anciennes configurations vers v5+"""
    if config_entry.version >= 5:
        return True

    new_data = dict(config_entry.data)

    defaults = {
        "temp_confort": 20.0,
        "temp_confort_m1": 19.0,
        "temp_confort_m2": 18.0,
        "temp_eco": 16.5,
        "frost_temp": DEFAULT_FROST_TEMP,
        "heating_calendar": None,
    }

    for key, default_value in defaults.items():
        new_data.setdefault(key, default_value)

    hass.config_entries.async_update_entry(
        config_entry,
        data=new_data,
        version=5
    )

    return True


class ElectricHeaterFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 5

    async def async_step_user(self, user_input=None):
        if not any(e.data.get("type") == CENTRAL for e in self.hass.config_entries.async_entries(DOMAIN)):
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        if user_input is not None:
            data = {
                "type": CENTRAL,
                "name": user_input.get("name", "Thermostat Central"),
                "temperature_sensor": user_input["temperature_sensor"],
                "master_switch": user_input["master_switch"],
                "heating_calendar": user_input.get("heating_calendar"),
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
                vol.Optional("heating_calendar"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["input_boolean", "binary_sensor", "calendar"], multiple=False)
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
            description_placeholders={"title": "Thermostat Central - Configuration principale"}
        )

    async def async_step_room(self, user_input=None):
        if user_input is not None:
            relay_entity = user_input["heater_relay"]
            state = self.hass.states.get(relay_entity)
            zigbee_id = state.attributes.get("friendly_name") if state else relay_entity.split(".")[1]

            data = {
                "type": ROOM,
                "name": user_input["name"],
                "heater_zigbee_id": zigbee_id,
                "temperature_sensor": user_input["temperature_sensor"],
                "window_sensors": ",".join(user_input.get("window_sensors", [])) or "",
            }
            return self.async_create_entry(title=user_input["name"], data=data)

        return self.async_show_form(
            step_id="room",
            data_schema=vol.Schema({
                vol.Required("name"): str,
                vol.Required("heater_relay"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="select",
                        filter=selector.EntityFilterSelectorConfig(integration="mqtt")
                    )
                ),
                vol.Required("temperature_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("window_sensors"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        multiple=True,
                        domain="binary_sensor",
                        device_class="window"
                    )
                ),
            }),
            description_placeholders={"title": "Ajouter un radiateur fil pilote"}
        )
