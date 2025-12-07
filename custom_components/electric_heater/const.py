DOMAIN = "electric_heater"
CENTRAL = "central"
ROOM = "room"

PRESET_COMFORT = "confort"
PRESET_COMFORT_M1 = "confort_-1"
PRESET_COMFORT_M2 = "confort_-2"
PRESET_ECO = "eco"
PRESET_HORS_GEL = "hors_gel"
PRESET_OFF = "off"

PRESETS = [
    PRESET_COMFORT,
    PRESET_COMFORT_M1,
    PRESET_COMFORT_M2,
    PRESET_ECO,
    PRESET_HORS_GEL,
    PRESET_OFF,
]

# OPTIONS EXACTES DE ZIGBEE2MQTT 2025 (underscores, pas de tirets !)
FIL_PILOTE_PAYLOAD = {
    PRESET_COMFORT:    {"fil_pilote": "comfort"},
    PRESET_COMFORT_M1: {"fil_pilote": "comfort_-1"},
    PRESET_COMFORT_M2: {"fil_pilote": "comfort_-2"},
    PRESET_ECO:        {"fil_pilote": "eco"},
    PRESET_HORS_GEL:   {"fil_pilote": "frost_protection"},
    PRESET_OFF:        {"fil_pilote": "off"},
}

DEFAULT_FROST_TEMP = 7.0
