"""Chauffage Électrique Fil Pilote FR - Intégration complète."""
from __future__ import annotations
from homeassistant.core import EventStateChangedData
from typing import cast
from datetime import datetime

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from datetime import timedelta

from .const import (
    NO_OPTIONS,
    BUILDING,
    CENTRAL,
    CONF_BUILDING_ENTRY_ID,
    CONF_CENTRAL_ENTRY_ID,
    DOMAIN,
    EVENT_WINDOWS_CHANGED,
    SETPOINT_KEYS,
    SIGNAL_SETPOINTS_UPDATED,
    VERSION,
)
from homeassistant.config_entries import SOURCE_IMPORT

from .building import (
    building_of,
    central_uid,
    default_central,
    get_central_entry,
    iter_room_entries,
    thermostat_of,
)
from .fil_pilote import windows_from_entry
from .frontend import async_register_card
from .temps import clean_setpoints
from .notifications import HeaterNotifier

PLATFORMS = ["climate", "sensor", "binary_sensor"]


@dataclass
class ElectricHeaterData:
    """Données d'exécution d'une entrée (entry.runtime_data)."""

    snapshot: tuple[str, str]
    notifier: HeaterNotifier | None = None


type ElectricHeaterConfigEntry = ConfigEntry[ElectricHeaterData]


def central_runtime(hass: HomeAssistant, central_id: str | None = None) -> ElectricHeaterData | None:
    """Données du thermostat central chargé du bâtiment (central par défaut si central_id est None)."""
    central = get_central_entry(hass, central_id)
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        if central is not None and entry.entry_id == central.entry_id:
            return cast(ElectricHeaterData, entry.runtime_data)
    return None


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """1.1 → 1.2 : chaque pièce est rattachée explicitement au central de son bâtiment.

    Aucun unique_id ni entity_id n'est modifié (historique conservé).
    """
    if entry.version > 1:
        return False  # version future : retour arrière non géré
    if entry.minor_version < 2:
        data = dict(entry.data)
        if data.get("type") != CENTRAL and not data.get(CONF_CENTRAL_ENTRY_ID):
            central = default_central(hass)
            if central is not None:
                data[CONF_CENTRAL_ENTRY_ID] = central.entry_id
        hass.config_entries.async_update_entry(entry, data=data, minor_version=2)
    if entry.minor_version < 3:
        # 1.3 : entrée « bâtiment ». Elle est créée au démarrage du thermostat (_ensure_building),
        # par un flux d'import : rien à modifier ici, aucun identifiant ne change.
        hass.config_entries.async_update_entry(entry, minor_version=3)
    return True


def building_uid_for(central_entry_id: str) -> str:
    """unique_id de l'entrée bâtiment créée pour un thermostat existant (migration)."""
    return f"electric_heater_building_{central_entry_id}"


async def _ensure_building(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Thermostat sans bâtiment (installation existante) : crée son entrée bâtiment.

    Un thermostat dont le bâtiment a été supprimé garde sa référence : rien n'est recréé.
    """
    if entry.data.get(CONF_BUILDING_ENTRY_ID):
        return
    uid = building_uid_for(entry.entry_id)
    if any(e.unique_id == uid for e in hass.config_entries.async_entries(DOMAIN)):
        return
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={"name": entry.title or entry.data.get("name"), CONF_CENTRAL_ENTRY_ID: entry.entry_id},
        )
    )


@callback
def _link_building(hass: HomeAssistant, building: ConfigEntry) -> None:
    """Bâtiment créé par la migration : y rattache le thermostat d'origine et ses radiateurs."""
    central = get_central_entry(hass, building.data.get(CONF_CENTRAL_ENTRY_ID))
    if central is None or central.entry_id != building.data.get(CONF_CENTRAL_ENTRY_ID):
        return
    if central.data.get(CONF_BUILDING_ENTRY_ID):
        return
    hass.config_entries.async_update_entry(
        central, data={**central.data, CONF_BUILDING_ENTRY_ID: building.entry_id}
    )
    for room in iter_room_entries(hass, central.entry_id):
        if not room.data.get(CONF_BUILDING_ENTRY_ID):
            hass.config_entries.async_update_entry(
                room, data={**room.data, CONF_BUILDING_ENTRY_ID: building.entry_id}
            )


def _snapshot(entry: ConfigEntry) -> tuple[str, str]:
    """Configuration hors consignes : seule sa modification recharge l'entrée."""
    # Le rattachement à l'entrée bâtiment seul ne recharge pas (migration sans coupure).
    data = {k: v for k, v in entry.data.items() if k not in SETPOINT_KEYS and k != CONF_BUILDING_ENTRY_ID}
    return (repr(sorted(data.items())), repr(sorted((entry.options or NO_OPTIONS).items())))


def _track_windows(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Relaie les changements des capteurs fenêtre de cette entrée (abonnement ciblé)."""
    windows = windows_from_entry(entry, hass)
    if not windows:
        return

    @callback
    def _on_window(event: Event[EventStateChangedData]) -> None:
        hass.bus.async_fire(EVENT_WINDOWS_CHANGED, {"entity_id": event.data.get("entity_id")})

    entry.async_on_unload(async_track_state_change_event(hass, windows, _on_window))

    async def _resync(_now: datetime | None = None) -> None:
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
    conf = {**entry.data, **(entry.options or NO_OPTIONS)}
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
    if entry.data.get("type") == CENTRAL and (DOMAIN, central_uid(entry)) in device_entry.identifiers:
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
    if entry.data.get("type") == BUILDING:
        # Le bâtiment ne porte aucune entité : un nom, au plus un thermostat, ses radiateurs.
        _link_building(hass, entry)
        _sync_orphan_issues(hass)
        entry.async_on_unload(entry.add_update_listener(_building_updated))
        return True
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
            identifiers={(DOMAIN, central_uid(entry))},
            name=entry.data.get("name", "Chauffage Central"),
            manufacturer="XAV59213",
            model="Thermostat virtuel 6 ordres",
            sw_version=VERSION,
        )
    if entry.data.get("type") == CENTRAL:
        # Le climate d'abord : ses capteurs retrouvent ensuite son entity_id dans le registre.
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS[:1])
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS[1:])
    else:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    if entry.data.get("type") == CENTRAL:
        notifier = HeaterNotifier(hass, entry)
        entry.runtime_data.notifier = notifier
        entry.async_on_unload(notifier.async_stop)
        await notifier.async_start()
        await _ensure_building(hass, entry)
        _adopt_rooms(hass, entry)
        _sync_orphan_issues(hass)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    return True


@callback
def _adopt_rooms(hass: HomeAssistant, central: ConfigEntry) -> None:
    """Nouveau thermostat d'un bâtiment : les radiateurs restés dans ce bâtiment le rejoignent."""
    bid = central.data.get(CONF_BUILDING_ENTRY_ID)
    if not bid:
        return
    for room in iter_room_entries(hass):
        if room.data.get(CONF_BUILDING_ENTRY_ID) == bid and room.data.get(CONF_CENTRAL_ENTRY_ID) != central.entry_id:
            hass.config_entries.async_update_entry(
                room, data={**room.data, CONF_CENTRAL_ENTRY_ID: central.entry_id}
            )


async def _building_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Bâtiment renommé : rien à recharger (les libellés relisent le titre)."""


def _sync_orphan_issues(hass: HomeAssistant) -> None:
    """Réparations : thermostat sans bâtiment, radiateurs d'un bâtiment sans thermostat."""
    for central in [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") == CENTRAL]:
        issue_id = f"thermostat_sans_batiment_{central.entry_id}"
        bid = central.data.get(CONF_BUILDING_ENTRY_ID)
        if bid and building_of(hass, central) is None:
            ir.async_create_issue(
                hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="thermostat_sans_batiment",
                translation_placeholders={"name": central.title},
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)
    for building in [e for e in hass.config_entries.async_entries(DOMAIN) if e.data.get("type") == BUILDING]:
        issue_id = f"batiment_sans_thermostat_{building.entry_id}"
        rooms = [
            r.title for r in hass.config_entries.async_entries(DOMAIN)
            if r.data.get("type") not in (CENTRAL, BUILDING)
            and r.data.get(CONF_BUILDING_ENTRY_ID) == building.entry_id
        ]
        if rooms and thermostat_of(hass, building.entry_id) is None:
            ir.async_create_issue(
                hass, DOMAIN, issue_id, is_fixable=False, severity=ir.IssueSeverity.WARNING,
                translation_key="batiment_sans_thermostat",
                translation_placeholders={"name": building.title, "rooms": ", ".join(rooms)},
            )
        else:
            ir.async_delete_issue(hass, DOMAIN, issue_id)


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Suppression d'un bâtiment ou d'un thermostat non vide : rien n'est supprimé en cascade.

    Le thermostat et les radiateurs restants continuent de fonctionner et une réparation
    indique comment les rattacher (reconfiguration du thermostat ou des radiateurs).
    """
    if entry.data.get("type") in (BUILDING, CENTRAL):
        _sync_orphan_issues(hass)
    ir.async_delete_issue(hass, DOMAIN, f"thermostat_sans_batiment_{entry.entry_id}")
    ir.async_delete_issue(hass, DOMAIN, f"batiment_sans_thermostat_{entry.entry_id}")


async def async_unload_entry(hass: HomeAssistant, entry: ElectricHeaterConfigEntry) -> bool:
    if entry.data.get("type") == BUILDING:
        return True
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for key in _CHECKED_SOURCES:
            ir.async_delete_issue(hass, DOMAIN, f"missing_{key}_{entry.entry_id}")
    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ElectricHeaterConfigEntry) -> None:
    _sync_orphan_issues(hass)
    data = getattr(entry, "runtime_data", None)
    if isinstance(data, ElectricHeaterData) and data.snapshot == _snapshot(entry):
        # Seules les consignes ont changé : pas de rechargement, le thermostat les relit.
        async_dispatcher_send(hass, SIGNAL_SETPOINTS_UPDATED.format(entry.entry_id))
        return
    await hass.config_entries.async_reload(entry.entry_id)
