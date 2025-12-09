DOMAIN = "electric_heater"

CENTRAL = "central"
ROOM = "room"

PRESET_COMFORT = "comfort"
PRESET_COMFORT_M1 = "comfort_-1"
PRESET_COMFORT_M2 = "comfort_-2"
PRESET_ECO = "eco"
PRESET_FROST_PROTECTION = "frost_protection"
PRESET_OFF = "off"

PRESETS = [
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
]

FIL_PILOTE_PAYLOAD = {
    PRESET_COMFORT: {"fil_pilote": "comfort"},
    PRESET_COMFORT_M1: {"fil_pilote": "comfort_-1"},
    PRESET_COMFORT_M2: {"fil_pilote": "comfort_-2"},
    PRESET_ECO: {"fil_pilote": "eco"},
    PRESET_FROST_PROTECTION: {"fil_pilote": "frost_protection"},
    PRESET_OFF: {"fil_pilote": "off"},
}

HYSTERESIS = {
    PRESET_COMFORT: 0.3,
    PRESET_COMFORT_M1: 0.3,
    PRESET_COMFORT_M2: 0.3,
    PRESET_ECO: 0.4,
    PRESET_FROST_PROTECTION: 0.5,
}

CONF_TEMP_METHOD = "temp_method"
CONF_TEMP_METHOD_AVERAGE = "average"
CONF_TEMP_METHOD_REFERENCE = "reference"
CONF_PRESENCE_SENSOR = "presence_sensor"
