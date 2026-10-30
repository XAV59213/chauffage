# Chauffage Électrique Fil Pilote FR (Pilot Wire Electric Heating)

<p align="center"><img src="https://raw.githubusercontent.com/XAV59213/chauffage/main/custom_components/electric_heater/brand/logo.png" alt="Chauffage Électrique Fil Pilote FR" width="360"></p>

🇫🇷 [Version française](README.md) · 🇬🇧 English

**100 % local** Home Assistant integration for French electric radiators controlled by **pilot wire** (*fil pilote*).

**NodOn SIN-4-FP-21 • Legrand • Delta Dore • Zigbee sensors • Zigbee2MQTT / ZHA • no cloud**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/XAV59213/chauffage?style=for-the-badge&label=Version)](https://github.com/XAV59213/chauffage/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2025.1-00A1DF.svg?style=for-the-badge)](https://www.home-assistant.io)

**Wiki**: [Home](wiki/Home-EN.md) · [Configuration](wiki/Configuration-EN.md) · [How it works](wiki/Fonctionnement-EN.md) · [Card](wiki/Carte-EN.md) · [Notifications](wiki/Notifications-EN.md) · [Troubleshooting](wiki/Depannage-EN.md)

---

## Principle

The **main thermostat is virtual**. Home Assistant creates `climate.electric_heater_central`.

It exposes the **6 pilot wire orders** and sends them to every radiator fitted with a relay.

| Pilot wire mode | Home Assistant preset |
|---|---|
| Comfort | `comfort` |
| Comfort -1 °C | `comfort_-1` |
| Comfort -2 °C | `comfort_-2` |
| Eco | `eco` |
| Frost protection | `frost_protection` |
| Off | `off` |

Each room has its own **sensor**, **relay** and optionally **window** detector.

---

## Thermostat modes

| HVAC mode | Role |
|---|---|
| **Auto** | Calendar, presence, windows. Setpoint visible and adjustable. |
| **Heat** | Mode + setpoint sent as-is to all radiators. |
| **Off** | All radiators off. |

In **Auto**:

- calendar **active** → Comfort (or last Comfort -1 / -2)
- calendar **inactive** → configured mode (Frost protection by default)
- calendar **unavailable** → last mode kept
- **nobody home** → Eco
- living-room window open **more than 45 s** → all radiators in window mode (Frost protection by default); closed again before 45 s → nothing changes; closed after → immediate resume
- mode picked by hand in Auto → kept until the next calendar change (set the thermostat back to Auto to return to the calendar right away)

Weather (`weather.*`) is **displayed** (Outdoor temperature sensor); it does not change orders yet.

---

## Features

- Virtual thermostat, 6 pilot wire modes
- Setpoint shown / adjustable in Auto, pushed to radiators
- Room regulation with hysteresis; configurable order above setpoint (Eco / Frost / Off)
- Room sensor unavailable → **Frost protection** for safety + alert
- Window per room = this radiator; living-room openings = all radiators
- Summary sensors: open windows, KO sensors, battery alert, people at home (with names)
- Home Assistant notifications (sensor KO, low battery, open window, back to OK)
- Native Lovelace card with auto-discovery
- Order sent only when it changes; resent when a relay comes back, if it differs for 15 s, and every 10 min
- Relays: `select` (Zigbee2MQTT) or `climate` (ZHA)

---

## Installation

### HACS (recommended)

1. HACS → Integrations → menu → **Custom repositories**
2. URL: `https://github.com/XAV59213/chauffage`
3. Category: **Integration** → Add
4. Search **Chauffage Électrique Fil Pilote FR** → Install
5. Restart Home Assistant

### Manual

Copy `custom_components/electric_heater/` into `config/custom_components/`, then restart.

Details: [wiki/Configuration-EN.md](wiki/Configuration-EN.md).

---

## Quick configuration

1. Add the integration → virtual thermostat (sensor, calendar, people, living-room windows, weather).
2. Add the integration **again** for each radiator (relay + sensor + room window).
3. Change later via **Configure**.

<p align="center">
  <img src="https://raw.githubusercontent.com/XAV59213/chauffage/main/docs/images/config-thermostat.jpg" alt="Virtual thermostat configuration" width="320">
</p>

---

## Lovelace card

Native card shipped with the integration: **Chauffage Fil Pilote**.

```yaml
type: custom:electric-heater-card
```

Dashboard → **Edit** → **Add card** → search **Chauffage Fil Pilote**.
No option needed: central thermostat, radiators, windows (state + battery), sensors (battery), people at home and alerts are found automatically.

<p align="center">
  <img src="https://raw.githubusercontent.com/XAV59213/chauffage/main/docs/images/carte-chauffage.jpg" alt="Chauffage Fil Pilote card" width="320">
</p>

Options and examples: [examples/lovelace/README.md](examples/lovelace/README.md).

---

## Troubleshooting

See [wiki/Depannage-EN.md](wiki/Depannage-EN.md).

---

## License

MIT · © [XAV59213](https://github.com/XAV59213)

<a href="https://www.buymeacoffee.com/xav59213"><img src="https://img.buymeacoffee.com/button-api/?text=xav59213&emoji=&slug=xav59213&button_colour=5F7FFF&font_colour=ffffff&font_family=Cookie&outline_colour=000000&coffee_colour=FFDD00" /></a>
