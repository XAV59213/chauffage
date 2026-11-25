"""Carte Lovelace : cache-busting, attributs lus par la carte, tests JS (node)."""

import hashlib
import shutil
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.electric_heater import frontend
from custom_components.electric_heater.const import VERSION

ROOT = Path(__file__).resolve().parents[1]
CARD = ROOT / "custom_components/electric_heater/frontend/electric-heater-card.js"
NODE = shutil.which("node")


async def test_card_url_has_content_hash(hass: HomeAssistant) -> None:
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    with patch.object(frontend, "add_extra_js_url") as add:
        await frontend.async_register_card(hass)
    digest = hashlib.sha256(CARD.read_bytes()).hexdigest()[:8]
    assert add.call_args[0][1] == f"/electric_heater/electric-heater-card.js?v={VERSION}-{digest}"


async def test_card_version_without_file(hass: HomeAssistant) -> None:
    with patch.object(Path, "read_bytes", side_effect=OSError):
        assert await frontend.card_version(hass) == VERSION


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_card_js_syntax() -> None:
    subprocess.run([NODE, "--check", str(CARD)], check=True)


@pytest.mark.skipif(NODE is None, reason="node absent")
def test_card_js_behaviour() -> None:
    result = subprocess.run(
        [NODE, str(ROOT / "tests/js/card_test.js")], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
