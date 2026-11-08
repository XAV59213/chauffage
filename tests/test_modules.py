"""Saison, sécurité, lien appareil, carte, relais fil pilote climate."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.core import HomeAssistant, ServiceCall
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.electric_heater import device_link, season as season_mod
from custom_components.electric_heater.const import CENTRAL, DOMAIN, PRESET_COMFORT, PRESET_ECO, PRESET_OFF
from custom_components.electric_heater.fil_pilote import apply_fil_pilote, relay_matches
from custom_components.electric_heater.safety import (
    DEFAULT_MAX_SAFE_TEMP,
    DEFAULT_OVERHEAT_MARGIN,
    DEFAULT_UNSTABLE_COUNT,
    max_safe_temp,
    overheat_margin,
    send_alert,
    unstable_count,
)
from custom_components.electric_heater.season import (
    MIN_DURATION,
    SeasonController,
    _parse_mmdd,
    get_season,
    in_date_season,
    read_outdoor,
)


def _central(hass, **opts):
    entry = MockConfigEntry(domain=DOMAIN, data={"type": CENTRAL}, options=opts)
    entry.add_to_hass(hass)
    return entry


async def test_dates() -> None:
    assert _parse_mmdd("13-40", "10-15") == (10, 15)
    assert _parse_mmdd(None, "04-15") == (4, 15)
    assert in_date_season(datetime(2026, 1, 5))
    assert not in_date_season(datetime(2026, 7, 1))
    assert in_date_season(datetime(2026, 6, 10), "06-01", "06-30")
    assert not in_date_season(datetime(2026, 7, 10), "06-01", "06-30")


async def test_read_outdoor(hass: HomeAssistant) -> None:
    assert read_outdoor(hass, None) is None
    hass.states.async_set("weather.m", "sunny", {"temperature": 9.04})
    assert read_outdoor(hass, "weather.m") == 9.0
    assert read_outdoor(hass, "sensor.none") is None
    hass.states.async_set("sensor.ext", "12.26")
    assert read_outdoor(hass, "sensor.ext") == 12.3
    hass.states.async_set("sensor.ext", "abc", {"temperature": "5.55"})
    assert read_outdoor(hass, "sensor.ext") == 5.5
    hass.states.async_set("sensor.ext", "abc", {"temperature": "zz"})
    assert read_outdoor(hass, "sensor.ext") is None
    hass.states.async_set("sensor.ext", "abc")
    assert read_outdoor(hass, "sensor.ext") is None


async def test_season_disabled(hass: HomeAssistant) -> None:
    _central(hass, saison_chauffe_active=False)
    res = SeasonController(hass).evaluate()
    assert res["in_season"] and res["raison"] == "saison_desactivee"
    assert get_season(hass) is get_season(hass)


async def test_season_outdoor_antiflap(hass: HomeAssistant) -> None:
    _central(hass, capteur_temperature_exterieure="sensor.ext", seuil_exterieur=16)
    clock = [1000.0]
    with patch.object(season_mod, "in_date_season", return_value=True), \
         patch.object(season_mod, "time", SimpleNamespace(monotonic=lambda: clock[0])):
        ctrl = SeasonController(hass)
        hass.states.async_set("sensor.ext", "10")
        res = ctrl.evaluate()
        assert res["in_season"] and res["raison"] == "en_saison"
        # Chaud : demande de bascule mise en attente 6 h
        ctrl._samples.clear()
        hass.states.async_set("sensor.ext", "20")
        assert ctrl.evaluate()["in_season"]
        assert ctrl._pending_out is True
        clock[0] += MIN_DURATION + 1
        ctrl._samples.clear()
        res = ctrl.evaluate()
        assert not res["in_season"] and res["raison"] == "exterieur_chaud"
        # Retour du froid : confirmé après 6 h
        ctrl._samples.clear()
        hass.states.async_set("sensor.ext", "5")
        assert not ctrl.evaluate()["in_season"]
        clock[0] += MIN_DURATION + 1
        ctrl._samples.clear()
        assert ctrl.evaluate()["in_season"]
        # Stable : rien en attente
        ctrl._samples.clear()
        ctrl.evaluate()
        assert ctrl._pending_out is None
        # Moyenne glissante purgée après 24 h
        clock[0] += 90000
        hass.states.async_set("sensor.ext", "unavailable")
        assert ctrl._avg_24h(None) is None
    with patch.object(season_mod, "in_date_season", return_value=False):
        assert SeasonController(hass).evaluate()["raison"] == "hors_periode"


async def test_safety_options(hass: HomeAssistant) -> None:
    assert max_safe_temp(hass) == DEFAULT_MAX_SAFE_TEMP
    _central(hass, consigne_max_securite="x", marge_surchauffe="y", seuil_detecteur_instable="z",
             notify_service="notify.mobile, absent")
    assert max_safe_temp(hass) == DEFAULT_MAX_SAFE_TEMP
    assert overheat_margin(hass) == DEFAULT_OVERHEAT_MARGIN
    assert unstable_count(hass) == DEFAULT_UNSTABLE_COUNT
    calls = async_mock_service(hass, "notify", "mobile")
    send_alert(hass, "k", "msg", 60, {})
    await hass.async_block_till_done()
    assert len(calls) == 1 and calls[0].data["message"] == "msg"


async def test_device_link(hass: HomeAssistant) -> None:
    assert device_link.via_central(None) == {}
    assert device_link.via_central(hass) == {}
    with patch.object(device_link, "_HAS_VIA_ID", False):
        assert device_link.via_central(hass) == {"via_device": device_link.CENTRAL_IDENTIFIER}
    dev = MagicMock(identifiers={device_link.CENTRAL_IDENTIFIER})
    # API (domain, ident) séparés
    reg = MagicMock()
    reg.async_get_device_by_identifier = MagicMock(side_effect=[TypeError, dev])
    assert device_link._central_device(reg) is dev
    # Repli async_get_devices
    reg = MagicMock(spec=["async_get_devices"])
    reg.async_get_devices = MagicMock(return_value=[MagicMock(identifiers=set()), dev])
    assert device_link._central_device(reg) is dev
    reg.async_get_devices = MagicMock(return_value=[])
    assert device_link._central_device(reg) is None
    # Très anciennes versions
    reg = MagicMock(spec=["async_get_device"])
    reg.async_get_device = MagicMock(return_value=dev)
    assert device_link._central_device(reg) is dev
    reg = MagicMock()
    reg.async_get_device_by_identifier = MagicMock(side_effect=TypeError)
    reg.async_get_devices = MagicMock(return_value=[dev])
    assert device_link._central_device(reg) is dev


async def test_register_card(hass: HomeAssistant) -> None:
    from custom_components.electric_heater import frontend

    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock(side_effect=RuntimeError)
    with patch.object(frontend, "add_extra_js_url") as add:
        await frontend.async_register_card(hass)
    assert "electric_heater" in add.call_args[0][1]


async def test_climate_relay(hass: HomeAssistant) -> None:
    eid = "climate.radiateur"
    calls: list[ServiceCall] = []
    for svc in ("set_hvac_mode", "set_preset_mode", "set_temperature"):
        hass.services.async_register("climate", svc, lambda c: calls.append(c))
    hass.states.async_set(eid, "off", {"preset_modes": ["comfort", "eco"]})
    assert not relay_matches(hass.states.get(eid), PRESET_ECO, "eco")
    assert relay_matches(hass.states.get(eid), PRESET_OFF, None)
    assert await apply_fil_pilote(hass, eid, PRESET_COMFORT, temperature=20)
    assert [c.service for c in calls] == ["set_hvac_mode", "set_preset_mode", "set_temperature"]
    calls.clear()
    hass.states.async_set(eid, "heat", {"preset_modes": ["comfort", "eco"], "preset_mode": "comfort", "temperature": 20})
    assert await apply_fil_pilote(hass, eid, PRESET_COMFORT, temperature=20)
    assert calls == []
    assert await apply_fil_pilote(hass, eid, PRESET_OFF)
    assert calls[0].data["hvac_mode"] == "off"
    # Domaine non supporté / service en erreur / relais absent
    hass.states.async_set("switch.r", "on")
    assert not await apply_fil_pilote(hass, "switch.r", PRESET_COMFORT)
    assert not await apply_fil_pilote(hass, None, PRESET_COMFORT)
    hass.states.async_set("select.r", "eco", {"options": ["comfort", "eco"]})
    assert not await apply_fil_pilote(hass, "select.r", PRESET_COMFORT)  # pas de service select
    assert not relay_matches(hass.states.get("switch.r"), PRESET_COMFORT, None)


async def test_central_lookup_fallbacks(hass: HomeAssistant) -> None:
    from custom_components.electric_heater.fil_pilote import get_central_state, is_central_climate

    assert get_central_state(hass) is None
    hass.states.async_set("climate.maison", "auto", {"virtual": True})
    assert get_central_state(hass).entity_id == "climate.maison"
    assert is_central_climate(hass, "climate.maison")
    assert not is_central_climate(hass, "select.x")
    assert not await apply_fil_pilote(hass, "climate.maison", PRESET_COMFORT)  # jamais d'ordre au central
    hass.states.async_set("climate.thermostat_virtuel", "heat")
    assert get_central_state(hass).entity_id == "climate.thermostat_virtuel"


async def test_area_windows(hass: HomeAssistant) -> None:
    from homeassistant.helpers import area_registry as ar, entity_registry as er

    from custom_components.electric_heater.fil_pilote import area_windows, windows_from_entry

    room = MockConfigEntry(domain=DOMAIN, data={"type": "room", "name": "Chambre"})
    room.add_to_hass(hass)
    assert area_windows(None, room) == []
    reg = er.async_get(hass)
    area = ar.async_get(hass).async_create("Chambre")
    assert area_windows(hass, room) == []
    c = reg.async_get_or_create("climate", DOMAIN, "r1", config_entry=room, suggested_object_id="chambre")
    reg.async_update_entity(c.entity_id, area_id=area.id)
    for uid, dc in (("fen", "window"), ("pile", "window"), ("mvt", "motion"), ("nodc", None)):
        e = reg.async_get_or_create("binary_sensor", "zha", uid, suggested_object_id=f"chambre_{uid}",
                                    original_device_class=dc)
        reg.async_update_entity(e.entity_id, area_id=area.id)
    reg.async_get_or_create("binary_sensor", "zha", "ailleurs", suggested_object_id="salon_fen",
                            original_device_class="window")
    assert area_windows(hass, room) == ["binary_sensor.chambre_fen"]
    assert windows_from_entry(room, hass) == ["binary_sensor.chambre_fen"]
