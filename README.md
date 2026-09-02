# Chauffage \u00c9lectrique Fil Pilote FR
**L\u2019int\u00e9gration 100 % locale pour radiateurs fil pilote fran\u00e7ais**
**SIN-4-FP-21 \u2022 TH01 \u2022 Zigbee2MQTT / ZHA \u2022 S\u00e9curit\u00e9 fen\u00eatre par pi\u00e8ce \u2022 Aucun cloud**

## Configuration (issue Thermostat Central)

### 1. Cr\u00e9er le thermostat central

Param\u00e8tres \u2192 Appareils et services \u2192 Ajouter une int\u00e9gration \u2192 **Chauffage \u00c9lectrique Fil Pilote FR**

1. Nom (`Chauffage Central`).
2. Source de temp\u00e9rature :
   - **Sonde que je choisis** \u2192 n\u2019importe quelle sonde `sensor.*` de classe temp\u00e9rature.
   - **Moyenne des sondes des pi\u00e8ces** \u2192 moyenne automatique une fois les radiateurs ajout\u00e9s.
3. R\u00e9glez Confort / Confort \u20131 / Confort \u20132 / \u00c9co / Hors-gel.
4. Validez. L\u2019entit\u00e9 `climate.electric_heater_central` commande **tous** les radiateurs.

### 2. Ajouter chaque radiateur

Ajoutez \u00e0 nouveau l\u2019int\u00e9gration. Pour chaque pi\u00e8ce :

1. Nom (ex. `Salon`).
2. Relais fil pilote : `select.radiateur_salon_pilot_wire_mode` (NodOn SIN-4-FP-21) ou un `climate.*`.
3. Sonde de temp\u00e9rature de la pi\u00e8ce (TH01, Aqara, Xiaomi\u2026).
4. Capteurs fen\u00eatre (optionnel).

### 3. Modifier plus tard

Sur l\u2019entr\u00e9e \u2192 **Configurer** : changer la sonde, le relais ou les consignes.

## Installation HACS

1. HACS \u2192 Int\u00e9grations \u2192 D\u00e9p\u00f4ts personnalis\u00e9s
2. URL : `https://github.com/XAV59213/chauffage`
3. Cat\u00e9gorie Integration \u2192 Ajouter \u2192 Installer \u2192 Red\u00e9marrer HA

Le relais n\u2019est plus limit\u00e9 \u00e0 MQTT : Zigbee2MQTT **et** ZHA sont accept\u00e9s.
