"""Chauffage Électrique Fil Pilote FR - Intégration complète."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CENTRAL, DOMAIN, EVENT_WINDOWS_CHANGED, VERSION
from .fil_pilote import all_configured_windows

PLATFORMS = ["climate", "sensor", "binary_sensor"]


def _ensure_window_bus(hass: HomeAssistant) -> None:
    store = hass.data.setdefault(DOMAIN, {})
    if store.get("window_bus"):
        return

    @callback
    def _on_state(event) -> None:
        entity_id = event.data.get("entity_id")
        if not entity_id:
            return
        if entity_id in all_configured_windows(hass):
            hass.bus.async_fire(EVENT_WINDOWS_CHANGED, {"entity_id": entity_id})

    store["window_bus"] = hass.bus.async_listen("state_changed", _on_state)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _ensure_window_bus(hass)
    if entry.data.get("type") == CENTRAL:
        device_registry = dr.async_get(hass)
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, "electric_heater_central")},
            name=entry.data.get("name", "Chauffage Central"),
            manufacturer="XAV59213",
            model="Thermostat virtuel 6 ordres",
            sw_version=VERSION,
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
