"""Diagnostics du chauffage électrique fil pilote."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_NOTIFY_SERVICE, VERSION

TO_REDACT = {CONF_NOTIFY_SERVICE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Retourne les diagnostics d'une entrée (configuration + état des entités)."""
    registry = er.async_get(hass)
    entities = []
    for ent in er.async_entries_for_config_entry(registry, entry.entry_id):
        state = hass.states.get(ent.entity_id)
        entities.append(
            {
                "entity_id": ent.entity_id,
                "unique_id": ent.unique_id,
                "disabled": ent.disabled_by is not None,
                "state": state.state if state else None,
                "attributes": dict(state.attributes) if state else None,
            }
        )
    return {
        "version": VERSION,
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "entities": entities,
    }
