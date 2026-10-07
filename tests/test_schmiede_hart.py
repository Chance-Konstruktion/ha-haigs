"""Die Schmiede unter feindlichem Beschuss (Flug 2093).

Captive Portale, Proxe und halbtote Server: die Auto-Erkennung darf
luegen, aber nicht raten. Bis Flug 2093 stand der 200-mit-HTML-Fall
beim verriegelten GitLab-Tor mit drin -- jeder Hotspot zwischen
Home Assistant und der Welt waere als GitLab ausgegeben worden.
Jetzt sagt die Schmiede: kein JSON, kein Anbieter, Hand-Wahl.
"""

import json

import pytest
from haigs.core.forge import ForgeFehler
from haigs.core.http_aiohttp import AiohttpClient, KeinJson
from haigs.core.identity import FORGEJO, GITEA, GITLAB
from haigs.core.schmiede import AnbieterUnbekannt, erkenne

from tests.attrappe import Aufzeichnung, SitzungsAttrappe

HOST = "schmiede.example"


def klient(aufzeichnungen: list[Aufzeichnung]):
    attrappe = SitzungsAttrappe(list(aufzeichnungen))
    return AiohttpClient(attrappe), attrappe


def html(seite: str = "<html>Willkommen im Hotel WLAN</html>") -> Aufzeichnung:
    """200 mit einer ganz normalen Hotspot-Begruessung."""
    return Aufzeichnung(text=seite, kopfzeilen={"Content-Type": "text/html"})


def version(text: str) -> Aufzeichnung:
    return Aufzeichnung(text=json.dumps({"version": text}))


def weg() -> Aufzeichnung:
    return Aufzeichnung(
        status=404, text=json.dumps({"message": "404 Not Found"}), kopfzeilen={}
    )


# ------------------------------------------------------------------
# Der Hotspot-Fall: 200 mit HTML ueberall
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_captive_portal_ist_kein_gitlab_mehr():
    """200-HTML auf der Versionsfrage: frueher wurde das als GitLab
    behauptet (der Fehler sass beim verriegelten Tor mit drin)."""
    klient_, _ = klient([html(), html()])
    with pytest.raises(AnbieterUnbekannt):
        await erkenne(klient_, HOST)


@pytest.mark.asyncio
async def test_html_auf_v4_und_json_auf_v1_erkennt_gitea():
    """Ein Proxy, der nur das v4-Tor verbaut: die Familie zahlt trotzdem."""
    klient_, _ = klient([html(), version("1.23.8"), html()])
    assert await erkenne(klient_, HOST) == GITEA


@pytest.mark.asyncio
async def test_html_auf_beiden_toren_nennt_den_grund():
    """Die Fehlermeldung sagt HTML, Portal und Hand-Wahl -- ehrlich."""
    klient_, _ = klient([html(), html()])
    with pytest.raises(AnbieterUnbekannt) as treffer:
        await erkenne(klient_, HOST)
    grund = str(treffer.value).lower()
    assert "html" in grund
    assert "hand" in grund


# ------------------------------------------------------------------
# Halbtote und boese Server
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_serverfehler_auf_der_versionsfrage():
    """500 auf /api/v4: ein Fehler, kein GitLab -- und kein Raten."""
    klient_, _ = klient(
        [
            Aufzeichnung(status=500, text="Internal Server Error", kopfzeilen={}),
            weg(),
        ]
    )
    with pytest.raises(ForgeFehler):
        await erkenne(klient_, HOST)


@pytest.mark.asyncio
async def test_gitea_version_mit_zusatz_und_leerzeichen():
    """' 1.23.8+dev-abc1 ' -- Leerzeichen und Zusatz stoeren nicht."""
    klient_, _ = klient([weg(), version(" 1.23.8+dev-abc1 ")])
    assert await erkenne(klient_, HOST) == GITEA


@pytest.mark.asyncio
async def test_versionsantwort_ohne_version_feld():
    """JSON, aber ohne Versionsfeld: die Seite entscheidet."""
    klient_, _ = klient(
        [
            weg(),
            Aufzeichnung(text="{}", kopfzeilen={}),
            Aufzeichnung(rohbytes=b"<footer>Powered by Forgejo</footer>"),
        ]
    )
    assert await erkenne(klient_, HOST) == FORGEJO


@pytest.mark.asyncio
async def test_leere_version_und_stille_startseite():
    """Leere Version, Seite sagt nichts: Gitea bleibt der Rueckhalt."""
    klient_, _ = klient(
        [
            weg(),
            version(""),
            Aufzeichnung(rohbytes=b"<html></html>"),
        ]
    )
    assert await erkenne(klient_, HOST) == GITEA


@pytest.mark.asyncio
async def test_startseite_mit_binarem_muell():
    """Eine Startseite in kaputtem Encoding: kein Absturz, Gitea."""
    klient_, _ = klient(
        [
            weg(),
            version("1.21.0"),
            Aufzeichnung(rohbytes=b"\xff\xfe\x00fa\xce"),
        ]
    )
    assert await erkenne(klient_, HOST) == GITEA


# ------------------------------------------------------------------
# KeinJson als eigene Fehlerart
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kein_json_ist_immer_noch_ein_forge_fehler():
    """Wer ForgeFehler faengt, faengt KeinJson mit -- alter Vertrag."""
    klient_, _ = klient([Aufzeichnung(text="ganz klar kein JSON")])
    with pytest.raises(ForgeFehler):
        await klient_.get_json(f"https://{HOST}/api/v4/version")


@pytest.mark.asyncio
async def test_kein_json_traegt_seinen_namen():
    """Die Fehlerart ist beim Namen nennbar -- fuer die Schmiede."""
    klient_, _ = klient([Aufzeichnung(text="ganz klar kein JSON")])
    with pytest.raises(KeinJson):
        await klient_.get_json(f"https://{HOST}/api/v4/version")


# ------------------------------------------------------------------
# Host-Schreibweisen
# ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_host_mit_schema_und_schraegstrich():
    """https://host/ und host werden dieselbe Adresse."""
    klient_, attrappe = klient([version("17.9.0")])
    assert await erkenne(klient_, "https://" + HOST + "/") == GITLAB
    assert attrappe.abrufe[0][0] == f"https://{HOST}/api/v4/version"


@pytest.mark.asyncio
async def test_host_mit_grossbuchstaben():
    """GITLAB.EXAMPLE -- DNS ist grosszuegig, die Schmiede auch."""
    klient_, attrappe = klient([version("17.9.0")])
    assert await erkenne(klient_, HOST.upper()) == GITLAB
    # Der Ruf geht an den Host, wie er ankam -- DNS klaert das.
    assert HOST.upper() in attrappe.abrufe[0][0]
