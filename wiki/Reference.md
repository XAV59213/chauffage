# Référence

[![Quality Scale](https://img.shields.io/badge/Quality%20Scale-Platinum-E5E4E2.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)


## Mise à jour des données
L'intégration est locale (`calculated`) : aucune interrogation d'un cloud.
- Réaction immédiate à chaque changement d'état des sondes, capteurs de fenêtre/présence et sélecteurs fil pilote.
- Resynchronisation des ordres fil pilote toutes les 60 s ; contrôle de sécurité (sonde/relais indisponible) toutes les 60 s.
- Statistiques et capteurs de consommation : toutes les minutes, remise à zéro à minuit.
- Saison de chauffe : vérifiée toutes les 15 min.

## Appareils compatibles
Tout radiateur piloté par une entité `select` fil pilote dans Home Assistant, par exemple :
- Module NodOn SIN-4-FP-21 (Zigbee, via ZHA ou Zigbee2MQTT)
- Modules fil pilote Legrand et Delta Dore exposés en `select`
- Sondes de température Zigbee pour chaque pièce

## Cas d'usage
- Un thermostat central qui commande tous les radiateurs fil pilote de la maison.
- Un thermostat par pièce avec consigne Confort/Éco, coupure fenêtre ouverte et absence.
- Calendrier de chauffe et suivi de consommation par radiateur.

## Limitations connues
- Le thermostat central contrôle ; les radiateurs suivent ses ordres et ne doivent pas être commandés en direct par une autre automatisation.
- Le fil pilote ne règle pas une température au radiateur : la régulation se fait par hystérésis sur la sonde de pièce.
- Sonde ou module indisponible : après 120 s de grâce au démarrage, le radiateur passe en Hors-gel par sécurité.
- Un client externe (assistant vocal, API) peut changer le mode du central ; l'intégration le journalise mais ne le bloque pas.

## Suppression
1. Paramètres → Appareils et services → Chauffage Électrique Fil Pilote FR → menu ⋮ → Supprimer, pour chaque entrée (pièces puis central).
2. Dans HACS, désinstaller l'intégration, puis redémarrer Home Assistant.
3. Retirer la carte Lovelace du tableau de bord si elle y est encore.
Les radiateurs gardent leur dernier mode fil pilote ; remettez-les manuellement dans le mode voulu.
