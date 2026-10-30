# Carte Lovelace « Chauffage Fil Pilote »

Livrée avec l'intégration (depuis 3.1.7), rien à installer en plus.

```yaml
type: custom:electric-heater-card
```

Tableau de bord → **Modifier** → **Ajouter une carte** → **Chauffage Fil Pilote**.

![Carte](../docs/images/carte-chauffage.jpg)

## Ce qu'elle affiche (découverte automatique)

- Thermostat central : température, consigne, mode, chauffe / inactif.
- Pastilles : fenêtres ouvertes, sondes KO, présents (avec prénoms), piles.
- Chaque radiateur : ordre fil pilote, température / consigne, fenêtre, sonde KO.
- **Détecteurs de fenêtre** : Ouvert / Fermé + pile (%). Détecteurs configurés sur le thermostat et chaque radiateur, plus ceux de la même pièce HA.
- **Piles des sondes de température** de chaque radiateur.

## Options (repli)

`titre`, `central`, `radiateurs`, `fenetres`, `sondes_ko`, `alerte_pile`, `presents`, `detecteurs_fenetre`, `sondes`, `exclure_personnes`.

Si la carte n'apparaît pas : Paramètres → Tableaux de bord → Ressources → `/electric_heater/electric-heater-card.js` (Module JavaScript).
