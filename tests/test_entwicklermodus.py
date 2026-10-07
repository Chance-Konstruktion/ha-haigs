"""Flug 2101 -- der Entwicklermodus: der Kopf des Zweigs ist die Version.

Wer entwickelt, will nicht auf ein Release warten. Im Entwicklermodus
fragt der Lauf statt nach Releases nach dem juengsten Commit des
Standardzweigs; die Version heisst ``zweig@sha7``, der volle SHA ist
der Ref fuer das Archiv. Ohne Home Assistant, ohne Netz.
"""

from __future__ import annotations

from pathlib import Path

from hacs_lab.core.aktualisierungen import Pruefauftrag, pruefe, zweig_version
from hacs_lab.core.forgejo_forge import ForgejoForge
from hacs_lab.core.gitlab_forge import GitLabForge

from tests.attrappe_kern import FakeHttp

SHA = "1a2b3c4d5e6f708192a3b4c5d6e7f80912345678"
SHA_ALT = "ffffeeee0000111122223333444455556666aaaa"


def gitlab(antworten: dict) -> tuple[GitLabForge, FakeHttp]:
    http = FakeHttp(json_antworten=antworten)
    return GitLabForge(http, "gitlab.example.net"), http


def gitlab_zweig(sha: str = SHA) -> dict:
    return {
        "name": "main",
        "commit": {
            "id": sha,
            "title": "Panel: Fuchs tanzt",
            "committed_date": "2026-10-07T18:00:00.000+02:00",
        },
    }


def dev_auftrag(installiert: str = "", zweig: str = "main") -> Pruefauftrag:
    return Pruefauftrag(
        schluessel="gitlab@gitlab.example.net:1",
        pfad="foo/bar",
        installiert=installiert,
        entwicklung=True,
        zweig=zweig,
    )


def test_die_version_eines_zweigstands() -> None:
    assert zweig_version("main", SHA) == "main@1a2b3c4"


async def test_der_kopf_des_zweigs_wird_zur_version() -> None:
    forge, http = gitlab({"foo%2Fbar/repository/branches/main": gitlab_zweig()})
    fund = await pruefe(forge, dev_auftrag())

    assert fund.fehler is None
    assert fund.neueste == "main@1a2b3c4"
    assert fund.tag == SHA  # der Ref fuer das Archiv
    assert fund.quelle == "zweig"
    assert fund.notizen == "Panel: Fuchs tanzt"
    assert fund.veroeffentlicht_am.startswith("2026-10-07")
    assert fund.verfuegbar is True
    # Releases werden im Entwicklermodus gar nicht erst gefragt.
    assert not any("/releases" in url for url, _ in http.aufrufe)


async def test_derselbe_stand_ist_kein_update() -> None:
    forge, _ = gitlab({"foo%2Fbar/repository/branches/main": gitlab_zweig()})
    fund = await pruefe(forge, dev_auftrag(installiert="main@1a2b3c4"))
    assert fund.verfuegbar is False


async def test_ein_neuer_push_ist_ein_update() -> None:
    forge, _ = gitlab({"foo%2Fbar/repository/branches/main": gitlab_zweig(SHA_ALT)})
    fund = await pruefe(forge, dev_auftrag(installiert="main@1a2b3c4"))
    assert fund.verfuegbar is True
    assert fund.neueste == "main@ffffeee"


async def test_ein_release_stand_wird_vom_zweig_abgeloest() -> None:
    """Wer vom Release in den Entwicklermodus wechselt, bekommt den Zweig angeboten."""
    forge, _ = gitlab({"foo%2Fbar/repository/branches/main": gitlab_zweig()})
    fund = await pruefe(forge, dev_auftrag(installiert="1.2.0"))
    assert fund.verfuegbar is True


async def test_ohne_zweig_fragt_der_lauf_nach_dem_standardzweig() -> None:
    forge, http = gitlab(
        {
            "foo%2Fbar/repository/branches/develop": gitlab_zweig(),
            "/projects/foo%2Fbar": {
                "id": 1,
                "path_with_namespace": "foo/bar",
                "default_branch": "develop",
            },
        }
    )
    fund = await pruefe(forge, dev_auftrag(zweig=""))
    assert fund.fehler is None
    assert fund.neueste == "develop@1a2b3c4"


async def test_ein_fehlender_zweig_wirft_nicht() -> None:
    forge, _ = gitlab({})
    fund = await pruefe(forge, dev_auftrag())
    assert fund.verfuegbar is False
    assert fund.fehler
    assert fund.neueste == ""


async def test_forgejo_kennt_den_zweigstand() -> None:
    http = FakeHttp(
        json_antworten={
            "/repos/foo/bar/branches/main": {
                "name": "main",
                "commit": {
                    "id": SHA,
                    "message": "Erste Zeile\n\nlanger Text",
                    "timestamp": "2026-10-07T16:00:00Z",
                },
            }
        }
    )
    forge = ForgejoForge(http, "codeberg.example")
    kopf = await forge.zweig_stand("foo/bar", "main")
    assert kopf.sha == SHA
    assert kopf.nachricht == "Erste Zeile"
    assert kopf.datum == "2026-10-07T16:00:00Z"


async def test_das_archiv_kommt_zum_sha() -> None:
    """Die Installation nimmt den SHA als Ref -- beide Schmieden kennen ihn."""
    forge, _ = gitlab({})
    url = await forge.archiv_url("foo/bar", SHA)
    assert SHA in url


def test_die_option_steht_im_dialog_beider_sprachen() -> None:
    wurzel = Path(__file__).resolve().parents[1] / "custom_components" / "hacs_lab"
    for datei in ("strings.json", "translations/en.json", "translations/de.json"):
        text = (wurzel / datei).read_text(encoding="utf-8")
        assert '"entwickler"' in text, datei
        assert '"entwicklermodus"' in text, datei
