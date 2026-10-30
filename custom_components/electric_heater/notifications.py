"""Notifications Home Assistant : sondes / piles KO et fenêtres ouvertes."""
from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
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
from .occupancy import present_names
from .fil_pilote import (
    get_central_state,
    open_windows,
    all_configured_windows,
    is_window_open_state,
    iter_room_entries,
    room_current_temp,
    windows_from_entry,
)

_LOGGER = logging.getLogger(__name__)

PILE_FAIBLE = 20
# Délai de grâce après le démarrage de HA (entités Zigbee / MQTT pas encore chargées)
STARTUP_GRACE = 180
# Une sonde / pile doit rester KO ce temps avant d'alerter (évite les coupures brèves)
KO_CONFIRM = 120
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
        self._ready = False
        self._ko_since: dict[str, float] = {}

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
            for eid in windows_from_entry(entry, self.hass):
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
        persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{key}_ok")
        self._send(f"{DOMAIN}_{key}", message)

    def _send(self, notification_id: str, message: str) -> None:
        _LOGGER.info("Notification : %s", message)
        persistent_notification.async_create(
            self.hass, message, title=_TITLE, notification_id=notification_id
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

    def _clear(self, key: str, ok_message: str | None = None) -> None:
        self._ko_since.pop(key, None)
        if key in self._active:
            self._active.discard(key)
            persistent_notification.async_dismiss(self.hass, f"{DOMAIN}_{key}")
            if ok_message:
                self._send(f"{DOMAIN}_{key}_ok", ok_message)

    def _confirmed_ko(self, key: str) -> bool:
        """Vrai si le problème dure depuis KO_CONFIRM secondes (et après la grâce de démarrage)."""
        now = time.monotonic()
        since = self._ko_since.setdefault(key, now)
        return self._ready and now - since >= KO_CONFIRM

    # -- évaluation -------------------------------------------------------
    @callback
    def _check_sensors(self, _event=None) -> None:
        for sensor, piece in self._room_sensors().items():
            key = f"sonde_{sensor}"
            if room_current_temp(self.hass, sensor) is None:
                if not self._confirmed_ko(key):
                    continue
                self._notify(
                    key,
                    f"🔋 Sonde de température KO – {piece} ({sensor}) : remplacer la pile de la sonde. "
                    "Le radiateur est en Hors-gel par sécurité.",
                )
            else:
                self._clear(
                    key,
                    f"✅ Sonde de température OK – {piece} ({sensor}) : de nouveau disponible, "
                    "régulation normale reprise.",
                )
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
                if not self._confirmed_ko(key):
                    continue
                self._notify(key, f"🔋 Pile faible du détecteur de fenêtre « {_name(self.hass, wid)} »{detail} : à remplacer.")
            elif st and st.state not in ("unknown", "unavailable"):
                self._clear(key, f"✅ Pile du détecteur de fenêtre « {_name(self.hass, wid)} »{detail} : OK.")

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
            async_track_time_interval(self.hass, self._periodic, timedelta(seconds=30))
        )
        # Grâce de démarrage : pas d'alerte sonde / pile tant que tout n'est pas chargé.
        if self.hass.is_running:
            self._start_grace()
        else:
            self._unsubs.append(
                self.hass.bus.async_listen_once(
                    EVENT_HOMEASSISTANT_STARTED, lambda _e: self._start_grace()
                )
            )
        self._check_windows()

    @callback
    def _start_grace(self) -> None:
        self._unsubs.append(async_call_later(self.hass, STARTUP_GRACE, self._end_grace))

    @callback
    def _end_grace(self, _now=None) -> None:
        self._ready = True
        self._ko_since = {k: time.monotonic() - KO_CONFIRM for k in self._ko_since}
        self._send_startup()
        self._check_sensors()
        self._check_absent()

    def _send_startup(self) -> None:
        """Après la grâce : « système opérationnel » + résumé des problèmes en cours."""
        problems: list[str] = []
        ko = [p for s, p in self._room_sensors().items() if room_current_temp(self.hass, s) is None]
        if ko:
            problems.append("sonde(s) KO : " + ", ".join(ko))
        wins = [w["name"] for w in open_windows(self.hass)]
        if wins:
            problems.append("fenêtre(s) ouverte(s) : " + ", ".join(wins))
        if problems:
            msg = "✅ Chauffage fil pilote opérationnel. ⚠️ Problème(s) : " + " ; ".join(problems) + "."
        else:
            msg = "✅ Chauffage fil pilote opérationnel : tout est OK."
        self._send(f"{DOMAIN}_demarrage", msg)

    # -- fenêtre ouverte + maison vide --------------------------------------
    def _occupants(self) -> int | None:
        central = get_central_state(self.hass)
        occ = central.attributes.get("occupants") if central else None
        if isinstance(occ, (int, float)):
            return int(occ)
        data = {**dict(self.entry.data), **dict(self.entry.options or {})}
        try:
            return len(present_names(self.hass, data))
        except Exception:  # noqa: BLE001
            return None

    @callback
    def _check_absent(self, _event=None) -> None:
        key = "fenetre_absents"
        if not self._ready:
            return
        wins = open_windows(self.hass)
        occ = self._occupants()
        if wins and occ == 0:
            if not self._confirmed_ko(key):
                return
            names = ", ".join(w["name"] for w in wins)
            self._notify(key, f"🚪 Personne à la maison et fenêtre(s) ouverte(s) : {names}. Pensez à fermer.")
        else:
            self._clear(key, "✅ Fenêtres fermées ou quelqu'un est rentré." if wins == [] else None)

    @callback
    def _periodic(self, _now=None) -> None:
        self._check_sensors()
        self._check_windows()
        self._check_absent()

    @callback
    def async_stop(self) -> None:
        for unsub in self._unsubs:
            try:
                unsub()
            except Exception:  # noqa: BLE001 - écouteur déjà déclenché
                pass
        self._unsubs.clear()
        for cancel in self._pending.values():
            cancel()
        self._pending.clear()
