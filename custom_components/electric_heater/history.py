"""Historique des décisions de régulation par radiateur (persisté)."""
from __future__ import annotations
from homeassistant.core import Context

from collections import deque
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger("custom_components.electric_heater")

MAX_ENTRIES = 200
MERGED_ID = "central_decisions"
ATTR_ENTRIES = 20
STORAGE_VERSION = 1


def find_power_sensor(hass: HomeAssistant, select_id: str | None) -> str | None:
    """Capteur de puissance (W) du même appareil que le relais fil pilote."""
    if not select_id:
        return None
    reg = er.async_get(hass)
    ent = reg.async_get(select_id)
    if not ent or not ent.device_id:
        return None
    for cand in er.async_entries_for_device(reg, ent.device_id):
        if cand.domain != "sensor" or cand.disabled_by:
            continue
        st = hass.states.get(cand.entity_id)
        unit = (st and st.attributes.get("unit_of_measurement")) or cand.unit_of_measurement
        dclass = cand.device_class or cand.original_device_class
        if unit in ("W", "kW") or dclass == "power":
            return cand.entity_id
    return None


def read_power(hass: HomeAssistant, sensor_id: str | None) -> float | None:
    if not sensor_id:
        return None
    st = hass.states.get(sensor_id)
    if st is None:
        return None
    try:
        val = float(st.state)
    except (AttributeError, TypeError, ValueError):
        return None
    if st.attributes.get("unit_of_measurement") == "kW":
        val *= 1000
    return round(val, 1)


class DecisionHistory:
    """Tampon circulaire des décisions, sauvegardé dans .storage."""

    def __init__(self, hass: HomeAssistant, entry_id: str, name: str) -> None:
        self.hass = hass
        self.name = name
        self.entry_id = entry_id
        self._loaded = False
        self._store: Store[list[dict[str, Any]]] = Store(hass, STORAGE_VERSION, f"{DOMAIN}.history_{entry_id}")
        self.entries: deque[dict[str, Any]] = deque(maxlen=MAX_ENTRIES)

    async def async_load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        try:
            data = await self._store.async_load()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, list):
            self.entries.extendleft(reversed(data[-MAX_ENTRIES:]))

    def add(self, **entry: Any) -> dict[str, Any]:
        entry = {"time": dt_util.now().isoformat(timespec="seconds"), **entry}
        self.entries.append(entry)
        if entry.get("par"):
            _LOGGER.info("[%s] %s par %s : %s → %s", self.name, entry.get("reason"),
                         entry.get("par"), entry.get("ancien"), entry.get("nouveau"))
        _LOGGER.info(
            "[%s] décision %s → %s (raison=%s, temp=%s, consigne=%s, hyst=%s, puissance=%s W)",
            self.name,
            entry.get("previous_order"),
            entry.get("new_order"),
            entry.get("reason"),
            entry.get("current_temp"),
            entry.get("target"),
            entry.get("hysteresis"),
            entry.get("power_W"),
        )
        self._store.async_delay_save(lambda: list(self.entries), 10)
        async_dispatcher_send(self.hass, signal(self.entry_id))
        if self.entry_id not in ("central", MERGED_ID):
            get_history(self.hass, MERGED_ID, "Toutes les pièces").append_raw(
                {**entry, "piece": self.name}
            )
        return entry

    def append_raw(self, entry: dict[str, Any]) -> None:
        """Ajout sans journal (historique fusionné des pièces)."""
        self.entries.append(entry)
        self._store.async_delay_save(lambda: list(self.entries), 30)
        async_dispatcher_send(self.hass, signal(self.entry_id))

    def last(self, count: int = ATTR_ENTRIES) -> list[dict[str, Any]]:
        return list(self.entries)[-count:][::-1]


def signal(entry_id: str) -> str:
    return f"{DOMAIN}_history_{entry_id}"


def get_history(hass: HomeAssistant, entry_id: str, name: str = "") -> DecisionHistory:
    store: dict[str, DecisionHistory] = hass.data.setdefault(DOMAIN, {}).setdefault("_histories", {})
    if entry_id not in store:
        store[entry_id] = DecisionHistory(hass, entry_id, name)
    return store[entry_id]


REASON_LABELS: dict[Any, str] = {
    "below_target": "sous consigne",
    "above_target": "au-dessus consigne",
    "hysteresis_keep": "hystérésis (ordre gardé)",
    "window_open": "fenêtre ouverte",
    "window_unavailable_keep": "détecteur fenêtre indisponible",
    "absence": "absence",
    "sensor_ko": "sonde KO",
    "no_target_safe_off": "consigne absente (sécurité)",
    "no_sensor_follow_preset": "sans sonde (preset)",
    "off_mode": "mode arrêt",
    "startup_wait_valid_data": "démarrage, attente données",
    "external_change": "changé hors intégration",
    "radiator_not_obeying": "radiateur n'obéit pas",
    "radiateur_desobeit": "radiateur n'obéit pas → Arrêt forcé",
    "surchauffe": "SURCHAUFFE → Arrêt forcé",
    "surchauffe_terminee": "fin de surchauffe",
    "detecteur_instable": "détecteur fenêtre instable",
    "detecteur_stable": "détecteur fenêtre redevenu stable",
    "hors_saison": "hors saison → Arrêt",
    "hors_saison_hors_gel": "hors saison → Hors-gel (pièce froide)",
}
ORDER_LABELS: dict[Any, str] = {
    "comfort": "Confort", "comfort_m1": "Confort -1", "comfort_m2": "Confort -2",
    "eco": "Eco", "frost_protection": "Hors-gel", "off": "Arrêt",
}


def reason_label(code: str | None) -> str:
    if not code:
        return "–"
    prefix = ""
    if code.startswith("startup:"):
        prefix, code = "démarrage · ", code[8:]
    if code.startswith("preset_"):
        return prefix + "preset " + ORDER_LABELS.get(code[7:], code[7:])
    return prefix + REASON_LABELS.get(code, code)


def _num(v: Any) -> str:
    return "–" if not isinstance(v, (int, float)) else f"{v:.1f}".replace(".", ",")


def _val(v: Any) -> str:
    if isinstance(v, (int, float)):
        return f"{v:g}".replace(".", ",")
    return ORDER_LABELS.get(v, MODE_LABELS.get(v, str(v) if v is not None else "–"))


MODE_LABELS: dict[Any, str] = {"auto": "Auto", "heat": "Chauffe", "off": "Arrêt"}


def entry_summary(e: dict[str, Any] | None) -> str:
    if not e:
        return "Aucune décision"
    reason = e.get("reason") or ""
    if reason in CHANGE_LABELS:
        unit = " °C" if reason in ("changement_consigne", "consigne_limitee") else ""
        return (f"{CHANGE_LABELS[reason]} {_val(e.get('ancien'))}→{_val(e.get('nouveau'))}{unit}"
                f" · par {e.get('par') or 'système'}")[:255]
    if reason == "external_change" and e.get("par"):
        return (f"Fil pilote changé en {_val(e.get('new_order'))} · par {e['par']}")[:255]
    order = ORDER_LABELS.get(e.get("new_order"), e.get("new_order") or "–")
    p = e.get("power_W")
    power = "– W" if p is None else f"{p:.0f} W"
    return (f"{order} · {reason_label(e.get('reason'))} · "
            f"{_num(e.get('current_temp'))}/{_num(e.get('target'))} °C · {power}")[:255]


def describe_callers(limit: int = 4) -> str:
    """Court résumé des appelants : frames custom_components hors electric_heater.

    Renvoie "" si aucun appelant externe n'est trouvé (appelant inconnu).
    """
    import traceback

    bits: list[str] = []
    for frame in traceback.extract_stack()[:-1]:
        path = frame.filename.replace("\\", "/")
        if "custom_components/" not in path:
            continue
        rel = path.split("custom_components/", 1)[1]
        if rel.startswith("electric_heater/"):
            continue
        bits.append(f"{rel}:{frame.lineno}:{frame.name}")
    return " <- ".join(bits[-limit:])


async def format_context(hass: HomeAssistant, context: Context | None) -> str:
    """Détail du contexte HA (id, utilisateur, parent, origine reconnue)."""
    if context is None:
        return "context=None"
    own = hass.data.get(DOMAIN, {}).get("_own_contexts", set())
    in_own = context.id in own
    parent_own = bool(context.parent_id and context.parent_id in own)
    extra = ""
    if context.user_id:
        try:
            user = await hass.auth.async_get_user(context.user_id)
        except Exception:  # noqa: BLE001
            user = None
        if user:
            flags = []
            if getattr(user, "system_generated", False):
                flags.append("system_generated")
            if getattr(user, "is_admin", False):
                flags.append("admin")
            if getattr(user, "is_active", True) is False:
                flags.append("inactive")
            extra = f" user_name={user.name!r}"
            if flags:
                extra += f" user_flags={','.join(flags)}"
        else:
            extra = " user_name=?"
    matched = ""
    for domain, label in (("automation", "automation"), ("script", "script")):
        for st in hass.states.async_all(domain):
            if st.context and st.context.id in (context.id, context.parent_id):
                matched = f" matched={label}:{st.entity_id}"
                break
        if matched:
            break
    return (
        f"ctx_id={context.id} parent_id={context.parent_id} user_id={context.user_id}"
        f"{extra} own={in_own} parent_own={parent_own}{matched}"
    )


async def resolve_who(hass: HomeAssistant, context: Context | None) -> str:
    """Nom de l'auteur d'un changement à partir du contexte HA."""
    if context is None:
        return "système"
    own = hass.data.get(DOMAIN, {}).get("_own_contexts", set())
    # HA enveloppe souvent l'appel de service : le parent est notre contexte.
    if context.id in own or (context.parent_id and context.parent_id in own):
        return "intégration"
    if context.user_id:
        try:
            user = await hass.auth.async_get_user(context.user_id)
        except Exception:  # noqa: BLE001
            user = None
        return (user.name if user and user.name else "utilisateur")
    for domain, label in (("automation", "automatisation"), ("script", "script")):
        for st in hass.states.async_all(domain):
            if st.context and st.context.id in (context.id, context.parent_id):
                return f"{label} « {st.attributes.get('friendly_name', st.entity_id)} »"
    if context.parent_id:
        return "automatisation"
    return "système"


def own_context(hass: HomeAssistant) -> Context:
    """Contexte des écritures de l'intégration (attribution correcte dans le journal)."""
    ctx = Context()
    own = hass.data.setdefault(DOMAIN, {}).setdefault("_own_contexts", set())
    if len(own) > 500:
        own.clear()
    own.add(ctx.id)
    return ctx


CHANGE_LABELS = {"consigne_limitee": "Consigne limitée (sécurité)", "changement_consigne": "Consigne", "changement_mode": "Mode", "changement_preset": "Preset"}
