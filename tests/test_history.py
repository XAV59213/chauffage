"""Attribution des changements (qui a éteint ?) et lecture de puissance."""

from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.electric_heater.history import (
    find_power_sensor,
    format_context,
    own_context,
    read_power,
    resolve_who,
)


async def test_resolve_who(hass: HomeAssistant) -> None:
    assert await resolve_who(hass, None) == "système"
    assert await resolve_who(hass, Context()) == "système"
    mine = own_context(hass)
    assert await resolve_who(hass, mine) == "intégration"
    assert await resolve_who(hass, Context(parent_id=mine.id)) == "intégration"
    user = await hass.auth.async_create_user("Xavier")
    assert await resolve_who(hass, Context(user_id=user.id)) == "Xavier"
    auto_ctx = Context()
    hass.states.async_set("automation.soir", "on", {"friendly_name": "Soir"}, context=auto_ctx)
    assert await resolve_who(hass, Context(parent_id=auto_ctx.id)) == "automatisation « Soir »"
    assert await resolve_who(hass, Context(parent_id="inconnu")) == "automatisation"


async def test_format_context(hass: HomeAssistant) -> None:
    assert await format_context(hass, None) == "context=None"
    user = await hass.auth.async_create_user("Xavier")
    text = await format_context(hass, Context(user_id=user.id))
    assert "user_name='Xavier'" in text and "own=False" in text
    mine = own_context(hass)
    assert "own=True" in await format_context(hass, mine)


async def test_power(hass: HomeAssistant) -> None:
    assert read_power(hass, None) is None
    hass.states.async_set("sensor.p", "1.5", {"unit_of_measurement": "kW"})
    assert read_power(hass, "sensor.p") == 1500.0
    hass.states.async_set("sensor.q", "x")
    assert read_power(hass, "sensor.q") is None
    assert find_power_sensor(hass, None) is None
    entry = MockConfigEntry(domain="zha")
    entry.add_to_hass(hass)
    dev = dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, identifiers={("zha", "nodon")})
    reg = er.async_get(hass)
    sel = reg.async_get_or_create("select", "zha", "fp", device_id=dev.id, config_entry=entry)
    pw = reg.async_get_or_create("sensor", "zha", "pw", device_id=dev.id, config_entry=entry,
                                 unit_of_measurement="W")
    assert find_power_sensor(hass, sel.entity_id) == pw.entity_id
