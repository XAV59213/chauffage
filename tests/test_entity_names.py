"""Gold : noms traduits (translation_key) sans changer entity_id ni noms visibles."""

from unittest.mock import patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .test_climate import _house

EXPECTED = {
    "binary_sensor.chambre_alerte_surchauffe": "Chambre Alerte surchauffe",
    "binary_sensor.thermostat_virtuel_alerte_surchauffe": "Thermostat virtuel Alerte surchauffe",
    "binary_sensor.thermostat_virtuel_calendrier_chauffage": "Thermostat virtuel Calendrier chauffage",
    "binary_sensor.thermostat_virtuel_calendrier_chauffage_active": "Thermostat virtuel Calendrier chauffage activé",
    "binary_sensor.thermostat_virtuel_chauffage_actif": "Thermostat virtuel Chauffage Actif",
    "binary_sensor.thermostat_virtuel_detecteur_fenetre_instable": "Thermostat virtuel Détecteur fenêtre instable",
    "binary_sensor.thermostat_virtuel_mode_eco_auto": "Thermostat virtuel Mode Eco Auto",
    "binary_sensor.thermostat_virtuel_presence": "Thermostat virtuel Presence",
    "binary_sensor.thermostat_virtuel_saison_de_chauffe": "Thermostat virtuel Saison de chauffe",
    "binary_sensor.thermostat_virtuel_sensor_battery_alert": "Thermostat virtuel Sensor battery alert",
    "climate.chambre_chauffage_chambre": "Chambre Chauffage Chambre",
    "climate.electric_heater_central": "Thermostat virtuel",
    "sensor.chambre_consommation_aujourd_hui": "Chambre Consommation aujourd'hui",
    "sensor.chambre_consommation_compteur_aujourd_hui": "Chambre Consommation compteur aujourd'hui",
    "sensor.chambre_consommation_totale": "Chambre Consommation totale",
    "sensor.chambre_derniere_decision": "Chambre Dernière décision",
    "sensor.chambre_etat_fenetre": "Chambre Etat fenetre",
    "sensor.chambre_temperature_piece": "Chambre Temperature Piece",
    "sensor.chambre_temps_de_chauffe_aujourd_hui": "Chambre Temps de chauffe aujourd'hui",
    "sensor.chambre_temps_de_chauffe_total": "Chambre Temps de chauffe total",
    "sensor.thermostat_virtuel_consommation_compteurs_aujourd_hui": "Thermostat virtuel Consommation compteurs aujourd'hui",
    "sensor.thermostat_virtuel_consommation_maison_aujourd_hui": "Thermostat virtuel Consommation maison aujourd'hui",
    "sensor.thermostat_virtuel_consommation_maison_totale": "Thermostat virtuel Consommation maison totale",
    "sensor.thermostat_virtuel_consommation_radiateurs_compteurs": "Thermostat virtuel Consommation radiateurs (compteurs)",
    "sensor.thermostat_virtuel_dernier_changement": "Thermostat virtuel Dernier changement",
    "sensor.thermostat_virtuel_derniere_decision": "Thermostat virtuel Dernière décision",
    "sensor.thermostat_virtuel_etat_fenetre": "Thermostat virtuel Etat fenetre",
    "sensor.thermostat_virtuel_failed_sensors": "Thermostat virtuel Failed sensors",
    "sensor.thermostat_virtuel_open_windows": "Thermostat virtuel Open windows",
    "sensor.thermostat_virtuel_presents": "Thermostat virtuel Presents",
    "sensor.thermostat_virtuel_temperature_centrale": "Thermostat virtuel Temperature Centrale",
    "sensor.thermostat_virtuel_temperature_exterieure": "Thermostat virtuel Temperature exterieure",
    "sensor.thermostat_virtuel_temps_de_chauffe_maison_aujourd_hui": "Thermostat virtuel Temps de chauffe maison aujourd'hui",
    "sensor.thermostat_virtuel_temps_de_chauffe_maison_total": "Thermostat virtuel Temps de chauffe maison total"
}

DISABLED = ("sensor.thermostat_virtuel_temperature_centrale", "sensor.thermostat_virtuel_temperature_exterieure")


async def test_entity_ids_and_names_unchanged(hass: HomeAssistant) -> None:
    with patch("custom_components.electric_heater.climate.RoomThermostat._in_startup_grace", return_value=False):
        hass.states.async_set("weather.maison", "sunny", {"temperature": 10})
        hass.states.async_set("binary_sensor.presence", "on")
        hass.states.async_set("calendar.chauffage", "on")
        await _house(hass, "16.0", central_extra={"presence_sensor": "binary_sensor.presence",
                                                  "heating_calendar": "calendar.chauffage",
                                                  "weather_entity": "weather.maison"})
    ours = {s.entity_id: s.attributes.get("friendly_name") for s in hass.states.async_all()
            if s.entity_id.split(".")[0] in ("sensor", "binary_sensor", "climate")
            and s.entity_id not in ("sensor.salon_temp", "sensor.chambre_temp", "binary_sensor.presence")}
    reg = er.async_get(hass)
    for eid in DISABLED:
        entry = reg.async_get(eid)
        assert entry is not None and entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
        ours[eid] = EXPECTED[eid]
    assert ours == EXPECTED
