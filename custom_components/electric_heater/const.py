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
    PRESET_ECO: 0.5,
    PRESET_FROST_PROTECTION: 1.0,
}

SENSOR_KO_MESSAGE = "Sonde de température indisponible : remplacer la pile de la sonde (radiateur en Hors-gel par sécurité)"

WINDOW_OFF_DELAY = 45
# Relais : délai avant de corriger un état différent de l'ordre attendu (s)
RELAY_CHECK_DELAY = 15
# Relais : renvoi périodique de l'ordre attendu (min)
RESYNC_INTERVAL_MIN = 10
WEATHER_MILD = 15.0
WEATHER_WARM = 18.0

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
CONF_WEATHER = "weather"
CONF_WINDOW_MODE = "window_mode"

# Modes proposés quand une fenêtre est ouverte
WINDOW_MODES = [PRESET_FROST_PROTECTION, PRESET_ECO, PRESET_OFF]
DEFAULT_WINDOW_MODE = PRESET_FROST_PROTECTION
# Ordre envoyé quand la pièce dépasse la consigne
CONF_ABOVE_TARGET_MODE = "above_target_mode"
ABOVE_TARGET_MODES = [PRESET_ECO, PRESET_FROST_PROTECTION, PRESET_OFF]
DEFAULT_ABOVE_TARGET_MODE = PRESET_ECO
# Réglages avancés (défauts = valeurs historiques)
CONF_HYSTERESIS = "hysteresis"
CONF_WINDOW_OFF_DELAY = "window_off_delay"
CONF_RESYNC_INTERVAL = "resync_interval"
# Notifications (pile / sonde KO, fenêtre ouverte)
CONF_NOTIFICATIONS = "notifications"
# Personnes suivies pour « Présents » (vide = détection automatique)
CONF_PERSONS = "persons"
# Entités person qui sont en fait des appareils / la maison (exclues automatiquement)
NOT_PERSON_HINTS = (
    "tablette", "tablet", "ipad", "iphone", "android", "telephone", "téléphone", "phone",
    "mqtt", "mqtta", "maison", "home", "tv", "television", "télévision", "pc", "ordinateur",
    "macbook", "laptop", "chromecast", "alexa", "echo", "box", "freebox", "serveur",
    "server", "voiture", "car", "koleos",
)
CONF_NOTIFY_SERVICE = "notify_service"
DEFAULT_CALENDAR_OFF_MODE = PRESET_FROST_PROTECTION

# Consignes : leur modification ne recharge pas l'intégration
SETPOINT_KEYS = (
    "comfort_temp",
    "comfort_m1_temp",
    "comfort_m2_temp",
    "eco_temp",
    "frost_temp",
)

CENTRAL_ENTITY_ID = "climate.electric_heater_central"

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
# Commande manuelle sur le thermostat virtuel : les radiateurs le suivent de nouveau
EVENT_CENTRAL_COMMAND = f"{DOMAIN}_central_command"
SIGNAL_SETPOINTS_UPDATED = f"{DOMAIN}_setpoints_updated_{{}}"

VERSION = "3.1.28"

# Carte Lovelace native
CARD_URL_BASE = "/electric_heater"
CARD_FILENAME = "electric-heater-card.js"
