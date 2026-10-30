# Changelog

## 3.1.31 — 2026-10-30

- **Statistiques de chauffe** (statistiques long terme HA) par radiateur : `Temps de chauffe aujourd'hui` / `total` (h) et `Consommation aujourd'hui` / `totale` (kWh estimés = temps de chauffe × puissance).
- **Global maison** sur le thermostat central : temps de chauffe et consommation (jour / total), détail `par_radiateur`.
- **Nouvelle option radiateur** « Puissance du radiateur (W) » (0 = consommation non suivie). Les capteurs kWh sont utilisables dans le tableau Énergie.
- **Compteurs réels auto-liés** : un `sensor.*_energy` (kWh) sur le même appareil que le relais, ou dans la même pièce HA (ex. `sensor.radiateur_papa_energy`, Chambre parental), est lié au radiateur (attribut `energy_sensor`). Somme globale : `Consommation radiateurs (compteurs)` (kWh, total_increasing, détail `par_radiateur`).
- **Carte** : temps de chauffe et kWh du jour sous chaque radiateur + kWh du compteur réel, pastilles globales (estimé du jour + total compteurs).

## 3.1.30 — 2026-10-30

- **Notification « système opérationnel »** après la grâce de démarrage (3 min), avec le résumé des problèmes en cours (sondes KO, fenêtres ouvertes), puis les alertes habituelles.
- **Fenêtre ouverte + personne à la maison** : notification si une fenêtre reste ouverte alors que Présents = 0 (après 2 min), « OK » quand c'est réglé.
- **Nouveau capteur** `binary_sensor` « Calendrier chauffage activé » : allumé quand le thermostat est en Auto ET que le calendrier est actif.

## 3.1.29 — 2026-10-30

- **Fix fenêtre ignorée** : un détecteur porte/fenêtre rangé dans la même pièce HA qu'un radiateur (ex. « Détecteur fenêtre papa » dans Chambre parentale) est maintenant pris en compte par la régulation, même s'il n'est pas (ou mal) renseigné dans Configurer. Le radiateur passe en mode fenêtre (Hors-gel) après le délai, comme ce que la carte affichait déjà.
- **Carte** : le badge « Fenêtres fermées » compte aussi l'état réel des détecteurs listés (plus de badge « fermées » avec un détecteur « Ouvert »).

## 3.1.28 — 2026-10-30

- **HACS** : workflow CI HACS + Hassfest, `manifest.json` (nom accentué) aligné sur `hacs.json`, version = `VERSION` = tag.
- **Traductions** : `strings.json`, `translations/en.json` et `translations/fr.json` ont exactement les mêmes clés (clés `comfort_-1/-2` invalides pour hassfest retirées de fr.json).
- **Docs FR / EN** : `README.en.md` + pages Wiki anglaises (`*-EN`), liens de langue et barre latérale bilingue.

## 3.1.27 — 2026-10-30

- **docs : Licence README** — licence MIT au nom de l'auteur (XAV59213) uniquement, avec son bouton Buy Me a Coffee. Aucun changement de code.

## 3.1.26 — 2026-10-30

- **docs : Licence README** — section Licence (MIT) avec remerciements à @gvigroux (projet d'origine) et boutons Buy Me a Coffee (xav59213, gvigroux). Aucun changement de code.

## 3.1.25 — 2026-10-30

- **Documentation** : section Licence (MIT) et remerciements à @gvigroux (projet d'origine) dans le README ; wiki du dépôt mis à jour (carte, notifications, options, régulation, dépannage). Aucun changement de code.

## 3.1.24 — 2026-10-30

- **Documentation** : README mis à jour avec la carte native « Chauffage Fil Pilote » et des captures (carte, configuration du thermostat). Capture de la carte aussi dans `examples/lovelace/README.md`. Aucun changement de code.

## 3.1.23 — 2026-10-30

- **Carte : détecteur du salon** : sont aussi ajoutés les `binary_sensor` fenêtre / porte / ouverture dont le nom contient la pièce d'un radiateur (zone Home Assistant, ou salon, séjour, cuisine, entrée, bureau…), même s'ils ne sont pas rangés dans la bonne zone.
- **Correctif : les détecteurs configurés sur un radiateur (Configurer) sont toujours listés**. Ils étaient lus seulement dans les données initiales de la pièce et pas dans ses options (cas du détecteur du salon). Les radiateurs exposent maintenant l'attribut `window_sensors`, que la carte lit directement ; capteurs « État fenêtre » et « Sécurité Fenêtre » corrigés de la même façon.
- Chaque détecteur affiche sa pièce Home Assistant à côté du nom (ex. « Détecteur baie vitrée · Salon »).

## 3.1.22 — 2026-10-30

- **Carte : détecteurs de la même pièce** : en plus des détecteurs configurés, la carte affiche les `binary_sensor` fenêtre / porte / ouverture situés dans la même pièce Home Assistant (zone de l'entité ou de son appareil) qu'un radiateur ou que le thermostat central — ex. détecteur fenêtre papa, salon. Les capteurs batterie, sabotage, problème et ceux de l'intégration sont ignorés.

## 3.1.21 — 2026-10-30

- **Carte : tous les détecteurs de fenêtre** (thermostat central et chaque radiateur) sont affichés. La déduplication de la 3.1.19 masquait à tort des détecteurs sans pile trouvée dont le nom ressemblait partiellement à un autre (fenetre_papa, fenetre_cuisine…). Elle ne fusionne plus que le même appareil, le même capteur de batterie ou exactement le même nom (hors « Détecteur » et suffixes techniques).

## 3.1.20 — 2026-10-30

- **Carte : état de chaque détecteur de fenêtre** : la section devient « Détecteurs de fenêtre (état et pile) » et affiche pour chaque détecteur un badge **Ouvert** / **Fermé** / Indisponible, à côté du pourcentage de pile (et « Pile faible » le cas échéant). Un clic ouvre la fiche du détecteur.

## 3.1.19 — 2026-10-30

- **Carte : plus de doublons « Pile ? »** (ex. `binary_sensor.baie_vitree`, `fenetre_papa`) : les piles sont dédupliquées par appareil, capteur batterie et nom de base ; une entité inexistante (ancien entity_id) est ignorée ; une ligne « Pile ? » n'est plus affichée si le même détecteur a déjà son pourcentage.

## 3.1.18 — 2026-10-30

- **Plus de fausses alertes au redémarrage** : les notifications sonde / pile attendent 3 minutes après le démarrage de Home Assistant (le temps que Zigbee / MQTT chargent les entités), puis une sonde ou une pile doit rester KO 2 minutes avant d'alerter.
- **Notification « OK »** : quand une sonde de température revient (ou qu'une pile de détecteur de fenêtre n'est plus faible) après une alerte, une notification « ✅ … OK » est envoyée et l'alerte est retirée.

## 3.1.17 — 2026-10-30

- **Correctif carte « Piles des détecteurs de fenêtre »** : des morceaux de configuration brute (`'window_sensors': …`, `{'fil_pilote_select': …}`) apparaissaient avec « Pile ? ». La lecture des détecteurs de fenêtre ne garde plus que de vrais entity_id (binary_sensor, sensor, input_boolean, cover), extrait la liste d'une configuration enregistrée sous forme de dict ou de texte, et supprime les doublons. Même nettoyage à l'enregistrement du formulaire et dans la carte.

## 3.1.16 — 2026-10-30

- **Carte : toutes les piles des détecteurs de fenêtre** (thermostat central et toutes les pièces). La batterie est trouvée via l'appareil, à défaut par le nom (`sensor.<détecteur>_battery`) ou l'attribut `battery` ; un détecteur sans batterie trouvée s'affiche « Pile ? » au lieu d'être masqué.
- **Carte : nouvelle section « Piles des sondes de température »** (sonde de chaque radiateur), avec % et « Pile faible » à 20 % ou moins. La pastille résumé compte toutes les piles faibles.
- **Présents** : les entités person d'appareils au nom collé (ipadpapa, tablettep…) sont reconnues et masquées, dans le capteur comme dans la carte. Les personnes cochées dans « Personnes suivies » restent prioritaires.

## 3.1.15 — 2026-10-30

- **Service notify en liste déroulante** : le champ « Service notify en plus » propose les services `notify.*` existants, applications mobiles (`mobile_app_…`) en premier. Saisie libre toujours possible.
- Rappel : les consignes du formulaire sont arrondies à 0,1 °C depuis la 3.1.14 (mettre à jour puis redémarrer Home Assistant et recharger l'application pour ne plus voir 20,199999…).

## 3.1.14 — 2026-10-30

- **Correctif « Temperature Confort 20,199999999999998 »** : les champs de température du formulaire n'imposent plus de pas de 0,1 côté navigateur (le calcul par pas produisait ces valeurs). L'arrondi à 0,1 °C est fait par l'intégration, en décimal exact, sur toutes les consignes (Confort, -1, -2, Eco, Hors-gel, min, max) et l'hystérésis : valeurs affichées, saisie et thermostat.
- Au démarrage, les consignes déjà enregistrées avec des décimales parasites sont nettoyées automatiquement.

## 3.1.13 — 2026-10-30

- **Correctif consignes « 11.600000000000001 » / « Value … is too large »** : toutes les consignes sont arrondies à 0,1 °C (lecture, réglage depuis le thermostat, enregistrement de la configuration).
- Formulaire de configuration : valeurs par défaut arrondies et ramenées dans les bornes du champ ; la température Hors-gel accepte maintenant jusqu'à 15 °C (au lieu de 10 °C).

## 3.1.12 — 2026-10-30

- **Correctif configuration du thermostat** : la validation échouait avec « value must be one of [binary_sensor…] ». Le sélecteur des fenêtres accepte maintenant toujours les détecteurs déjà configurés (même renommés ou hors filtre). Le champ « Personnes suivies » reste un sélecteur de `person` distinct.
- À la création du thermostat central, les personnes suivies, le service notify, l'ordre au-dessus de la consigne, l'hystérésis, les délais et l'option notifications sont bien enregistrés.

## 3.1.11 — 2026-10-30

- **Choix des personnes** : nouveau sélecteur multiple « Personnes suivies » dans la configuration du thermostat central (Configurer). On y coche les vraies personnes (Papa, Maman, Xavier…) ; le capteur `Présents` et la carte n'affichent qu'elles.
- **Appareils exclus** : les entités `person` qui sont des appareils ou la maison (Tablette, iPad, iPhone, téléphone, mqtt, MAISON, voiture…) ne sont plus proposées dans le sélecteur ni comptées comme présentes. Sans choix, la détection automatique les ignore aussi.

## 3.1.10 — 2026-10-30

- **Correctif fenêtre affichée « Fermée » alors qu'elle est ouverte** : l'attribut `fenetre` des thermostats ne passait à « Ouverte » qu'après le délai de coupure (45 s par défaut). Il suit maintenant la détection immédiate (nouvel attribut `fenetre_detectee`) ; la coupure du chauffage garde son délai. La carte affiche l'icône fenêtre dès la détection.
- Détecteurs de fenêtre : états `ouvert` / `ouverte` / `fermé` / `fermée` et attribut `contact` (Zigbee2MQTT) reconnus. Le capteur « État fenêtre » affiche « Indisponible » si tous les détecteurs sont indisponibles, au lieu de « Fermée ».
- **Notifications Home Assistant** (activées par défaut, désactivables dans les options du thermostat central) :
  - sonde de température de pièce KO : « remplacer la pile de la sonde » ;
  - pile d'un détecteur de fenêtre faible (20 % ou moins) ;
  - fenêtre ouverte, une seule notification une fois l'ouverture confirmée après le délai configuré.
  Une notification par problème, retirée automatiquement au retour à la normale. Option : service `notify` supplémentaire (ex. application mobile).

## 3.1.9 — 2026-10-30

- **Piles des détecteurs de fenêtre** sur la carte « Chauffage Fil Pilote » : pour chaque détecteur de fenêtre configuré, le capteur batterie du même appareil est trouvé automatiquement (pourcentage ou alerte batterie). Affichage du % et d'un badge « Pile faible » à 20 % ou moins, plus une pastille résumé « N piles fenêtre faibles » / « Piles fenêtres OK ». Option de repli `detecteurs_fenetre`.
- **Présents** : l'entité `person` « MAISON » (qui représente la maison, pas une personne) n'apparaît plus dans les prénoms. Option carte `exclure_personnes` pour en masquer d'autres.

## 3.1.8 — 2026-10-30

- **Présents avec les prénoms** : la carte « Chauffage Fil Pilote » affiche une pastille par personne à la maison (nom des entités `person.*` à l'état « home », ex. Papa, Maman, Xavier, Anais), en plus du compte. Clic sur un prénom = fiche de la personne.
- Capteur `Présents` : nouveaux attributs `personnes` (liste) et `noms` (texte), mis à jour à chaque arrivée / départ.

## 3.1.7 — 2026-10-30

- **Carte Lovelace native « Chauffage Fil Pilote »** (`type: custom:electric-heater-card`), livrée et chargée automatiquement par l'intégration : Tableau de bord → Ajouter une carte → « Chauffage Fil Pilote ».
- **Découverte automatique** : thermostat central, tous les radiateurs ajoutés (ordre fil pilote, température / consigne, fenêtre, sonde KO), fenêtres ouvertes, sondes KO / alerte pile et présents. Options manuelles uniquement en repli.
- Documentation : `examples/lovelace/README.md`.

## 3.1.6 — 2026-10-30

- **Capteurs résumé** sur le thermostat central :
  - `Fenêtres ouvertes` : nombre de fenêtres ouvertes, avec la liste (noms, entités, pièces) en attributs.
  - `Sondes KO` : nombre de sondes de pièce indisponibles, avec les pièces et sondes concernées.
  - `Alerte pile sonde` (binary_sensor, problème) : activé dès qu'une sonde est KO — « Remplacer la pile de la sonde ».
- Le capteur `Présents` existant reste inchangé et est repris dans la vue exemple.
- **Vue Lovelace** prête à coller : `examples/lovelace-statut-chauffage.yaml` (fenêtres ouvertes, alertes pile, présence, radiateurs).
- Traductions FR / EN des nouveaux capteurs.

## 3.1.5 — 2026-10-30

- **Ordre au-dessus de la consigne réglable** : nouvelle option du thermostat central pour choisir l'ordre fil pilote envoyé quand la pièce dépasse la consigne : Eco (par défaut, comportement inchangé), Hors-gel ou Arrêt.
- **Hystérésis et délais réglables** dans les options du thermostat central : hystérésis Confort (0,3 °C par défaut), délai avant coupure fenêtre ouverte (45 s), renvoi périodique de l'ordre fil pilote (10 min, pris en compte après redémarrage). Les valeurs par défaut reprennent les anciennes valeurs fixes.
- Traductions FR / EN des nouvelles options.

## 3.1.4 — 2026-10-30

- **Sonde de température KO = Hors-gel de sécurité** : si la sonde d'une pièce est indisponible, inconnue ou renvoie une valeur invalide (pile vide, perte radio…), le radiateur passe en Hors-gel au lieu de recevoir l'ordre de base (Confort).
- **Alerte pile** : nouveaux attributs `sonde_ko`, `alerte` (`pile_sonde`) et `message` (« remplacer la pile de la sonde ») sur le thermostat de la pièce, avec un avertissement dans les logs. Traductions FR / EN.
- Dès que la sonde revient, la régulation normale reprend automatiquement.

## 3.1.3 — 2026-10-30

- **Absence / Eco ne force plus Confort** : sous la consigne, l'ordre fil pilote ne remonte jamais au-dessus de l'ordre de base (un radiateur en Eco reste en Eco).
- **Hystérésis avec mémoire** : entre consigne − hystérésis et consigne, le dernier ordre envoyé est conservé, ce qui supprime le va-et-vient Confort / Eco autour de la consigne.
- **hvac_action cohérent** : l'état Chauffe / Inactif des radiateurs est déduit de l'ordre fil pilote réellement envoyé (Confort, −1, −2 = chauffe ; Eco, Hors-gel, Arrêt = inactif). Nouvel attribut `ordre_envoye`.

## 3.1.2 — 2026-10-30

- **Régulation au-dessus de la consigne** : quand la pièce dépasse la consigne, l'ordre fil pilote passe en Eco (non chauffant) au lieu de Confort −1, qui restait un ordre de chauffe via le thermostat interne du radiateur.
- En mode Chauffage (heat), la régulation par sonde s'applique aussi ; seule une fenêtre ouverte force l'ordre exact.
- Un changement de température de pièce renvoie toujours l'ordre fil pilote, y compris en mode heat.

## 3.1.1 — 2026-10-28

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
