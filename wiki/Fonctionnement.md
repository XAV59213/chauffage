# Fonctionnement

## Auto

La consigne reste visible et réglable. Elle part vers les radiateurs.

| Condition | Ordre |
|---|---|
| Calendrier actif + quelqu'un à la maison | Confort (ou dernier Confort -1 / -2) |
| Calendrier inactif | Mode configuré (souvent Arrêt) |
| Nombre famille home = 0 | Eco |
| Extérieur ≥ 15 °C | Confort -1 |
| Extérieur ≥ 18 °C | Confort -2 |

Priorités : fenêtre salon (après 45 s) > calendrier off > maison vide > météo > confort.

## Chauffage forcé

Le mode et la consigne choisis sont envoyés **tels quels** à tous les radiateurs.
Calendrier, présence et écart de température ne changent plus l'ordre.

## Fenêtres

| Où | Effet |
|---|---|
| Fenêtre d'une pièce | Coupe **ce** radiateur après 45 s |
| Baie / portes / fenêtre du salon (thermostat) | Thermostat Auto → Off, tous les radiateurs |
| Refermée avant 45 s | Rien n'est coupé |
| Refermée après coupure | Reprise immédiate |

Capteur affiché : **État fenêtre** (Ouverte / Fermée).

## Présence

Un seul capteur source : celui choisi sur le thermostat (**Nombre famille home**).

Capteur **Présents** : `Personne` / `1 personne` / `2 personnes`.

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
