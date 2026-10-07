"""Gemeinsame Ausstattung der Home-Assistant-Bahn.

Diese Bahn laeuft mit ``-p pytest_homeassistant_custom_component``
(siehe CI-Job ``tests-homeassistant``): das Plugin stellt ``hass`` und
die weiteren Fixtures. Die Kern-Suite in ``tests/`` bekommt von alledem
nichts mit und bleibt ohne Home-Assistant-Installation lauffaehig.

Die Attrappe aus ``tests/attrappe.py`` leistet hier denselben Dienst
wie im Kern: Home Assistants aiohttp-Clientsitzung wird durch sie
ersetzt, der ganze Weg -- Einrichtungsdialog bis Herzschlag -- laeuft
offline.
"""

from __future__ import annotations

from typing import Any

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.attrappe import Aufzeichnung, SitzungsAttrappe


@pytest.fixture(autouse=True)
def _eigene_integration_freischalten(enable_custom_integrations: None) -> None:
    """Jeder Test dieser Bahn laedt die eigene Integration aus dem Repo."""
    yield


@pytest.fixture(autouse=True)
async def _wie_im_richtigen_haus(hass: HomeAssistant) -> None:
    """http und websocket_api stehen bereit, bevor Integrationen laufen.

    Das Hochfahren von Home Assistant richtet beides immer vor den
    Konfigurationseintraegen (Bootstrap-Reihenfolge). Die Testumgebung
    tut das erst auf Anfrage -- seit Stufe M7 meldet die Oberflaeche
    einen statischen Weg an, sobald die Komponente laeuft, darum wird
    die Produktions-Reihenfolge hier fuer jeden Test hergestellt.
    """
    assert await async_setup_component(hass, "websocket_api", {})
    yield


@pytest.fixture
def sitzung_einpflanzen(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Setzt die HA-Clientsitzung durch die Attrappe -- offline.

    Jeder Aufruf pflanzt eine frische Attrappe mit eigenen
    Aufzeichnungen; beide Stellen, die die Sitzung holen (Einrichtungs-
    dialog und Geruest), werden ersetzt.
    """

    def _einpflanzen(aufzeichnungen: list[Aufzeichnung]) -> SitzungsAttrappe:
        attrappe = SitzungsAttrappe(list(aufzeichnungen))
        for ziel in (
            "custom_components.haigs.config_flow",
            "custom_components.haigs",
        ):
            monkeypatch.setattr(
                f"{ziel}.async_get_clientsession",
                lambda hass, **_: attrappe,
            )
        return attrappe

    return _einpflanzen


@pytest.fixture
def tote_sitzung(monkeypatch: pytest.MonkeyPatch, hass: HomeAssistant) -> None:
    """Eine Sitzung, bei der schon der Verbindungsaufbau stirbt."""

    class _ToteSitzung:
        async def get(self, url, *, params=None, headers=None):
            raise OSError("Verbindungsaufbau fehlgeschlagen")

    for ziel in (
        "custom_components.haigs.config_flow",
        "custom_components.haigs",
    ):
        monkeypatch.setattr(
            f"{ziel}.async_get_clientsession",
            lambda hass, **_: _ToteSitzung(),
        )
