"""Forgejo-Client -- geprueft gegen eine Attrappe, ohne Netz.

Der zweite Teil prueft gegen **echte** Aufzeichnungen von codeberg.org
(die Referenzinstanz fuer Forgejo): die Abnahme von Stufe M9 -- ein
Codeberg-Repository laeuft durch denselben Ablauf wie ein GitLab-
Repository, ohne dass der Ablauf den Anbieter kennt.
"""

import pytest
from haigs.core.entdeckung import entdecke
from haigs.core.forge import NichtGefunden
from haigs.core.forgejo_forge import ForgejoForge

from tests.attrappe_kern import FakeHttp
from tests.forgejo_antworten import (
    HACS_JSON_DYNDNS,
    HACS_JSON_HAVACATION,
    HACS_JSON_THAMES,
    RELEASES_MIT_ANHAENGEN,
    REPO_THAMES,
    SUCHE,
    TAGS_THAMES,
)

HOST = "codeberg.example"


def forge(**rest):
    return ForgejoForge(FakeHttp(**rest), HOST)


def forgejo_repo(
    full_name="foo/bar",
    id=42,
    description="eine Beschreibung",
    default_branch="main",
    topics=("hacs",),
    stars=7,
    issues=2,
    archived=False,
    avatar_url="",
):
    """Ein Forgejo-Projektdatensatz, wie API v1 ihn liefert."""
    return {
        "id": id,
        "full_name": full_name,
        "description": description,
        "default_branch": default_branch,
        "topics": list(topics),
        "stars_count": stars,
        "open_issues_count": issues,
        "archived": archived,
        "html_url": "https://" + HOST + "/" + full_name,
        "avatar_url": avatar_url,
    }


# ------------------------------------------------------------------
# Stammdaten und Identitaet
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pfad_wird_kodiert_und_das_suffix_vorher_entfernt():
    http = FakeHttp(json_antworten={"/repos/": forgejo_repo()})
    f = ForgejoForge(http, "https://" + HOST + "/")
    await f.repository("foo/bar*forge")
    url = http.aufrufe[0][0]
    assert "repos/foo/bar" in url
    assert "*forge" not in url
    assert f.host == HOST
    assert f.api == "https://" + HOST + "/api/v1"


@pytest.mark.asyncio
async def test_stammdaten_kommen_vollstaendig_an():
    http = FakeHttp(json_antworten={"/repos/foo/bar": forgejo_repo(stars=11, issues=3)})
    info = await ForgejoForge(http, HOST).repository("foo/bar")
    assert info.provider_id == "42"
    assert info.full_name == "foo/bar"
    assert info.beschreibung == "eine Beschreibung"
    assert info.sterne == 11
    assert info.offene_tickets == 3
    assert info.topics == ("hacs",)
    assert info.archiviert is False
    assert info.web_url == "https://" + HOST + "/foo/bar"


@pytest.mark.asyncio
async def test_stammdaten_nennen_das_bildzeichen():
    """Flug 2084: das Zeichen des Projekts -- oder leer, nie geraten."""
    http = FakeHttp(
        json_antworten={
            "/repos/foo/bar": forgejo_repo(avatar_url="https://" + HOST + "/avatars/42")
        }
    )
    info = await ForgejoForge(http, HOST).repository("foo/bar")
    assert info.avatar_url == "https://" + HOST + "/avatars/42"

    http = FakeHttp(json_antworten={"/repos/": forgejo_repo()})
    info = await ForgejoForge(http, HOST).repository("foo/bar")
    assert info.avatar_url == ""


@pytest.mark.asyncio
async def test_identitaet_traegt_host_und_id():
    ident = await forge(json_antworten={"/repos/": forgejo_repo(id=1678556)}).identitaet(
        "foo/bar"
    )
    assert ident.provider == "forgejo"
    assert ident.uid == "forgejo:1678556"
    assert ident.display_full_name == "foo/bar*forge"
    assert ident.host == HOST
    assert ident.storage_key == "forgejo@" + HOST + ":1678556"


@pytest.mark.asyncio
async def test_fehlendes_projekt_wird_als_solches_gemeldet():
    with pytest.raises(NichtGefunden):
        await forge().repository("gibt/es/nicht")


# ------------------------------------------------------------------
# Versionen: Releases und Tags
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_releases_werden_uebersetzt():
    antwort = [
        {
            "tag_name": "v1.2.0",
            "name": "Version 1.2.0",
            "published_at": "2026-09-01T10:00:00+02:00",
            "prerelease": False,
            "draft": False,
            "assets": [
                {
                    "name": "paket.zip",
                    "browser_download_url": "https://x/paket.zip",
                }
            ],
        },
        {
            "tag_name": "v1.3.0-rc1",
            "name": "",
            "published_at": "2026-09-02T08:00:00+02:00",
            "prerelease": True,
            "draft": False,
            "assets": [],
        },
    ]
    releases = await forge(json_antworten={"/releases": antwort}).releases("foo/bar")
    assert [r.tag for r in releases] == ["v1.2.0", "v1.3.0-rc1"]
    assert releases[0].anhaenge == {"paket.zip": "https://x/paket.zip"}
    assert releases[0].veroeffentlicht_am == "2026-09-01T10:00:00+02:00"
    assert releases[0].vorabversion is False
    assert releases[1].vorabversion is True
    assert releases[1].name == "v1.3.0-rc1"  # leerer Name faellt auf den Tag


@pytest.mark.asyncio
async def test_entwuerfe_zaehlen_nicht_als_release():
    antwort = [
        {"tag_name": "v2.0.0", "draft": True, "prerelease": False, "assets": []},
        {"tag_name": "v1.0.0", "draft": False, "prerelease": False, "assets": []},
    ]
    releases = await forge(json_antworten={"/releases": antwort}).releases("foo/bar")
    assert [r.tag for r in releases] == ["v1.0.0"]


@pytest.mark.asyncio
async def test_tags_als_rueckfallebene():
    antwort = [{"name": "v1.1.2"}, {"name": "v1.1.1"}]
    tags = await forge(json_antworten={"/tags": antwort}).tags("foo/bar")
    assert tags == ["v1.1.2", "v1.1.1"]


@pytest.mark.asyncio
async def test_projekt_ohne_releases_meldet_sich_nicht_als_fehlerliste():
    # Forgejo antwortet auf /releases ohne Releases mit 404 -- im Kern
    # heisst das NichtGefunden, nicht "leere Liste". Die Rueckfallebene
    # sind die Tags.
    with pytest.raises(NichtGefunden):
        await forge().releases("foo/bar")


# ------------------------------------------------------------------
# Inhalte
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_datei_laeuft_ueber_den_raw_endpunkt():
    http = FakeHttp(dateien={"raw/hacs.json": b'{"name": "x"}'})
    await ForgejoForge(http, HOST).datei("foo/bar", "hacs.json", "main")
    url = http.aufrufe[0][0]
    assert url.endswith("/repos/foo/bar/raw/hacs.json?ref=main")


@pytest.mark.asyncio
async def test_archiv_url_zeigt_auf_archive_endpunkt():
    url = await forge().archiv_url("foo/bar", "v1.1.2")
    assert url == "https://" + HOST + "/api/v1/repos/foo/bar/archive/v1.1.2.zip"


# ------------------------------------------------------------------
# Entdeckung
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instanzsuche_filtert_exakt_auf_das_topic():
    antwort = {
        "ok": True,
        "data": [
            forgejo_repo(full_name="a/mit", topics=("hacs",)),
            forgejo_repo(full_name="b/ohne", topics=()),
            forgejo_repo(full_name="c/falsch", topics=("hacs-development",)),
        ],
    }
    treffer = await forge(json_antworten={"/repos/search": antwort}).suche_nach_topic(
        "hacs"
    )
    assert [t.full_name for t in treffer] == ["a/mit"]


@pytest.mark.asyncio
async def test_gruppensuche_laeuft_ueber_die_organisation():
    antwort = [
        forgejo_repo(full_name="gruppe/mit", topics=("hacs",)),
        forgejo_repo(full_name="gruppe/ohne", topics=()),
    ]
    http = FakeHttp(json_antworten={"/orgs/gruppe/repos": antwort})
    treffer = await ForgejoForge(http, HOST).suche_nach_topic("hacs", gruppe="gruppe")
    assert [t.full_name for t in treffer] == ["gruppe/mit"]
    assert "/orgs/gruppe/repos" in http.aufrufe[0][0]


@pytest.mark.asyncio
async def test_gruppensuche_faellt_auf_die_benutzerliste_zurueck():
    antwort = [forgejo_repo(full_name="user/mit", topics=("hacs",))]
    http = FakeHttp(json_antworten={"/users/user/repos": antwort})
    treffer = await ForgejoForge(http, HOST).suche_nach_topic("hacs", gruppe="user")
    assert [t.full_name for t in treffer] == ["user/mit"]
    urls = [aufruf[0] for aufruf in http.aufrufe]
    assert any("/orgs/user/repos" in u for u in urls)  # zuerst versucht
    assert any("/users/user/repos" in u for u in urls)  # dann genommen


@pytest.mark.asyncio
async def test_untergruppen_sind_ein_akzeptiertes_no_op():
    # Forgejo-Organisationen liegen flach: der Parameter wird angenommen,
    # macht aber keinen Unterschied. Das ist dokumentiertes Verhalten,
    # kein Fehler.
    antwort = [forgejo_repo(full_name="g/mit", topics=("hacs",))]
    http = FakeHttp(json_antworten={"/orgs/g/repos": antwort})
    treffer = await ForgejoForge(http, HOST).suche_nach_topic(
        "hacs", gruppe="g", mit_untergruppen=True
    )
    assert [t.full_name for t in treffer] == ["g/mit"]
    assert len(http.aufrufe) == 1


@pytest.mark.asyncio
async def test_stichwort_ersetzt_das_suchwort_topic_bleibt_scharf():
    """Flug 2091: die Kopfsuche -- das Wort tritt als ``q`` an die
    Stelle des Themennamens; die exakte Themen-Filterung laeuft danach
    trotzdem, genau wie ohne Stichwort."""
    antwort = {
        "ok": True,
        "data": [
            forgejo_repo(full_name="a/zigbee", topics=("hacs",)),
            forgejo_repo(full_name="b/zigbee-ohne", topics=()),
        ],
    }
    http = FakeHttp(json_antworten={"/repos/search": antwort})
    treffer = await ForgejoForge(http, HOST).suche_nach_topic("hacs", stichwort="zigbee")
    assert [t.full_name for t in treffer] == ["a/zigbee"]
    assert http.aufrufe[0][1]["q"] == "zigbee"


@pytest.mark.asyncio
async def test_gruppensuche_filtert_das_stichwort_von_hand():
    # Die Organisations-Listung kennt kein Suchwort: Name und
    # Beschreibung werden hier gefiltert -- gross/klein ist gleich.
    antwort = [
        forgejo_repo(full_name="gruppe/zigbee", description="Sensor"),
        forgejo_repo(full_name="gruppe/anderes", description="ganz was anderes"),
        forgejo_repo(full_name="gruppe/sensor", description="zigbee stack"),
    ]
    http = FakeHttp(json_antworten={"/orgs/gruppe/repos": antwort})
    treffer = await ForgejoForge(http, HOST).suche_nach_topic(
        "hacs", gruppe="gruppe", stichwort="ZigBee"
    )
    assert sorted(t.full_name for t in treffer) == [
        "gruppe/sensor",
        "gruppe/zigbee",
    ]


# ------------------------------------------------------------------
# Die Abnahme von M9: echte Aufzeichnungen von codeberg.org
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_instanzsuche_findet_genau_die_projekte_mit_topic():
    # Zehn Stichwort-Treffer, drei davon tragen das Topic ``hacs`` --
    # genau diese drei, bytegenau aus der echten Antwort.
    treffer = await ForgejoForge(
        FakeHttp(json_antworten={"/repos/search": SUCHE}), "codeberg.org"
    ).suche_nach_topic("hacs")
    assert sorted(t.full_name for t in treffer) == [
        "Etuldan/hassio-dyndns",
        "jelmer/HA-Thames-Water",
        "touero/HaVacation",
    ]


@pytest.mark.asyncio
async def test_codeberg_repository_laeuft_durch_den_gleichen_ablauf():
    """Die Abnahme: Entdeckung, Pruefung, Version, Archiv -- ohne dass
    der Ablauf den Anbieter kennt. Alle Daten stammen bytegenau von
    codeberg.org."""
    http = FakeHttp(
        json_antworten={"/repos/search": SUCHE, "/tags": TAGS_THAMES},
        dateien={
            "jelmer/HA-Thames-Water/raw/hacs.json": HACS_JSON_THAMES,
            "touero/HaVacation/raw/hacs.json": HACS_JSON_HAVACATION,
            "Etuldan/hassio-dyndns/raw/hacs.json": HACS_JSON_DYNDNS,
        },
    )
    f = ForgejoForge(http, "codeberg.org")

    funde = await entdecke(f)
    nach_name = {fund.identitaet.full_name: fund for fund in funde}

    # Der gueltige HACS-Treffer: hacs.json geprueft, Kategorie aus Topics
    thames = nach_name["jelmer/HA-Thames-Water"]
    assert thames.befund.gueltig is True
    assert thames.befund.name == "Thames Water"
    assert thames.befund.kategorie == "integration"
    assert thames.identitaet.provider == "forgejo"
    assert thames.identitaet.uid == "forgejo:1678556"
    assert thames.identitaet.display_full_name == "jelmer/HA-Thames-Water*forge"

    # Alle drei Topic-Treffer sind gueltige HACS-Projekte: touero und
    # Etuldan aus demselben echten Suchergebnis. Etuldan liegt auf dem
    # Zweig ``master`` -- Forgejo-Projekte nennen ihn selbst, der Ablauf
    # fragt ihn ab, statt ``main`` festzunageln.
    assert nach_name["touero/HaVacation"].befund.gueltig is True
    assert nach_name["Etuldan/hassio-dyndns"].befund.gueltig is True
    assert nach_name["Etuldan/hassio-dyndns"].befund.name == "DynDNS"

    # Versionen: keine Releases auf diesem Projekt -- die Instanz
    # antwortet 404, im Kern NichtGefunden. Rueckfallebene Tags.
    with pytest.raises(NichtGefunden):
        await f.releases("jelmer/HA-Thames-Water")
    tags = await f.tags("jelmer/HA-Thames-Water")
    assert tags[0] == "v1.1.2"

    # Archiv-Adresse fuer die gewaehlte Version
    url = await f.archiv_url("jelmer/HA-Thames-Water", tags[0])
    assert url == (
        "https://codeberg.org/api/v1/repos/jelmer/HA-Thames-Water/archive/v1.1.2.zip"
    )


@pytest.mark.asyncio
async def test_echte_releases_mit_anhaengen_werden_uebersetzt():
    # forgejo/forgejo v16.0.3 mit 21 echten Anhaengen -- der Beweis,
    # dass die Uebersetzung der Forgejo-Release-Form ohne Sonderweg
    # dieselbe Release-Gestalt liefert wie GitLab.
    releases = await ForgejoForge(
        FakeHttp(json_antworten={"/releases": RELEASES_MIT_ANHAENGEN}),
        "codeberg.org",
    ).releases("forgejo/forgejo")
    assert len(releases) == 1
    r = releases[0]
    assert r.tag == "v16.0.3"
    assert r.name == "v16.0.3"
    assert r.vorabversion is False
    assert r.veroeffentlicht_am == "2026-08-20T10:49:50+02:00"
    assert len(r.anhaenge) == 21
    assert r.anhaenge["forgejo-16.0.3-linux-amd64"] == (
        "https://codeberg.org/forgejo/forgejo/releases/download/"
        "v16.0.3/forgejo-16.0.3-linux-amd64"
    )


@pytest.mark.asyncio
async def test_echte_stammdaten_kommen_vollstaendig_an():
    info = await ForgejoForge(
        FakeHttp(json_antworten={"/repos/jelmer/HA-Thames-Water": REPO_THAMES}),
        "codeberg.org",
    ).repository("jelmer/HA-Thames-Water*forge")
    assert info.provider_id == "1678556"
    assert info.full_name == "jelmer/HA-Thames-Water"
    assert info.standardzweig == "main"
    assert "hacs" in info.topics
    assert info.web_url == "https://codeberg.org/jelmer/HA-Thames-Water"
    # Das Suffix der Anzeige taucht nie in der Anfrage auf
    assert "*forge" not in str(info)


# -- Stufe M8: Stammdaten ueber die ID --------------------------------
@pytest.mark.asyncio
async def test_stammdaten_nach_id_ueber_das_eigene_tor():
    """Forgejo adressiert die ID ueber /repositories/{id} -- unabhaengig vom Pfad."""
    http = FakeHttp({"/repositories/42": forgejo_repo()})
    f = ForgejoForge(http, HOST)
    info = await f.repository_nach_id("42")
    assert info.provider_id == "42"
    assert info.full_name == "foo/bar"
    assert info.topics == ("hacs",)


@pytest.mark.asyncio
async def test_stammdaten_nach_id_nennen_den_neuen_namen():
    """Umbenannt: die alte ID meldet den neuen Namen -- fuer den Nachzug."""
    http = FakeHttp({"/repositories/42": forgejo_repo(full_name="neu/baz")})
    f = ForgejoForge(http, HOST)
    info = await f.repository_nach_id("42")
    assert info.full_name == "neu/baz"
    assert "repositories/42" in http.aufrufe[0][0]


@pytest.mark.asyncio
async def test_stammdaten_nach_id_geloescht_ist_nicht_gefunden():
    with pytest.raises(NichtGefunden):
        await forge().repository_nach_id("111")


@pytest.mark.asyncio
async def test_stammdaten_nach_id_keine_ziffern_kein_weg():
    from haigs.core.forge import ForgeFehler

    with pytest.raises(ForgeFehler):
        await forge().repository_nach_id("7a/../")
