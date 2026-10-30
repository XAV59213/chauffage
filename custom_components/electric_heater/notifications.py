"""Notifications Home Assistant : sondes / piles KO et fenêtres ouvertes."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_interval,
)
from datetime import timedelta

from .const import (
    CONF_NOTIFICATIONS,
    CONF_NOTIFY_SERVICE,
    CONF_TEMPERATURE_SENSOR,
    CONF_WINDOW_OFF_DELAY,
    DOMAIN,
    WINDOW_OFF_DELAY,
)
from .fil_pilote import (
    all_configured_windows,
    is_window_open_state,
    iter_room_entries,
    room_current_temp,
    windows_from_entry,
)

_LOGGER = logging.getLogger(__name__)

PILE_FAIBLE = 20
_TITLE = "Chauffage fil pilote"


def _name(hass: HomeAssistant, entity_id: str) -> str:
    st = hass.states.get(entity_id)
    return (st and st.attributes.get("friendly_name")) or entity_id


class HeaterNotifier:
    """Une notification par problème, envoyée une seule fois et retirée au retour à la normale."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._active: set[str] = set()
        self._pending: dict[str, Any] = {}
        self._unsubs: list = []

    # -- options --------------------------------------------------------
    def _opt(self, key: str, default: Any = None) -> Any:
        value = (self.entry.options or {}).get(key, self.entry.data.get(key))
        return default if value is None else value

    def _window_delay(self) -> float:
        try:
            return float(self._opt(CONF_WINDOW_OFF_DELAY, WINDOW_OFF_DELAY))
        except (TypeError, ValueError):
            return float(WINDOW_OFF_DELAY)

    # -- sources --------------------------------------------------------
    def _room_sensors(self) -> dict[str, str]:
        return {
            e.data[CONF_TEMPERATURE_SENSOR]: e.data.get("name") or e.title
            for e in iter_room_entries(self.hass)
            if e.data.get(CONF_TEMPERATURE_SENSOR)
        }

    def _window_invert(self) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for entry in self.hass.config_entries.async_entries(DOMAIN):
            inv = bool(entry.data.get("window_invert") or (entry.options or {}).get("window_invert"))
            for eid in windows_from_entry(entry):
                result.setdefault(eid, inv)
        return result

    def _window_batteries(self) -> dict[str, str]:
        """Capteur batterie (même appareil) -> détecteur de fenêtre."""
        ent_reg = er.async_get(self.hass)
        out: dict[str, str] = {}
        for wid in all_configured_windows(self.hass):
            ent = ent_reg.async_get(wid)
            if not ent or not ent.device_id:
                continue
            for other in er.async_entries_for_device(ent_reg, ent.device_id):
                st = self.hass.states.get(other.entity_id)
                if st and st.attributes.get("device_class") == "battery":
                    out[other.entity_id] = wid
        return out

    # -- notifications ----------------------------------------------------
    def _notify(self, key: str, message: str) -> None:
        if key in self._active:
            return
        self._active.add(key)
        _LOGGER.info("Notification : %s", message)
        persistent_notification.async_create(
            self.hass, message, title=_TITLE, notification_id=f"{DOMAIN}_{key}"
        )
        service = str(self._opt(CONF_NOTIFY_SERVICE, "") or "").strip()
        if service:
            service = service.removeprefix("notify.")
            if self.hass.services.has_service("notify", service):
                self.hass.async_create_task(
                    self.hass.services.async_call(
                        "notify", service, {"title": _TITLE, "message": message}
                    )
                )
            else:
                _LOGGER.warning("Service notify.%s introuvable", service)

    def _clear(self, key: str) -> None:
        if key in self._active:
            self._active.discard(key)
            persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{key}")

    # -- évaluation -------------------------------------------------------
    @callback
    def _check_sensors(self, _event=None) -> None:
        for sensor, piece in self._room_sensors().items():
            key = f"sonde_{sensor}"
            if room_current_temp(self.hass, sensor) is None:
                self._notify(
                    key,
                    f"🔋 Sonde de température KO – {piece} ({sensor}) : remplacer la pile de la sonde. "
                    "Le radiateur est en Hors-gel par sécurité.",
                )
            else:
                self._clear(key)
        for bat, wid in self._window_batteries().items():
            key = f"pile_{bat}"
            st = self.hass.states.get(bat)
            low = False
            detail = ""
            if st and st.state not in ("unknown", "unavailable"):
                if bat.startswith("binary_sensor."):
                    low = st.state == "on"
                else:
                    try:
                        pct = float(st.state)
                        low = pct <= PILE_FAIBLE
                        detail = f" ({round(pct)} %)"
                    except ValueError:
                        low = False
            if low:
                self._notify(key, f"🔋 Pile faible du détecteur de fenêtre « {_name(self.hass, wid)} »{detail} : à remplacer.")
            else:
                self._clear(key)

    @callback
    def _check_windows(self, _event=None) -> None:
        for wid, invert in self._window_invert().items():
            st = self.hass.states.get(wid)
            known = st is not None and st.state not in ("unknown", "unavailable")
            opened = known and (is_window_open_state(st) != invert)
            key = f"fenetre_{wid}"
            if opened:
                if key in self._active or wid in self._pending:
                    continue

                @callback
                def _confirm(_now, wid=wid, key=key, invert=invert) -> None:
                    self._pending.pop(wid, None)
                    cur = self.hass.states.get(wid)
                    if cur and is_window_open_state(cur) != invert:
                        self._notify(
                            key,
                            f"🪟 Fenêtre ouverte : « {_name(self.hass, wid)} ». "
                            "Le chauffage de la pièce passe en mode fenêtre.",
                        )

                self._pending[wid] = async_call_later(self.hass, self._window_delay(), _confirm)
            else:
                if (cancel := self._pending.pop(wid, None)):
                    cancel()
                self._clear(key)

    # -- cycle de vie -----------------------------------------------------
    async def async_start(self) -> None:
        if not self._opt(CONF_NOTIFICATIONS, True):
            return
        watched = list(self._room_sensors()) + list(self._window_batteries())
        if watched:
            self._unsubs.append(
                async_track_state_change_event(self.hass, watched, self._check_sensors)
            )
        windows = all_configured_windows(self.hass)
        if windows:
            self._unsubs.append(
                async_track_state_change_event(self.hass, windows, self._check_windows)
            )
        # Pièces / fenêtres ajoutées après le démarrage.
        self._unsubs.append(
            async_track_time_interval(self.hass, self._periodic, timedelta(minutes=5))
        )
        self._check_sensors()
        self._check_windows()

    @callback
    def _periodic(self, _now=None) -> None:
        self._check_sensors()
        self._check_windows()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            unsub()
        self._unsubs.clear()
        for cancel in self._pending.values():
            cancel()
        self._pending.clear()
