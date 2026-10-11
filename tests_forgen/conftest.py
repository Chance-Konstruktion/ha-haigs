"""Ausstattung der Forgen-Bahn: echte Gitea- und Forgejo-Instanzen.

Diese Bahn laeuft NUR im Job ``tests-forgen``: ``ci/forgen.sh`` startet
beide Instanzen ohne TLS, ``ci/forgen_saat.py`` saet unsere Repos. Hier
wird -- anders als in ``tests/`` -- wirklich ins Netz gerufen, aber nur
nach 127.0.0.1. Ohne die Variable ``HAIGS_FORGEN`` springt die Bahn
ueber sich selbst, damit ein lokales ``pytest tests_forgen`` nicht rot
wird, nur weil keine Forge laeuft.
"""

from __future__ import annotations

import os

import aiohttp
import pytest

import tests.kern_laden  # noqa: F401 -- Anmeldung als Nebenwirkung

#: name -> Basisadresse; gesetzt vom CI-Job ("gitea=http://...,forgejo=...").
FORGEN = dict(
    paar.split("=", 1) for paar in os.environ.get("HAIGS_FORGEN", "").split(",") if paar
)

pytestmark = pytest.mark.skipif(not FORGEN, reason="HAIGS_FORGEN nicht gesetzt")


@pytest.fixture(params=sorted(FORGEN) or ["keine"])
def forge_name(request) -> str:
    if request.param == "keine":
        pytest.skip("HAIGS_FORGEN nicht gesetzt")
    return request.param


@pytest.fixture
def eingabe(forge_name: str) -> str:
    """Was der Mensch in den Dialog tippt: die Adresse MIT http://."""
    return FORGEN[forge_name]


@pytest.fixture
async def klient_und_spur():
    """Echter AiohttpClient ohne Token -- und die Liste aller gerufenen URLs."""
    spur: list[str] = []

    async def mitschreiben(_sitzung, _ctx, params) -> None:
        spur.append(str(params.url))

    verfolgung = aiohttp.TraceConfig()
    verfolgung.on_request_start.append(mitschreiben)
    # Erst hier importiert: der Kern ist erst nach tests.kern_laden da,
    # und die Import-Sortierung darf das nicht umdrehen.
    from haigs.core.http_aiohttp import AiohttpClient

    async with aiohttp.ClientSession(trace_configs=[verfolgung]) as sitzung:
        yield AiohttpClient(sitzung, None), spur
