# Wiki — Chauffage Électrique Fil Pilote FR (English)

🇫🇷 [Français](Home.md) · 🇬🇧 English

Local Home Assistant integration to drive French **pilot wire** electric radiators from a **virtual thermostat**.

## Pages

- [Configuration](Configuration-EN.md)
- [How it works](Fonctionnement-EN.md)
- [Lovelace card](Carte-EN.md)
- [Notifications](Notifications-EN.md)
- [Troubleshooting](Depannage-EN.md)

Documented version: **3.1.33** (manifest, `VERSION` and release tag aligned; HACS installs the release zip `electric_heater.zip`).

## In two sentences

1. Create the virtual thermostat **once** (`climate.electric_heater_central`).
2. Add **each radiator** (pilot wire relay + sensor + optional window).

## HVAC modes

| Mode | Role |
|---|---|
| **Auto** | Calendar, presence, windows, adjustable setpoint |
| **Heat** | Order and setpoint **forced** to all radiators |
| **Off** | All radiators off |

## 6 pilot wire orders

| Mode | HA preset |
|---|---|
| Comfort | `comfort` |
| Comfort -1 °C | `comfort_-1` |
| Comfort -2 °C | `comfort_-2` |
| Eco | `eco` |
| Frost protection | `frost_protection` |
| Off | `off` |
