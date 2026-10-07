"""GitLab-Client -- geprueft gegen eine Attrappe, ohne Netz."""

import json

import pytest
from haigs.core.forge import NichtGefunden
from haigs.core.gitlab_forge import GitLabForge

from tests.attrappe import projekt
from tests.attrappe_kern import FakeHttp

HOST = "gitlab.example.net"


def forge(**rest):
    return GitLabForge(FakeHttp(**rest), HOST)


@pytest.mark.asyncio
async def test_pfad_wird_kodiert_und_das_suffix_vorher_entfernt():
    http = FakeHttp({"/projects/": projekt()})
    f = GitLabForge(http, "https://" + HOST + "/")
    await f.repository("foo/bar*lab")
    url = http.aufrufe[0][0]
    assert "foo%2Fbar" in url
    assert "*lab" not in url
    assert f.host == HOST


@pytest.mark.asyncio
async def test_stammdaten_kommen_vollstaendig_an():
    info = await forge(json_antworten={"/projects/": projekt()}).repository("foo/bar")
    assert info.provider_id == "789012"
    assert info.full_name == "foo/bar"
    assert info.sterne == 7
    assert info.offene_tickets == 2
    assert info.topics == ("hacs",)


@pytest.mark.asyncio
async def test_identitaet_traegt_host_und_id():
    ident = await forge(json_antworten={"/projects/": projekt()}).identitaet("foo/bar")
    assert ident.uid == "gitlab:789012"
    assert ident.display_full_name == "foo/bar*lab"
    assert ident.host == HOST


@pytest.mark.asyncio
async def test_fehlendes_projekt_wird_als_solches_gemeldet():
    with pytest.raises(NichtGefunden):
        await forge().repository("gibt/es/nicht")


@pytest.mark.asyncio
async def test_releases_werden_uebersetzt():
    antwort = [
        {
            "tag_name": "v1.2.0",
            "name": "Version 1.2.0",
            "released_at": "2026-09-01T10:00:00Z",
            "assets": {"links": [{"name": "paket.zip", "url": "https://x/paket.zip"}]},
        },
        {"name": "ohne Tag"},
    ]
    releases = await forge(json_antworten={"/releases": antwort}).releases("foo/bar")
    assert len(releases) == 1
    assert releases[0].tag == "v1.2.0"
    assert releases[0].anhaenge["paket.zip"] == "https://x/paket.zip"


@pytest.mark.asyncio
async def test_datei_wird_am_richtigen_ref_geholt():
    http = FakeHttp(dateien={"hacs.json": {"name": "Bar"}})
    f = GitLabForge(http, HOST)
    roh = await f.datei("foo/bar", "hacs.json", "v1.2.0")
    assert json.loads(roh)["name"] == "Bar"
    assert "ref=v1.2.0" in http.aufrufe[0][0]
    assert "hacs.json" in http.aufrufe[0][0]


@pytest.mark.asyncio
async def test_archiv_url_zeigt_auf_den_tag():
    url = await forge().archiv_url("foo/bar", "v1.2.0")
    assert url.endswith("/repository/archive.zip?sha=v1.2.0")


@pytest.mark.asyncio
async def test_gruppensuche_nimmt_untergruppen_mit():
    http = FakeHttp({"/groups/": [projekt(), projekt(pid=2, full_name="foo/baz")]})
    treffer = await GitLabForge(http, HOST).suche_nach_topic("hacs", gruppe="foo")
    assert [t.full_name for t in treffer] == ["foo/bar", "foo/baz"]
    params = http.aufrufe[0][1]
    assert params["topic"] == "hacs"
    assert params["include_subgroups"] == "true"
    assert params["archived"] == "false"


@pytest.mark.asyncio
async def test_instanzweite_suche_geht_ohne_gruppe():
    http = FakeHttp({"/api/v4/projects": [projekt()]})
    treffer = await GitLabForge(http, HOST).suche_nach_topic("hacs")
    assert len(treffer) == 1
    assert "include_subgroups" not in http.aufrufe[0][1]


@pytest.mark.asyncio
async def test_stichwort_reist_als_search_parameter():
    """Flug 2091: die Kopfsuche des Ladens -- das Wort sucht in Name
    und Beschreibung, das Topic bleibt daneben scharf."""
    http = FakeHttp({"/api/v4/projects": [projekt()]})
    treffer = await GitLabForge(http, HOST).suche_nach_topic(
        "hacs", stichwort="bienentanz"
    )
    assert len(treffer) == 1
    params = http.aufrufe[0][1]
    assert params["search"] == "bienentanz"
    assert params["topic"] == "hacs"


@pytest.mark.asyncio
async def test_stichwort_und_gruppe_reisen_zusammen():
    http = FakeHttp({"/groups/": [projekt()]})
    treffer = await GitLabForge(http, HOST).suche_nach_topic(
        "hacs", gruppe="foo", stichwort="bar"
    )
    assert len(treffer) == 1
    params = http.aufrufe[0][1]
    assert params["search"] == "bar"
    assert params["include_subgroups"] == "true"


@pytest.mark.asyncio
async def test_stammdaten_nennen_die_web_ansichten():
    """Tickets und Releases: die Links gehoeren dem Anbieter (Stufe M7).

    Ohne web_url bleibt beides leer -- niemand ratet Adressen.
    """
    info = await forge(json_antworten={"/projects/": projekt()}).repository("foo/bar")
    assert info.web_url == "https://gitlab.example.net/foo/bar"
    assert info.tickets_url == "https://gitlab.example.net/foo/bar/-/issues"
    assert info.releases_url == "https://gitlab.example.net/foo/bar/-/releases"

    bloss = projekt()
    del bloss["web_url"]
    info = await forge(json_antworten={"/projects/": bloss}).repository("foo/bar")
    assert info.web_url == ""
    assert info.tickets_url == ""
    assert info.releases_url == ""


@pytest.mark.asyncio
async def test_stammdaten_nennen_das_bildzeichen():
    """Flug 2084: das Zeichen des Projekts -- oder leer, nie geraten.

    Der Laden zeigt die Zeichen seiner Karten; fehlt das Bild (keins
    hochgeladen, Feld abwesend), bleibt das Feld leer und die Ober-
    flaeche faellt auf einen Buchstaben zurueck.
    """
    mit_bild = projekt()
    mit_bild["avatar_url"] = "https://gitlab.example.net/uploads/bar.png"
    info = await forge(json_antworten={"/projects/": mit_bild}).repository("foo/bar")
    assert info.avatar_url == "https://gitlab.example.net/uploads/bar.png"

    bloss = projekt()
    info = await forge(json_antworten={"/projects/": bloss}).repository("foo/bar")
    assert info.avatar_url == ""


# -- Stufe M8: Stammdaten ueber die ID --------------------------------
@pytest.mark.asyncio
async def test_stammdaten_nach_id_oeffnen_dasselbe_tor():
    """Die ID ist der stabile Weg: dasselbe Antwortformat wie ueber den Pfad."""
    info = await forge(json_antworten={"/projects/789012": projekt()}).repository_nach_id(
        "789012"
    )
    assert info.provider_id == "789012"
    assert info.full_name == "foo/bar"
    assert info.topics == ("hacs",)


@pytest.mark.asyncio
async def test_stammdaten_nach_id_nennen_den_neuen_namen():
    """Ein umbenanntes Projekt antwortet unter der alten ID mit dem neuen Pfad."""
    http = FakeHttp({"/projects/789012": projekt(full_name="neu/baz")})
    f = GitLabForge(http, HOST)
    info = await f.repository_nach_id("789012")
    assert info.full_name == "neu/baz"
    assert info.provider_id == "789012"
    assert "789012" in http.aufrufe[0][0]


@pytest.mark.asyncio
async def test_stammdaten_nach_id_geloescht_ist_nicht_gefunden():
    with pytest.raises(NichtGefunden):
        await forge().repository_nach_id("111")


@pytest.mark.asyncio
async def test_stammdaten_nach_id_keine_ziffern_kein_weg():
    """Die ID kommt aus der Ablage -- trotzdem wird sie geprueft, bevor sie reist."""
    from haigs.core.forge import ForgeFehler

    with pytest.raises(ForgeFehler):
        await forge(json_antworten={"/projects/": projekt()}).repository_nach_id("../7a")


# -- Die Probe im Einrichtungsdialog ---------------------------------


@pytest.mark.asyncio
async def test_grenze_setzt_per_page_und_verbietet_das_blaettern():
    """``grenze`` muss BEIDES tun. Ein kleineres ``per_page`` allein
    bremst nichts -- der HTTP-Zugang blaettert sonst weiter, bis die
    Liste zu Ende ist, und die Probe waere so teuer wie der Abruf."""
    http = FakeHttp({"/projects": [{"id": 1, "path_with_namespace": "a/b"}]})
    forge = GitLabForge(http, HOST)

    await forge.suche_nach_topic(grenze=1)

    _, params = http.aufrufe[-1]
    assert params["per_page"] == "1"
    assert http.seitenwuensche[-1] == 1


@pytest.mark.asyncio
async def test_ohne_grenze_bleibt_es_beim_vollen_abruf():
    http = FakeHttp({"/projects": [{"id": 1, "path_with_namespace": "a/b"}]})
    forge = GitLabForge(http, HOST)

    await forge.suche_nach_topic()

    _, params = http.aufrufe[-1]
    assert params["per_page"] == "100"
    assert http.seitenwuensche[-1] is None
