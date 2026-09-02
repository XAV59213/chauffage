"""Config flow : thermostat virtuel + radiateurs fil pilote."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CENTRAL,
    CONF_CALENDAR_OFF_MODE,
    CONF_CALENDAR_ON_MODE,
    CONF_FIL_PILOTE_SELECT,
    CONF_HEATING_CALENDAR,
    CONF_PRESENCE_AWAY_MODE,
    CONF_PRESENCE_SENSOR,
    CONF_TEMP_METHOD,
    CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMP_METHOD_REFERENCE,
    CONF_TEMPERATURE_SENSOR,
    CONF_WINDOW_SENSORS,
    DOMAIN,
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_LABELS,
    PRESET_OFF,
    PRESETS,
    ROOM,
)

_TEMP_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
)
_PRESENCE_SENSOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="sensor")
)
_CALENDAR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["calendar", "schedule"])
)
_FIL_PILOTE = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["select", "climate"])
)
_WINDOWS = selector.EntitySelector(
    selector.EntitySelectorConfig(multiple=True, domain="binary_sensor")
)
_PRESET = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[{"value": p, "label": PRESET_LABELS[p]} for p in PRESETS],
        mode="dropdown",
    )
)


def _number(min_v, max_v, step=0.1):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_v, max=max_v, step=step, mode="box", unit_of_measurement="C"
        )
    )


def _with_default(key, selector_obj, defaults, required=False):
    val = (defaults or {}).get(key)
    marker = vol.Required if required else vol.Optional
    if val:
        return {marker(key, default=val): selector_obj}
    return {marker(key): selector_obj}


def _parse_windows(value):
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [s for s in value if s]
    return [s.strip() for s in str(value).split(",") if s.strip()]


def _windows_field(defaults):
    windows = _parse_windows((defaults or {}).get(CONF_WINDOW_SENSORS))
    if windows:
        return {vol.Optional(CONF_WINDOW_SENSORS, default=windows): _WINDOWS}
    return {vol.Optional(CONF_WINDOW_SENSORS): _WINDOWS}


def _central_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    schema: dict = {
        vol.Optional(CONF_NAME, default=d.get(CONF_NAME, "Thermostat virtuel")): str,
        vol.Required(
            CONF_TEMP_METHOD,
            default=d.get(CONF_TEMP_METHOD, CONF_TEMP_METHOD_REFERENCE),
        ): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {
                        "value": CONF_TEMP_METHOD_REFERENCE,
                        "label": "Sonde que je choisis",
                    },
                    {
                        "value": CONF_TEMP_METHOD_AVERAGE,
                        "label": "Moyenne des sondes des pieces",
                    },
                ],
                mode="dropdown",
            )
        ),
    }
    schema.update(_with_default(CONF_TEMPERATURE_SENSOR, _TEMP_SENSOR, d))
    schema.update(_with_default(CONF_HEATING_CALENDAR, _CALENDAR, d))
    schema.update(
        {
            vol.Required(
                CONF_CALENDAR_ON_MODE,
                default=d.get(CONF_CALENDAR_ON_MODE, PRESET_COMFORT),
            ): _PRESET,
            vol.Required(
                CONF_CALENDAR_OFF_MODE,
                default=d.get(CONF_CALENDAR_OFF_MODE, PRESET_OFF),
            ): _PRESET,
            vol.Required(
                CONF_PRESENCE_AWAY_MODE,
                default=d.get(CONF_PRESENCE_AWAY_MODE, PRESET_ECO),
            ): _PRESET,
        }
    )
    schema.update(_with_default(CONF_PRESENCE_SENSOR, _PRESENCE_SENSOR, d))
    schema.update(_windows_field(d))
    schema.update(
        {
            vol.Required(
                "comfort_temp", default=d.get("comfort_temp", 20.0)
            ): _number(15, 30),
            vol.Required(
                "comfort_m1_temp", default=d.get("comfort_m1_temp", 19.0)
            ): _number(15, 30),
            vol.Required(
                "comfort_m2_temp", default=d.get("comfort_m2_temp", 18.0)
            ): _number(15, 30),
            vol.Required(
                "eco_temp", default=d.get("eco_temp", 16.5)
            ): _number(10, 25),
            vol.Required(
                "frost_temp", default=d.get("frost_temp", 7.0)
            ): _number(5, 10),
            vol.Required("min_temp", default=d.get("min_temp", 7.0)): _number(5, 15),
            vol.Required("max_temp", default=d.get("max_temp", 30.0)): _number(20, 35),
            vol.Required("temp_step", default=d.get("temp_step", 0.1)): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0.1, max=1.0, step=0.1, mode="box")
            ),
        }
    )
    return vol.Schema(schema)


def _room_schema(defaults: dict | None = None) -> vol.Schema:
    d = defaults or {}
    name_default = d.get(CONF_NAME)
    schema: dict = {}
    if name_default:
        schema[vol.Required(CONF_NAME, default=name_default)] = str
    else:
        schema[vol.Required(CONF_NAME)] = str
    schema.update(_with_default(CONF_FIL_PILOTE_SELECT, _FIL_PILOTE, d, required=True))
    schema.update(_with_default(CONF_TEMPERATURE_SENSOR, _TEMP_SENSOR, d, required=True))
    schema.update(_windows_field(d))
    return vol.Schema(schema)


def _normalize_windows(value) -> str:
    return ",".join(_parse_windows(value))


class ElectricHeaterConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        central_exists = any(
            e.data.get("type") == CENTRAL
            for e in self.hass.config_entries.async_entries(DOMAIN)
        )
        if not central_exists:
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            method = user_input[CONF_TEMP_METHOD]
            sensor = user_input.get(CONF_TEMPERATURE_SENSOR)
            if method == CONF_TEMP_METHOD_REFERENCE and not sensor:
                errors[CONF_TEMPERATURE_SENSOR] = "sensor_required"
            else:
                await self.async_set_unique_id("electric_heater_central")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, "Thermostat virtuel"),
                    data={
                        "type": CENTRAL,
                        CONF_NAME: user_input[CONF_NAME],
                        CONF_TEMP_METHOD: method,
                        CONF_TEMPERATURE_SENSOR: sensor,
                        CONF_HEATING_CALENDAR: user_input.get(CONF_HEATING_CALENDAR),
                        CONF_CALENDAR_ON_MODE: user_input.get(
                            CONF_CALENDAR_ON_MODE, PRESET_COMFORT
                        ),
                        CONF_CALENDAR_OFF_MODE: user_input.get(
                            CONF_CALENDAR_OFF_MODE, PRESET_OFF
                        ),
                        CONF_PRESENCE_AWAY_MODE: user_input.get(
                            CONF_PRESENCE_AWAY_MODE, PRESET_ECO
                        ),
                        CONF_PRESENCE_SENSOR: user_input.get(CONF_PRESENCE_SENSOR),
                        CONF_WINDOW_SENSORS: _normalize_windows(
                            user_input.get(CONF_WINDOW_SENSORS)
                        ),
                        "comfort_temp": user_input["comfort_temp"],
                        "comfort_m1_temp": user_input["comfort_m1_temp"],
                        "comfort_m2_temp": user_input["comfort_m2_temp"],
                        "eco_temp": user_input["eco_temp"],
                        "frost_temp": user_input["frost_temp"],
                        "min_temp": user_input["min_temp"],
                        "max_temp": user_input["max_temp"],
                        "temp_step": user_input["temp_step"],
                    },
                )

        return self.async_show_form(
            step_id="central",
            data_schema=_central_schema(),
            errors=errors,
        )

    async def async_step_room(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            fil_id = user_input[CONF_FIL_PILOTE_SELECT]
            await self.async_set_unique_id(f"electric_heater_room_{fil_id}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={
                    "type": ROOM,
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_FIL_PILOTE_SELECT: fil_id,
                    CONF_TEMPERATURE_SENSOR: user_input[CONF_TEMPERATURE_SENSOR],
                    CONF_WINDOW_SENSORS: _normalize_windows(
                        user_input.get(CONF_WINDOW_SENSORS)
                    ),
                },
            )

        return self.async_show_form(
            step_id="room",
            data_schema=_room_schema(),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ElectricHeaterOptionsFlow()


class ElectricHeaterOptionsFlow(config_entries.OptionsFlow):
    """Permet de changer sonde, calendrier, modes, fenetres et consignes."""

    async def async_step_init(self, user_input=None):
        if self.config_entry.data.get("type") == CENTRAL:
            return await self.async_step_central()
        return await self.async_step_room()

    async def async_step_central(self, user_input=None):
        errors: dict[str, str] = {}
        if user_input is not None:
            method = user_input[CONF_TEMP_METHOD]
            sensor = user_input.get(CONF_TEMPERATURE_SENSOR)
            if method == CONF_TEMP_METHOD_REFERENCE and not sensor:
                errors[CONF_TEMPERATURE_SENSOR] = "sensor_required"
            else:
                new_data = {
                    **self.config_entry.data,
                    **user_input,
                    CONF_TEMPERATURE_SENSOR: sensor,
                    CONF_HEATING_CALENDAR: user_input.get(CONF_HEATING_CALENDAR),
                    CONF_PRESENCE_SENSOR: user_input.get(CONF_PRESENCE_SENSOR),
                    CONF_WINDOW_SENSORS: _normalize_windows(
                        user_input.get(CONF_WINDOW_SENSORS)
                    ),
                }
                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    title=user_input.get(CONF_NAME, self.config_entry.title),
                )
                return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="central",
            data_schema=_central_schema(dict(self.config_entry.data)),
            errors=errors,
        )

    async def async_step_room(self, user_input=None):
        if user_input is not None:
            new_data = {
                **self.config_entry.data,
                **user_input,
                CONF_WINDOW_SENSORS: _normalize_windows(
                    user_input.get(CONF_WINDOW_SENSORS)
                ),
            }
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data,
                title=user_input.get(CONF_NAME, self.config_entry.title),
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="room",
            data_schema=_room_schema(dict(self.config_entry.data)),
        )
