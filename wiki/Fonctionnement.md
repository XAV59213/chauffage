# Fonctionnement

## Auto

La consigne reste visible et réglable. Elle part vers les radiateurs.

| Condition | Ordre |
|---|---|
| Calendrier actif + quelqu'un à la maison | Confort (ou dernier Confort -1 / -2) |
| Calendrier inactif | Mode configuré (Hors-gel par défaut pour une nouvelle installation) |
| Calendrier indisponible | Dernier mode gardé (Eco si aucun) |
| Nombre famille home = 0 | Eco |
| Mode choisi à la main | Gardé jusqu'au prochain changement du calendrier |

Priorités : thermostat Éteint > fenêtre (après 45 s) > mode choisi à la main > calendrier inactif > maison vide > confort.

La météo est seulement **affichée** (capteur Température extérieure) : elle ne change pas encore les ordres.

Un mode choisi à la main en Auto (ex. Hors-gel pour des vacances) est **maintenu** jusqu'au prochain changement du calendrier, même après un redémarrage.

## Chauffage forcé

Le mode et la consigne choisis sont envoyés **tels quels** à tous les radiateurs.
Calendrier, présence et écart de température ne changent plus l'ordre.

## Fenêtres

| Où | Effet |
|---|---|
| Fenêtre d'une pièce | **Ce** radiateur passe dans le mode fenêtre après le délai (45 s par défaut) |
| Baie / portes / fenêtre du salon (thermostat) | **Tous** les radiateurs passent dans le mode fenêtre après le délai |
| Refermée avant le délai | Rien ne change (l'état affiché passe quand même à « Ouverte » dès la détection) |
| Refermée après | Reprise immédiate du mode normal |

Mode fenêtre : **Hors-gel** par défaut (réglable : Hors-gel, Eco ou Arrêt). Il ne fait que baisser l'ordre : un radiateur à l'Arrêt reste à l'Arrêt.

Capteur affiché : **État fenêtre** (Ouverte / Fermée).

## Présence

Un seul capteur source : celui choisi sur le thermostat (**Nombre famille home**).

Capteur **Présents** : `Personne` / `1 personne` / `2 personnes`, avec les prénoms (attributs `personnes`, `noms`) des personnes suivies à la maison.

## Régulation par sonde

| Situation | Ordre fil pilote |
|---|---|
| Pièce ≥ consigne | Ordre réglable (Eco par défaut, ou Hors-gel / Arrêt) |
| Pièce ≤ consigne − hystérésis | Ordre de base (jamais plus chaud) |
| Entre les deux | Dernier ordre conservé |
| Mode Eco / absence | Reste Eco, jamais remonté en Confort |
| Sonde indisponible | **Hors-gel** par sécurité + alerte « remplacer la pile de la sonde » |

## Capteurs résumé

`Fenêtres ouvertes`, `Sondes KO`, `Alerte pile sonde`, `Présents` sur le thermostat central.

## Consignes

Attributs du thermostat et des radiateurs :

- `consigne` : valeur actuelle
- `consigne_mode` : nom du mode
- `consignes` : Confort, Confort -1, Confort -2, Eco, Hors-gel

En Auto, le curseur règle la consigne du mode en cours et la pousse aux radiateurs.

## Seuils de température

| Mode | Bande |
|---|---|
| Confort / -1 / -2 | 0,3 °C |
| Eco | 0,5 °C |
| Hors-gel | 1,0 °C |

Chauffe sous `consigne - bande`, coupe à la consigne.

## Radiateur réglé à la main

Changer le mode ou la consigne d'**un** radiateur le détache du thermostat : le réglage est gardé (aussi après un redémarrage).
Pour qu'il suive de nouveau le thermostat : mettre le radiateur en **Auto**, ou changer le mode du thermostat virtuel (tous les radiateurs le suivent alors).

## Relais

- Un ordre n'est envoyé que s'il change (moins de trafic Zigbee).
- Relais de retour après une coupure, ou changé à la main : l'ordre attendu est renvoyé (après 15 s s'il diffère).
- Toutes les 10 min, l'ordre attendu est renvoyé à chaque relais.
- Un échec d'envoi est écrit dans le journal.
