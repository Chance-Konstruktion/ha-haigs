"""Entdeckung und Validierung: Topic ist Absicht, nicht Aufnahme."""

import json

import pytest
from haigs.core.entdeckung import entdecke
from haigs.core.gitlab_forge import GitLabForge
from haigs.core.validierung import pruefe_hacs_json, pruefe_manifest

from tests.attrappe import projekt
from tests.attrappe_kern import FakeHttp

HOST = "gitlab.example.net"
GUELTIG = json.dumps({"name": "Bar", "render_readme": True})


@pytest.mark.asyncio
async def test_gefunden_geprueft_uebernommen():
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert len(funde) == 1
    assert funde[0].uebernehmen
    assert funde[0].anzeigename == "foo/bar*lab"


@pytest.mark.asyncio
async def test_topic_allein_reicht_nicht():
    # Projekt traegt das Topic, hat aber keine hacs.json.
    http = FakeHttp({"/groups/": [projekt()]}, {})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert not funde[0].uebernehmen
    assert "hacs.json fehlt" in funde[0].befund.fehler


@pytest.mark.asyncio
async def test_entwicklungsrepos_bleiben_ohne_wunsch_draussen():
    http = FakeHttp(
        {"/groups/": [projekt(topics=("hacs", "hacs-development"))]},
        {"hacs.json": GUELTIG},
    )
    forge = GitLabForge(http, HOST)
    assert await entdecke(forge, gruppe="foo") == []
    assert len(await entdecke(forge, gruppe="foo", mit_vorab=True)) == 1


@pytest.mark.asyncio
async def test_kategorie_kommt_aus_dem_zusatz_topic():
    http = FakeHttp(
        {"/groups/": [projekt(topics=("hacs", "hacs-plugin"))]},
        {"hacs.json": json.dumps({"name": "Bar", "filename": "bar.js"})},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde[0].befund.kategorie == "plugin"


def test_kaputte_hacs_json_faellt_durch():
    assert not pruefe_hacs_json("{kein json")
    assert not pruefe_hacs_json(json.dumps({"render_readme": True}))
    assert not pruefe_hacs_json(json.dumps(["liste"]))
    assert not pruefe_hacs_json(GUELTIG, kategorie="erfunden")


def test_gueltige_hacs_json_kommt_durch():
    befund = pruefe_hacs_json(GUELTIG)
    assert befund
    assert befund.name == "Bar"
    assert befund.fehler == []


def test_plugin_ohne_dateiname_ist_gueltig_aber_auffaellig():
    befund = pruefe_hacs_json(json.dumps({"name": "Bar"}), kategorie="plugin")
    assert befund.gueltig
    assert befund.hinweise


def test_manifest_braucht_domain_name_version():
    assert not pruefe_manifest(json.dumps({"domain": "bar"}))
    voll = json.dumps({"domain": "bar", "name": "Bar", "version": "1.2.0"})
    befund = pruefe_manifest(voll)
    assert befund.gueltig
    assert befund.hinweise  # documentation fehlt


# ------------------------------------------------------------- Stufe M6


def _release(tag: str) -> dict:
    return {"tag_name": tag, "name": tag, "released_at": "2026-01-01T00:00:00Z"}


@pytest.mark.asyncio
async def test_fund_traegt_die_letzte_stabile_version():
    """Die Ergebnisliste (M6) will die letzte Version sehen -- stabil,
    Vorabversionen zaehlen nicht."""
    http = FakeHttp(
        {
            "/groups/": [projekt()],
            "releases": [
                _release("v1.0.0"),
                _release("v1.3.0-rc1"),
                _release("v1.2.0"),
            ],
        },
        {"hacs.json": GUELTIG},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert len(funde) == 1
    assert funde[0].letzte_version == "1.2.0"
    assert funde[0].uebernehmen


@pytest.mark.asyncio
async def test_ohne_releases_bleibt_die_version_leer():
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde[0].uebernehmen
    assert funde[0].letzte_version == ""


@pytest.mark.asyncio
async def test_releases_stoerung_bricht_den_scan_nicht():
    """Ein einzelner Ausfall darf nicht den ganzen Scan kosten."""
    http = FakeHttp(
        {"/groups/": [projekt()], "releases": {"message": "500 Internal Server Error"}},
        {"hacs.json": GUELTIG},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde[0].uebernehmen
    assert funde[0].letzte_version == ""


@pytest.mark.asyncio
async def test_version_nur_fuer_brauchbare_kandidaten():
    """Kandidaten ohne hacs.json kriegen keinen Release-Abruf -- der
    Scan bleibt so guenstig wie moeglich."""
    http = FakeHttp({"/groups/": [projekt()]}, {})
    await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert not any("releases" in url for url, _ in http.aufrufe)


@pytest.mark.asyncio
async def test_mit_version_fals_spart_die_abrufe():
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    await entdecke(GitLabForge(http, HOST), gruppe="foo", mit_version=False)
    assert not any("releases" in url for url, _ in http.aufrufe)


@pytest.mark.asyncio
async def test_instanzweite_suche_ohne_gruppe():
    """M6: die Quelle kann die ganze Instanz sein."""
    http = FakeHttp(
        {
            "/groups/": [projekt()],
            "releases": [_release("v2.1.0")],
            "/api/v4/projects": [projekt()],
        },
        {"hacs.json": GUELTIG},
    )
    funde = await entdecke(GitLabForge(http, HOST))
    assert len(funde) == 1
    assert funde[0].letzte_version == "2.1.0"
    assert any(url.endswith("/api/v4/projects") for url, _ in http.aufrufe)


@pytest.mark.asyncio
async def test_untergruppen_weitergabe():
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    forge = GitLabForge(http, HOST)
    await entdecke(forge, gruppe="foo")
    params = next(p for url, p in http.aufrufe if "/groups/" in url)
    assert params.get("include_subgroups") == "true"

    http.aufrufe.clear()
    await entdecke(forge, gruppe="foo", mit_untergruppen=False)
    params = next(p for url, p in http.aufrufe if "/groups/" in url)
    assert "include_subgroups" not in params


@pytest.mark.asyncio
async def test_stichwort_weitergabe():
    """Flug 2091: das Wort der Kopfsuche reist bis zum Anbieter --
    die Naht gibt es unverstuemmelt weiter."""
    http = FakeHttp({"/groups/": [projekt()]}, {"hacs.json": GUELTIG})
    forge = GitLabForge(http, HOST)
    await entdecke(forge, gruppe="foo", stichwort="bar")
    params = next(p for url, p in http.aufrufe if "/groups/" in url)
    assert params.get("search") == "bar"

    http.aufrufe.clear()
    await entdecke(forge, gruppe="foo")
    params = next(p for url, p in http.aufrufe if "/groups/" in url)
    assert "search" not in params


@pytest.mark.asyncio
async def test_abnahme_gemischte_gruppe_liefert_genau_die_richtigen():
    """Das Abnahmekriterium aus #6: mit Topic, ohne Topic, mit Topic
    aber ohne hacs.json -- nur der erste ist ein Treffer."""
    gemischt = [
        projekt(pid=1, full_name="gruppe/gut"),
        projekt(pid=2, full_name="gruppe/ohne-topic", topics=()),
        projekt(pid=3, full_name="gruppe/ohne-hacs-json"),
        projekt(pid=4, full_name="gruppe/archiviert", archived=True),
        projekt(
            pid=5,
            full_name="gruppe/entwicklung",
            topics=("hacs", "hacs-development"),
        ),
    ]
    http = FakeHttp(
        {"/groups/": gemischt, "releases": [_release("v3.0.0")]},
        {
            # die Datei-Adresse kodiert den Pfad -- die Schluessel
            # folgen ihr (gruppe%2Fgut statt gruppe/gut)
            "gruppe%2Fgut": GUELTIG,
            "gruppe%2Fohne-topic": GUELTIG,
            "gruppe%2Farchiviert": GUELTIG,
            "gruppe%2Fentwicklung": GUELTIG,
        },
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="gruppe")
    # Funde: alles mit Topic, unarchiviert, nicht Entwicklung -- auch
    # der Kandidat ohne hacs.json (Fehler benennen statt verschlucken)
    assert [fund.info.full_name for fund in funde] == [
        "gruppe/gut",
        "gruppe/ohne-hacs-json",
    ]
    # Treffer (Abnahme aus #6): genau der gueltige Kandidat
    treffer = [fund for fund in funde if fund.uebernehmen]
    assert [fund.info.full_name for fund in treffer] == ["gruppe/gut"]
    assert treffer[0].letzte_version == "3.0.0"
    assert treffer[0].anzeigename == "gruppe/gut*lab"

    # auf Wunsch kommen die Entwicklungs-Kandidaten dazu
    funde = await entdecke(GitLabForge(http, HOST), gruppe="gruppe", mit_vorab=True)
    assert [fund.info.full_name for fund in funde] == [
        "gruppe/gut",
        "gruppe/ohne-hacs-json",
        "gruppe/entwicklung",
    ]


@pytest.mark.asyncio
async def test_kaputte_hacs_json_ist_kandidat_aber_kein_treffer():
    http = FakeHttp(
        {"/groups/": [projekt(full_name="gruppe/kaputt")]},
        {"gruppe%2Fkaputt": "{kein json"},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="gruppe")
    assert len(funde) == 1
    assert not funde[0].uebernehmen
    assert funde[0].letzte_version == ""
