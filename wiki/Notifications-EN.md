# Notifications

🇫🇷 [Français](Notifications.md) · 🇬🇧 English

On by default (**Notifications** option of the central thermostat). Home Assistant notification + optional `notify` service (e.g. mobile app).

| Event | Message |
|---|---|
| Room sensor unavailable | 🔋 Sensor KO – replace battery (radiator in Frost protection) |
| Window detector battery ≤ 20 % | 🔋 Low detector battery |
| Window open (after delay) | 🪟 Window open |
| Back to normal | ✅ … OK |

- One notification per problem, dismissed when back to normal.
- On restart: 3 min grace, then a problem must last 2 min before alerting.
