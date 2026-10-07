"""Gitea-Client -- die Tochter von Forgejo, geprueft ohne Netz.

Zwei Dinge unterscheidet die Tochter von der Mutter (Flug 2088): der
Name und der ``topic``-Parameter der Stichwortsuche. Diese Pruefungen
halten beide fest -- und vor allem das Erbe: alles, was die Mutter
gegen echte Codeberg-Aufzeichnungen bewiesen hat, gilt unveraendert
fuer die Tochter, weil sie denselben Code laeuft. Dafuer laufen hier
ausserdem die echten Aufzeichnungen durch die Gitea-Schmiede.
"""

import pytest
from haigs.core.forge import NichtGefunden
from haigs.core.gitea_forge import GiteaForge
from haigs.core.identity import GITEA, RepositoryIdentity, strip_suffix
from haigs.core.schmiede import schmiede

from tests.attrappe_kern import FakeHttp
from tests.forgejo_antworten import (
    HACS_JSON_THAMES,
    RELEASES_MIT_ANHAENGEN,
    REPO_THAMES,
    SUCHE,
    TAGS_THAMES,
)

HOST = "gitea.example"


def forge(**rest):
    return GiteaForge(FakeHttp(**rest), HOST)


# ------------------------------------------------------------------
# Name und Suffix -- das Eigene der Tochter
# ------------------------------------------------------------------


def test_der_name_ist_gitea():
    """Die Schmiede liefert die Tochter zum Namen -- und der Name reist weiter."""
    gitea = schmiede(FakeHttp(), HOST, GITEA)
    assert isinstance(gitea, GiteaForge)
    assert gitea.provider == GITEA
    # Der Suffix gehoert dem Kern: *gitea, unterscheidbar von *lab und *forge.
    identitaet = RepositoryIdentity(
        provider=GITEA, host=HOST, provider_id="42", full_name="foo/bar"
    )
    assert identitaet.display_full_name == "foo/bar*gitea"
    assert strip_suffix("foo/bar*gitea") == "foo/bar"
    assert strip_suffix("foo/bar*forge") == "foo/bar"
    assert strip_suffix("foo/bar") == "foo/bar"


def test_sie_ist_ein_forge():
    """Die Tochter erfuellt die Naht -- jedes geforderte Stueck ist da."""
    gitea = GiteaForge(FakeHttp(), HOST)
    for stueck in (
        "repository",
        "repository_nach_id",
        "releases",
        "tags",
        "datei",
        "archiv",
        "archiv_url",
        "anhang",
        "suche_nach_topic",
    ):
        assert callable(getattr(gitea, stueck)), stueck


# ------------------------------------------------------------------
# Die Suche -- der eine parameterische Unterschied
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_die_suche_schickt_topic_mit():
    """Gitea ehrt ``topic=true``; die Tochter schickt ihn mit.

    Forgejo (Mutter) schickt ihn nicht -- das Gegenstueck sitzt in
    ``test_forgejo_forge.py``. Die exakte Filterung bleibt scharf:
    der Perlen-Treffer ohne Topic faellt weiterhin raus.
    """
    gitea = forge(json_antworten={"/repos/search": SUCHE})
    funde = await gitea.suche_nach_topic(grenze=5)
    pfad, parameter = gitea.http.aufrufe[0]
    assert parameter.get("topic") == "true", "Gitea sucht Themen, wenn es gefragt wird"
    assert parameter.get("q") == "hacs"
    assert [f.full_name for f in funde] == [
        "jelmer/HA-Thames-Water",
        "Etuldan/hassio-dyndns",
        "touero/HaVacation",
    ]


@pytest.mark.asyncio
async def test_die_gruppe_listet_organisationen():
    """Das Erbe der Mutter: Organisation zuerst, Benutzer als Rueckhalt."""
    gitea = forge(
        json_antworten={
            "/orgs/super-z/repos": [REPO_THAMES],
        }
    )
    funde = await gitea.suche_nach_topic(gruppe="super-z", grenze=5)
    assert [f.full_name for f in funde] == ["jelmer/HA-Thames-Water"]


# ------------------------------------------------------------------
# Das Erbe gegen echte Aufzeichnungen (Codeberg, API v1)
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stammdaten_aus_echter_aufzeichnung():
    gitea = forge(json_antworten={"/repos/jelmer/HA-Thames-Water": REPO_THAMES})
    info = await gitea.repository("jelmer/HA-Thames-Water")
    assert info.provider_id == str(REPO_THAMES["id"])
    assert info.full_name == "jelmer/HA-Thames-Water"
    assert info.sterne == REPO_THAMES["stars_count"]


@pytest.mark.asyncio
async def test_identitaet_traegt_den_gitea_namen():
    gitea = forge(json_antworten={"/repos/foo/bar": REPO_THAMES})
    identitaet = await gitea.identitaet("foo/bar")
    assert identitaet.provider == GITEA
    assert identitaet.storage_key == "gitea@" + HOST + ":" + str(REPO_THAMES["id"])


@pytest.mark.asyncio
async def test_datei_aus_echter_aufzeichnung():
    gitea = forge(dateien={"/raw/hacs.json": HACS_JSON_THAMES})
    roh = await gitea.datei("jelmer/HA-Thames-Water", "hacs.json", "main")
    assert roh == HACS_JSON_THAMES


@pytest.mark.asyncio
async def test_releases_mit_anhaengen():
    gitea = forge(json_antworten={"/releases": RELEASES_MIT_ANHAENGEN})
    releases = await gitea.releases("forgejo/forgejo")
    assert releases[0].tag == "v16.0.3"
    assert len(releases[0].anhaenge) == len(RELEASES_MIT_ANHAENGEN[0]["assets"])


@pytest.mark.asyncio
async def test_tags_als_rueckfallebene():
    gitea = forge(json_antworten={"/tags": TAGS_THAMES})
    tags = await gitea.tags("jelmer/HA-Thames-Water")
    assert tags == [t["name"] for t in TAGS_THAMES if t.get("name")]


@pytest.mark.asyncio
async def test_archivadresse_traegt_zip():
    gitea = forge()
    url = await gitea.archiv_url("foo/bar", "v1.2.0")
    assert url == f"https://{HOST}/api/v1/repos/foo/bar/archive/v1.2.0.zip"


@pytest.mark.asyncio
async def test_404_bleibt_nicht_gefunden():
    gitea = forge()  # FakeHttp antwortet 404 Project Not Found
    with pytest.raises(NichtGefunden):
        await gitea.repository("gibt/es/nicht")
