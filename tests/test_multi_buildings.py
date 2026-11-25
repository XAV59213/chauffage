"""Multi-bâtiments (PR A) : identifiants figés, migration, deux bâtiments indépendants."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.components.sensor import DATA_COMPONENT as SENSOR
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater import async_migrate_entry, central_runtime
from custom_components.electric_heater import building, fil_pilote, safety, season, stats
from custom_components.electric_heater.const import CENTRAL, DOMAIN, ROOM

from .test_init import CENTRAL_DATA

SEL_A = "select.salon_pilot_wire_mode"
SEL_B = "select.gite_pilot_wire_mode"
OPTIONS = ["comfort", "eco", "anti_freeze", "off", "comfort_-1", "comfort_-2"]

# Installation à un seul bâtiment : (unique_id, entity_id) relevés sur main (v3.1.77),
# plus les 4 nouveaux totaux « toutes dépendances ». Rien d'autre ne doit bouger.
FROZEN = [
    ("electric_heater_central", "climate.electric_heater_central"),
    ("electric_heater_central_alerte_instable", "binary_sensor.thermostat_virtuel_detecteur_fenetre_instable"),
    ("electric_heater_central_alerte_pile", "binary_sensor.thermostat_virtuel_sensor_battery_alert"),
    ("electric_heater_central_alerte_surchauffe", "binary_sensor.thermostat_virtuel_alerte_surchauffe"),
    ("electric_heater_central_calendrier", "binary_sensor.thermostat_virtuel_calendrier_chauffage"),
    ("electric_heater_central_calendrier_active", "binary_sensor.thermostat_virtuel_calendrier_chauffage_active"),
    ("electric_heater_central_chauffage_actif", "binary_sensor.thermostat_virtuel_chauffage_actif"),
    ("electric_heater_central_chauffe_jour", "sensor.thermostat_virtuel_temps_de_chauffe_maison_aujourd_hui"),
    ("electric_heater_central_chauffe_total", "sensor.thermostat_virtuel_temps_de_chauffe_maison_total"),
    ("electric_heater_central_compteurs_jour", "sensor.thermostat_virtuel_consommation_compteurs_aujourd_hui"),
    ("electric_heater_central_conso_compteurs", "sensor.thermostat_virtuel_consommation_radiateurs_compteurs"),
    ("electric_heater_central_conso_jour", "sensor.thermostat_virtuel_consommation_maison_aujourd_hui"),
    ("electric_heater_central_conso_total", "sensor.thermostat_virtuel_consommation_maison_totale"),
    ("electric_heater_central_dernier_changement", "sensor.thermostat_virtuel_dernier_changement"),
    ("electric_heater_central_derniere_decision", "sensor.thermostat_virtuel_derniere_decision"),
    ("electric_heater_central_etat_fenetre", "sensor.thermostat_virtuel_etat_fenetre"),
    ("electric_heater_central_exterieur", "sensor.thermostat_virtuel_temperature_exterieure"),
    ("electric_heater_central_fenetres_ouvertes", "sensor.thermostat_virtuel_open_windows"),
    ("electric_heater_central_mode_eco_auto", "binary_sensor.thermostat_virtuel_mode_eco_auto"),
    ("electric_heater_central_presence", "binary_sensor.thermostat_virtuel_presence"),
    ("electric_heater_central_presents", "sensor.thermostat_virtuel_presents"),
    ("electric_heater_central_saison_chauffe", "binary_sensor.thermostat_virtuel_saison_de_chauffe"),
    ("electric_heater_central_sondes_ko", "sensor.thermostat_virtuel_failed_sensors"),
    ("electric_heater_central_temperature", "sensor.thermostat_virtuel_temperature_centrale"),
    ("electric_heater_room_ROOMID", "climate.chambre_chauffage_chambre"),
    ("electric_heater_room_ROOMID_alerte_instable", "binary_sensor.chambre_detecteur_fenetre_instable"),
    ("electric_heater_room_ROOMID_alerte_surchauffe", "binary_sensor.chambre_alerte_surchauffe"),
    ("electric_heater_room_ROOMID_chauffe_jour", "sensor.chambre_temps_de_chauffe_aujourd_hui"),
    ("electric_heater_room_ROOMID_chauffe_total", "sensor.chambre_temps_de_chauffe_total"),
    ("electric_heater_room_ROOMID_compteur_jour", "sensor.chambre_consommation_compteur_aujourd_hui"),
    ("electric_heater_room_ROOMID_conso_jour", "sensor.chambre_consommation_aujourd_hui"),
    ("electric_heater_room_ROOMID_conso_total", "sensor.chambre_consommation_totale"),
    ("electric_heater_room_ROOMID_derniere_decision", "sensor.chambre_derniere_decision"),
    ("electric_heater_room_ROOMID_etat_fenetre", "sensor.chambre_etat_fenetre"),
    ("electric_heater_room_ROOMID_securite_fenetre", "binary_sensor.chambre_securite_fenetre"),
    ("electric_heater_room_ROOMID_temperature", "sensor.chambre_temperature_piece"),
]
GLOBAL = [
    ("electric_heater_global_chauffe_jour", "sensor.thermostat_virtuel_temps_de_chauffe_toutes_dependances_aujourd_hui"),
    ("electric_heater_global_chauffe_total", "sensor.thermostat_virtuel_temps_de_chauffe_toutes_dependances_total"),
    ("electric_heater_global_conso_jour", "sensor.thermostat_virtuel_consommation_toutes_dependances_aujourd_hui"),
    ("electric_heater_global_conso_total", "sensor.thermostat_virtuel_consommation_toutes_dependances_totale"),
]


@pytest.fixture(autouse=True)
def no_grace():
    with patch(
        "custom_components.electric_heater.climate.RoomThermostat._in_startup_grace",
        return_value=False,
    ):
        yield


def _relays(hass: HomeAssistant, *selects: str) -> list:
    calls: list = []

    async def _select(call):
        calls.append(call)
        eid = call.data["entity_id"]
        for e in eid if isinstance(eid, list) else [eid]:
            hass.states.async_set(e, call.data["option"], {"options": OPTIONS})

    hass.services.async_register("select", "select_option", _select)
    for sel in selects:
        hass.states.async_set(sel, "off", {"options": OPTIONS})
    return calls


def _dev(devices, ident):
    entries = {d.id: d for e in ("CENTRALID", "ROOMID", "BATA", "BATB", "ROOMA", "ROOMB")
               for d in dr.async_entries_for_config_entry(devices, e)}
    return next(d for d in entries.values() if ident in d.identifiers)


def _last(calls: list, select: str) -> str | None:
    found = [c.data["option"] for c in calls if c.data["entity_id"] in (select, [select])]
    return found[-1] if found else None


async def _svc(hass, service, eid, **data):
    await hass.services.async_call("climate", service, {"entity_id": eid, **data}, blocking=True)
    await hass.async_block_till_done()


async def _later(hass, seconds):
    from datetime import timedelta

    from homeassistant.util import dt as dt_util
    from pytest_homeassistant_custom_component.common import async_fire_time_changed

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await hass.async_block_till_done()


async def test_single_building_ids_frozen(hass: HomeAssistant) -> None:
    """Un seul bâtiment : unique_id, entity_id et appareils strictement inchangés."""
    hass.states.async_set("sensor.salon_temp", "19.0")
    hass.states.async_set("sensor.chambre_temp", "18.0")
    hass.states.async_set("binary_sensor.fenetre_chambre", "off")
    hass.states.async_set("select.chambre_pilot_wire_mode", "off", {"options": OPTIONS})
    central = MockConfigEntry(domain=DOMAIN, data=CENTRAL_DATA, unique_id="electric_heater_central",
                              title="Thermostat virtuel", entry_id="CENTRALID")
    central.add_to_hass(hass)
    room = MockConfigEntry(
        domain=DOMAIN, title="Chambre", entry_id="ROOMID",
        unique_id="electric_heater_room_select.chambre_pilot_wire_mode",
        data={"type": ROOM, "name": "Chambre", "fil_pilote_select": "select.chambre_pilot_wire_mode",
              "temperature_sensor": "sensor.chambre_temp", "window_sensors": "binary_sensor.fenetre_chambre"},
    )
    room.add_to_hass(hass)
    assert await hass.config_entries.async_setup(central.entry_id)
    await hass.async_block_till_done()
    reg = er.async_get(hass)
    ours = sorted((e.unique_id, e.entity_id) for e in reg.entities.values() if e.platform == DOMAIN)
    assert ours == sorted(FROZEN + GLOBAL)
    devices = dr.async_get(hass)
    central_dev = _dev(devices, (DOMAIN, "electric_heater_central"))
    room_dev = _dev(devices, (DOMAIN, "room_ROOMID"))
    assert central_dev is not None and room_dev is not None
    assert room_dev.via_device_id == central_dev.id
    # Migration 1.1 → 1.2 : la pièce est rattachée au central, sans autre changement.
    assert room.minor_version == 2 and room.data["central_entry_id"] == "CENTRALID"


async def test_migration(hass: HomeAssistant) -> None:
    central = MockConfigEntry(domain=DOMAIN, data=CENTRAL_DATA, unique_id="electric_heater_central")
    central.add_to_hass(hass)
    room = MockConfigEntry(domain=DOMAIN, data={"type": ROOM, "name": "R"}, minor_version=1)
    room.add_to_hass(hass)
    assert await async_migrate_entry(hass, room)
    assert room.minor_version == 2 and room.data["central_entry_id"] == central.entry_id
    assert await async_migrate_entry(hass, central)
    assert "central_entry_id" not in central.data and central.minor_version == 2
    # Déjà rattachée : rien ne change
    other = MockConfigEntry(domain=DOMAIN, data={"type": ROOM, "name": "O", "central_entry_id": "X"}, minor_version=1)
    other.add_to_hass(hass)
    assert await async_migrate_entry(hass, other)
    assert other.data["central_entry_id"] == "X"
    future = MockConfigEntry(domain=DOMAIN, data={"type": ROOM}, version=2)
    assert not await async_migrate_entry(hass, future)


async def _two_buildings(hass: HomeAssistant, central_b_extra=None, room_b_extra=None):
    calls = _relays(hass, SEL_A, SEL_B)
    hass.states.async_set("sensor.salon_temp", "16.0")
    hass.states.async_set("sensor.gite_temp", "16.0")
    hass.states.async_set("sensor.ref_gite", "16.0")
    a = MockConfigEntry(domain=DOMAIN, data={**CENTRAL_DATA, "name": "Maison"}, title="Maison",
                        unique_id="electric_heater_central", entry_id="BATA")
    a.add_to_hass(hass)
    b = MockConfigEntry(
        domain=DOMAIN, title="Gîte", entry_id="BATB", unique_id="electric_heater_central_BATB",
        data={**CENTRAL_DATA, "name": "Gîte", "temperature_sensor": "sensor.ref_gite",
              "notify_service": [], **(central_b_extra or {})},
    )
    b.add_to_hass(hass)
    ra = MockConfigEntry(domain=DOMAIN, title="Salon", entry_id="ROOMA", unique_id=f"electric_heater_room_{SEL_A}",
                         data={"type": ROOM, "name": "Salon", "fil_pilote_select": SEL_A,
                               "temperature_sensor": "sensor.salon_temp", "central_entry_id": "BATA",
                               "power": 1000})
    ra.add_to_hass(hass)
    rb = MockConfigEntry(domain=DOMAIN, title="Salon", entry_id="ROOMB", unique_id=f"electric_heater_room_{SEL_B}",
                         data={"type": ROOM, "name": "Salon", "fil_pilote_select": SEL_B,
                               "temperature_sensor": "sensor.gite_temp", "central_entry_id": "BATB",
                               "power": 2000, **(room_b_extra or {})})
    rb.add_to_hass(hass)
    assert await hass.config_entries.async_setup(a.entry_id)
    await hass.async_block_till_done()
    cid_a = building.central_entity_id(hass, "BATA")
    cid_b = building.central_entity_id(hass, "BATB")
    assert cid_a == "climate.electric_heater_central" and cid_b and cid_b != cid_a
    return calls, cid_a, cid_b


async def test_two_buildings_ids_and_devices(hass: HomeAssistant) -> None:
    await _two_buildings(hass)
    reg = er.async_get(hass)
    uids = {e.unique_id for e in reg.entities.values() if e.platform == DOMAIN}
    assert "electric_heater_central" in uids and "electric_heater_central_BATB" in uids
    assert "electric_heater_central_BATB_conso_jour" in uids
    assert "electric_heater_central_BATB_alerte_surchauffe" in uids
    assert "electric_heater_central_BATB_etat_fenetre" in uids
    # Total global : une seule fois, sur le central historique
    glob = [e for e in reg.entities.values() if e.unique_id == "electric_heater_global_conso_jour"]
    assert len(glob) == 1 and glob[0].config_entry_id == "BATA"
    devices = dr.async_get(hass)
    dev_a = _dev(devices, (DOMAIN, "electric_heater_central"))
    dev_b = _dev(devices, (DOMAIN, "electric_heater_central_BATB"))
    assert _dev(devices, (DOMAIN, "room_ROOMA")).via_device_id == dev_a.id
    assert _dev(devices, (DOMAIN, "room_ROOMB")).via_device_id == dev_b.id
    assert central_runtime(hass, "BATB") is hass.config_entries.async_get_entry("BATB").runtime_data
    assert [e.entry_id for e in building.iter_room_entries(hass, "BATB")] == ["ROOMB"]
    assert building.default_central(hass).entry_id == "BATA"
    # Notifications : identifiants préfixés pour le 2e bâtiment, nom du bâtiment dans le message
    notifier_b = hass.config_entries.async_get_entry("BATB").runtime_data.notifier
    notifier_a = hass.config_entries.async_get_entry("BATA").runtime_data.notifier
    assert notifier_a._prefix == DOMAIN and notifier_b._prefix == f"{DOMAIN}_BATB"
    with patch(
        "custom_components.electric_heater.notifications.persistent_notification.async_create"
    ) as create:
        notifier_b._send("x", "msg")
    assert create.call_args.args[1] == "Gîte : msg"


async def test_two_buildings_orders_are_independent(hass: HomeAssistant) -> None:
    calls, a, b = await _two_buildings(hass)
    await _svc(hass, "set_hvac_mode", a, hvac_mode=HVACMode.HEAT)
    await _svc(hass, "set_preset_mode", a, preset_mode="comfort")
    await _svc(hass, "set_hvac_mode", b, hvac_mode=HVACMode.HEAT)
    await _svc(hass, "set_preset_mode", b, preset_mode="eco")
    assert _last(calls, SEL_A) == "comfort"
    assert _last(calls, SEL_B) == "eco"
    before_b = len([c for c in calls if c.data["entity_id"] in (SEL_B, [SEL_B])])
    await _svc(hass, "set_preset_mode", a, preset_mode="frost_protection")
    assert _last(calls, SEL_A) == "anti_freeze"
    assert _last(calls, SEL_B) == "eco"
    assert len([c for c in calls if c.data["entity_id"] in (SEL_B, [SEL_B])]) == before_b
    # Jamais d'ordre fil pilote à un central, quel que soit le bâtiment
    for central in (a, b):
        assert not any(central in str(c.data.get("entity_id")) for c in calls)
        assert fil_pilote.is_central_climate(hass, central)
    assert not fil_pilote.is_central_climate(hass, "climate.salon_chauffage_salon")


async def test_two_buildings_off_only_its_own_rooms(hass: HomeAssistant) -> None:
    calls, a, b = await _two_buildings(hass)
    for central in (a, b):
        await _svc(hass, "set_hvac_mode", central, hvac_mode=HVACMode.HEAT)
        await _svc(hass, "set_preset_mode", central, preset_mode="comfort")
    await _svc(hass, "set_hvac_mode", b, hvac_mode=HVACMode.OFF)
    assert _last(calls, SEL_B) == "off"
    assert _last(calls, SEL_A) == "comfort"
    assert hass.states.get(a).state == HVACMode.HEAT
    await _svc(hass, "set_hvac_mode", a, hvac_mode=HVACMode.OFF)
    await _svc(hass, "set_hvac_mode", b, hvac_mode=HVACMode.HEAT)
    assert _last(calls, SEL_A) == "off"
    assert _last(calls, SEL_B) == "comfort"


async def test_two_buildings_window_only_its_own_building(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.porte_gite", "off")
    calls, a, b = await _two_buildings(hass, central_b_extra={"window_sensors": "binary_sensor.porte_gite"})
    for central in (a, b):
        await _svc(hass, "set_hvac_mode", central, hvac_mode=HVACMode.HEAT)
        await _svc(hass, "set_preset_mode", central, preset_mode="comfort")
    hass.states.async_set("binary_sensor.porte_gite", "on")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert hass.states.get(b).attributes["window_open"] is True
    assert hass.states.get(a).attributes["window_open"] is False
    assert _last(calls, SEL_B) == "anti_freeze"
    assert _last(calls, SEL_A) == "comfort"
    assert fil_pilote.house_window_open(hass, "BATB") and not fil_pilote.house_window_open(hass, "BATA")
    assert [w["entity_id"] for w in fil_pilote.open_windows(hass, "BATB")] == ["binary_sensor.porte_gite"]
    assert fil_pilote.open_windows(hass, "BATA") == []
    hass.states.async_set("binary_sensor.porte_gite", "off")
    await hass.async_block_till_done()
    await _later(hass, 600)
    assert _last(calls, SEL_B) == "comfort"


async def test_two_buildings_settings_are_per_building(hass: HomeAssistant) -> None:
    await _two_buildings(hass, central_b_extra={"consigne_max_securite": 19.0, "hysteresis": 0.8,
                                                "saison_chauffe_active": False})
    assert safety.max_safe_temp(hass, "BATB") == 19.0
    assert safety.max_safe_temp(hass, "BATA") == safety.DEFAULT_MAX_SAFE_TEMP
    assert safety.max_safe_temp(hass) == safety.DEFAULT_MAX_SAFE_TEMP
    assert fil_pilote.central_option(hass, "hysteresis", None, "BATB") == 0.8
    assert season.get_season(hass, "BATB") is not season.get_season(hass, "BATA")
    assert season.get_season(hass) is season.get_season(hass, "BATA")
    assert season.get_season(hass, "BATB").options()["active"] is False
    assert season.get_season(hass, "BATA").options()["active"] is True
    room_b = hass.config_entries.async_get_entry("ROOMB")
    assert building.building_id(hass, room_b) == "BATB"
    assert building.building_id(None, room_b) == "BATB"
    # Central inconnu : repli sur le central par défaut
    lost = MockConfigEntry(domain=DOMAIN, data={"type": ROOM, "central_entry_id": "NOPE"})
    assert building.building_id(hass, lost) == "BATA"
    assert building.building_id(hass, None) is None


async def test_two_buildings_stats_and_global_total(hass: HomeAssistant) -> None:
    clock = [1000.0]
    with patch.object(stats, "time", SimpleNamespace(monotonic=lambda: clock[0])):
        calls, a, b = await _two_buildings(hass)
        for central in (a, b):
            await _svc(hass, "set_hvac_mode", central, hvac_mode=HVACMode.HEAT)
            await _svc(hass, "set_preset_mode", central, preset_mode="comfort")
        reg = er.async_get(hass)

        def _sensor(uid):
            return hass.data[SENSOR].get_entity(reg.async_get_entity_id("sensor", DOMAIN, uid))

        rooms = [_sensor(stats.stat_uid(r, "energy", True)) for r in ("ROOMA", "ROOMB")]
        for s in rooms:
            s._tick()
        clock[0] += 3600
        for s in rooms:
            s._tick()
        day_a = _sensor("electric_heater_central_conso_jour")
        day_b = _sensor("electric_heater_central_BATB_conso_jour")
        glob = _sensor("electric_heater_global_conso_jour")
        for s in (day_a, day_b, glob):
            s._update()
        assert day_a.native_value == 1.0
        assert day_b.native_value == 2.0
        assert glob.native_value == 3.0
        assert day_a.extra_state_attributes["par_radiateur"] == {"Salon": 1.0}
        attrs = glob.extra_state_attributes
        assert attrs["par_radiateur"] == {"Maison · Salon": 1.0, "Gîte · Salon": 2.0}
        assert attrs["par_batiment"] == {"Maison": 1.0, "Gîte": 2.0}
        assert _sensor("electric_heater_central_BATB_compteurs_jour") is not None


async def test_second_central_sensors_follow_their_own_central(hass: HomeAssistant) -> None:
    calls, a, b = await _two_buildings(hass)
    await _svc(hass, "set_hvac_mode", b, hvac_mode=HVACMode.OFF)
    await _svc(hass, "set_hvac_mode", a, hvac_mode=HVACMode.HEAT)
    reg = er.async_get(hass)
    heat_b = reg.async_get_entity_id("binary_sensor", DOMAIN, "electric_heater_central_BATB_chauffage_actif")
    heat_a = reg.async_get_entity_id("binary_sensor", DOMAIN, "electric_heater_central_chauffage_actif")
    assert hass.states.get(heat_b).state == "off"
    assert hass.states.get(heat_a).state == "on"
    rooms_b = hass.states.get(b).attributes["rooms"]
    assert rooms_b == ["Salon"] and hass.states.get(a).attributes["rooms"] == ["Salon"]
    # Le central d'un autre bâtiment n'est pas compté comme radiateur
    assert b not in hass.data["climate"].get_entity(a)._room_climate_ids()
    assert building.central_entity_id(None) == "climate.electric_heater_central"


async def test_unregistered_second_central(hass: HomeAssistant) -> None:
    b = MockConfigEntry(domain=DOMAIN, data={**CENTRAL_DATA, "type": CENTRAL}, unique_id="electric_heater_central_X",
                        entry_id="X")
    b.add_to_hass(hass)
    # Pas encore chargé : aucun entity_id deviné, pas de repli sur le central historique
    assert building.central_entity_id(hass, "X") is None
    assert fil_pilote.get_central_state(hass, "X") is None
    assert building.central_uid(b, "presents") == "electric_heater_central_X_presents"
    assert building.central_history_id(b) == "central_X"
    assert building.central_history_id(None) == "central"


async def test_change_building_reloads_and_relinks(hass: HomeAssistant) -> None:
    """Pièce déplacée de Maison vers Gîte : rechargée, via_device mis à jour, suit le Gîte."""
    calls, a, b = await _two_buildings(hass)
    room = hass.config_entries.async_get_entry("ROOMA")
    for central, preset in ((a, "comfort"), (b, "eco")):
        await _svc(hass, "set_hvac_mode", central, hvac_mode=HVACMode.HEAT)
        await _svc(hass, "set_preset_mode", central, preset_mode=preset)
    assert _last(calls, SEL_A) == "comfort"
    result = await room.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {
        "name": "Salon", "fil_pilote_select": SEL_A, "temperature_sensor": "sensor.salon_temp",
        "central_entry_id": "BATB", "power": 1000})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    devices = dr.async_get(hass)
    dev_b = _dev(devices, (DOMAIN, "electric_heater_central_BATB"))
    assert _dev(devices, (DOMAIN, "room_ROOMA")).via_device_id == dev_b.id
    assert [e.entry_id for e in building.iter_room_entries(hass, "BATB")] == ["ROOMA", "ROOMB"]
    assert hass.states.get(b).attributes["rooms"] == ["Salon", "Salon"]
    assert hass.states.get(a).attributes["rooms"] == []
    await _svc(hass, "set_preset_mode", b, preset_mode="frost_protection")
    assert _last(calls, SEL_A) == "anti_freeze"
    await _svc(hass, "set_preset_mode", a, preset_mode="comfort")
    assert _last(calls, SEL_A) == "anti_freeze"
