"""Saison de chauffe automatique (dates + température extérieure)."""
from __future__ import annotations

from datetime import datetime
import logging
import re
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .fil_pilote import central_option
from .weather import outdoor_temperature

_LOGGER = logging.getLogger("custom_components.electric_heater")

CONF_SAISON_ACTIVE = "saison_chauffe_active"
CONF_DEBUT_SAISON = "debut_saison"
CONF_FIN_SAISON = "fin_saison"
CONF_CAPTEUR_EXT = "capteur_temperature_exterieure"
CONF_SEUIL_EXT = "seuil_exterieur"

DEFAULT_DEBUT = "10-15"
DEFAULT_FIN = "04-15"
DEFAULT_SEUIL = 16.0
HYST_EXT = 1.0  # °C
MIN_DURATION = 6 * 3600  # 6 h avant bascule par température (anti-flap)
FROST_FLOOR = 7.0  # °C hors saison → Hors-gel pièce
_MMDD = re.compile(r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")


def _parse_mmdd(value: str | None, default: str) -> tuple[int, int]:
    raw = (value or default).strip()
    if not _MMDD.match(raw):
        raw = default
    mm, dd = raw.split("-")
    return int(mm), int(dd)


def in_date_season(now: datetime | None = None, debut: str | None = None, fin: str | None = None) -> bool:
    """True si la date du jour est dans [début, fin] (saison qui peut chevaucher le nouvel an)."""
    now = now or dt_util.now()
    sm, sd = _parse_mmdd(debut, DEFAULT_DEBUT)
    em, ed = _parse_mmdd(fin, DEFAULT_FIN)
    start = (sm, sd)
    end = (em, ed)
    today = (now.month, now.day)
    if start <= end:
        return start <= today <= end
    # Ex. 15/10 → 15/04
    return today >= start or today <= end


def read_outdoor(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Température extérieure depuis un sensor (°C) ou une entité weather."""
    if not entity_id:
        return None
    if entity_id.startswith("weather."):
        return outdoor_temperature(hass, entity_id)
    st = hass.states.get(entity_id)
    if not st or st.state in ("unknown", "unavailable"):
        return None
    try:
        return round(float(st.state), 1)
    except (TypeError, ValueError):
        raw = st.attributes.get("temperature")
        try:
            return round(float(raw), 1) if raw is not None else None
        except (TypeError, ValueError):
            return None


class SeasonController:
    """Décide si on est en saison de chauffe (dates + seuil extérieur anti-flap)."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._pending_out: bool | None = None
        self._pending_since: float | None = None
        self._outdoor_override: bool | None = None  # True = forcer hors saison par T°ext
        self._samples: list[tuple[float, float]] = []  # (monotonic, temp) 24 h

    def options(self) -> dict[str, Any]:
        return {
            "active": bool(central_option(self.hass, CONF_SAISON_ACTIVE, True)),
            "debut": central_option(self.hass, CONF_DEBUT_SAISON, DEFAULT_DEBUT) or DEFAULT_DEBUT,
            "fin": central_option(self.hass, CONF_FIN_SAISON, DEFAULT_FIN) or DEFAULT_FIN,
            "capteur": central_option(self.hass, CONF_CAPTEUR_EXT),
            "seuil": float(central_option(self.hass, CONF_SEUIL_EXT, DEFAULT_SEUIL) or DEFAULT_SEUIL),
        }

    def _avg_24h(self, current: float | None) -> float | None:
        now = time.monotonic()
        if current is not None:
            self._samples.append((now, current))
        self._samples = [(t, v) for t, v in self._samples if now - t < 86400]
        if not self._samples:
            return current
        return round(sum(v for _, v in self._samples) / len(self._samples), 1)

    def evaluate(self) -> dict[str, Any]:
        """Retourne l'état saison : in_season, reason, outdoor, ..."""
        opt = self.options()
        if not opt["active"]:
            return {
                "in_season": True,
                "raison": "saison_desactivee",
                "outdoor": None,
                "outdoor_avg": None,
                "date_ok": True,
                **opt,
            }
        date_ok = in_date_season(debut=opt["debut"], fin=opt["fin"])
        outdoor = read_outdoor(self.hass, opt["capteur"])
        avg = self._avg_24h(outdoor)
        ref = avg if avg is not None else outdoor
        outdoor_force_off = False
        if ref is not None and opt["capteur"]:
            seuil = opt["seuil"]
            want_off = ref >= seuil + (0 if self._outdoor_override else HYST_EXT)
            want_on = ref <= seuil - (0 if not self._outdoor_override else HYST_EXT)
            # Anti-flap : confirmer 6 h
            target = None
            if self._outdoor_override is None:
                target = True if ref >= seuil else False
            elif self._outdoor_override and want_on:
                target = False
            elif not self._outdoor_override and want_off:
                target = True
            if target is not None and target != self._outdoor_override:
                if self._pending_out != target:
                    self._pending_out = target
                    self._pending_since = time.monotonic()
                elif self._pending_since and time.monotonic() - self._pending_since >= MIN_DURATION:
                    self._outdoor_override = target
                    self._pending_out = None
                    self._pending_since = None
                    _LOGGER.info(
                        "Saison : bascule température extérieure → %s (moy=%.1f °C, seuil=%.1f)",
                        "hors saison" if target else "en saison",
                        ref,
                        seuil,
                    )
            else:
                self._pending_out = None
                self._pending_since = None
            if self._outdoor_override is None:
                self._outdoor_override = ref >= seuil
            outdoor_force_off = bool(self._outdoor_override)
        in_season = date_ok and not outdoor_force_off
        if not date_ok:
            raison = "hors_periode"
        elif outdoor_force_off:
            raison = "exterieur_chaud"
        else:
            raison = "en_saison"
        return {
            "in_season": in_season,
            "raison": raison,
            "outdoor": outdoor,
            "outdoor_avg": avg,
            "date_ok": date_ok,
            **opt,
        }


def get_season(hass: HomeAssistant) -> SeasonController:
    store = hass.data.setdefault("electric_heater", {}).setdefault("_season", {})
    if "ctrl" not in store:
        store["ctrl"] = SeasonController(hass)
    return store["ctrl"]
