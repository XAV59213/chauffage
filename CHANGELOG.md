# Changelog

## Non publié

- **hassfest sans erreur** :
  - `manifest.json` : retrait de la clé `homeassistant` (non autorisée ; la version minimale 2025.1.0 reste dans `hacs.json`) et clés triées dans l'ordre attendu ;
  - traductions : retrait des clés non autorisées `config.entry_type` et `config.initiate_flow.reconfigure` ;
  - libellés des presets `comfort_-1` / `comfort_-2` : clés refusées par hassfest (`_-`). Les valeurs des presets ne changent **pas** (automatisations et relais intacts) ; les libellés « Confort -1 C » / « Confort -2 C » restent en français (`translations/fr.json`) mais sont retirés de `strings.json` et de l'anglais, où Home Assistant affiche donc la valeur brute `comfort_-1` / `comfort_-2`.
- **Traductions complètes** : `strings.json`, `translations/en.json` et `translations/fr.json` ont les mêmes clés (section des entités, descriptions des options) ; descriptions FR/EN du thermostat alignées sur le fonctionnement actuel (Hors-gel par défaut si calendrier inactif pour une nouvelle installation, mode fenêtre après 45 s).
- **Documentation** (README et wiki) : exemple Lovelace avec les vrais `entity_id` des radiateurs (`climate.salon_chauffage_salon`…), délai fenêtre de 45 s, réglage « Mode si une fenêtre est ouverte », radiateur réglé à la main et retour en Auto, renvoi des ordres aux relais ; la météo est indiquée comme simple affichage (elle ne change pas encore les ordres).

## 3.1.0 — 2026-10-28

- `release.yml` : tag obligatoire (plus de valeur par défaut figée 1.1.3), contrôle que le tag = `manifest.json` = `const.py` et que la release n'existe pas encore, notes générées automatiquement (fin du texte figé de la 1.1.3). Le job « Zip HACS » est conservé

### Hiver : sécurité et fiabilité du chauffage

- **Fenêtre refermée avant 45 s** : un radiateur pouvait rester éteint (l'ordre « Arrêt » partait dès qu'une sonde changeait pendant le délai, sans être annulé ensuite). Seul l'état confirmé de la fenêtre compte désormais, et l'ordre normal est renvoyé à la fermeture.
- **Abonnements libérés** : tous les écouteurs (thermostat, radiateurs, capteurs) sont libérés au rechargement ou au retrait. Avant, d'anciennes copies du thermostat continuaient d'envoyer des ordres périmés aux relais (18 ordres au lieu de 2 à l'ouverture d'une fenêtre, dont des « Confort » obsolètes). L'écoute globale de tous les changements d'état de Home Assistant est remplacée par un abonnement aux seuls capteurs fenêtre configurés.
- **Consigne sans rechargement** : changer une consigne ne recharge plus l'intégration (le thermostat relit simplement les consignes, y compris depuis « Configurer »).
- **Mode manuel maintenu en Auto** : un mode choisi à la main en Auto (ex. Hors-gel pour des vacances, Eco) est gardé jusqu'au prochain changement du calendrier ; la présence ne l'écrase plus. Il est conservé après un redémarrage, comme le mode du thermostat.
- **Hors-gel** :
  - nouveau réglage **« Mode si une fenêtre est ouverte »** : Hors-gel par défaut (ou Eco, Arrêt). Une fenêtre ouverte ne fait que baisser l'ordre : un radiateur à l'Arrêt reste à l'Arrêt ;
  - « Mode si calendrier inactif » : Hors-gel par défaut pour les **nouvelles** installations. Une installation existante garde le mode enregistré ;
  - calendrier indisponible : le dernier mode est gardé (Eco s'il n'est pas encore connu) au lieu de tout passer à l'Arrêt.
- **Relais** :
  - l'ordre attendu est renvoyé quand un relais revient après une coupure, et quand son état diffère de l'ordre attendu depuis 15 s (changé à la main, redémarré) ;
  - renvoi de l'ordre attendu toutes les 10 min ;
  - un ordre n'est envoyé que s'il change (moins de trafic Zigbee) ;
  - les ordres sont envoyés en attendant la réponse : un échec est écrit dans le journal (« Impossible d'appliquer le mode … ») et un relais indisponible est signalé une fois.
- **Radiateur réglé à la main** : changer le mode ou la consigne d'un radiateur le détache du thermostat ; le réglage est gardé (aussi après un redémarrage). Pour qu'il suive de nouveau le thermostat : le mettre en **Auto**, ou changer le mode du thermostat virtuel.
- Traductions FR/EN du nouveau réglage ; champs manquants ajoutés à la configuration en anglais ; README et wiki mis à jour.

## 3.0.3 — 2026-10-28

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
