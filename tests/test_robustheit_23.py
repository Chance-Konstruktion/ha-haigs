"""Ticket #23 -- Robustheit (Kern): Deckel, Grenze, Vorfuehrer.

Drei der sieben Punkte des Sammeltickets leben ohne Home Assistant:
der Deckel auf ``Retry-After`` (Punkt 5), die Obergrenze beim Laden
eines Archivs (Punkt 7) und der Zielname, der im Vorfuehrer statt im
Ereigniskreis gelesen wird (Punkt 6). Die vier uebrigen -- Lager-Rennen,
erster Lauf, Unload, Herzschlag -- brauchen die HA-Schicht und stehen
in ``tests_ha/test_robustheit_23.py``.
"""

from __future__ import annotations

import asyncio
import io
import json
import threading
import zipfile
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

import pytest
from haigs import installation
from haigs.core.forge import ForgeFehler
from haigs.core.http_aiohttp import AiohttpClient
from haigs.installation import installiere_version

from tests.attrappe import Aufzeichnung, SitzungsAttrappe

URL = "https://gitlab.example.net/api/v4/projects"


class WarteProtokoll:
    """Statt zu schlafen: merkt sich die verlangten Sekunden."""

    def __init__(self) -> None:
        self.sekunden: list[float] = []

    async def __call__(self, sekunden: float) -> None:
        self.sekunden.append(sekunden)


def antwort(daten, status: int = 200, kopfzeilen: dict | None = None) -> Aufzeichnung:
    return Aufzeichnung(
        status=status, text=json.dumps(daten), kopfzeilen=kopfzeilen or {}
    )


def klient(aufzeichnungen, **rest):
    warte = rest.pop("warte", None) or WarteProtokoll()
    k = AiohttpClient(SitzungsAttrappe(list(aufzeichnungen)), warte=warte, **rest)
    return k, warte


# -- Punkt 5: Retry-After hat einen Deckel und kennt die Datumsform --


@pytest.mark.asyncio
async def test_429_mit_riesigem_retry_after_wartet_hoechstens_den_deckel():
    """``Retry-After: 3600`` waere eine Stunde Stillstand -- der Deckel greift.

    Der Anbieter darf um Geduld bitten, aber nicht die Integration
    stundenlang stilllegen; nach dem Deckel wird erneut gefragt, und
    die drei Versuche bleiben endlich.
    """
    k, warte = klient(
        [
            Aufzeichnung(status=429, text="", kopfzeilen={"Retry-After": "3600"}),
            antwort({"ok": True}),
        ]
    )
    assert await k.get_json(URL) == {"ok": True}
    assert warte.sekunden == [60.0]


@pytest.mark.asyncio
async def test_429_mit_http_datum_in_der_zukunft_wird_geparst_und_gedeckelt():
    """RFC 9110 erlaubt die Datumsform; vorher warf sie ValueError (-> 1 s).

    ``float("Wed, 21 Oct ...")`` scheitert immer -- die Datumsform fiel
    damit still auf die hoefliche Sekunde zurueck. Jetzt wird sie
    gelesen, und der Deckel gilt auch fuer sie.
    """
    k, warte = klient(
        [
            Aufzeichnung(
                status=429,
                text="",
                kopfzeilen={
                    "Retry-After": format_datetime(datetime.now(UTC) + timedelta(hours=1))
                },
            ),
            antwort({}),
        ]
    )
    await k.get_json(URL)
    assert warte.sekunden == [60.0]


@pytest.mark.asyncio
async def test_429_mit_nahem_http_datum_wartet_das_delta():
    """Die Wartezeit ist der Abstand bis zum genannten Zeitpunkt."""
    k, warte = klient(
        [
            Aufzeichnung(
                status=429,
                text="",
                kopfzeilen={
                    "Retry-After": format_datetime(
                        datetime.now(UTC) + timedelta(seconds=20)
                    )
                },
            ),
            antwort({}),
        ]
    )
    await k.get_json(URL)
    assert 15 <= warte.sekunden[0] <= 20, warte.sekunden


@pytest.mark.asyncio
async def test_429_mit_vergangenem_http_datum_wartet_nicht_negativ():
    """Ein Zeitpunkt, der schon vorbei ist, kostet keine Wartezeit."""
    k, warte = klient(
        [
            Aufzeichnung(
                status=429,
                text="",
                kopfzeilen={
                    "Retry-After": format_datetime(
                        datetime.now(UTC) - timedelta(seconds=30)
                    )
                },
            ),
            antwort({}),
        ]
    )
    await k.get_json(URL)
    assert warte.sekunden == [0.0]


# -- Punkt 7: der Download hat eine Obergrenze -----------------------


@pytest.mark.asyncio
async def test_download_mit_angekuendigter_ueberlaenge_bricht_vor_dem_lesen_ab():
    """Die ``Content-Length`` allein reicht: nicht erst alles einlesen.

    Die Grenze des Entpackers (256 MB entpackt) hilft hier nicht --
    sie greift nach dem Download. Angekuendigte Ueberlaenge wird
    abgewiesen, bevor der erste Block im Speicher landet.
    """
    aufzeichnung = Aufzeichnung(
        status=200, rohbytes=b"x" * 4096, kopfzeilen={"Content-Length": "4096"}
    )
    k, _ = klient([aufzeichnung], max_bytes=1024)
    with pytest.raises(ForgeFehler, match="4096"):
        await k.get_bytes(URL)
    assert aufzeichnung.content.gelesen == 0


@pytest.mark.asyncio
async def test_download_ohne_ankuendigung_bricht_beim_lesen_ab():
    """Ohne ``Content-Length`` (gestueckelt) zaehlt die Grenze beim Lesen."""
    aufzeichnung = Aufzeichnung(status=200, rohbytes=b"x" * 4096)
    k, _ = klient([aufzeichnung], max_bytes=1024)
    with pytest.raises(ForgeFehler, match="1024"):
        await k.get_bytes(URL)
    assert aufzeichnung.content.gelesen < 4096, "abgebrochen, nicht alles gelesen"


@pytest.mark.asyncio
async def test_download_unter_der_grenze_kommt_vollstaendig_an():
    """Die Grenze darf den Normalfall nicht anfassen."""
    k, _ = klient([Aufzeichnung(status=200, rohbytes=b"kleines archiv")], max_bytes=1024)
    assert await k.get_bytes(URL) == b"kleines archiv"


# -- Codex C03, Befund 3: die Grenze gilt fuer JSON genauso -----------


@pytest.mark.asyncio
async def test_json_ueber_grenze_wird_abgewiesen():
    """Eine JSON-Antwort folgt derselben Obergrenze wie jede Datei —
    ein fremder oder kaputter Server darf die Instanz nicht mit einer
    Riesen-Antwort aufdruecken (vorher las _als_json den Koerper
    vollstaendig, nur get_bytes trug die Grenze)."""
    aufzeichnung = Aufzeichnung(status=200, rohbytes=b'{"x": "' + b"y" * 4096)
    k, _ = klient([aufzeichnung], max_bytes=1024)
    with pytest.raises(ForgeFehler, match="1024"):
        await k.get_json(URL)
    assert aufzeichnung.content.gelesen < 4096, "abgebrochen, nicht alles gelesen"


@pytest.mark.asyncio
async def test_json_angekuendigte_ueberlaenge_wird_nicht_geladen():
    """Die angekuendigte Ueberlaenge wird abgewiesen, bevor der erste
    Block im Speicher landet — derselbe Griff wie beim Download."""
    aufzeichnung = Aufzeichnung(
        status=200,
        rohbytes=b'{"x": 1}',
        kopfzeilen={"Content-Length": "999999"},
    )
    k, _ = klient([aufzeichnung], max_bytes=1024)
    with pytest.raises(ForgeFehler, match="999999"):
        await k.get_json(URL)
    assert aufzeichnung.content.gelesen == 0


@pytest.mark.asyncio
async def test_json_unter_der_grenze_kommt_vollstaendig_an():
    """Die Grenze darf den Normalfall nicht anfassen."""
    k, _ = klient([antwort({"id": 7})], max_bytes=1024)
    assert await k.get_json(URL) == {"id": 7}


@pytest.mark.asyncio
async def test_json_liste_ueber_grenze_bricht_bei_der_seite_ab():
    """Auch die Folgeseiten einer Liste folgen der Grenze."""
    erste = Aufzeichnung(
        status=200, rohbytes=b'[{"id": 1}]', kopfzeilen={"X-Next-Page": "2"}
    )
    zweite = Aufzeichnung(status=200, rohbytes=b'[{"id": "' + b"y" * 4096 + b'"}]')
    k, _ = klient([erste, zweite], max_bytes=1024)
    with pytest.raises(ForgeFehler, match="1024"):
        await k.get_json(URL)


# -- Punkt 6: der Zielname wird im Vorfuehrer gelesen ----------------


class HassAttrappe:
    """So viel Home Assistant, wie ``installiere_version`` braucht."""

    def __init__(self, config_dir: Path) -> None:
        self.config = SimpleNamespace(config_dir=str(config_dir))

    async def async_add_executor_job(self, ziel, *args):
        return await asyncio.get_running_loop().run_in_executor(None, ziel, *args)


class ForgeAttrappe:
    """Liefert ein Tag-Archiv -- ohne Releases, ohne Netz."""

    def __init__(self, archiv: bytes) -> None:
        self.archiv_bytes = archiv

    async def releases(self, pfad: str):
        return []

    async def archiv(self, pfad: str, tag: str) -> bytes:
        return self.archiv_bytes


def integrations_archiv(domain: str = "beispielint") -> bytes:
    """Ein Archiv in der ueblichen HACS-Form, mit ``manifest.json``."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as zip_datei:
        zip_datei.writestr(
            f"projekt-v1.2.0/custom_components/{domain}/manifest.json",
            json.dumps({"domain": domain, "name": "Beispiel", "version": "1.2.0"}),
        )
    return puffer.getvalue()


@pytest.mark.asyncio
async def test_zielname_der_integration_wird_im_vorfuehrer_gelesen(monkeypatch, tmp_path):
    """Die ``manifest.json`` zu oeffnen ist Dateiarbeit -- ab in den Vorfuehrer.

    Gemessen wird der Faden, in dem ``_domain_aus_manifest`` laeuft:
    der Ereigniskreis ist der Faden des Tests, der Vorfuehrer ist ein
    anderer. Vor der Heilung lief die Zip-Arbeit im Kreis.
    """
    faeden: list[threading.Thread] = []
    echt = installation._domain_aus_manifest

    def messend(archiv: bytes) -> str:
        faeden.append(threading.current_thread())
        return echt(archiv)

    monkeypatch.setattr(installation, "_domain_aus_manifest", messend)

    hass = HassAttrappe(tmp_path)
    forge = ForgeAttrappe(integrations_archiv())
    eintrag = SimpleNamespace(
        kategorie="integration",
        identitaet=SimpleNamespace(full_name="foo/beispielint"),
    )

    ergebnis = await installiere_version(hass, forge, eintrag, "v1.2.0")

    schleifen_faden = threading.current_thread()
    assert faeden, "der Zielname muss berechnet werden"
    assert faeden[0] is not schleifen_faden, "der Zielname gehoert in den Vorfuehrer"
    assert ergebnis.pfad == PurePosixPath("custom_components/beispielint")
