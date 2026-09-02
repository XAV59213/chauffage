# Chauffage Electrique Fil Pilote FR

Integration Home Assistant **100 % locale** pour les radiateurs electriques francais a **fil pilote**.

**NodOn SIN-4-FP-21 • Legrand • Delta Dore • sondes Zigbee • Zigbee2MQTT / ZHA • aucun cloud**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/XAV59213/chauffage?style=for-the-badge&label=Version)](https://github.com/XAV59213/chauffage/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2025.1-00A1DF.svg?style=for-the-badge)](https://www.home-assistant.io)

**Wiki** : [Accueil](wiki/Home.md) · [Configuration](wiki/Configuration.md) · [Fonctionnement](wiki/Fonctionnement.md) · [Depannage](wiki/Depannage.md)

---

## Principe

Le **thermostat principal est virtuel**. Home Assistant cree `climate.electric_heater_central`.

Il expose les **6 ordres fil pilote** et les envoie a tous les radiateurs equipes d'un relais.

| Mode fil pilote | Preset Home Assistant |
|---|---|
| Confort | `comfort` |
| Confort -1 C | `comfort_-1` |
| Confort -2 C | `comfort_-2` |
| Eco | `eco` |
| Hors-gel | `frost_protection` |
| Arret | `off` |

Chaque piece a sa **sonde**, son **relais** et éventuellement sa **fenetre**.

---

## Modes du thermostat

| Mode HVAC | Role |
|---|---|
| **Auto** | Calendrier, presence, meteo. Consigne visible et reglable. |
| **Chauffage** | Mode + consigne envoyes tels quels aux radiateurs. |
| **Eteint** | Tous les radiateurs a l'arret. |

En **Auto** :

- calendrier **actif** → Confort (ou dernier Confort -1 / -2)
- calendrier **inactif** → mode configure (souvent Arret)
- **Nombre famille home** = 0 → Eco
- fenetre salon ouverte 45 s → Off global
- exterieur ≥ 15 C → Confort -1 ; ≥ 18 C → Confort -2

---

## Fonctionnalites

- Thermostat virtuel, 6 modes fil pilote
- Consigne affichee / reglable en Auto, poussee vers les radiateurs
- Attributs `consigne`, `consigne_mode`, `consignes`
- Calendrier / planning pour l'Auto
- Presence = capteur choisi (Nombre famille home)
- Fenetre piece = ce radiateur ; ouvertures salon = thermostat Off
- Delai 45 s avant coupure fenetre
- Meteo locale (`weather.*`)
- Relais `select` (Zigbee2MQTT) ou `climate` (ZHA)

---

## Installation

### HACS (recommande)

1. HACS -> Integrations -> menu -> **Depots personnalises**
2. URL : `https://github.com/XAV59213/chauffage`
3. Categorie : **Integration** -> Ajouter
4. Rechercher **Chauffage Electrique Fil Pilote FR** -> Installer
5. Redemarrer Home Assistant

### Installation manuelle

Copier `custom_components/electric_heater/` dans `config/custom_components/`, puis redemarrer.

Details : [wiki/Configuration.md](wiki/Configuration.md).

---

## Configuration rapide

1. Ajouter l'integration → thermostat virtuel (sonde, calendrier, presence, fenetres salon, meteo).
2. Ajouter l'integration **a nouveau** pour chaque radiateur (relais + sonde + fenetre piece).
3. Modifier plus tard via **Configurer**.

---

## Carte Lovelace

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.electric_heater_central
    name: Thermostat virtuel

  - type: glance
    title: Radiateurs
    entities:
      - climate.chauffage_salon
      - climate.chauffage_chambre
      - climate.chauffage_cuisine
    state_color: true
```

---

## Depannage

Voir [wiki/Depannage.md](wiki/Depannage.md).
