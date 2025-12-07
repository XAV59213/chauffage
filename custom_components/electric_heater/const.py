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
OFFSET = {
    PRESET_COMFORT: 0.0,
    PRESET_COMFORT_M1: -1.0,
    PRESET_COMFORT_M2: -2.0,
    PRESET_ECO: -3.5,
}
FIL_PILOTE_PAYLOAD = {
    PRESET_COMFORT: {"fil_pilote": "comfort"},
    PRESET_COMFORT_M1: {"fil_pilote": "comfort_minus_1"},
    PRESET_COMFORT_M2: {"fil_pilote": "comfort_minus_2"},
    PRESET_ECO: {"fil_pilote": "eco"},
    PRESET_HORS_GEL: {"fil_pilote": "frost_protection"},
    PRESET_OFF: {"fil_pilote": "off"},
}
DEFAULT_FROST_TEMP = 7.0
DEFAULT_MQTT_BASE_TOPIC = "zigbee2mqtt"  # ← Ajoute cette ligne (topic base standard pour Z2M)
