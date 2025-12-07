# custom_components/electric_heater/config_flow.py
from homeassistant import config_entries
from homeassistant.helpers import selector
import voluptuous as vol

from .const import DOMAIN, CENTRAL, ROOM, DEFAULT_FROST_TEMP


class ElectricHeaterFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration – version finale propre."""

    VERSION = 5

    async def async_step_user(self, user_input=None):
        """Première étape : central ou pièce."""
        if not any(e.entry_id == "electric_heater_central" for e in self.hass.config_entries.async_entries(DOMAIN)):
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        """Configuration du thermostat central (créé une seule fois)."""
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
            # ←←← LIGNE MAGIQUE : entry_id fixe → le central se crée à coup sûr
            return self.async_create_entry(
                title="Thermostat Central",
                data=data,
                entry_id="electric_heater_central"
            )

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
                    selector.EntitySelectorConfig(domain=["input_boolean", "binary_sensor", "calendar"])
                ),
                vol.Optional("temp_confort", default=20.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=15, max=30, step=0.5, mode="box", unit_of_measurement="°C")
                ),
                vol.Optional("temp_confort_m1", default=19.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=25, step=0.5, mode="box", unit_of_measurement="°C")
                ),
                vol.Optional("temp_confort_m2", default=18.0): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=25, step=0.5, mode="box", unit_of_measurement="°C")
                ),
                vol.Optional("temp_eco", default=16.5): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=10, max=22, step=0.5, mode="box", unit_of_measurement="°C")
                ),
                vol.Optional("frost_temp", default=DEFAULT_FROST_TEMP): selector.NumberSelector(
                    selector.NumberSelectorConfig(min=7, max=10, step=0.5, mode="slider", unit_of_measurement="°C")
                ),
            }),
        )

    async def async_step_room(self, user_input=None):
        """Ajout d’une pièce."""
        if user_input is not None:
            data = {
                "type": ROOM,
                "name": user_input["name"],
                "heater_relay": user_input["heater_relay"],
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
                    selector.EntitySelectorConfig(multiple=True, domain="binary_sensor", device_class="window")
                ),
            }),
        )
