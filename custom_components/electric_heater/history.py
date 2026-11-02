"""Historique des décisions de régulation par radiateur (persisté)."""
from __future__ import annotations

from collections import deque
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN

_LOGGER = logging.getLogger("custom_components.electric_heater")

MAX_ENTRIES = 200
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
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.history_{entry_id}")
        self.entries: deque[dict[str, Any]] = deque(maxlen=MAX_ENTRIES)

    async def async_load(self) -> None:
        try:
            data = await self._store.async_load()
        except Exception:  # noqa: BLE001
            data = None
        if isinstance(data, list):
            self.entries.extend(data[-MAX_ENTRIES:])

    def add(self, **entry: Any) -> dict[str, Any]:
        entry = {"time": dt_util.now().isoformat(timespec="seconds"), **entry}
        self.entries.append(entry)
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
        return entry

    def last(self, count: int = ATTR_ENTRIES) -> list[dict[str, Any]]:
        return list(self.entries)[-count:][::-1]
