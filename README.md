# Chauffage Electrique Fil Pilote FR

Integration Home Assistant **100 % locale** pour les radiateurs electriques francais a **fil pilote**.

**NodOn SIN-4-FP-21 • Legrand • Delta Dore • sondes Zigbee • Zigbee2MQTT / ZHA • aucun cloud**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/XAV59213/chauffage?style=for-the-badge&label=Version)](https://github.com/XAV59213/chauffage/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2025.1-00A1DF.svg?style=for-the-badge)](https://www.home-assistant.io)

---

## Principe

Le **thermostat principal est virtuel**. Il n'y a pas de boitier physique : Home Assistant cree l'entite `climate.electric_heater_central`.

Ce thermostat virtuel expose les **6 ordres fil pilote** et les envoie a tous les radiateurs equipes d'un relais :

| Mode fil pilote | Preset Home Assistant | Effet sur le radiateur |
|---|---|---|
| Confort | `comfort` | Consigne du radiateur |
| Confort -1 C | `comfort_-1` | Consigne - 1 C |
| Confort -2 C | `comfort_-2` | Consigne - 2 C |
| Eco | `eco` | Consigne - 3,5 C environ |
| Hors-gel | `frost_protection` | 7 a 8 C |
| Arret | `off` | Radiateur coupe |

Chaque piece a ensuite sa **propre sonde** et son **relais fil pilote**.

---

## Fonctionnalites

- Thermostat principal **virtuel** avec les 6 modes fil pilote
- Sonde du thermostat : celle que vous choisissez, ou moyenne des pieces
- Un radiateur = un relais + une sonde (ajout piece par piece)
- Relais `select` (Zigbee2MQTT) **ou** `climate` (ZHA)
- Coupure si une fenetre de la piece est ouverte
- Eco automatique si un capteur de presence / nombre de personnes passe a 0
- Modification de la sonde, du relais et des consignes sans tout recreer

---

## Materiel compatible

| Materiel | Notes |
|---|---|
| NodOn SIN-4-FP-21 | Entite typique : `select.xxx_pilot_wire_mode` |
| Legrand, Delta Dore, Equation / Adeo | Modes reconnus via alias (`comfort-1`, `anti-freeze`, `stop`...) |
| Sonoff SNZB-02 / SNZB-02D (TH01) | Temperature piece ou thermostat |
| Aqara / Xiaomi temperature | Idem |
| Capteur fenetre Zigbee | Optionnel, par piece |
| Zigbee2MQTT ou ZHA | Les deux sont acceptes |

---

## Installation

### HACS (recommande)

1. HACS -> Integrations -> menu -> **Depots personnalises**
2. URL : `https://github.com/XAV59213/chauffage`
3. Categorie : **Integration** -> Ajouter
4. Rechercher **Chauffage Electrique Fil Pilote FR** -> Installer
5. Redemarrer Home Assistant

### Installation manuelle

Copier le dossier `custom_components/electric_heater/` dans `config/custom_components/`, puis redemarrer Home Assistant.

---

## Configuration

### 1. Thermostat virtuel (une seule fois)

Parametres -> Appareils et services -> **Ajouter une integration** -> *Chauffage Electrique Fil Pilote FR*

1. Nom (par defaut : Thermostat virtuel)
2. Source de temperature :
   - **Sonde que je choisis** : n'importe quel `sensor` de classe temperature
   - **Moyenne des sondes des pieces** : calculee apres l'ajout des radiateurs
3. Consignes Confort / Confort -1 / Confort -2 / Eco / Hors-gel
4. Valider

L'entite creee est `climate.electric_heater_central`. C'est le seul point de commande globale.

### 2. Chaque radiateur

Ajouter **a nouveau** l'integration pour chaque piece :

1. Nom de la piece (ex. Salon)
2. Relais fil pilote : `select.radiateur_salon_pilot_wire_mode` (ou un `climate`)
3. Sonde de temperature de **cette** piece
4. Capteurs fenetre (optionnel)

Le thermostat virtuel envoie alors le meme ordre fil pilote a tous les relais.

### 3. Modifier plus tard

Sur l'entree concernee -> **Configurer** : changer la sonde, le relais ou les consignes.

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

Les presets du thermostat virtuel sont : `comfort`, `comfort_-1`, `comfort_-2`, `eco`, `frost_protection`, `off`.

---

## Depannage

- Le menu du relais est vide : dans Developpeur -> Etats, chercher `select.*pilot_wire*` ou `select.*fil_pilote*`.
- Un radiateur ne change pas de mode : verifier que l'option exposee est bien l'un des alias reconnus (`comfort`, `comfort_-1`, `eco`, `frost_protection`, `off`...).
- Le thermostat n'affiche pas de temperature : la sonde choisie est absente, ou aucune piece n'est encore ajoutee en mode moyenne.
