"""Sécurités : consigne max, surchauffe / radiateur désobéissant, détecteur instable."""
from __future__ import annotations
from typing import Any

import logging
import time

from homeassistant.components import persistent_notification
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import CONF_NOTIFY_SERVICE, DOMAIN
from .fil_pilote import central_option

_LOGGER = logging.getLogger("custom_components.electric_heater")

CONF_MAX_SAFE_TEMP = "consigne_max_securite"
CONF_OVERHEAT_MARGIN = "marge_surchauffe"
CONF_UNSTABLE_COUNT = "seuil_detecteur_instable"
DEFAULT_MAX_SAFE_TEMP = 23.0
DEFAULT_OVERHEAT_MARGIN = 2.0
DEFAULT_UNSTABLE_COUNT = 5
OVERHEAT_DELAY = 180
DISOBEY_POWER_W = 10
OVERHEAT_RATE = 1800
UNSTABLE_RATE = 6 * 3600
UNSTABLE_WINDOW = 3600
SIGNAL_ALERTS = f"{DOMAIN}_alerts"
EVENT_ALERT = f"{DOMAIN}_alerte"
_TITLE = "Chauffage fil pilote"


def max_safe_temp(hass: HomeAssistant) -> float:
    try:
        return float(central_option(hass, CONF_MAX_SAFE_TEMP, DEFAULT_MAX_SAFE_TEMP))
    except (TypeError, ValueError):
        return DEFAULT_MAX_SAFE_TEMP


def overheat_margin(hass: HomeAssistant) -> float:
    try:
        return float(central_option(hass, CONF_OVERHEAT_MARGIN, DEFAULT_OVERHEAT_MARGIN))
    except (TypeError, ValueError):
        return DEFAULT_OVERHEAT_MARGIN


def unstable_count(hass: HomeAssistant) -> int:
    try:
        return int(central_option(hass, CONF_UNSTABLE_COUNT, DEFAULT_UNSTABLE_COUNT))
    except (TypeError, ValueError):
        return DEFAULT_UNSTABLE_COUNT


def clamp_target(hass: HomeAssistant, value: Any) -> Any:
    if not isinstance(value, (int, float)):
        return value
    return min(float(value), max_safe_temp(hass))


def alerts(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    """{entry_id: {"piece", "surchauffe", "surchauffe_detail", "instable", "instable_detail"}}"""
    result: dict[str, dict[str, Any]] = hass.data.setdefault(DOMAIN, {}).setdefault("_alerts", {})
    return result


def set_alert(hass: HomeAssistant, entry_id: str, piece: str, kind: str, on: bool, detail: Any = None) -> bool:
    room = alerts(hass).setdefault(entry_id, {"piece": piece})
    room["piece"] = piece
    changed = bool(room.get(kind)) != on
    room[kind] = on
    room[f"{kind}_detail"] = detail if on else None
    if changed:
        async_dispatcher_send(hass, SIGNAL_ALERTS)
    return changed


def send_alert(hass: HomeAssistant, key: str, message: str, rate: float, data: dict[str, Any]) -> None:
    """Événement + notification persistante + services notify (limité dans le temps)."""
    hass.bus.async_fire(EVENT_ALERT, {**data, "message": message})
    _LOGGER.warning("Alerte chauffage : %s", message)
    last = hass.data.setdefault(DOMAIN, {}).setdefault("_alert_sent", {})
    now = time.monotonic()
    if key in last and now - last[key] < rate:
        return
    last[key] = now
    persistent_notification.async_create(
        hass, message, title=_TITLE, notification_id=f"{DOMAIN}_{key}"
    )
    raw = central_option(hass, CONF_NOTIFY_SERVICE, []) or []
    items = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
    for item in items:
        service = str(item).strip().removeprefix("notify.")
        if service and hass.services.has_service("notify", service):
            hass.async_create_task(
                hass.services.async_call("notify", service, {"title": _TITLE, "message": message})
            )
