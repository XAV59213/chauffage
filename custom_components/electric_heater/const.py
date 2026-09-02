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

PRESET_LABELS = {
    PRESET_COMFORT: "Confort",
    PRESET_COMFORT_M1: "Confort -1 C",
    PRESET_COMFORT_M2: "Confort -2 C",
    PRESET_ECO: "Eco",
    PRESET_FROST_PROTECTION: "Hors-gel",
    PRESET_OFF: "Arret",
}

FIL_PILOTE_PAYLOAD = {
    PRESET_COMFORT: {"fil_pilote": "comfort"},
    PRESET_COMFORT_M1: {"fil_pilote": "comfort_-1"},
    PRESET_COMFORT_M2: {"fil_pilote": "comfort_-2"},
    PRESET_ECO: {"fil_pilote": "eco"},
    PRESET_FROST_PROTECTION: {"fil_pilote": "frost_protection"},
    PRESET_OFF: {"fil_pilote": "off"},
}

FIL_PILOTE_ALIASES = {
    PRESET_COMFORT: ["comfort", "confort", "Comfort", "Confort"],
    PRESET_COMFORT_M1: [
        "comfort_-1",
        "comfort-1",
        "confort_-1",
        "confort-1",
        "Comfort -1",
        "Confort -1",
        "comfort_1",
    ],
    PRESET_COMFORT_M2: [
        "comfort_-2",
        "comfort-2",
        "confort_-2",
        "confort-2",
        "Comfort -2",
        "Confort -2",
        "comfort_2",
    ],
    PRESET_ECO: ["eco", "Eco", "economique", "éco", "Eco mode"],
    PRESET_FROST_PROTECTION: [
        "frost_protection",
        "frost-protection",
        "frost",
        "anti-freeze",
        "antifreeze",
        "hors_gel",
        "hors-gel",
        "horsgel",
        "holiday",
    ],
    PRESET_OFF: [
        "off",
        "Off",
        "OFF",
        "stop",
        "Stop",
        "arret",
        "arrêt",
        "Arret",
        "Arrêt",
        "pilot_wire_off",
    ],
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
CONF_WINDOW_INVERT = "window_invert"
CONF_HEATING_CALENDAR = "heating_calendar"
CONF_CALENDAR_ON_MODE = "calendar_on_mode"
CONF_CALENDAR_OFF_MODE = "calendar_off_mode"
CONF_PRESENCE_AWAY_MODE = "presence_away_mode"

FIL_PILOTE_DATA_KEYS = (
    CONF_FIL_PILOTE_SELECT,
    "fil_pilote",
    "mqtt_device",
    "heater",
    "relay",
)

EVENT_CENTRAL_CHANGED = f"{DOMAIN}_central_changed"
EVENT_ROOMS_CHANGED = f"{DOMAIN}_rooms_changed"
EVENT_WINDOWS_CHANGED = f"{DOMAIN}_windows_changed"

VERSION = "1.1.10"
