# Changelog

## Non publié

- Publication / HACS : chaque release GitHub joint désormais l'archive **`electric_heater.zip`** (contenu de `custom_components/electric_heater`, sans `__pycache__` ni `.pyc`). `hacs.json` passe en `"zip_release": true` / `"filename": "electric_heater.zip"` : HACS installe depuis ce zip et affiche un **compteur de téléchargements**. Nouveau workflow `release-zip.yaml` (release publiée à la main, lancement manuel, ou appelé par les workflows de release existants) qui vérifie que le tag correspond à la version de `manifest.json`. Aucun code de l'intégration modifié
- `hacs.json` : retrait des clés refusées par la validation HACS (`domains`, `iot_class`, `config_flow`, `persistent_directory: false`) et correction de `filename` (`electric_heater` → `electric_heater.zip`)

## 3.0.2 — 2026-09-02

Version alignée `manifest.json` + `const.py` + tag GitHub / HACS.

### Fonctionnement
- Consigne visible et réglable en **Auto**, envoyée aux radiateurs
- En **Chauffage** forcé : mode et consigne envoyés tels quels (plus de Confort -1 / Eco automatiques)
- Attributs `consigne`, `consigne_mode`, `consignes`
- Météo locale (`weather.*`) : ≥15 °C Confort -1, ≥18 °C Confort -2
- Fenêtres : délai 45 s, état Ouverte / Fermée
- Présence via le capteur choisi (Nombre famille home) → Eco si personne

### Interface
- Bouton **Ajouter un radiateur**
- **Configurer le thermostat** / **Configurer le radiateur**
- Wiki : Accueil, Configuration, Fonctionnement, Dépannage

### Correctifs depuis 3.0.1
- Wiki à jour
- Libellés d'ajout et de configuration
- Version affichée dans HA = tag de release
