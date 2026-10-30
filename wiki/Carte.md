# Carte Lovelace « Chauffage Fil Pilote »

🇫🇷 Français · 🇬🇧 [English](Carte-EN.md)

Livrée avec l'intégration (depuis 3.1.7), rien à installer en plus.

```yaml
type: custom:electric-heater-card
```

Tableau de bord → **Modifier** → **Ajouter une carte** → **Chauffage Fil Pilote**.

![Carte](../docs/images/carte-chauffage.jpg)

## Ce qu'elle affiche (découverte automatique)

- Thermostat central : température, consigne, mode, chauffe / inactif.
- Pastilles : fenêtres ouvertes, sondes KO, calendrier chauffage actif / inactif, présents (avec prénoms), piles.
- Chaque radiateur : ordre fil pilote, température / consigne, fenêtre, sonde KO.
- **Détecteurs de fenêtre** : Ouvert / Fermé + pile (%). Détecteurs configurés sur le thermostat et chaque radiateur, plus ceux de la même pièce HA.
- **Consommation du jour par radiateur** (temps + kWh) et total.
- **Piles des sondes de température** de chaque radiateur.

- **Graphique** : courbes de température de tous les radiateurs (24 h par défaut).

## Options (repli)

`titre`, `central`, `radiateurs`, `fenetres`, `sondes_ko`, `alerte_pile`, `presents`, `detecteurs_fenetre`, `sondes`, `exclure_personnes`, `graphique` (false pour masquer), `heures` (durée du graphique, 24 par défaut).

Si la carte n'apparaît pas : Paramètres → Tableaux de bord → Ressources → `/electric_heater/electric-heater-card.js` (Module JavaScript).
