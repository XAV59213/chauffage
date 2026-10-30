# Troubleshooting

🇫🇷 [Français](Depannage.md) · 🇬🇧 English

## Relay / pilot wire

- Empty relay list: Developer tools → States → search `select.*pilot_wire*` or `select.*fil_pilote*`.
- Radiator does not change mode: the option must match an alias (`comfort`, `comfort_-1`, `eco`, `frost_protection`, `off`, `stop`…).
- Turning the thermostat off does not cut: the relay field must point to `select.*_pilot_wire_mode`, not the room climate.

## Temperature and setpoint

- No temperature on the thermostat: missing sensor, or no room in average mode.
- Forced Heat not followed: update the integration.

## Windows

- Window shown closed: check the detector entity_id (Developer tools → States, it must turn `on`).
- Detector missing from the card: add it in the radiator's **Configure**, or put it in the same HA area as the radiator.
- Too fast change: 45 s delay before window mode.

## Radiator no longer follows the thermostat

- It was set by hand: set it back to **Auto**, or change the virtual thermostat mode.
- Window open: the radiator is in **window mode**.

## Configuration form

- "value must be one of [binary_sensor…]": fixed in 3.1.12.
- Setpoints like 20.199999: fixed in 3.1.14 (update, restart, reload the app).

## Presence / Eco

- Tablet / iPad shown as present: tick real people in **Tracked people**.
- Eco while someone is home: use the people-at-home count sensor, not `zone.home`.

## Auto / calendar

- Auto stays off: no current event in the calendar / schedule.
- Auto does not switch to Comfort: the calendar must turn `on` / `active`.
