"""Assistant de configuration : fenêtres, services notify, valeurs par défaut."""

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.electric_heater import config_flow as cf


async def test_window_options(hass: HomeAssistant) -> None:
    assert cf._window_options(None) == []
    assert cf._windows_selector(None) is cf._WINDOWS_FALLBACK
    hass.states.async_set("binary_sensor.porte_entree", "off", {"friendly_name": "Porte entrée"})
    hass.states.async_set("binary_sensor.mouvement", "off", {"device_class": "motion"})
    hass.states.async_set("sensor.contact_z2m", "x", {"friendly_name": "Contact"})
    opts = cf._window_options(hass, ["sensor.contact_z2m", "sensor.absent", "light.x"])
    values = [o["value"] for o in opts]
    assert "binary_sensor.porte_entree" in values and "binary_sensor.mouvement" not in values
    assert "sensor.contact_z2m" in values and "sensor.absent" in values and "light.x" not in values
    field = cf._windows_field({"window_sensors": ["binary_sensor.porte_entree"]}, hass)
    assert list(field)[0].default() == ["binary_sensor.porte_entree"]


async def test_notify_helpers(hass: HomeAssistant) -> None:
    assert cf.notify_list(None) == []
    assert cf.notify_list("a, notify.b, a") == ["notify.a", "notify.b"]
    async_mock_service(hass, "notify", "mobile_app_pixel")
    async_mock_service(hass, "notify", "email")
    sel = cf._notify_selector(hass, ["notify.ancien"])
    labels = [o["label"] for o in sel.config["options"]]
    assert labels[0].startswith("📱 pixel") and "notify.email" in labels and "notify.ancien" in labels


async def test_defaults() -> None:
    assert cf._temp_default({"t": "abc"}, "t", 20.0, 7, 25) == 20.0
    assert cf._temp_default({"t": 40}, "t", 20.0, 7, 25) == 25.0
    assert list(cf._with_default("k", str, {"k": "v"}, required=True))[0].default() == "v"
    assert cf._parse_windows("binary_sensor.a, binary_sensor.b") == ["binary_sensor.a", "binary_sensor.b"]


async def test_room_schema_with_energy_sensor(hass: HomeAssistant) -> None:
    schema = cf._room_schema({"name": "Chambre", "energy_sensor": "sensor.rad_energy", "power": 1500}, hass)
    keys = {str(k): k for k in schema.schema}
    assert keys["energy_sensor"].description == {"suggested_value": "sensor.rad_energy"}
    assert keys["name"].default() == "Chambre" and keys["power"].default() == 1500
