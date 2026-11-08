"""Chauffage Électrique Fil Pilote FR - Intégration complète."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from datetime import timedelta

from .const import (
    CENTRAL,
    DOMAIN,
    EVENT_WINDOWS_CHANGED,
    SETPOINT_KEYS,
    SIGNAL_SETPOINTS_UPDATED,
    VERSION,
)
from .fil_pilote import windows_from_entry
from .frontend import async_register_card
from .temps import clean_setpoints
from .notifications import HeaterNotifier

PLATFORMS = ["climate", "sensor", "binary_sensor"]


@dataclass
class ElectricHeaterData:
    """Données d'exécution d'une entrée (entry.runtime_data)."""

    snapshot: tuple
    notifier: HeaterNotifier | None = None


type ElectricHeaterConfigEntry = ConfigEntry[ElectricHeaterData]


def central_runtime(hass: HomeAssistant) -> ElectricHeaterData | None:
    """Données du thermostat central chargé (recherche inter-entrées)."""
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if entry.data.get("type") == CENTRAL:
            return entry.runtime_data
    return None


def _snapshot(entry: ConfigEntry) -> tuple:
    """Configuration hors consignes : seule sa modification recharge l'entrée."""
    data = {k: v for k, v in entry.data.items() if k not in SETPOINT_KEYS}
    return (repr(sorted(data.items())), repr(sorted((entry.options or {}).items())))


def _track_windows(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Relaie les changements des capteurs fenêtre de cette entrée (abonnement ciblé)."""
    windows = windows_from_entry(entry, hass)
    if not windows:
        return

    @callback
    def _on_window(event: Event) -> None:
        hass.bus.async_fire(EVENT_WINDOWS_CHANGED, {"entity_id": event.data.get("entity_id")})

    entry.async_on_unload(async_track_state_change_event(hass, windows, _on_window))

    async def _resync(_now=None) -> None:
        """Toutes les 60 s : relance les détecteurs indisponibles et réévalue les fenêtres."""
        stale = [
            eid for eid in windows
            if (st := hass.states.get(eid)) is None or st.state in ("unknown", "unavailable")
        ]
        if stale:
            try:
                await hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": stale}, blocking=False
                )
            except Exception:  # noqa: BLE001 - capteur radio non interrogeable
                pass
        hass.bus.async_fire(EVENT_WINDOWS_CHANGED, {"entity_id": None, "resync": True})

    entry.async_on_unload(async_track_time_interval(hass, _resync, timedelta(seconds=60)))


_CHECKED_SOURCES = ("temperature_sensor", "fil_pilote_select")


def _check_sources(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Crée/supprime un repair si une entité source configurée n'existe plus."""
    registry = er.async_get(hass)
    conf = {**entry.data, **(entry.options or {})}
    for key in _CHECKED_SOURCES:
        entity_id = conf.get(key)
        issue_id = f"missing_{key}_{entry.entry_id}"
        if not entity_id or not isinstance(entity_id, str):
            ir.async_delete_issue(hass, DOMAIN, issue_id)
            continue
        if registry.async_get(entity_id) is None and hass.states.get(entity_id) is None:
            ir.async_create_issue(
                hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_entity",
                translation_placeholders={"entity_id": entity_id, "name": entry.title},
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: ConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Autorise la suppression manuelle d'un appareil obsolète (pas le central actif)."""
    if (DOMAIN, "electric_heater_central") in device_entry.identifiers and entry.data.get("type") == CENTRAL:
        return False
    registry = er.async_get(hass)
    return not any(
        ent.config_entry_id == entry.entry_id
        for ent in er.async_entries_for_device(registry, device_entry.id)
    )


async def async_setup_entry(hass: HomeAssistant, entry: ElectricHeaterConfigEntry) -> bool:
    # Nettoie les consignes déjà enregistrées (ex. 20.199999999999998 -> 20.2).
    if (cleaned := clean_setpoints(dict(entry.data))) is not None:
        hass.config_entries.async_update_entry(entry, data=cleaned)
    entry.runtime_data = ElectricHeaterData(snapshot=_snapshot(entry))
    # Carte Lovelace : ressource globale au domaine, enregistrée une seule fois.
    domain_data = hass.data.setdefault(DOMAIN, {})
    if not domain_data.get("_card_registered"):
        await async_register_card(hass)
        domain_data["_card_registered"] = True
    _track_windows(hass, entry)
    _check_sources(hass, entry)
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
    if entry.data.get("type") == CENTRAL:
        notifier = HeaterNotifier(hass, entry)
        entry.runtime_data.notifier = notifier
        entry.async_on_unload(notifier.async_stop)
        await notifier.async_start()
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ElectricHeaterConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for key in _CHECKED_SOURCES:
            ir.async_delete_issue(hass, DOMAIN, f"missing_{key}_{entry.entry_id}")
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ElectricHeaterConfigEntry) -> None:
    data = getattr(entry, "runtime_data", None)
    if isinstance(data, ElectricHeaterData) and data.snapshot == _snapshot(entry):
        # Seules les consignes ont changé : pas de rechargement, le thermostat les relit.
        async_dispatcher_send(hass, SIGNAL_SETPOINTS_UPDATED.format(entry.entry_id))
        return
    await hass.config_entries.async_reload(entry.entry_id)
