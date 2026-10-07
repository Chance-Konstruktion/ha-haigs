"""Die Schmiede -- Formung und Erkennung, geprueft ohne Netz.

Die Erkennung redet mit dem echten HTTP-Zugang (``AiohttpClient`` auf
der Sitzungs-Attrappe): die Uebersetzung von 404 und 401/403 in
``NichtGefunden`` und ``ForgeFehler`` ist Teil des Vertrags, den die
Erkennung auswertet -- hier darf nichts doppelt gemimt werden.

Die Fragen der Erkennung, in der Reihenfolge des Codes:

1. ``GET /api/v4/version`` -- 200 (JSON) oder 401/403: GitLab.
2. ``GET /api/v1/version`` -- 200: die Gitea-Familie.
3. Innerhalb der Familie: Nummer ab 2 (Forgejo zaehlt selbst seit
   v7, 2024) oder der Fusstext der Startseite; sagt die Seite nichts,
   gilt Gitea.
"""

import json

import pytest
from haigs.core.forge import ForgeFehler
from haigs.core.forgejo_forge import ForgejoForge
from haigs.core.gitea_forge import GiteaForge
from haigs.core.gitlab_forge import GitLabForge
from haigs.core.http_aiohttp import AiohttpClient
from haigs.core.identity import FORGEJO, GITEA, GITLAB
from haigs.core.schmiede import AnbieterUnbekannt, erkenne, schmiede

from tests.attrappe import Aufzeichnung, SitzungsAttrappe
from tests.attrappe_kern import FakeHttp

HOST = "schmiede.example"


def klient(aufzeichnungen: list[Aufzeichnung]):
    """Ein echter AiohttpClient auf der Attrappe -- plus die Attrappe selbst."""
    attrappe = SitzungsAttrappe(list(aufzeichnungen))
    return AiohttpClient(attrappe), attrappe


def version(text: str) -> Aufzeichnung:
    return Aufzeichnung(text=json.dumps({"version": text}))


def weg() -> Aufzeichnung:
    """Ein 404, wie jede Forge es auf einen Pfad ohne Tor meldet."""
    return Aufzeichnung(
        status=404, text=json.dumps({"message": "404 Not Found"}), kopfzeilen={}
    )


# ------------------------------------------------------------------
# Die Formung
# ------------------------------------------------------------------


def test_drei_namen_drei_klassen():
    """Jeder Name formt seine Klasse -- und nichts sonst."""
    f = FakeHttp()
    assert isinstance(schmiede(f, HOST, GITLAB), GitLabForge)
    assert isinstance(schmiede(f, HOST, FORGEJO), ForgejoForge)
    assert isinstance(schmiede(f, HOST, GITEA), GiteaForge)
    for name in (GITLAB, FORGEJO, GITEA):
        assert schmiede(f, HOST, name).provider == name


def test_unbekannter_name_ist_ein_fehler():
    """Kein Geraten: ein unbekannter Name fliegt sofort raus."""
    with pytest.raises(ForgeFehler):
        schmiede(FakeHttp(), HOST, "hub")


def test_leerer_name_ist_ebenfalls_ein_fehler():
    """Die Schmiede rate nicht -- Alt-Eintraege versorgt das Geruest.

    In ``__init__.py`` steht das ``or GITLAB`` fuer Eintraege ohne
    Namen; die Schmiede selbst bleibt streng, damit kein leerer Name
    je unbemerkt durchrauscht.
    """
    with pytest.raises(ForgeFehler):
        schmiede(FakeHttp(), HOST, "")


# ------------------------------------------------------------------
# Die Erkennung: GitLab
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gitlab_mit_offenem_tor():
    klient_, attrappe = klient([version("17.9.0")])
    assert await erkenne(klient_, HOST) == GITLAB
    assert attrappe.abrufe[0][0] == f"https://{HOST}/api/v4/version"


@pytest.mark.asyncio
async def test_gitlab_mit_verriegeltem_tor():
    """401 auf die Versionfrage ist GitLab -- nur GitLab verschliesst sie."""
    klient_, _ = klient(
        [
            Aufzeichnung(
                status=401,
                text=json.dumps({"message": "401 Unauthorized"}),
                kopfzeilen={},
            )
        ]
    )
    assert await erkenne(klient_, HOST) == GITLAB


# ------------------------------------------------------------------
# Die Erkennung: die Familie und ihre Geschwister
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_forgejo_an_der_nummer():
    """Forgejo zaehlt selbst (v7, 2024): Nummer ab 2 nennt den Namen."""
    klient_, _ = klient([weg(), version("13.0.1+gitea-1.22.0")])
    assert await erkenne(klient_, HOST) == FORGEJO


@pytest.mark.asyncio
async def test_gitea_an_der_nummer_und_der_seite():
    """Gitea bleibt bei 1.x -- und die Seite nennt ihn beim Namen."""
    klient_, attrappe = klient(
        [
            weg(),
            version("1.23.8"),
            Aufzeichnung(rohbytes=b"<html><footer>Powered by Gitea</footer></html>"),
        ]
    )
    assert await erkenne(klient_, HOST) == GITEA
    assert attrappe.abrufe[2][0] == f"https://{HOST}/"


@pytest.mark.asyncio
async def test_gitea_ohne_aussage_der_seite():
    """Schweigt die Seite (oder versagt sie), gilt Gitea -- die API ist gemeinsam."""
    klient_, _ = klient([weg(), version("1.22.0"), weg()])
    assert await erkenne(klient_, HOST) == GITEA


@pytest.mark.asyncio
async def test_alte_forgejo_nennt_die_seite():
    """Forgejo aus 1.x-Zeiten: die Nummer trennt nicht, die Seite tut es."""
    klient_, _ = klient(
        [
            weg(),
            version("1.21.11"),
            Aufzeichnung(rohbytes=b"Powered by Forgejo -- a fork of Gitea"),
        ]
    )
    assert await erkenne(klient_, HOST) == FORGEJO


@pytest.mark.asyncio
async def test_unlesbare_nummer_fragt_die_seite():
    klient_, _ = klient(
        [weg(), Aufzeichnung(text=json.dumps({"version": "fast ein Sonntag"})), weg()]
    )
    assert await erkenne(klient_, HOST) == GITEA


@pytest.mark.asyncio
async def test_verriegelte_familie_fragt_die_seite():
    """401 auf die Familienfrage: Tor da, Nummer verwehrt -- die Seite entscheidet."""
    klient_, _ = klient(
        [
            weg(),
            Aufzeichnung(
                status=403,
                text=json.dumps({"message": "403 Forbidden"}),
                kopfzeilen={},
            ),
            Aufzeichnung(rohbytes=b"Powered by Gitea"),
        ]
    )
    assert await erkenne(klient_, HOST) == GITEA


# ------------------------------------------------------------------
# Die Erkennung: keiner da
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kein_anbieter_dort():
    """Zweimal 404: die ehrliche Antwort heisst 'von Hand waehlen'."""
    klient_, _ = klient([weg(), weg()])
    with pytest.raises(AnbieterUnbekannt):
        await erkenne(klient_, HOST)


@pytest.mark.asyncio
async def test_formlose_version_ist_ein_fehler():
    """Antwortet das GitLab-Tor mit etwas ohne Form, ist das ein Fehler.

    Kein Dict dort, wo eines hingehoert, ist kein Grund zu raten --
    der Fehler geht weiter, der Dialog nennt ihn.
    """
    klient_, _ = klient([Aufzeichnung(text=json.dumps(["kein", "dict"]))])
    with pytest.raises(ForgeFehler):
        await erkenne(klient_, HOST)
