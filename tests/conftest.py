"""Fixtures communes."""

from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Active les intégrations personnalisées."""
    yield


@pytest.fixture(autouse=True)
def no_card():
    """La carte Lovelace a besoin du serveur HTTP : on la neutralise."""
    with patch(
        "custom_components.electric_heater.async_register_card", AsyncMock()
    ):
        yield


@pytest.fixture(autouse=True)
def fake_frontend(hass):
    """frontend/http (carte Lovelace) inutiles en test : marqués comme chargés."""
    hass.config.components.update({"http", "frontend"})
    yield
