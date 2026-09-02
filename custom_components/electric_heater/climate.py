"""Climate : thermostat virtuel + radiateurs fil pilote."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    CONF_CALENDAR_OFF_MODE,
    CONF_CALENDAR_ON_MODE,
    CONF_HEATING_CALENDAR,
    CONF_PRESENCE_AWAY_MODE,
    CONF_PRESENCE_SENSOR,
    CONF_TEMP_METHOD,
    CONF_TEMP_METHOD_AVERAGE,
    CONF_TEMPERATURE_SENSOR,
    DOMAIN,
    EVENT_CENTRAL_CHANGED,
    EVENT_ROOMS_CHANGED,
    HYSTERESIS,
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
    PRESETS,
    VERSION,
)
from .fil_pilote import (
    apply_fil_pilote,
    get_central_state,
    iter_room_entries,
    room_fil_pilote_id,
)

_LOGGER = logging.getLogger(__name__)

SUPPORTED_FEATURES = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)

PRESET_TO_TEMP_KEY = {
    PRESET_COMFORT: "comfort",
    PRESET_COMFORT_M1: "comfort_m1",
    PRESET_COMFORT_M2: "comfort_m2",
    PRESET_ECO: "eco",
    PRESET_FROST_PROTECTION: "frost_protection",
}

ACTIVE_CALENDAR_STATES = {"on", "active", "true", "home"}
COMFORT_PRESETS = {PRESET_COMFORT, PRESET_COMFORT_M1, PRESET_COMFORT_M2}
