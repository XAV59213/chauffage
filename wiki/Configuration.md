# Configuration

## Installation

HACS → Dépôts personnalisés → `https://github.com/XAV59213/chauffage` → catégorie Integration → installer → redémarrer.

## 1. Thermostat virtuel

Paramètres → Appareils et services → Ajouter → **Chauffage Electrique Fil Pilote FR**

| Champ | Usage |
|---|---|
| Nom | Ex. Thermostat virtuel |
| Source de température | Sonde choisie **ou** moyenne des pièces |
| Sonde | `sensor` température du salon |
| Météo locale | Entité `weather.*` (optionnel) |
| Calendrier | `calendar.*` ou `schedule.*` pour l'Auto |
| Mode si calendrier actif | Souvent Confort |
| Mode si calendrier inactif | Souvent Arrêt |
| Mode si personne à la maison | Souvent Eco |
| Capteur de présence | **Nombre famille home** |
| Fenêtres salon | Baie, portes, fenêtre → coupure globale |
| Consignes | Confort, -1, -2, Eco, Hors-gel |

Entité : `climate.electric_heater_central`.

## 2. Chaque radiateur

Ajouter **à nouveau** l'intégration pour chaque pièce.

| Champ | Usage |
|---|---|
| Nom | Ex. Chambre papa |
| Relais fil pilote | `select.*pilot_wire_mode` ou `climate` |
| Sonde de la pièce | Obligatoire |
| Fenêtre(s) de la pièce | Coupe **ce** radiateur seulement |

## 3. Modifier plus tard

Sur l'entrée → **Configurer**. Pas besoin de tout recrer.
