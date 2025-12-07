"""Chauffage Électrique Fil Pilote Français
Auteur : XAV59213
Compatible SIN-4-FP-21 + TH01 + Zigbee2MQTT
100 % local - Décembre 2025
"""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

PLATFORMS = ["climate"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
