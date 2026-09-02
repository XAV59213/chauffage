# Wiki — Chauffage Electrique Fil Pilote FR

Integration Home Assistant locale pour piloter des radiateurs électriques français à **fil pilote** depuis un **thermostat virtuel**.

## Pages

- [Configuration](Configuration.md)
- [Fonctionnement](Fonctionnement.md)
- [Dépannage](Depannage.md)

## En deux phrases

1. On crée **une fois** le thermostat virtuel (`climate.electric_heater_central`).
2. On ajoute **chaque radiateur** (relais fil pilote + sonde + fenêtre éventuelle).

## Modes HVAC

| Mode | Rôle |
|---|---|
| **Auto** | Calendrier, présence, météo, consigne réglable |
| **Chauffage** | Ordre et consigne **forcés** vers tous les radiateurs |
| **Éteint** | Tous les radiateurs à l'arrêt |

## 6 ordres fil pilote

| Mode | Preset HA |
|---|---|
| Confort | `comfort` |
| Confort -1 °C | `comfort_-1` |
| Confort -2 °C | `comfort_-2` |
| Eco | `eco` |
| Hors-gel | `frost_protection` |
| Arrêt | `off` |
