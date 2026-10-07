"""Tests fuer den Update-Lauf der Stufe M5 -- ohne Home Assistant, ohne Netz."""

from __future__ import annotations

import pytest
from haigs.core.aktualisierungen import Fund, Pruefauftrag, lauf, pruefe
from haigs.core.forge import ForgeFehler
from haigs.core.gitlab_forge import GitLabForge

from tests.attrappe_kern import FakeHttp

HOST = "gitlab.example.net"


def forge_mit(antworten: dict) -> GitLabForge:
    """Ein Forge auf der Attrappe; Schluessel sind URL-Teile."""
    return GitLabForge(FakeHttp(json_antworten=antworten), HOST)


def release_daten(tag: str, beschreibung: str = "", veroeffentlicht: str = "") -> dict:
    return {
        "tag_name": tag,
        "name": "Version " + tag,
        "description": beschreibung,
        "released_at": veroeffentlicht,
    }


def auftrag(installiert: str = "", vorab: bool = False) -> Pruefauftrag:
    return Pruefauftrag(
        schluessel="gitlab@" + HOST + ":789012",
        pfad="foo/bar",
        installiert=installiert,
        mit_vorabversionen=vorab,
    )


async def test_fund_aus_releases_mit_notizen() -> None:
    forge = forge_mit(
        {
            "foo%2Fbar/releases": [
                release_daten("v1.2.0", "Die Notizen", "2026-09-01T10:00:00Z"),
                release_daten("v1.1.0", "Alte Notizen"),
            ]
        }
    )
    fund = await pruefe(forge, auftrag(installiert="1.1.0"))

    assert fund.verfuegbar is True
    assert fund.installiert == "1.1.0"
    assert fund.neueste == "1.2.0"
    assert fund.tag == "v1.2.0"
    assert fund.notizen == "Die Notizen"
    assert fund.quelle == "releases"
    assert fund.veroeffentlicht_am == "2026-09-01T10:00:00Z"
    assert fund.fehler is None


async def test_auf_dem_neuesten_stand() -> None:
    forge = forge_mit({"foo%2Fbar/releases": [release_daten("v1.2.0", "Die Notizen")]})
    fund = await pruefe(forge, auftrag(installiert="v1.2.0"))

    assert fund.verfuegbar is False
    assert not fund
    assert fund.neueste == "1.2.0"


async def test_vorabversion_nur_mit_schalter() -> None:
    antwort = [release_daten("v1.3.0-rc1", "Vorsicht")]
    forge = forge_mit({"foo%2Fbar/releases": antwort})

    ohne = await pruefe(forge, auftrag(installiert="1.2.0"))
    assert ohne.verfuegbar is False
    assert ohne.neueste == "1.2.0"
    assert ohne.tag == ""

    mit = await pruefe(forge, auftrag(installiert="1.2.0", vorab=True))
    assert mit.verfuegbar is True
    assert mit.neueste == "1.3.0-rc1"
    assert mit.tag == "v1.3.0-rc1"
    assert mit.notizen == "Vorsicht"


async def test_leere_releases_fallen_auf_tags() -> None:
    forge = forge_mit(
        {
            "foo%2Fbar/releases": [],
            "foo%2Fbar/repository/tags": [
                {"name": "v0.9.0"},
                {"name": "v1.0.0"},
                {"name": "v0.8.0"},
            ],
        }
    )
    fund = await pruefe(forge, auftrag(installiert="0.9.0"))

    assert fund.quelle == "tags"
    assert fund.neueste == "1.0.0"
    assert fund.verfuegbar is True
    assert fund.notizen == ""
    assert fund.tag == "v1.0.0"


async def test_fehlende_releases_fallen_auf_tags() -> None:
    """404 auf Releases ist kein Fehler -- die Rueckfallebene greift."""
    forge = forge_mit({"foo%2Fbar/repository/tags": [{"name": "v1.0.0"}]})
    fund = await pruefe(forge, auftrag(installiert="1.0.0"))

    assert fund.fehler is None
    assert fund.quelle == "tags"
    assert fund.neueste == "1.0.0"
    assert fund.verfuegbar is False


async def test_beides_gescheitert_ist_ein_fehler_fund() -> None:
    forge = forge_mit({})
    fund = await pruefe(forge, auftrag(installiert="1.0.0"))

    assert fund.fehler is not None
    assert fund.verfuegbar is False
    assert fund.neueste == ""
    assert not fund


async def test_fehler_isoliert_den_lauf() -> None:
    """Ein kaputtes Repo bricht den Lauf der anderen nicht ab."""
    forge = forge_mit(
        {
            "foo%2Fbar/releases": [release_daten("v2.0.0", "Neu")],
            # kaputt/bar hat keine Antworten: 404 ueberall
        }
    )
    funde = await lauf(
        forge,
        [
            Pruefauftrag("schluessel-gesund", "foo/bar", "1.0.0"),
            Pruefauftrag("schluessel-kaputt", "kaputt/bar", "1.0.0"),
        ],
    )

    assert funde["schluessel-gesund"].verfuegbar is True
    assert funde["schluessel-gesund"].fehler is None
    assert funde["schluessel-kaputt"].fehler is not None
    assert funde["schluessel-kaputt"].verfuegbar is False


async def test_lauf_ohne_auftraege_ist_leer() -> None:
    forge = forge_mit({})
    assert await lauf(forge, []) == {}


async def test_unerwarteter_fehler_wird_fund() -> None:
    """Auch Attrappen-Wut (NichtGefunden, TypeError) wird Text, nie Wurf."""

    class ZornigerHttp(FakeHttp):
        async def get_json(self, url, params=None, **_):
            raise ForgeFehler("Instanz bockt")

    forge = GitLabForge(ZornigerHttp(), HOST)
    fund = await pruefe(forge, auftrag(installiert="1.0.0"))

    assert fund.fehler == "Instanz bockt"
    assert fund.verfuegbar is False


def test_release_beschreibung_durch_den_forge() -> None:
    """Die Notizen reisen als ``beschreibung`` durch die GitLab-Schicht."""

    class StummerHttp(FakeHttp):
        async def get_json(self, url, params=None, **_):
            return [
                {
                    "tag_name": "v9.9.9",
                    "name": "Neun",
                    "description": "Die Beschreibung",
                    "released_at": "2026-08-01",
                    "assets": {"links": [{"name": "zip", "url": "https://x/y.zip"}]},
                }
            ]

    forge = GitLabForge(StummerHttp(), HOST)
    releases = []
    import asyncio

    releases = asyncio.run(forge.releases("foo/bar"))

    assert releases[0].beschreibung == "Die Beschreibung"
    assert releases[0].anhaenge == {"zip": "https://x/y.zip"}


def test_fund_ist_falsch_wenn_nichts_verfuegbar() -> None:
    fund = Fund(schluessel="x", verfuegbar=False, installiert="1.0.0", neueste="1.0.0")
    assert bool(fund) is False


@pytest.mark.parametrize(
    ("installiert", "erwartet"),
    [
        ("1.2.0", "1.3.0"),
        ("1.3.0", "1.3.0"),
    ],
)
async def test_notizen_gehoeren_zur_gewaehlten_version(
    installiert: str, erwartet: str
) -> None:
    forge = forge_mit(
        {
            "foo%2Fbar/releases": [
                release_daten("v1.2.0", "Notizen 1.2.0"),
                release_daten("v1.3.0", "Notizen 1.3.0"),
            ]
        }
    )
    fund = await pruefe(forge, auftrag(installiert=installiert))

    assert fund.neueste == erwartet
    assert fund.notizen == "Notizen " + erwartet
