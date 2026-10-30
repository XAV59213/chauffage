# How it works

🇫🇷 [Français](Fonctionnement.md) · 🇬🇧 English

## Auto

| Condition | Order |
|---|---|
| Calendar active + someone home | Comfort (or last Comfort -1 / -2) |
| Calendar inactive | Configured mode (Frost protection by default) |
| Calendar unavailable | Last mode kept (Eco if none) |
| Nobody home | Eco |
| Mode picked by hand | Kept until the next calendar change |

Priorities: thermostat Off > window (after 45 s) > manual mode > calendar inactive > empty house > comfort.

Weather is only **displayed**; it does not change orders yet.

## Heat (forced)

The chosen mode and setpoint are sent **as-is** to all radiators.

## Windows

| Where | Effect |
|---|---|
| Room window | **This** radiator goes to window mode after the delay (45 s default) |
| Living-room bay / doors (thermostat) | **All** radiators go to window mode after the delay |
| Closed before the delay | Nothing changes (displayed state still switches to "Open" immediately) |
| Closed after | Normal mode resumes immediately |

Window mode: **Frost protection** by default (Frost, Eco or Off). It only ever lowers the order.

## Presence

**Présents** sensor: count plus names (`personnes`, `noms` attributes) of tracked people at home.

## Sensor regulation

| Situation | Pilot wire order |
|---|---|
| Room ≥ setpoint | Configurable order (Eco default, or Frost / Off) |
| Room ≤ setpoint − hysteresis | Base order (never warmer) |
| In between | Last order kept |
| Eco / away | Stays Eco, never raised to Comfort |
| Sensor unavailable | **Frost protection** for safety + "replace sensor battery" alert |

## Summary sensors

`Fenêtres ouvertes` (open windows), `Sondes KO` (KO sensors), `Alerte pile sonde` (battery alert), `Présents` (people home).

## Setpoints

Attributes: `consigne` (current), `consigne_mode` (mode name), `consignes` (all setpoints).

## Temperature bands

| Mode | Band |
|---|---|
| Comfort / -1 / -2 | 0.3 °C |
| Eco | 0.5 °C |
| Frost protection | 1.0 °C |

## Radiator set by hand

Changing one radiator's mode or setpoint detaches it from the thermostat (kept after restart). Set it back to **Auto**, or change the thermostat mode, to follow again.

## Relays

- An order is sent only when it changes.
- Relay back after an outage or changed by hand: expected order resent (after 15 s if different).
- Every 10 min the expected order is resent.
- Send failures are logged.
