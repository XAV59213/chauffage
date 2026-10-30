# Configuration

🇫🇷 [Français](Configuration.md) · 🇬🇧 English

## Installation

HACS → Custom repositories → `https://github.com/XAV59213/chauffage` → category Integration → install → restart.

## 1. Virtual thermostat

Settings → Devices & services → Add → **Chauffage Électrique Fil Pilote FR**

| Field | Use |
|---|---|
| Name | e.g. Virtual thermostat |
| Temperature source | Chosen sensor **or** average of rooms |
| Sensor | Living-room temperature `sensor` |
| Local weather | `weather.*` entity (optional, shows outdoor temperature) |
| Calendar | `calendar.*` or `schedule.*` for Auto |
| Mode when calendar active | Usually Comfort |
| Mode when calendar inactive | Frost protection by default |
| Mode when nobody home | Usually Eco |
| Presence sensor | People-at-home count |
| Tracked people | Tick real people. Empty = automatic; tablets, iPad, mqtt, MAISON excluded |
| Living-room windows | Bay, doors, window → all radiators in window mode |
| Mode when a window is open | Frost protection by default (or Eco, Off) |
| Setpoints | Comfort, -1, -2, Eco, Frost (rounded to 0.1 °C; Frost 5–15 °C) |
| Order above setpoint | Eco (default), Frost protection or Off |
| Comfort hysteresis | 0.3 °C by default |
| Open-window delay | 45 s by default |
| Periodic pilot wire resend | 10 min by default (applied after restart) |
| Notifications | On by default (see [Notifications](Notifications-EN.md)) |
| Extra notify service | List of `notify.*` (mobile app first) |

Entity: `climate.electric_heater_central`.

## 2. Each radiator

Add the integration **again** for each room.

| Field | Use |
|---|---|
| Name | e.g. Bedroom |
| Pilot wire relay | `select.*pilot_wire_mode` or `climate` |
| Room sensor | Required |
| Room window(s) | Only **this** radiator goes to window mode |
| Power (W) | For estimated consumption (0 = not tracked) |

## 3. Change later

On the entry → **Configure**. No need to recreate anything.
