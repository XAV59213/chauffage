from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    DOMAIN,
    CENTRAL,
    ROOM,
    DEFAULT_FROST_TEMP,
    DEFAULT_MQTT_BASE_TOPIC,
)


class ElectricHeaterFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration pour Chauffage Électrique Fil Pilote FR."""

    VERSION = 5

    async def async_step_user(self, user_input=None):
        """Première étape : si pas de central -> central, sinon pièce."""
        if not any(e.data.get("type") == CENTRAL for e in self.hass.config_entries.async_entries(DOMAIN)):
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        """Configuration du thermostat central."""
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
        """Ajout d'une pièce / radiateur fil pilote."""
        if user_input is not None:
            relay_entity = user_input["heater_relay"]
            state = self.hass.states.get(relay_entity)

            # Friendly name du select Z2M, sinon ce qu'il y a après le point
            zigbee_id = state.attributes.get("friendly_name") if state else relay_entity.split(".")[1]

            data = {
                "type": ROOM,
                "name": user_input["name"],
                "heater_zigbee_id": zigbee_id,
                "heater_relay": relay_entity,  # sauvegarde pour compat & debug
                "temperature_sensor": user_input["temperature_sensor"],
                "window_sensors": ",".join(user_input.get("window_sensors", [])) or "",
                "mqtt_base_topic": user_input.get("mqtt_base_topic", DEFAULT_MQTT_BASE_TOPIC),
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
                vol.Optional("mqtt_base_topic", default=DEFAULT_MQTT_BASE_TOPIC): str,
            }),
            description_placeholders={"title": "Ajouter un radiateur fil pilote"}
        )
