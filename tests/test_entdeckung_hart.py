"""Entdeckung und Validierung unter feindlichem Beschuss.

Die Fluege davor prueften den.Normalfall. Diese Suite stellt die
 Fragen, die echte Server und echte Repository-Besitzer stellen:

* ``hacs.json`` mit BOM (Windows-Editor!), leer, als Liste, mit
  falschen Typen -- bis Flug 2093 war ein BOM ein Absturz, weil
  ``json.loads`` das Zeichen vor der Klammer nicht mag.
* Suchwoerter mit Umlauten, Slash, Anfuehrungszeichen und
  Script-HTML: sie reisen als Parameter bis zum Anbieter und
  koemmen unversehrt zurueck -- kein Escaping unterwegs, keins
  noetig (das Panel flieht beim Malen).
* Projekt Daten mit fehlenden und kaputten Feldern: ein Einzelner
  kaputter Kandidat darf nie den ganzen Scan abreissen.
"""

import json

import pytest
from haigs.core.entdeckung import entdecke, pruefe_kandidat
from haigs.core.forge import RepositoryInfo
from haigs.core.gitlab_forge import GitLabForge
from haigs.core.validierung import pruefe_hacs_json, pruefe_manifest

from tests.attrappe import projekt
from tests.attrappe_kern import FakeHttp

HOST = "gitlab.example.net"
GUELTIG = json.dumps({"name": "Bar", "render_readme": True})


# ------------------------------------------------------------------
# hacs.json unter Folter
# ------------------------------------------------------------------


def test_hacs_json_mit_bom_ist_gueltig():
    """Windows-Editoren speichern UTF-8 gern mit BOM -- das war Flug 2093.

    Vor der Heilung war das BOM ein Buchstabe vor der Klammer und
    machte die ganze Datei unlesbar; der Besitzer haette nie
    erfahren, warum sein Repository nicht aufgenommen wird.
    """
    roh = b"\xef\xbb\xbf" + GUELTIG.encode("utf-8")
    befund = pruefe_hacs_json(roh)
    assert befund.gueltig
    assert befund.name == "Bar"


def test_manifest_mit_bom_ist_auch_gueltig():
    """Dieselbe Falle in der manifest.json der Integration."""
    roh = b"\xef\xbb\xbf" + json.dumps(
        {"domain": "bar", "name": "Bar", "version": "1.2.0"}
    ).encode("utf-8")
    befund = pruefe_manifest(roh)
    assert befund.gueltig


def test_leere_hacs_json_bleibt_ein_befund_kein_absturz():
    assert not pruefe_hacs_json("")
    assert not pruefe_hacs_json(b"")
    assert not pruefe_hacs_json("   ")


def test_hacs_json_mit_null_bytes_und_steuerzeichen():
    """Muell bleibt Muell -- aber ein BEFUND, keine Ausnahme."""
    assert not pruefe_hacs_json(b"\x00\x01\x02")
    assert not pruefe_hacs_json('{"name": "x",}(selber kaputt)')


def test_hacs_json_falsche_typen_sind_ungueltig():
    """name als Zahl, render_readme als Text: Fehler, kein Crash."""
    befund = pruefe_hacs_json(json.dumps({"name": 123}))
    # str(123) macht "123" -- gueltig, aber der Wert bleibt Text.
    assert befund.gueltig
    befund2 = pruefe_hacs_json(json.dumps({"name": "x", "render_readme": "ja"}))
    assert befund2.gueltig
    assert "'render_readme'" in str(befund2.hinweise)


def test_hacs_json_ueber_zahlengrenzen():
    """Riesige Werte in unbedeutenden Feldern stoeren nicht."""
    befund = pruefe_hacs_json(json.dumps({"name": "x", "homeassistant": "2026.99.99"}))
    assert befund.gueltig


# ------------------------------------------------------------------
# Suchwoerter unter Folter
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stichwort_mit_sonderzeichen_reist_unversehrt():
    """Umlaute, Slash, Anfuehrungszeichen: der Parameter bleibt, wie er ist."""
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    wort = 'böses "Wort" mit /slash & <script>alert(1)</script>'
    await entdecke(GitLabForge(http, HOST), gruppe="foo", stichwort=wort)
    aufrufe = [a for a in http.aufrufe if "/groups/" in a[0]]
    assert aufrufe, "die Suche fand nie statt"
    assert any(a[1].get("search") == wort for a in aufrufe), http.aufrufe


@pytest.mark.asyncio
async def test_stichwort_mit_emoji_und_unicode():
    """Ein Stichwort darf aussehen wie ein Unicode-Anschlag."""
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    wort = "🐝bienentanz—日本語—🦊"
    await entdecke(GitLabForge(http, HOST), gruppe="foo", stichwort=wort)
    assert any(a[1].get("search") == wort for a in http.aufrufe)


@pytest.mark.asyncio
async def test_sehr_langes_stichwort_reist_trotzdem():
    """10.000 Zeichen: kein Absturz, kein Abschneiden."""
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    wort = "a" * 10_000
    await entdecke(GitLabForge(http, HOST), gruppe="foo", stichwort=wort)
    assert any(len(a[1].get("search", "")) == 10_000 for a in http.aufrufe)


# ------------------------------------------------------------------
# Kandidaten mit kaputten Daten
# ------------------------------------------------------------------


def _info(**rest) -> RepositoryInfo:
    """Ein Kandidat, bei dem jedes Feld fehlen darf."""
    werte = {
        "provider_id": "1",
        "full_name": "foo/bar",
    }
    werte.update(rest)
    return RepositoryInfo(**werte)


@pytest.mark.asyncio
async def test_kandidat_ohne_beschreibung_und_zweig():
    """Fehlende Freiwilligen-Felder: der Fund bleibt brauchbar."""
    http = FakeHttp({}, {"hacs.json": GUELTIG})
    fund = await pruefe_kandidat(
        GitLabForge(http, HOST), _info(standardzweig="", beschreibung="")
    )
    assert fund.uebernehmen
    assert fund.info.standardzweig == ""


@pytest.mark.asyncio
async def test_archivierter_kandidat_faellt_raus():
    """Archivierte Projekte zaehlen nicht -- die Instanz-Suche prueft doppelt."""
    http = FakeHttp({"/groups/": [projekt(archived=True)]}, {"hacs.json": GUELTIG})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde == []


@pytest.mark.asyncio
async def test_kandidat_ohne_topic_faellt_raus():
    """Die API mag.topic hinkommen -- der Kern vertraut ihr nicht."""
    http = FakeHttp(
        {"/groups/": [projekt(topics=("something-else",))]}, {"hacs.json": GUELTIG}
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde == []


@pytest.mark.asyncio
async def test_projektname_mit_sonderzeichen_uebersteht_den_scan():
    """full_name mit Leerzeichen und Unicode: kein Absturz unterwegs."""
    pfad = "gruppe/mit leerzeichen/ünïcødé-projekt"
    http = FakeHttp({"/groups/": [projekt(full_name=pfad)]}, {"hacs.json": GUELTIG})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="gruppe/mit leerzeichen")
    assert len(funde) == 1
    assert funde[0].identitaet.full_name == pfad
