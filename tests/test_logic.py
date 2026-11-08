"""Régulation : hystérésis, arrondis, saison."""

from datetime import datetime

import pytest

from custom_components.electric_heater.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    PRESET_FROST_PROTECTION,
    PRESET_OFF,
)
from custom_components.electric_heater.hysteresis import (
    order_heats,
    regulate_preset,
    should_heat,
)
from custom_components.electric_heater.season import in_date_season
from custom_components.electric_heater.temps import clean_setpoints, round_temp


@pytest.mark.parametrize(
    ("current", "last", "expected"),
    [
        (18.0, None, PRESET_COMFORT),  # bien sous la consigne : chauffe
        (20.5, None, PRESET_OFF),  # au-dessus : arrêt
        (20.0, None, PRESET_OFF),  # consigne atteinte : arrêt
        (19.9, PRESET_OFF, PRESET_OFF),  # dans l'hystérésis : garde l'arrêt
        (19.9, PRESET_COMFORT, PRESET_COMFORT),  # dans l'hystérésis : garde la chauffe
        (None, None, PRESET_OFF),  # sonde KO : jamais Confort
    ],
)
def test_regulate_comfort(current, last, expected) -> None:
    assert regulate_preset(PRESET_COMFORT, current, 20.0, last, comfort_hyst=0.3) == expected


def test_eco_never_becomes_comfort() -> None:
    assert regulate_preset(PRESET_ECO, 10.0, 20.0) == PRESET_ECO


def test_hold_presets_untouched() -> None:
    assert regulate_preset(PRESET_OFF, 10.0, 20.0) == PRESET_OFF
    assert regulate_preset(PRESET_FROST_PROTECTION, 25.0, 20.0) == PRESET_FROST_PROTECTION


def test_above_frost_and_invalid_target() -> None:
    assert regulate_preset(PRESET_COMFORT, 21, 20, above=PRESET_FROST_PROTECTION) == PRESET_FROST_PROTECTION
    assert regulate_preset(PRESET_COMFORT, 21, 20, above=PRESET_ECO) == PRESET_OFF
    assert regulate_preset(PRESET_COMFORT, 15, 0) == PRESET_OFF


def test_should_heat_and_orders() -> None:
    assert should_heat(18, 20, PRESET_COMFORT, False)
    assert not should_heat(20.1, 20, PRESET_COMFORT, True)
    assert should_heat(19.9, 20, PRESET_COMFORT, True, comfort_hyst=0.5)
    assert not should_heat(None, 20, PRESET_COMFORT, True)
    assert order_heats(PRESET_COMFORT) and not order_heats(PRESET_ECO)


def test_round_and_clean() -> None:
    assert round_temp(20.199999999999998) == 20.2
    assert round_temp(None) is None and round_temp(True) is None and round_temp("x") is None
    assert clean_setpoints({"comfort_temp": 11.600000000000001}) == {"comfort_temp": 11.6}
    assert clean_setpoints({"comfort_temp": 20.2}) is None


def test_date_season() -> None:
    assert in_date_season(datetime(2026, 1, 15), "10-01", "04-30")
    assert not in_date_season(datetime(2026, 7, 15), "10-01", "04-30")
