"""Der HACS-Katalog als Schmiede -- geprueft ohne Netz."""

import io
import json
import zipfile

import pytest
from haigs.core.entdeckung import entdecke
from haigs.core.forge import ForgeFehler, NichtGefunden
from haigs.core.hacs_katalog_forge import HacsKatalogForge
from haigs.core.identity import GITHUB
from haigs.core.schmiede import schmiede

from tests.attrappe_kern import FakeHttp

INTEGRATION = {
    "101": {
        "full_name": "foo/ha-bar",
        "description": "Eine Integration",
        "domain": "bar",
        "stargazers_count": 42,
        "downloads": 1234,
        "last_version": "1.2.3",
        "last_updated": "2026-09-01T10:00:00Z",
        "topics": ["sensor"],
        "open_issues": 3,
        "manifest_name": "Bar",
    }
}
PLUGIN = {
    "202": {
        "full_name": "baz/lovelace-karte",
        "description": "Eine Karte",
        "stargazers_count": 9,
        "last_version": "v0.4",
    }
}


def forge(**rest):
    antworten = {
        "/integration/data.json": INTEGRATION,
        "/plugin/data.json": PLUGIN,
        "/theme/data.json": {},
    }
    return HacsKatalogForge(FakeHttp(json_antworten=antworten, **rest))


def test_die_schmiede_liefert_den_katalog_fuer_github():
    katalog = schmiede(FakeHttp(), "github.com", GITHUB)
    assert isinstance(katalog, HacsKatalogForge)
    assert katalog.provider == GITHUB
    assert katalog.host == "github.com"


async def test_stammdaten_kommen_aus_dem_katalog():
    f = forge()
    info = await f.repository("foo/ha-bar")
    assert info.provider_id == "101"
    assert info.sterne == 42
    assert info.downloads == 1234
    assert info.offene_tickets == 3
    assert "hacs-integration" in info.topics
    assert info.avatar_url.endswith("/bar/icon.png")
    assert info.web_url == "https://github.com/foo/ha-bar"
    # Plugins tragen das Bild des Besitzers statt eines Marken-Icons.
    karte = await f.repository_nach_id("202")
    assert karte.avatar_url.startswith("https://github.com/baz.png")
    with pytest.raises(NichtGefunden):
        await f.repository("gibt/es-nicht")
    with pytest.raises(NichtGefunden):
        await f.repository_nach_id("999")


async def test_der_katalog_wird_nur_einmal_geholt():
    f = forge()
    await f.repository("foo/ha-bar")
    await f.repository_nach_id("202")
    await f.suche_nach_topic()
    assert len(f.http.aufrufe) == 3  # je Kategorie ein Abruf


async def test_entdecke_schliesst_kurz_ohne_einzelabfragen():
    f = forge()
    funde = await entdecke(f)
    assert {x.info.full_name for x in funde} == {"foo/ha-bar", "baz/lovelace-karte"}
    kategorien = {x.info.full_name: x.befund.kategorie for x in funde}
    assert kategorien == {"foo/ha-bar": "integration", "baz/lovelace-karte": "plugin"}
    assert all(x.uebernehmen for x in funde)
    assert {x.letzte_version for x in funde} == {"1.2.3", "v0.4"}
    # Nur die drei Katalogdateien, keine hacs.json je Repository.
    assert all("data-v2.hacs.xyz" in url for url, _ in f.http.aufrufe)
    nur_karten = await entdecke(f, stichwort="Karte")
    assert [x.info.full_name for x in nur_karten] == ["baz/lovelace-karte"]


async def test_ausgefallene_kategorie_laesst_die_anderen_stehen():
    f = HacsKatalogForge(FakeHttp(json_antworten={"/integration/data.json": INTEGRATION}))
    # Plugin und Theme antworten mit dem Fehlerkoerper des Fakes (kein dict
    # mit full_name) -- sie liefern nichts, aber die Integration steht.
    assert len(await f.suche_nach_topic()) == 1


async def test_ohne_jede_antwort_ist_es_ein_fehler():
    class Tot(FakeHttp):
        async def get_json(self, url, params=None, *, seiten=None):
            raise ForgeFehler("kein Netz")

    with pytest.raises(ForgeFehler):
        await HacsKatalogForge(Tot()).katalog()


async def test_release_mit_zip_wenn_hacs_json_es_verlangt():
    hacs = {"zip_release": True, "filename": "bar.zip"}
    f = forge(dateien={"raw.githubusercontent.com/foo/ha-bar/1.2.3/hacs.json": hacs})
    releases = await f.releases("foo/ha-bar")
    assert [r.tag for r in releases] == ["1.2.3"]
    assert releases[0].anhaenge == {
        "bar.zip": "https://github.com/foo/ha-bar/releases/download/1.2.3/bar.zip"
    }


async def test_release_ohne_hacs_json_hat_nur_das_quellarchiv():
    releases = await forge().releases("baz/lovelace-karte")
    assert releases[0].tag == "v0.4"
    assert releases[0].anhaenge == {}


async def test_archiv_und_dateien_laufen_ueber_github_hosts():
    f = forge(dateien={"raw.githubusercontent.com": "# Hallo"})
    assert await f.archiv_url("foo/ha-bar", "1.2.3") == (
        "https://codeload.github.com/foo/ha-bar/zip/1.2.3"
    )
    assert await f.datei("foo/ha-bar", "README.md", "HEAD") == b"# Hallo"
    assert f.http.aufrufe[-1][0] == (
        "https://raw.githubusercontent.com/foo/ha-bar/HEAD/README.md"
    )
    assert await f.tags("foo/ha-bar") == []


async def test_archiv_wird_geladen():
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        z.writestr("x/hacs.json", json.dumps({}))
    f = forge(dateien={"codeload.github.com": puffer.getvalue()})
    assert (await f.archiv("foo/ha-bar", "1.2.3")) == puffer.getvalue()


async def test_entwicklermodus_gibt_es_nicht():
    with pytest.raises(ForgeFehler):
        await forge().zweig_stand("foo/ha-bar", "main")
