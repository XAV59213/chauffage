"""Presence : uniquement le capteur choisi sur le thermostat."""
from __future__ import annotations

import re

from homeassistant.core import HomeAssistant, State

from .const import CONF_PERSONS, NOT_PERSON_HINTS


_STRONG_HINTS = (
    "tablette", "tablet", "ipad", "iphone", "android", "mqtt", "telephone", "téléphone",
    "smartphone", "galaxy", "pixel", "macbook", "laptop", "chromecast", "freebox",
)


def _words(text: str) -> set[str]:
    return set(re.split(r"[^0-9a-zà-ÿ]+", text.lower())) - {""}


def is_real_person(state: State | None) -> bool:
    """Faux pour les entités person qui sont des appareils (Tablette, iPad, mqtt...) ou la maison."""
    if state is None:
        return False
    name = str(state.attributes.get("friendly_name") or "")
    words = _words(name) | _words(state.entity_id.split(".", 1)[-1])
    if any(hint in words for hint in NOT_PERSON_HINTS):
        return False
    # Indices forts collés au nom : ipadpapa, tablettep, iphonexav...
    flat = f"{name} {state.entity_id}".lower()
    return not any(hint in flat for hint in _STRONG_HINTS)


def tracked_persons(hass: HomeAssistant, data: dict | None) -> list[State]:
    """Personnes suivies : celles choisies dans la config, sinon les vraies personnes détectées."""
    chosen = list((data or {}).get(CONF_PERSONS) or [])
    if chosen:
        return [st for eid in chosen if (st := hass.states.get(eid)) is not None]
    return [st for st in hass.states.async_all("person") if is_real_person(st)]


def present_names(hass: HomeAssistant, data: dict | None) -> list[str]:
    return sorted(
        str(st.attributes.get("friendly_name") or st.entity_id)
        for st in tracked_persons(hass, data)
        if st.state == "home"
    )


def occupancy_count(hass: HomeAssistant, sensor_id: str | None) -> int:
    if not sensor_id:
        return 0
    state = hass.states.get(sensor_id)
    if not state or state.state in ("unknown", "unavailable"):
        return 0
    try:
        return int(float(state.state))
    except (TypeError, ValueError):
        return 0 if str(state.state).lower() in ("off", "false", "not_home", "personne") else 1
