# Dépannage

## Relais / fil pilote

- Menu du relais vide : Développeur → États → chercher `select.*pilot_wire*` ou `select.*fil_pilote*`.
- Le radiateur ne change pas de mode : l'option doit correspondre à un alias (`comfort`, `comfort_-1`, `eco`, `frost_protection`, `off`, `stop`…).
- Éteindre le thermostat ne coupe pas : le champ relais doit pointer vers `select.*_pilot_wire_mode`, pas vers le climate de la pièce.

## Température et consigne

- Pas de température sur le thermostat : sonde absente, ou aucune pièce en mode moyenne.
- Pas de curseur en Auto : mettre à jour l'intégration (consigne toujours affichée depuis 2.0.x).
- En Chauffage forcé le radiateur ne suit pas : mettre à jour, le mode est envoyé tel quel.

## Fenêtres

- Fenêtre affichée fermée : vérifier l'entity_id du détecteur (Outils de développement → États, il doit passer à `on`).
- Détecteur absent de la carte : l'ajouter dans **Configurer** du radiateur, ou le ranger dans la même pièce HA que le radiateur.

- État fenêtre pas à jour : vérifier l'entity_id dans Configurer (ex. `binary_sensor.fenetre_papa_3`).
- Doublon Fenêtre ouverte : ancienne entité, à supprimer dans Réglages → Entités.
- Changement trop rapide : délai de 45 s avant le mode fenêtre (Hors-gel par défaut).

## Radiateur qui ne suit plus le thermostat

- Il a été réglé à la main (mode ou consigne) : le remettre en **Auto**, ou changer le mode du thermostat virtuel.
- Fenêtre ouverte : le radiateur est dans le **mode fenêtre** (Hors-gel par défaut, réglable dans Configurer).

## Formulaire de configuration

- « value must be one of [binary_sensor…] » : corrigé en 3.1.12.
- Consignes du type 20,199999 : corrigé en 3.1.14 (mettre à jour, redémarrer, recharger l'application).

## Présence / Eco

- Tablette / iPad affichés comme présents : cocher les vraies personnes dans **Personnes suivies**.

- Eco alors que quelqu'un est là : le thermostat doit utiliser **Nombre famille home**, pas `zone.home`.
- Doublon Nombre de personnes : garder **Présents**, supprimer l'ancienne entité.

## Auto / calendrier

- Auto reste éteint : pas d'événement en cours sur le calendrier / planning.
- Auto ne passe pas en Confort : calendrier doit passer à `on` / `active`.
