"""Flux de configuration."""

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
import pytest
from homeassistant.data_entry_flow import AbortFlow, FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater.const import BUILDING, CENTRAL, DOMAIN


def _building(hass, entry_id="BLDA", title="Maison"):
    entry = MockConfigEntry(domain=DOMAIN, entry_id=entry_id, title=title,
                            unique_id=f"electric_heater_building_{entry_id}",
                            data={"type": BUILDING, "name": title})
    entry.add_to_hass(hass)
    return entry


async def test_first_flow_is_building(hass: HomeAssistant) -> None:
    """Étape 1 : rien n'existe, on commence par le bâtiment."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "building"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "   "})
    assert result["errors"] == {"name": "name_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "  Maison  "})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.title == "Maison" and entry.data == {"type": BUILDING, "name": "Maison"}
    assert entry.unique_id.startswith("electric_heater_building_")


async def test_building_name_unique(hass: HomeAssistant) -> None:
    _building(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    # Bâtiment sans thermostat : menu Bâtiment / Thermostat (pas encore de radiateur possible)
    assert result["type"] is FlowResultType.MENU and result["menu_options"] == ["building", "central"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "building"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": " MAISON "})
    assert result["errors"] == {"name": "building_exists"}


async def test_menu_full_and_without_free_building(hass: HomeAssistant) -> None:
    _building(hass)
    _central(hass, "BATA", "T", "electric_heater_central", "BLDA")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    # Le seul bâtiment a son thermostat : pas de « Thermostat » (1 par bâtiment)
    assert result["menu_options"] == ["building", "room"]
    _building(hass, "BLDB", "Gîte")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["menu_options"] == ["building", "central", "room"]


async def test_thermostat_needs_free_building(hass: HomeAssistant) -> None:
    flow = await _flow(hass)
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "no_free_building"
    _building(hass)
    _central(hass, "BATA", "T", "electric_heater_central", "BLDA")
    flow = await _flow(hass)
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["reason"] == "no_free_building"


async def test_thermostat_building_choice(hass: HomeAssistant) -> None:
    _building(hass)
    _building(hass, "BLDB", "Gîte")
    _central(hass, "BATA", "T", "electric_heater_central", "BLDA")
    _building(hass, "BLDC", "Grange")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "central"})
    schema = result["data_schema"].schema
    field = next(k for k in schema if k == "building_entry_id")
    # Seulement les bâtiments sans thermostat
    assert [o["value"] for o in schema[field].config["options"]] == ["BLDB", "BLDC"]
    name = next(k for k in schema if k == "name")
    assert name.default() == "Thermostat Gîte"
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_central({**CENTRAL_INPUT, "building_entry_id": "BLDA"})
    assert result["errors"] == {"building_entry_id": "building_has_thermostat"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CENTRAL_INPUT, "name": "Thermostat Grange", "building_entry_id": "BLDC"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.data["building_entry_id"] == "BLDC" and entry.unique_id != "electric_heater_central"


async def test_import_creates_building_once(hass: HomeAssistant, no_setup) -> None:
    data = {"name": " Maison ", "central_entry_id": "BATA"}
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "electric_heater_building_BATA" and result["title"] == "Maison"
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=data)
    assert result["reason"] == "already_configured"


async def test_rename_building_reconfigure_and_options(hass: HomeAssistant, no_setup) -> None:
    maison = _building(hass)
    _building(hass, "BLDB", "Gîte")
    result = await maison.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_building"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": " gîte"})
    assert result["errors"] == {"name": "building_exists"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": ""})
    assert result["errors"] == {"name": "name_required"}
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Maison"})
    assert result["reason"] == "reconfigure_successful"
    result = await maison.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Ferme"})
    await hass.async_block_till_done()
    assert maison.title == "Ferme" and maison.data["name"] == "Ferme"
    result = await hass.config_entries.options.async_init(maison.entry_id)
    assert result["step_id"] == "building"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": "GÎTE"})
    assert result["errors"] == {"name": "building_exists"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": " "})
    assert result["errors"] == {"name": "name_required"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": "Ferme Est"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert maison.title == "Ferme Est" and maison.data == {"type": BUILDING, "name": "Ferme Est"}


async def test_move_thermostat_rooms_follow(hass: HomeAssistant, no_setup) -> None:
    _building(hass)
    _building(hass, "BLDB", "Gîte")
    central = _central(hass, "BATA", "T", "electric_heater_central", "BLDA")
    room = _room_entry(hass)
    hass.config_entries.async_update_entry(
        room, data={**room.data, "central_entry_id": "BATA", "building_entry_id": "BLDA"})
    orphan = _room_entry(hass, "select.orphan")
    hass.config_entries.async_update_entry(
        orphan, data={**orphan.data, "central_entry_id": "GONE", "building_entry_id": "BLDB"})
    result = await central.start_reconfigure_flow(hass)
    field = next(k for k in result["data_schema"].schema if k == "building_entry_id")
    assert field.default() == "BLDA"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**CENTRAL_INPUT, "building_entry_id": "BLDB"})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert central.data["building_entry_id"] == "BLDB"
    assert room.data["building_entry_id"] == "BLDB" and room.data["central_entry_id"] == "BATA"
    assert orphan.data["central_entry_id"] == "BATA"
    # Options : retour dans le premier bâtiment
    result = await hass.config_entries.options.async_init(central.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**CENTRAL_INPUT, "building_entry_id": "BLDA"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert central.data["building_entry_id"] == "BLDA" and room.data["building_entry_id"] == "BLDA"


async def test_central_requires_sensor_in_reference_mode(hass: HomeAssistant) -> None:
    _building(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    result = await flow.async_step_central(
        {"name": "T", "temp_method": "reference", "temperature_sensor": None}
    )
    assert result["errors"] == {"temperature_sensor": "sensor_required"}


async def test_room_flow_after_central(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, data={"type": CENTRAL, "name": "T"}, unique_id="electric_heater_central"
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    # Un thermostat existe : menu Bâtiment / Radiateur
    assert result["type"] is FlowResultType.MENU
    assert result["menu_options"] == ["building", "room"]
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "room"})
    assert result["step_id"] == "room"
    # Un seul bâtiment : pas de champ « Bâtiment »
    assert "central_entry_id" not in result["data_schema"].schema


CENTRAL_INPUT = {
    "name": "Thermostat virtuel",
    "temp_method": "reference",
    "temperature_sensor": "sensor.salon_temp",
    "comfort_temp": 20.199999999999998,
    "comfort_m1_temp": 19,
    "comfort_m2_temp": 18,
    "eco_temp": 17,
    "frost_temp": 7,
    "min_temp": 7,
    "max_temp": 25,
    "temp_step": 0.1,
}


async def _flow(hass):
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    return hass.config_entries.flow._progress[result["flow_id"]]


async def test_central_created_and_rounded(hass: HomeAssistant) -> None:
    _building(hass)
    flow = await _flow(hass)
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["type"] == CENTRAL
    # Un seul bâtiment libre : rattaché automatiquement ; premier thermostat = ids historiques
    assert result["data"]["building_entry_id"] == "BLDA"
    assert flow.unique_id == "electric_heater_central"
    assert result["data"]["comfort_temp"] == 20.2


async def test_room_created_then_duplicate_aborts(hass: HomeAssistant) -> None:
    MockConfigEntry(
        domain=DOMAIN, data={"type": CENTRAL, "name": "T"}, unique_id="electric_heater_central"
    ).add_to_hass(hass)
    room = {
        "name": "Chambre",
        "fil_pilote_select": "select.chambre_pilot_wire_mode",
        "temperature_sensor": "sensor.chambre_temp",
    }
    flow = await _flow(hass)
    result = await flow.async_step_room(dict(room))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    MockConfigEntry(
        domain=DOMAIN, data=result["data"],
        unique_id="electric_heater_room_select.chambre_pilot_wire_mode",
    ).add_to_hass(hass)
    flow = await _flow(hass)
    with pytest.raises(AbortFlow):
        await flow.async_step_room(dict(room))


async def test_options_room_updates_entry(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Chambre",
        data={"type": "room", "name": "Chambre",
              "fil_pilote_select": "select.chambre_pilot_wire_mode",
              "temperature_sensor": "sensor.a"},
    )
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "room"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"name": "Chambre 2", "fil_pilote_select": "select.chambre_pilot_wire_mode",
         "temperature_sensor": "sensor.b"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["temperature_sensor"] == "sensor.b"
    assert entry.title == "Chambre 2"


async def test_options_central_sensor_required(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="T", data={"type": CENTRAL, "name": "T"})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["step_id"] == "central"
    flow = hass.config_entries.options._progress[result["flow_id"]]
    result = await flow.async_step_central({"temp_method": "reference", "temperature_sensor": None})
    assert result["errors"] == {"temperature_sensor": "sensor_required"}
    result = await flow.async_step_central(dict(CENTRAL_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["temperature_sensor"] == "sensor.salon_temp"


@pytest.fixture
def no_setup():
    from unittest.mock import AsyncMock, patch

    with patch("custom_components.electric_heater.async_setup_entry", AsyncMock(return_value=True)):
        yield


def _room_entry(hass, fil="select.chambre_pilot_wire_mode"):
    entry = MockConfigEntry(
        domain=DOMAIN, title="Chambre", unique_id=f"electric_heater_room_{fil}",
        data={"type": "room", "name": "Chambre", "fil_pilote_select": fil, "temperature_sensor": "sensor.a"},
    )
    entry.add_to_hass(hass)
    return entry


async def test_reconfigure_central(hass: HomeAssistant, no_setup) -> None:
    entry = MockConfigEntry(domain=DOMAIN, title="T", unique_id="electric_heater_central",
                            data={"type": CENTRAL, "name": "T"})
    entry.add_to_hass(hass)
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_central"
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(fid, {k: v for k, v in CENTRAL_INPUT.items() if k != "temperature_sensor"})
    assert result["errors"] == {"temperature_sensor": "sensor_required"}
    result = await hass.config_entries.flow.async_configure(fid, {**CENTRAL_INPUT, "name": "Maison", "notify_service": ["mobile"]})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "reconfigure_successful"
    assert entry.title == "Maison" and entry.data["comfort_temp"] == 20.2
    assert entry.data["notify_service"] == ["notify.mobile"] and entry.data["type"] == CENTRAL


async def test_reconfigure_room(hass: HomeAssistant, no_setup) -> None:
    entry = _room_entry(hass)
    _room_entry(hass, "select.salon_pilot_wire_mode")
    result = await entry.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure_room"
    fid = result["flow_id"]
    # Même relais, nouvelle sonde
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre", "fil_pilote_select": "select.chambre_pilot_wire_mode", "temperature_sensor": "sensor.b",
         "power": 1500})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["temperature_sensor"] == "sensor.b" and entry.data["power"] == 1500
    assert entry.data["type"] == "room"
    # Relais déjà utilisé par une autre pièce : refusé
    result = await entry.start_reconfigure_flow(hass)
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre", "fil_pilote_select": "select.salon_pilot_wire_mode", "temperature_sensor": "sensor.b"})
    assert result["reason"] == "already_configured"
    # Nouveau relais libre : unique_id mis à jour
    result = await entry.start_reconfigure_flow(hass)
    fid = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        fid,
        {"name": "Chambre 2", "fil_pilote_select": "select.neuf", "temperature_sensor": "sensor.b"})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.unique_id == "electric_heater_room_select.neuf" and entry.title == "Chambre 2"


ROOM_INPUT = {
    "name": "Chambre",
    "fil_pilote_select": "select.chambre_pilot_wire_mode",
    "temperature_sensor": "sensor.chambre_temp",
}


def _central(hass, entry_id, title, unique_id, building_entry_id=None):
    data = {"type": CENTRAL, "name": title}
    if building_entry_id:
        data["building_entry_id"] = building_entry_id
    entry = MockConfigEntry(domain=DOMAIN, entry_id=entry_id, title=title, unique_id=unique_id, data=data)
    entry.add_to_hass(hass)
    return entry


async def test_room_needs_a_central(hass: HomeAssistant) -> None:
    flow = await _flow(hass)  # aucun central : formulaire du central
    result = await flow.async_step_room(dict(ROOM_INPUT))
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "no_central"


async def test_single_building_room_attached_automatically(hass: HomeAssistant) -> None:
    _central(hass, "BATA", "Maison", "electric_heater_central")
    flow = await _flow(hass)
    result = await flow.async_step_room(dict(ROOM_INPUT))
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["central_entry_id"] == "BATA"


async def test_second_building_from_menu(hass: HomeAssistant) -> None:
    """Bâtiment → Thermostat : le 2e thermostat a des identifiants propres, l'historique est intact."""
    _building(hass)
    _central(hass, "BATA", "Maison", "electric_heater_central", "BLDA")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "building"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Gîte"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    gite = result["result"]
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "central"})
    assert result["step_id"] == "central"
    # Un seul bâtiment libre : pas de champ, rattachement automatique
    assert "building_entry_id" not in result["data_schema"].schema
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {**CENTRAL_INPUT, "name": "Thermostat Gîte"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.unique_id.startswith("electric_heater_central_") and entry.unique_id != "electric_heater_central"
    assert entry.data["type"] == CENTRAL and entry.data["building_entry_id"] == gite.entry_id
    # Le central historique est intact
    assert hass.config_entries.async_get_entry("BATA").unique_id == "electric_heater_central"


async def test_room_building_choice(hass: HomeAssistant) -> None:
    _central(hass, "BATA", "Maison", "electric_heater_central")
    _central(hass, "BATB", "Gîte", "electric_heater_central_abc")
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"next_step_id": "room"})
    schema = result["data_schema"].schema
    assert "central_entry_id" in schema
    field = next(k for k in schema if k == "central_entry_id")
    assert field.default() == "BATA"
    options = schema[field].config["options"]
    assert [o["value"] for o in options] == ["BATA", "BATB"] and options[1]["label"] == "Gîte"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ROOM_INPUT, "central_entry_id": "BATB"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["central_entry_id"] == "BATB"


async def test_change_building_reconfigure_and_options(hass: HomeAssistant, no_setup) -> None:
    _central(hass, "BATA", "Maison", "electric_heater_central")
    _central(hass, "BATB", "Gîte", "electric_heater_central_abc")
    entry = _room_entry(hass)
    hass.config_entries.async_update_entry(entry, data={**entry.data, "central_entry_id": "BATA"})
    result = await entry.start_reconfigure_flow(hass)
    field = next(k for k in result["data_schema"].schema if k == "central_entry_id")
    assert field.default() == "BATA"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**ROOM_INPUT, "temperature_sensor": "sensor.a", "central_entry_id": "BATB"})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["central_entry_id"] == "BATB"
    # Options : retour dans le premier bâtiment
    result = await hass.config_entries.options.async_init(entry.entry_id)
    field = next(k for k in result["data_schema"].schema if k == "central_entry_id")
    assert field.default() == "BATB"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**ROOM_INPUT, "temperature_sensor": "sensor.a", "central_entry_id": "BATA"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.data["central_entry_id"] == "BATA"
