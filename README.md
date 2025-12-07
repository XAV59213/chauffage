# Chauffage Électrique Fil Pilote FR  
**L’intégration ultime 100 % locale pour radiateurs fil pilote français**  
**SIN-4-FP-21 • TH01 • Zigbee2MQTT • Sécurité fenêtre par pièce • Aucun cloud**

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/integration)
[![Version](https://img.shields.io/github/v/release/XAV59213/chauffage?style=for-the-badge&label=Version)](https://github.com/XAV59213/chauffage/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-%3E%3D2025.1-00A1DF.svg?style=for-the-badge)](https://www.home-assistant.io)

> Créée et maintenue par **XAV59213** – Décembre 2025  
> La solution que tout le monde attendait pour remplacer les box Tydom, Sowee, Wiser, Netatmo, etc.

---

## Fonctionnalités

| Fonctionnalité                                    | État     |
|---------------------------------------------------|----------|
| Thermostat central virtuel avec vraie sonde       | Yes      |
| 6 ordres fil pilote réels (SIN-4-FP-21)           | Yes      |
| Confort • Confort –1 • Confort –2 • Éco • Hors-gel • Arrêt | Yes      |
| Consigne Confort réglable à 0,1 °C près           | Yes      |
| Température hors-gel réglable (7 → 10 °C)         | Yes      |
| Sécurité fenêtre ouverte **par pièce**            | Yes      |
| Chaque pièce avec sa propre sonde TH01            | Yes      |
| Compatible Zigbee2MQTT (recommandé)               | Yes      |
| Installation HACS en 1 clic                       | Yes      |
| Aucun cloud • Aucun abonnement                    | Yes      |

---

## Matériel 100 % testé et garanti compatible

| Matériel                              | Résultat         | Notes                              |
|---------------------------------------|------------------|------------------------------------|
| NodOn SIN-4-FP-21                     | Parfait          | 6 ordres fil pilote                |
| Sonoff SNZB-02 / SNZB-02D (TH01)      | Excellent        | Température + humidité             |
| Aqara / Xiaomi température            | Parfait          | Plus fiable que le TH01            |
| Tout capteur fenêtre Zigbee           | Fonctionne       | Sécurité locale immédiate          |
| Zigbee2MQTT (addon)                   | Recommandé       | Meilleure stabilité                |

---

## Installation (5 minutes max)

### Via HACS (recommandé)

1. HACS → **Intégrations**  
2. Menu 3 points → **Dépôts personnalisés**  
3. URL : `https://github.com/XAV59213/chauffage`  
4. Catégorie : **Integration** → **Ajouter**  
5. Cherche **"Chauffage Électrique Fil Pilote FR"** → **Installer**  
6. Redémarre Home Assistant

### Installation manuelle

Copie le dossier `custom_components/electric_heater/` dans ton `config/custom_components/` → redémarre HA.

---

## Configuration

1. **Première fois** → création obligatoire du **Thermostat Central**  
   - Nom  
   - Sonde température centrale (ex: salon)  
   - Switch maître (input_boolean ou module au tableau)  
   - Température hors-gel (7 à 10 °C)

2. **Ensuite** → ajout des pièces une par une :  
   - Nom de la pièce  
   - ID Zigbee du SIN-4-FP-21 (friendly name ou 0x…)  
   - Sonde de température de la pièce  
   - (Optionnel) Capteurs fenêtre (séparés par virgule)

**Contrôle total depuis une seule entité** → `climate.electric_heater_central`

---

## Carte Lovelace recommandée (copie-colle)

```yaml
type: vertical-stack
cards:
  - type: custom:mushroom-climate-card
    entity: climate.electric_heater_central
    name: Chauffage Maison
    icon: mdi:home-thermometer-outline
    show_temperature_control: true
    hvac_modes: [auto, 'off']
    preset_modes:
      - confort
      - confort_-1
      - confort_-2
      - eco
      - hors_gel
      - 'off'
    collapsible_controls: false

  - type: glance
    title: Radiateurs
    entities:
      - climate.radiateur_salon
      - climate.radiateur_chambre
      - climate.radiateur_cuisine
    state_color: true
```
## Pourquoi c’est mieux que les box commerciales ?

| Critère                              | Chauffage Électrique Fil Pilote FR | Box Tydom / Sowee / Wiser / Netatmo |
|--------------------------------------|------------------------------------|--------------------------------------|
| **Prix**                             | Gratuit                            | 150–400 € + abonnement annuel       |
| **Cloud obligatoire**                | Non                                | Oui                                  |
| **Sécurité fenêtre ouverte par pièce** | Oui (coupure immédiate)           | Rarement ou jamais                   |
| **Modes Confort –1 °C / –2 °C**      | Oui                                | Souvent absent                       |
| **Hors-gel réglable**                | 7 → 10 °C (choix utilisateur)     | Fixe à 7 °C                          |
| **Consommation détaillée par radiateur** | Oui (SIN-4-FP-21)                | Parfois ou payant                    |
| **Automatisations Home Assistant**   | Illimitées                         | Très limitées                        |
| **Mises à jour & nouvelles fonctions**| Instantanées (GitHub)             | Dépend du fabricant (lent ou jamais) |
| **Confidentialité des données**      | 100 % local                        | Données dans le cloud                |
| **Indépendance du fournisseur d’énergie** | Total                        | Lié au contrat électricité           |

**Conclusion :**  
Tu as exactement la même chose (voire mieux) que les box à 300 €… mais **gratuit, sans cloud, sans abonnement et avec toutes les automatisations que tu veux**.
