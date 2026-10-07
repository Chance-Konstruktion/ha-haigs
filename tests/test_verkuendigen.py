"""Verkuendigung (M10-Nachklapp): der Pruefstand fuer den Release-Eintrag.

Befund c aus dem !11-Review: statt dem release-cli-Image laeuft die
Verkuendung als reine Standardbibliothek -- ZIP per PUT in die
Generic Package Registry, Eintrag per POST, beides mit dem JOB-TOKEN
des laufenden Jobs. Hier wird bewiesen:

* **Was auf die Reise geht** -- die Paketadresse, die Anhang-Bytes,
  der Text des Eintrags, der Link auf die Paketadresse (nicht auf
  den Job, der vergeht).
* **Was der Fehlerfall sagt** -- fehlende Variablen, fehlender ZIP,
  ein Tag, der nicht zur manifest.json passt, eine Registry, die
  ablehnt, ein Release, der schon existiert. Eintragung ist nichts,
  was man lautlos zuruecknimmt -- die Verweigerung muss beim Namen
  nennen, was sie verweigert.

Der Transport ist die Naht: die Tests legen eine Attrappe hinein, es
geht nie ein Byte ins Netz.
"""

import json
from pathlib import Path

import pytest

from auslieferung.release_bauen import ANZEIGENAME, fingerabdruck, lies_version
from auslieferung.verkuendigen import (
    ERFORDERLICH,
    VerkuendigungsFehler,
    haupt,
    verkuendigen,
)

#: Die Wurzel des ausgecheckten Standes -- zwei Ebenen ueber diesem Test.
WURZEL = Path(__file__).resolve().parents[1]

#: Version und Tag des ausgecheckten Standes -- aus der manifest.json
#: gelesen, nie von Hand gepflegt. Diese Pruefungen laufen bei JEDEM
#: Release-Schnitt weiter (Befund Flug 2082: die hartcodierte Version
#: brach die Bahn bei jedem Bump und verdaechtigte den Schnitt).
VERSION = lies_version(WURZEL)
TAG = f"v{VERSION}"


class Attrappe:
    """Zeichnet jeden Aufruf auf und spielt vorbereitete Antworten ein."""

    def __init__(self, antworten: list[tuple[int, bytes]] | None = None):
        self.aufrufe: list[dict] = []
        self.antworten = list(antworten or [])

    def __call__(self, methode, url, token, inhalt=None, inhaltstyp=None):
        self.aufrufe.append(
            {
                "methode": methode,
                "url": url,
                "token": token,
                "inhalt": inhalt,
                "inhaltstyp": inhaltstyp,
            }
        )
        if self.antworten:
            status, koerper = self.antworten.pop(0)
            return status, koerper
        return 201, b"{}"


def umgebung(tag: str | None = None) -> dict[str, str]:
    """Eine CI-Umgebung, wie sie der Job vorfindet -- ohne echte Adresse.

    Ohne Angabe passt der Tag zum ausgecheckten Stand -- der Normalfall:
    CI haengt den Tag an den Lauf, der aus genau diesem Stand gebaut ist.
    """
    return {
        "CI_API_V4_URL": "https://gitlab.example.test/api/v4",
        "CI_PROJECT_ID": "42",
        "CI_JOB_TOKEN": "job-token-dieses-laufs",
        "CI_COMMIT_TAG": tag or TAG,
    }


@pytest.fixture
def zip_pfad(tmp_path: Path) -> Path:
    pfad = tmp_path / f"{ANZEIGENAME}-{TAG}.zip"
    pfad.write_bytes(b"zip-inhalt, zwei Bauten gleich")
    return pfad


# ------------------------------------------------- Was auf die Reise geht


class TestHerangang:
    def test_laedt_paket_und_traegt_release_ein(self, zip_pfad: Path):
        attrappe = Attrappe()
        protokoll = verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)

        assert len(attrappe.aufrufe) == 2
        put, post = attrappe.aufrufe

        assert put["methode"] == "PUT"
        assert put["url"] == (
            "https://gitlab.example.test/api/v4/projects/42"
            f"/packages/generic/{ANZEIGENAME}/{VERSION}/{ANZEIGENAME}-{TAG}.zip"
        )
        assert put["token"] == "job-token-dieses-laufs"
        assert put["inhalt"] == b"zip-inhalt, zwei Bauten gleich"
        assert put["inhaltstyp"] == "application/zip"

        assert post["methode"] == "POST"
        assert post["url"] == "https://gitlab.example.test/api/v4/projects/42/releases"
        assert post["inhaltstyp"] == "application/json"
        eintrag = json.loads(post["inhalt"])
        assert eintrag["tag_name"] == TAG
        assert eintrag["name"] == f"HAIGS {TAG}"
        assert fingerabdruck(zip_pfad) in eintrag["description"]
        (link,) = eintrag["assets"]["links"]
        assert link["name"] == f"{ANZEIGENAME}-{TAG}.zip -- Hand-Installation"
        assert link["url"] == put["url"]

        assert protokoll["paket"] == put["url"]
        assert protokoll["sha"] == fingerabdruck(zip_pfad)

    def test_link_zieht_auf_die_paketadresse_nicht_auf_den_job(self, zip_pfad: Path):
        attrappe = Attrappe()
        verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)

        eintrag = json.loads(attrappe.aufrufe[1]["inhalt"])
        (link,) = eintrag["assets"]["links"]
        assert "/-/jobs/" not in link["url"]
        assert "/packages/generic/" in link["url"]

    def test_v_wird_vor_der_version_entfernt(self, zip_pfad: Path):
        attrappe = Attrappe()
        verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)
        assert f"/{VERSION}/" in attrappe.aufrufe[0]["url"]


# ------------------------------------------------- Was der Fehlerfall sagt


class TestFehlerfaelle:
    def test_fehlende_variablen_beim_namen_genannt(self, zip_pfad: Path):
        env = umgebung()
        del env["CI_JOB_TOKEN"]
        attrappe = Attrappe()
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, zip_pfad, env, transport=attrappe)
        assert "CI_JOB_TOKEN" in str(befund.value)
        assert attrappe.aufrufe == []  # nichts geht auf die Reise

    def test_zip_fehlt(self, tmp_path: Path):
        attrappe = Attrappe()
        fehlt = tmp_path / "nirgendwo.zip"
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, fehlt, umgebung(), transport=attrappe)
        assert "fehlt" in str(befund.value)
        assert attrappe.aufrufe == []

    def test_tag_widerspricht_der_manifest_version(self, zip_pfad: Path):
        attrappe = Attrappe()
        falsch = "v9.9.9" if VERSION != "9.9.9" else "v8.8.8"
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, zip_pfad, umgebung(tag=falsch), transport=attrappe)
        assert "manifest.json" in str(befund.value)
        assert attrappe.aufrufe == []

    def test_registry_lehnt_den_zip_ab(self, zip_pfad: Path):
        attrappe = Attrappe(antworten=[(500, b'{"message":"nope"}')])
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)
        assert "500" in str(befund.value)
        assert "nope" in str(befund.value)

    def test_release_existiert_bereits(self, zip_pfad: Path):
        attrappe = Attrappe(
            antworten=[(201, b"{}"), (400, b'{"message":"Release already exists"}')]
        )
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)
        assert "bereits" in str(befund.value)
        assert len(attrappe.aufrufe) == 2  # der ZIP liegt, der Eintrag nicht doppelt

    def test_unbekannter_fehler_zeigt_den_koerper(self, zip_pfad: Path):
        attrappe = Attrappe(antworten=[(201, b"{}"), (403, b'{"message":"verboten"}')])
        with pytest.raises(VerkuendigungsFehler) as befund:
            verkuendigen(WURZEL, zip_pfad, umgebung(), transport=attrappe)
        assert "403" in str(befund.value)
        assert "verboten" in str(befund.value)


# ------------------------------------------------- Kommandozeile


class TestKommandozeile:
    def test_haupt_mit_umgebung(self, zip_pfad: Path, capsys):
        attrappe = Attrappe()
        assert haupt([str(zip_pfad)], env=umgebung(), transport=attrappe) == 0
        ausgabe = capsys.readouterr().out
        assert f"/packages/generic/{ANZEIGENAME}/{VERSION}/" in ausgabe
        assert "SHA-256" in ausgabe
        assert f"HAIGS {TAG}" in ausgabe
        assert len(attrappe.aufrufe) == 2

    def test_haupt_ohne_alles(self):
        assert haupt([], env={}) == 1

    def test_haupt_zu_viele_pfade(self, zip_pfad: Path):
        assert haupt([str(zip_pfad), "noch-einer"], env=umgebung()) == 2

    def test_standardpfad_liegt_unter_dist(self, zip_pfad: Path):
        """Ohne Angabe wird dist/ gesucht -- der Ort, den der Bau ablegt."""
        from auslieferung.verkuendigen import STANDARD_ZIP_VERZEICHNIS

        assert STANDARD_ZIP_VERZEICHNIS == Path("dist")
        assert "CI_JOB_TOKEN" in ERFORDERLICH
