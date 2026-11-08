# Reference

[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum-E5E4E2.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)


## Data updates
Local integration, no cloud polling. Reacts instantly to sensor, window/presence and pilot-wire `select` changes; pilot-wire orders are resynced every 60 s, safety checks run every 60 s, statistics every minute (reset at midnight), heating season every 15 min.

## Supported devices
Any radiator driven by a pilot-wire `select` entity in Home Assistant, e.g. NodOn SIN-4-FP-21 (ZHA or Zigbee2MQTT), Legrand and Delta Dore pilot-wire modules, plus a Zigbee temperature sensor per room.

## Use cases
A central thermostat driving every pilot-wire radiator; per-room thermostats with Comfort/Eco, open-window cut-off and absence; heating calendar and per-radiator consumption.

## Known limitations
- The central thermostat is in control; radiators follow it and should not be driven directly by other automations.
- Pilot wire does not set a temperature on the radiator: regulation is hysteresis on the room sensor.
- If a sensor or module is unavailable (after a 120 s grace period at startup), the radiator goes to Frost protection for safety.
- An external client (voice assistant, API) can change the central mode; it is logged, not blocked.

## Removal
Settings → Devices & services → the integration → ⋮ → Delete for each entry (rooms, then central); uninstall it in HACS and restart Home Assistant; remove the Lovelace card. Radiators keep their last pilot-wire mode.
