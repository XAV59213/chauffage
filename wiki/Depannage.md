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

- État fenêtre pas à jour : vérifier l'entity_id dans Configurer (ex. `binary_sensor.fenetre_papa_3`).
- Doublon Fenêtre ouverte : ancienne entité, à supprimer dans Réglages → Entités.
- Coupure trop rapide : délai de 45 s avant Off.

## Présence / Eco

- Eco alors que quelqu'un est là : le thermostat doit utiliser **Nombre famille home**, pas `zone.home`.
- Doublon Nombre de personnes : garder **Présents**, supprimer l'ancienne entité.

## Auto / calendrier

- Auto reste éteint : pas d'événement en cours sur le calendrier / planning.
- Auto ne passe pas en Confort : calendrier doit passer à `on` / `active`.
