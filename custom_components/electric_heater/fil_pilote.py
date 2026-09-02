"""Application des ordres fil pilote sur un select ou un climate HA."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    FIL_PILOTE_ALIASES,
    PRESET_OFF,
)

_LOGGER = logging.getLogger(__name__)


def resolve_fil_pilote_option(preset: str, available: list[str] | None) -> str | None:
    """Trouve l'option réelle exposée par l'entité (Z2M, ZHA, Legrand…)."""
    aliases = FIL_PILOTE_ALIASES.get(preset, [preset])
    if not available:
        return aliases[0]

    available_map = {opt.casefold(): opt for opt in available}
    for alias in aliases:
        if alias.casefold() in available_map:
            return available_map[alias.casefold()]

    # Dernier recours : correspondance partielle (ex. "Comfort -1")
    for alias in aliases:
        needle = alias.replace("_", " ").replace("-", " ").casefold()
        for key, original in available_map.items():
            cleaned = key.replace("_", " ").replace("-", " ")
            if needle == cleaned or needle in cleaned:
                return original
    return None


async def apply_fil_pilote(hass: HomeAssistant, entity_id: str | None, preset: str) -> None:
    """Envoie l'ordre fil pilote à un select.* ou climate.*"""
    if not entity_id:
        return

    state = hass.states.get(entity_id)
    if state is None:
        _LOGGER.warning("Entité fil pilote introuvable: %s", entity_id)
        return

    domain = entity_id.split(".", 1)[0]
    option = resolve_fil_pilote_option(
        preset,
        state.attributes.get("options") or state.attributes.get("preset_modes"),
    )
    if option is None:
        _LOGGER.warning(
            "Aucun mode fil pilote correspondant à %s sur %s (dispo: %s)",
            preset,
            entity_id,
            state.attributes.get("options") or state.attributes.get("preset_modes"),
        )
        return

    try:
        if domain == "select":
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": entity_id, "option": option},
                blocking=False,
            )
        elif domain == "climate":
            data: dict[str, Any] = {"entity_id": entity_id}
            if preset == PRESET_OFF:
                await hass.services.async_call(
                    "climate",
                    "set_hvac_mode",
                    {**data, "hvac_mode": "off"},
                    blocking=False,
                )
            else:
                if state.state == "off":
                    await hass.services.async_call(
                        "climate",
                        "set_hvac_mode",
                        {**data, "hvac_mode": "heat"},
                        blocking=False,
                    )
                await hass.services.async_call(
                    "climate",
                    "set_preset_mode",
                    {**data, "preset_mode": option},
                    blocking=False,
                )
        else:
            _LOGGER.warning("Type d'entité fil pilote non supporté: %s", entity_id)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Impossible d'appliquer le mode %s sur %s", preset, entity_id)
