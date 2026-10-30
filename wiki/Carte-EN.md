# Lovelace card "Chauffage Fil Pilote"

🇫🇷 [Français](Carte.md) · 🇬🇧 English

Shipped with the integration (since 3.1.7), nothing extra to install.

```yaml
type: custom:electric-heater-card
```

Dashboard → **Edit** → **Add card** → **Chauffage Fil Pilote**.

![Card](../docs/images/carte-chauffage.jpg)

## What it shows (auto-discovery)

- Central thermostat: temperature, setpoint, mode, heating / idle.
- Chips: open windows, KO sensors, heating calendar active / inactive, people home (with names), batteries.
- Each radiator: pilot wire order, temperature / setpoint, window, sensor KO.
- **Window detectors**: Open / Closed + battery (%). Detectors configured on the thermostat and each radiator, plus those in the same HA area.
- **Batteries of room temperature sensors**.
- **Daily consumption per radiator** (time + kWh) and total: 🔌 real meter (e.g. `sensor.radiateur_papa_energy`) when linked, otherwise ≈ estimate.

- **Chart**: temperature curves of all radiators (24 h by default).

## Options (fallback)

`titre`, `central`, `radiateurs`, `fenetres`, `sondes_ko`, `alerte_pile`, `presents`, `detecteurs_fenetre`, `sondes`, `exclure_personnes`, `graphique` (false to hide), `heures` (chart duration, default 24).

If the card does not appear: Settings → Dashboards → Resources → `/electric_heater/electric-heater-card.js` (JavaScript module).
