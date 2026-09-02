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

FIL_PILOTE_ALIASES = {
    PRESET_COMFORT: ["comfort", "confort", "Comfort"],
    PRESET_COMFORT_M1: [
        "comfort_-1",
        "comfort-1",
        "confort_-1",
        "confort-1",
        "Comfort -1",
        "comfort_1",
    ],
    PRESET_COMFORT_M2: [
        "comfort_-2",
        "comfort-2",
        "confort_-2",
        "confort-2",
        "Comfort -2",
        "comfort_2",
    ],
    PRESET_ECO: ["eco", "Eco", "Eco", "economique"],
    PRESET_FROST_PROTECTION: [
        "frost_protection",
        "frost-protection",
        "anti-freeze",
        "antifreeze",
        "hors_gel",
        "hors-gel",
        "horsgel",
    ],
    PRESET_OFF: ["off", "stop", "arret", "Off", "Stop"],
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
CONF_TEMPERATURE_SENSOR = "temperature_sensor"
CONF_FIL_PILOTE_SELECT = "fil_pilote_select"
CONF_WINDOW_SENSORS = "window_sensors"

EVENT_CENTRAL_CHANGED = f"{DOMAIN}_central_changed"
EVENT_ROOMS_CHANGED = f"{DOMAIN}_rooms_changed"

VERSION = "1.4.1"
