# Notifications

🇫🇷 Français · 🇬🇧 [English](Notifications-EN.md)

Activées par défaut (option **Notifications** du thermostat central). Notification Home Assistant + service `notify` optionnel (ex. application mobile).

| Événement | Message |
|---|---|
| Sonde de pièce indisponible | 🔋 Sonde KO – remplacer la pile (radiateur en Hors-gel) |
| Pile détecteur fenêtre ≤ 20 % | 🔋 Pile faible du détecteur |
| Fenêtre ouverte (après le délai) | 🪟 Fenêtre ouverte |
| Démarrage terminé (après 3 min) | ✅ Chauffage opérationnel (+ problèmes en cours) |
| Fenêtre ouverte et personne à la maison (2 min) | 🚪 Personne à la maison et fenêtre ouverte |
| Retour à la normale | ✅ … OK |

- Une seule notification par problème, retirée au retour à la normale.
- Au redémarrage : 3 min de grâce, puis un problème doit durer 2 min avant d'alerter.
