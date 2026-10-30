"""Enregistre la carte Lovelace « Chauffage Fil Pilote » livrée avec l'intégration."""
from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from ..const import CARD_FILENAME, CARD_URL_BASE, VERSION

_LOGGER = logging.getLogger(__name__)


async def async_register_card(hass: HomeAssistant) -> None:
    """Sert le JS depuis le paquet de l'intégration et le charge dans le frontend.

    Aucune copie dans www, aucune ressource Lovelace créée : le paramètre ?v=
    force le rechargement à chaque nouvelle version.
    """
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL_BASE, str(Path(__file__).parent), False)]
        )
    except RuntimeError:
        _LOGGER.debug("Chemin statique déjà enregistré : %s", CARD_URL_BASE)
    add_extra_js_url(hass, f"{CARD_URL_BASE}/{CARD_FILENAME}?v={VERSION}")
