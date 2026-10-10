"""Die M4b-Naht: Anhang-Auswahl, Beschaffung, Zielweg, Deinstallation.

Vier Dinge muessen hier bewiesen werden:

* **Auswahl** -- genau EIN Zip-Anhang zaehlt; null oder mehrere bedeuten
  Rueckfall aufs Tag-Archiv. Raterei zwischen Zips ist keine Auswahl.
* **Beschaffung** -- Anhang zuerst, Tag-Archiv sonst; auch dann, wenn
  die Release-Frage selbst scheitert (der Anhang ist Bevorzugung,
  keine Pflicht).
* **Zielweg** -- die Installation meldet den Weg relativ zur
  Konfiguration; genau dieser Weg geht in das Protokoll.
* **Deinstallation** -- der verzeichnete Weg wird geprueft (Ablagen
  lassen sich von Hand veraendern), das Ziel in einem Zug wegbenannt,
  nie halbe Zustaende.

Die Attrappe fuer den HTTP-Zugang des Kerns wohnt in
``tests/attrappe_kern.py``; der Forge hier ist eine kleine Klasse, kein
Netz.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path, PurePosixPath

import pytest
from haigs.core.forge import Release
from haigs.core.zielpfade import ist_zielpfad
from haigs.installation import (
    InstallationsFehler,
    _deinstalliere_sync,
    _installiere_sync,
    beschaffe_archiv,
    finde_lagerform,
    lese_archiv_datei,
    waehle_anhang,
)

# ---------------------------------------------------- Anhang-Auswahl


class TestWaehleAnhang:
    def test_genau_ein_zip_liefert_die_adresse(self):
        assert waehle_anhang({"paket.zip": "https://x/paket.zip"}) == (
            "https://x/paket.zip"
        )

    def test_grossschreibung_zaehlt_nicht(self):
        assert waehle_anhang({"Paket.ZIP": "https://x/p"}) == "https://x/p"

    def test_kein_zip_kein_treffer(self):
        assert waehle_anhang({"paket.tar.gz": "https://x/t"}) is None
        assert waehle_anhang({"sha256": "https://x/s"}) is None
        assert waehle_anhang({}) is None

    def test_zwei_zips_kein_treffer(self):
        """Zwischen zwei Zips wuerfeln ist Raterei -- also: keiner."""
        assert waehle_anhang({"a.zip": "https://x/a", "b.zip": "https://x/b"}) is None

    def test_zip_mit_leerer_adresse_zaehlt_nicht(self):
        assert waehle_anhang({"paket.zip": ""}) is None

    def test_zip_neben_zusaetzen_nimmt_das_zip(self):
        """Signaturen sind Zusatz, nicht Konkurrenz."""
        assert (
            waehle_anhang({"paket.zip": "https://x/p", "paket.zip.sha256": "https://x/s"})
            == "https://x/p"
        )


# ----------------------------------------------------- Beschaffung


class ForgeAttrappe:
    """Ein Forge, der alles aus dem Regal kennt -- ohne Netz."""

    def __init__(
        self,
        releases: list[Release] | None = None,
        anhaenge: dict[str, bytes] | None = None,
        versagt_bei_releases: bool = False,
    ) -> None:
        self.releases_antwort = releases or []
        self.anhaenge = anhaenge or {}
        self.versagt_bei_releases = versagt_bei_releases
        self.verlangte_url: str | None = None
        self.verlangtes_archiv: tuple[str, str] | None = None

    async def releases(self, pfad: str) -> list[Release]:
        if self.versagt_bei_releases:
            raise RuntimeError("Release-Frage gescheitert")
        return self.releases_antwort

    async def anhang(self, url: str) -> bytes:
        self.verlangte_url = url
        return self.anhaenge[url]

    async def archiv(self, pfad: str, ref: str) -> bytes:
        self.verlangtes_archiv = (pfad, ref)
        return b"ARCHIV:" + ref.encode()


def _release(tag: str, anhaenge: dict[str, str]) -> Release:
    return Release(tag=tag, name=tag, anhaenge=anhaenge)


class TestBeschaffeArchiv:
    async def test_anhang_geht_vor(self):
        forge = ForgeAttrappe(
            releases=[_release("v1", {"p.zip": "https://x/p.zip"})],
            anhaenge={"https://x/p.zip": b"ZIP-BYTES"},
        )
        archiv, herkunft = await beschaffe_archiv(forge, "foo/bar", "v1")
        assert archiv == b"ZIP-BYTES"
        assert herkunft == "anhang"
        assert forge.verlangtes_archiv is None  # Archiv nie angefasst

    async def test_ohne_anhang_das_tag_archiv(self):
        forge = ForgeAttrappe(releases=[_release("v1", {})])
        archiv, herkunft = await beschaffe_archiv(forge, "foo/bar", "v1")
        assert archiv == b"ARCHIV:v1"
        assert herkunft == "archiv"

    async def test_mehrdeutiger_anhang_das_tag_archiv(self):
        forge = ForgeAttrappe(
            releases=[_release("v1", {"a.zip": "u1", "b.zip": "u2"})],
            anhaenge={"u1": b"x", "u2": b"y"},
        )
        _, herkunft = await beschaffe_archiv(forge, "foo/bar", "v1")
        assert herkunft == "archiv"

    async def test_anderer_tag_das_tag_archiv(self):
        forge = ForgeAttrappe(
            releases=[_release("v2", {"p.zip": "https://x/p.zip"})],
            anhaenge={"https://x/p.zip": b"ZIP"},
        )
        _, herkunft = await beschaffe_archiv(forge, "foo/bar", "v1")
        assert herkunft == "archiv"

    async def test_versagende_release_frage_das_tag_archiv(self):
        """Der Anhang ist Bevorzugung -- sein Scheitern ist kein Abbruch."""
        forge = ForgeAttrappe(versagt_bei_releases=True)
        archiv, herkunft = await beschaffe_archiv(forge, "foo/bar", "v1")
        assert archiv == b"ARCHIV:v1"
        assert herkunft == "archiv"


# --------------------------------------------------------- Zielweg


class TestIstZielpfad:
    def test_bekannte_wurzeln_zaehlen(self):
        assert ist_zielpfad("custom_components/beispiel")
        assert ist_zielpfad("themes")
        assert ist_zielpfad("www/community/beispiel")

    def test_fremde_wurzel_zaehlt_nicht(self):
        assert not ist_zielpfad("homeassistant/components")
        assert not ist_zielpfad("configuration.yaml")

    def test_absolut_und_flucht_zaehlen_nicht(self):
        assert not ist_zielpfad("/etc")
        assert not ist_zielpfad("custom_components/../x")
        assert not ist_zielpfad("")
        assert not ist_zielpfad("..")


# ---------------------------------------------------- Deinstallation


class TestDeinstallation:
    def test_entfernt_das_verzeichnete_ziel(self, tmp_path: Path):
        ziel = tmp_path / "custom_components" / "beispiel"
        ziel.mkdir(parents=True)
        (ziel / "manifest.json").write_text("{}", encoding="utf-8")

        _deinstalliere_sync("custom_components/beispiel", tmp_path)

        assert not ziel.exists()
        zwischen = tmp_path / ".haigs_zwischenlager"
        assert not list(zwischen.glob("*.weg"))  # auch das Lager ist leer

    def test_untauglicher_weg_wird_abgewiesen(self, tmp_path: Path):
        """Die Ablage ist eine Datei -- Vertrauen ist keine Pruefung."""
        (tmp_path / "wichtig.txt").write_text("bleib", encoding="utf-8")
        for boese in (
            "../wichtig",
            "/etc",
            "homeassistant/components",
            "custom_components/../../wichtig",
            "",
        ):
            with pytest.raises(InstallationsFehler):
                _deinstalliere_sync(boese, tmp_path)
        assert (tmp_path / "wichtig.txt").read_text(encoding="utf-8") == "bleib"

    def test_fehlendes_ziel_ist_klartext(self, tmp_path: Path):
        with pytest.raises(InstallationsFehler, match="nichts installiert"):
            _deinstalliere_sync("custom_components/weg_damit", tmp_path)

    def test_alte_weg_rest_werden_mit_geraeumt(self, tmp_path: Path):
        """Ein frueherer Abbruch darf beim naechsten Lauf kein Hindernis sein."""
        zwischen = tmp_path / ".haigs_zwischenlager"
        zwischen.mkdir()
        (zwischen / "beispiel.weg").mkdir()
        (zwischen / "beispiel.weg" / "muell.txt").write_text("x", encoding="utf-8")

        ziel = tmp_path / "custom_components" / "beispiel"
        ziel.mkdir(parents=True)
        _deinstalliere_sync("custom_components/beispiel", tmp_path)
        assert not ziel.exists()


# ------------------------------------------------------ Archiv-Lesen


class TestLeseArchivDatei:
    def test_kein_zip_ist_klartext(self):
        """Ein Release-Anhang, der kein ZIP ist, wird nicht installiert."""
        with pytest.raises(InstallationsFehler, match="kein ZIP"):
            lese_archiv_datei(b"definitiv kein zip", "manifest.json")


# ------------------------------------------------ Lagerform (Befund #15)


def _zip(baum: dict[str, bytes]) -> bytes:
    """Ein ZIP aus {pfad: inhalt} -- stabil sortiert, ohne Ordner-Eintraege."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as datei:
        for name in sorted(baum):
            datei.writestr(name, baum[name])
    return puffer.getvalue()


def _manifest(domain: str, version: str = "1.0.0") -> bytes:
    """Eine gueltige manifest.json -- Domain und Version einsetzbar."""
    return json.dumps(
        {
            "domain": domain,
            "name": "Beispiel",
            "version": version,
            "documentation": "https://example.org/beispiel",
        }
    ).encode("utf-8")


class TestLeseArchivDateiTiefe:
    """Befund #15: die manifest.json kann vier Ebenen tief liegen."""

    def test_tiefer_einziger_treffer_zaehlt(self):
        archiv = _zip(
            {
                "beispiel-v1.0.0/README.md": b"repo-wurzel",
                "beispiel-v1.0.0/hacs.json": b'{"name": "Beispiel"}',
                "beispiel-v1.0.0/custom_components/bienentanz/const.py": b"DOMAIN = 1",
                "beispiel-v1.0.0/custom_components/bienentanz/manifest.json": _manifest(
                    "bienentanz"
                ),
            }
        )
        assert lese_archiv_datei(archiv, "manifest.json") == _manifest("bienentanz")

    def test_flacher_geht_vor_tiefem(self):
        """Die hacs.json der Repo-Wurzel zaehlt mehr als eine tiefe Kopie."""
        archiv = _zip(
            {
                "beispiel-v1.0.0/hacs.json": b'{"name": "wurzel"}',
                "beispiel-v1.0.0/docs/beispiele/hacs.json": b'{"name": "tief"}',
            }
        )
        assert lese_archiv_datei(archiv, "hacs.json") == b'{"name": "wurzel"}'

    def test_zwei_tiefe_bleiben_mehrdeutig(self):
        archiv = _zip(
            {
                "a/custom_components/eins/manifest.json": _manifest("eins"),
                "b/custom_components/zwei/manifest.json": _manifest("zwei"),
            }
        )
        assert lese_archiv_datei(archiv, "manifest.json") is None

    def test_wurzel_und_ordner_bleiben_wie_sie_sind(self):
        """Die alte Regel gilt weiter: Wurzel oder ein Ordner, eindeutig."""
        for pfad in ("manifest.json", "bienentanz/manifest.json"):
            archiv = _zip({pfad: _manifest("bienentanz")})
            assert lese_archiv_datei(archiv, "manifest.json") == _manifest("bienentanz")


class TestFindeLagerform:
    """Entschluss b zu #15: die Lagerform kennt ihre Tiefe selbst."""

    def test_tag_quell_archiv_liefert_den_vollen_weg(self):
        archiv = _zip(
            {
                "beispiel-v1.0.0/README.md": b"repo-wurzel",
                "beispiel-v1.0.0/custom_components/bienentanz/manifest.json": (
                    _manifest("bienentanz")
                ),
            }
        )
        assert (
            finde_lagerform(archiv, "bienentanz")
            == "beispiel-v1.0.0/custom_components/bienentanz"
        )

    def test_gebauter_anhang_liefert_den_ordner(self):
        archiv = _zip({"bienentanz/manifest.json": _manifest("bienentanz")})
        assert finde_lagerform(archiv, "bienentanz") == "bienentanz"

    def test_custom_components_ohne_tag_huelle(self):
        """Die eigene Anhang-Form von haigs: Praefix ohne Tag-Ordner."""
        archiv = _zip({"custom_components/haigs/manifest.json": _manifest("haigs")})
        assert finde_lagerform(archiv, "haigs") == "custom_components/haigs"

    def test_wurzelmanifest_ist_keine_lagerform(self):
        archiv = _zip({"beispiel-v1.0.0/manifest.json": _manifest("bienentanz")})
        assert finde_lagerform(archiv, "bienentanz") is None

    def test_falscher_ordnername_ist_klartext(self):
        """custom_components/ kuendigt an, der Ordner loest es nicht ein."""
        archiv = _zip(
            {
                "beispiel-v1.0.0/custom_components/anderer_name/manifest.json": (
                    _manifest("bienentanz")
                ),
            }
        )
        with pytest.raises(InstallationsFehler, match="anderer_name"):
            finde_lagerform(archiv, "bienentanz")

    def test_zwei_lagerformen_sind_raterei(self):
        archiv = _zip(
            {
                "a/custom_components/bienentanz/manifest.json": _manifest("bienentanz"),
                "b/custom_components/bienentanz/manifest.json": _manifest("bienentanz"),
            }
        )
        with pytest.raises(InstallationsFehler, match="mehrfach"):
            finde_lagerform(archiv, "bienentanz")


class TestInstalliereLagerform:
    """Der ganze Tausch aus getrockneten Archiven -- ohne Netz, ohne HA."""

    def test_tag_quell_archiv_installiert_nur_die_integration(self, tmp_path: Path):
        """Repo-Wurzel (README, CI, hacs.json) gehoert NICHT ins Ziel."""
        archiv = _zip(
            {
                "beispiel-v1.0.0/README.md": b"repo-wurzel",
                "beispiel-v1.0.0/hacs.json": b'{"name": "Beispiel"}',
                "beispiel-v1.0.0/.gitlab-ci.yml": b"stufen: [form]",
                "beispiel-v1.0.0/custom_components/bienentanz/__init__.py": b"# tanz",
                "beispiel-v1.0.0/custom_components/bienentanz/const.py": b"DOMAIN = 1",
                "beispiel-v1.0.0/custom_components/bienentanz/manifest.json": (
                    _manifest("bienentanz")
                ),
            }
        )

        weg = _installiere_sync(archiv, "integration", "bienentanz", tmp_path)

        assert weg.pfad == PurePosixPath("custom_components/bienentanz")
        ziel = tmp_path / "custom_components" / "bienentanz"
        assert (ziel / "manifest.json").read_bytes() == _manifest("bienentanz")
        assert (ziel / "__init__.py").exists()
        assert (ziel / "const.py").exists()
        assert not (ziel / "README.md").exists()
        assert not (ziel / "hacs.json").exists()
        assert not (ziel / ".gitlab-ci.yml").exists()
        assert not (ziel / "custom_components").exists()

    def test_gebauter_anhang_bleibt_bei_der_alten_lagerform(self, tmp_path: Path):
        archiv = _zip(
            {
                "bienentanz/__init__.py": b"# tanz",
                "bienentanz/manifest.json": _manifest("bienentanz", "1.1.0"),
            }
        )

        weg = _installiere_sync(archiv, "integration", "bienentanz", tmp_path)

        assert weg.pfad == PurePosixPath("custom_components/bienentanz")
        ziel = tmp_path / "custom_components" / "bienentanz"
        assert (ziel / "__init__.py").exists()
        assert (ziel / "manifest.json").read_bytes() == _manifest("bienentanz", "1.1.0")

    def test_die_eigene_form_installiert_sich_selbst(self, tmp_path: Path):
        """haigss Anhang behaelt custom_components/ -- und geht jetzt auf."""
        archiv = _zip(
            {
                "custom_components/haigs/manifest.json": _manifest("haigs"),
                "custom_components/haigs/__init__.py": b"# schicht",
                "custom_components/haigs/core/entpacken.py": b"# kern",
            }
        )

        _installiere_sync(archiv, "integration", "haigs", tmp_path)

        ziel = tmp_path / "custom_components" / "haigs"
        assert (ziel / "core" / "entpacken.py").exists()
        assert (ziel / "manifest.json").exists()
        assert not (ziel / "custom_components").exists()

    def test_wurzelstruktur_bleibt_beim_oberteil(self, tmp_path: Path):
        """Ohne custom_components/ gilt weiter: der Ordner oben faellt weg."""
        archiv = _zip(
            {
                "beispiel-v1.0.0/__init__.py": b"# tanz",
                "beispiel-v1.0.0/manifest.json": _manifest("bienentanz"),
            }
        )

        _installiere_sync(archiv, "integration", "bienentanz", tmp_path)

        ziel = tmp_path / "custom_components" / "bienentanz"
        assert (ziel / "__init__.py").exists()
        assert (ziel / "manifest.json").exists()

    def test_flacher_anhang_manifest_in_der_wurzel(self, tmp_path: Path):
        """Flug 2096, Wunde 3b aus dem 3-System-Test: der gebaute ZIP-
        Anhang traegt die Dateien OHNE jeden Ordner -- die manifest.json
        liegt an der Wurzel (so baut es svasek/homeassistant-vistapool-
        modbus, und HACS nimmt es an). Die Wurzel IST die Integration."""
        archiv = _zip(
            {
                "__init__.py": b"# flach",
                "manifest.json": _manifest("vistapool", "1.19.0"),
                "sensor.py": b"DOMAIN = 'vistapool'",
                "modbus.py": b"# antrieb",
            }
        )

        weg = _installiere_sync(archiv, "integration", "vistapool", tmp_path)

        assert weg.pfad == PurePosixPath("custom_components/vistapool")
        ziel = tmp_path / "custom_components" / "vistapool"
        assert (ziel / "manifest.json").read_bytes() == _manifest("vistapool", "1.19.0")
        assert (ziel / "__init__.py").exists()
        assert (ziel / "sensor.py").exists()
        assert (ziel / "modbus.py").exists()

    def test_flach_ohne_manifest_bleibt_ein_fehler(self, tmp_path: Path):
        """Ohne manifest.json an der Wurzel ist und bleibt es Raterei --
        der ehrliche Fehler steht, nichts wird geschrieben."""
        archiv = _zip(
            {
                "__init__.py": b"# flach ohne zeug",
                "sensor.py": b"DOMAIN = 'was'",
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "integration", "vistapool", tmp_path)
        assert not any(tmp_path.iterdir())

    def test_flacher_anhang_gilt_nur_bei_integrationen(self, tmp_path: Path) -> None:
        """Andere Kategorien kennen keine Wurzel-Erkennung -- dort bleibt
        die Ausschnitt-Regel der hacs.json Herr im Haus (datei-Beispiel)."""
        archiv = _zip(
            {
                "manifest.json": _manifest("vistapool", "1.19.0"),
                "theme.yaml": b"wunder",
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "plugin", "vistapool", tmp_path)
        assert not (tmp_path / "custom_components").exists()

    def test_falsche_lagerform_schreibt_nichts(self, tmp_path: Path):
        archiv = _zip(
            {
                "beispiel-v1.0.0/custom_components/anderer_name/manifest.json": (
                    _manifest("bienentanz")
                ),
            }
        )
        with pytest.raises(InstallationsFehler, match="anderer_name"):
            _installiere_sync(archiv, "integration", "bienentanz", tmp_path)
        assert not any(tmp_path.iterdir())  # kein halber Zustand, gar keiner


class TestFilenameOhneAnhang:
    """Flug 2096, Wunde B: filename in der hacs.json meint den GEBAUTEN
    Release-Anhang (ha-powerline: powerline.zip). Fehlt der Anhang, ist
    das Tag-Archiv die Quelle -- und dort lebt die Integration in der
    Lagerform custom_components/<domain>/."""

    def test_filename_fehlt_im_archiv_lagerform_faellt_ein(self, tmp_path: Path):
        archiv = _zip(
            {
                "ha-powerline-github-v0.2.0/README.md": b"quellstand",
                "ha-powerline-github-v0.2.0/hacs.json": (
                    b'{"name": "Powerline", "zip_release": true,'
                    b' "filename": "powerline.zip"}'
                ),
                "ha-powerline-github-v0.2.0/custom_components/powerline/__init__.py": (
                    b"# strom"
                ),
                "ha-powerline-github-v0.2.0/custom_components/powerline/manifest.json": (
                    _manifest("powerline", "0.2.0")
                ),
            }
        )

        weg = _installiere_sync(archiv, "integration", "powerline", tmp_path)

        assert weg.pfad == PurePosixPath("custom_components/powerline")
        ziel = tmp_path / "custom_components" / "powerline"
        assert (ziel / "manifest.json").read_bytes() == _manifest("powerline", "0.2.0")
        assert (ziel / "__init__.py").exists()
        assert not (ziel / "README.md").exists()
        assert not (ziel / "hacs.json").exists()

    def test_filename_ohne_lagerform_bleibt_fehler(self, tmp_path: Path):
        """Keine Lagerform im Archiv: der ehrliche Fehler steht."""
        archiv = _zip(
            {
                "wupp/hacs.json": b'{"filename": "etwas.zip"}',
                "wupp/anderes/manifest.json": _manifest("powerline"),
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "integration", "powerline", tmp_path)
        assert not any(tmp_path.iterdir())

    def test_dateien_fallback_gilt_nur_bei_integrationen(self, tmp_path: Path):
        """Bei anderen Kategorien bleibt die Ausschnitt-Regel hart."""
        archiv = _zip(
            {
                "wupp/hacs.json": b'{"filename": "etwas.zip"}',
                "wupp/theme.yaml": b"farbe",
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "theme", "wupp", tmp_path)


# ------------------------- hacs.json im Archiv (Befund #18: Klartext)


class TestHacsJsonKeinObjekt:
    """Die hacs.json IM ARCHIV kann einer bauen, der die im Repo-Wurzel
    schon sauber hatte (Issue #18): die Aufnahme prueft nur die im Repo,
    die Installation liest die im Archiv."""

    def test_klartext_statt_unbound_local_error(self, tmp_path: Path):
        """Vor der Heilung starb die Naht mit UnboundLocalError, weil der
        except-Zweig 'schnitt.art' las, obwohl ausschnitt() schon warf.
        Der Befund: Klartext fuer Menschen."""
        archiv = _zip(
            {
                "beispiel-v1.0.0/manifest.json": _manifest("bienentanz"),
                "beispiel-v1.0.0/__init__.py": b"# tanz",
                "beispiel-v1.0.0/hacs.json": b'["liste", "ist", "kein", "objekt"]',
            }
        )
        with pytest.raises(InstallationsFehler, match="kein Objekt"):
            _installiere_sync(archiv, "integration", "bienentanz", tmp_path)
        assert not (tmp_path / "custom_components").exists()

    def test_untauglicher_typ_bleibt_fehler_ohne_nebenwirkung(self, tmp_path: Path):
        """hacs.json als Liste PLUS Kategorie theme: der Fehler bleibt
        derselbe Klartext (kein Sturz im except)."""
        archiv = _zip(
            {
                "wupp/hacs.json": b"[1, 2, 3]",
                "wupp/theme.yaml": b"farbe",
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "theme", "wupp", tmp_path)


class TestFilenameMitAusbruch:
    """Der Zielname aus der hacs.json faengt die Installation, nicht erst
    das Entpacken (Issue #18)."""

    def test_absoluter_zielname_wird_abgelehnt(self, tmp_path: Path):
        archiv = _zip(
            {
                "beispiel-v1.0.0/manifest.json": _manifest("bienentanz"),
                "beispiel-v1.0.0/custom_components/bienentanz/__init__.py": b"# tanz",
                "beispiel-v1.0.0/hacs.json": b'{"filename": "/tmp/x/e.txt"}',
            }
        )
        with pytest.raises(InstallationsFehler):
            _installiere_sync(archiv, "integration", "bienentanz", tmp_path)
        assert not (tmp_path / "custom_components").exists()

    def test_kopierplan_ausbruch_erreicht_kein_dateisystem(self, tmp_path: Path):
        """Selbst wenn eine Zuordnung mit Ausbruch bis zum Kern kaeme:
        das Schreiben wehrt ab, nichts entsteht (das zweite Netz)."""
        from haigs.core.entpacken import PfadAusbruch, entpacke

        with pytest.raises(PfadAusbruch):
            entpacke(
                _zip({"gut.txt": b"x"}),
                tmp_path / "staging" / "probe",
                nur={"gut.txt": "../draussen.txt"},
            )


# ------------------ Geteilte Wurzeln (Befund #19: theme & python_script)


class TestFlacheKategorien:
    """themes/ und python_scripts/ gehoeren ALLEN Installationen -- die
    Wurzel darf nie getauscht werden (Issue #19)."""

    def test_zwei_themes_nebeneinander(self, tmp_path: Path):
        """Das Ticket: zwei Themes nacheinander installieren -- beide
        muessen vorhanden sein. Vor der Heilung fraß die zweite
        Installation die erste (Wurzeltausch)."""
        hell = _zip(
            {"blume-v1/hell.yaml": b"hell", "blume-v1/hacs.json": b'{"name": "Blume"}'}
        )
        nacht = _zip(
            {
                "nacht-v1/dunkel.yaml": b"dunkel",
                "nacht-v1/hacs.json": b'{"name": "Nacht"}',
            }
        )

        weg_hell = _installiere_sync(hell, "theme", "blume", tmp_path)
        weg_nacht = _installiere_sync(nacht, "theme", "nacht", tmp_path)

        assert weg_hell.pfad == PurePosixPath("themes")
        assert weg_hell.dateien == ("hell.yaml",)
        assert weg_nacht.dateien == ("dunkel.yaml",)
        assert (tmp_path / "themes" / "hell.yaml").read_bytes() == b"hell"
        assert (tmp_path / "themes" / "dunkel.yaml").read_bytes() == b"dunkel"
        # Die Beschreibung der Quelle gehoert nicht in die geteilte Wurzel:
        assert not (tmp_path / "themes" / "hacs.json").exists()

    def test_deinstallation_nimmt_nur_die_eigenen_dateien(self, tmp_path: Path):
        """Das Ticket: eines deinstallieren -- nur dessen Dateien
        verschwinden, Fremddateien und das andere Theme bleiben."""
        hell = _zip({"blume-v1/hell.yaml": b"hell"})
        nacht = _zip({"nacht-v1/dunkel.yaml": b"dunkel"})
        _installiere_sync(hell, "theme", "blume", tmp_path)
        _installiere_sync(nacht, "theme", "nacht", tmp_path)
        hand_pflege = tmp_path / "themes" / "fremd.yaml"
        hand_pflege.write_bytes(b"hand")

        _deinstalliere_sync("themes", tmp_path, dateien=("hell.yaml",))

        assert not (tmp_path / "themes" / "hell.yaml").exists()
        assert (tmp_path / "themes" / "dunkel.yaml").exists()
        assert hand_pflege.read_bytes() == b"hand"
        assert (tmp_path / "themes").is_dir()

    def test_blanke_wurzel_ohne_dateiliste_wird_abgewiesen(self, tmp_path: Path):
        """Alt-Installationen (vor der Heilung) tragen nur den Pfad
        'themes' -- die Deinstallation darf die geteilte Wurzel NICHT
        als Ordner entfernen. Klartext statt Datenverlust."""
        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "liebling.yaml").write_bytes(b"bleib")

        with pytest.raises(InstallationsFehler, match="Wurzel"):
            _deinstalliere_sync("themes", tmp_path)

        assert (themen / "liebling.yaml").read_bytes() == b"bleib"

    def test_update_entsorgt_alte_dateien_die_wegfallen(self, tmp_path: Path):
        """Eine Datei, die in der neuen Version nicht mehr vorkommt,
        wird entfernt -- sonst bleiben Leichen bei Umbenennungen."""
        alt = _zip({"blume-v1/a.yaml": b"alt", "blume-v1/b.yaml": b"b"})
        neu = _zip({"blume-v2/a.yaml": b"neu"})
        _installiere_sync(alt, "theme", "blume", tmp_path)

        ergebnis = _installiere_sync(
            neu, "theme", "blume", tmp_path, fruehere_dateien=("a.yaml", "b.yaml")
        )

        assert ergebnis.dateien == ("a.yaml",)
        assert (tmp_path / "themes" / "a.yaml").read_bytes() == b"neu"
        assert not (tmp_path / "themes" / "b.yaml").exists()

    def test_fremddatei_wird_nicht_ueberschrieben(self, tmp_path: Path):
        """Eine schon liegende Datei, die nicht zur eigenen (alten)
        Installation gehoert, ist eine Kollision -- Abweisung mit
        Klartext statt stiller Ueberschreibung (Datenverlust)."""
        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "fremd.yaml").write_bytes(b"hand")
        archiv = _zip({"blume-v1/fremd.yaml": b"verdeckt"})

        with pytest.raises(InstallationsFehler, match="fremd.yaml"):
            _installiere_sync(archiv, "theme", "blume", tmp_path)

        assert (themen / "fremd.yaml").read_bytes() == b"hand"

    def test_eigene_alte_datei_darf_erneuert_werden(self, tmp_path: Path):
        """Update desselben Repo: die eigene Datei wird ersetzt -- das
        ist der Normalfall, keine Kollision."""
        alt = _zip({"blume-v1/a.yaml": b"alt"})
        neu = _zip({"blume-v2/a.yaml": b"neu"})
        _installiere_sync(alt, "theme", "blume", tmp_path)

        _installiere_sync(neu, "theme", "blume", tmp_path, fruehere_dateien=("a.yaml",))

        assert (tmp_path / "themes" / "a.yaml").read_bytes() == b"neu"

    def test_python_scripts_genauso(self, tmp_path: Path):
        """Die zweite flache Kategorie kennt dieselbe Heilung."""
        erst = _zip({"erst-v1/x.py": b"x"})
        zweit = _zip({"zweit-v1/y.py": b"y"})
        weg = _installiere_sync(erst, "python_script", "erst", tmp_path)
        _installiere_sync(zweit, "python_script", "zweit", tmp_path)

        assert weg.pfad == PurePosixPath("python_scripts")
        assert (tmp_path / "python_scripts" / "x.py").exists()
        assert (tmp_path / "python_scripts" / "y.py").exists()

        _deinstalliere_sync("python_scripts", tmp_path, dateien=("y.py",))
        assert not (tmp_path / "python_scripts" / "y.py").exists()
        assert (tmp_path / "python_scripts" / "x.py").exists()

    def test_deinstallation_mit_ausbrechendem_dateinamen_wird_abgewiesen(
        self, tmp_path: Path
    ):
        """Die Ablage ist eine Datei -- die Dateiliste ist Eingabe,
        die wird geprueft, nicht geglaubt (wie der Pfad selbst)."""
        sicher = tmp_path / "wichtig.txt"
        sicher.write_bytes(b"bleib")
        with pytest.raises(InstallationsFehler):
            _deinstalliere_sync("themes", tmp_path, dateien=("../wichtig.txt",))
        assert sicher.read_bytes() == b"bleib"

    def test_unterordner_im_flachen_ziel(self, tmp_path: Path):
        """Themes duerfen Unterordner tragen -- sie entstehen in der
        Wurzel, und die Deinstallation raeumt sie leer mit weg."""
        archiv = _zip({"blume-v1/gruppe/a.yaml": b"a"})
        weg = _installiere_sync(archiv, "theme", "blume", tmp_path)

        assert weg.dateien == ("gruppe/a.yaml",)
        assert (tmp_path / "themes" / "gruppe" / "a.yaml").read_bytes() == b"a"

        _deinstalliere_sync("themes", tmp_path, dateien=("gruppe/a.yaml",))
        assert not (tmp_path / "themes" / "gruppe" / "a.yaml").exists()
        assert not (tmp_path / "themes" / "gruppe").exists()
        assert (tmp_path / "themes").is_dir()

    def test_lager_wird_geraeumt(self, tmp_path: Path):
        """Das Zwischenlager traegt keine Reste der flachen Wege."""
        archiv = _zip({"blume-v1/a.yaml": b"a"})
        _installiere_sync(archiv, "theme", "blume", tmp_path)
        lager = tmp_path / ".haigs_zwischenlager"
        assert not list(lager.glob("themes.*"))


# ----- Nachbesserung nach claudes Review zu !50: die drei offenen Faelle


class TestKollisionVorab:
    """Befund 1: Kollisionen werden geprueft, BEVOR das erste
    os.replace laeuft -- und ein Dateisystemfehler mittendrin
    protokolliert sein Bruchstueck, damit der zweite Versuch nicht an
    den eigenen Resten scheitert (die Deinstallation ebenso wenig)."""

    def test_kollision_hinterlaesst_nichts_halbes(self, tmp_path: Path):
        """Archiv mit a.yaml und zz.yaml, fremde zz.yaml liegt schon:
        die Abweisung kommt VOR dem ersten Verschieben -- a.yaml wird
        nicht mehr hingelegt (vorher blieb es als Sperre liegen)."""
        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "zz.yaml").write_bytes(b"hand")
        archiv = _zip({"blume-v1/a.yaml": b"a", "blume-v1/zz.yaml": b"zz"})

        with pytest.raises(InstallationsFehler, match="zz.yaml"):
            _installiere_sync(archiv, "theme", "blume", tmp_path)

        assert not (themen / "a.yaml").exists()
        assert (themen / "zz.yaml").read_bytes() == b"hand"

    def test_bruchstueck_nach_dateisystemfehler(self, tmp_path: Path, monkeypatch):
        """Das Dateisystem versagt mittendrin: was schon geschrieben
        wurde, reist in der Ausnahme (pfad und dateien) -- der zweite
        Versuch mit dem Bruchstueck als fruehere Liste laeuft durch."""
        archiv = _zip({"blume-v1/a.yaml": b"a", "blume-v1/b.yaml": b"b"})
        echt = os.replace
        zaehler = {"n": 0}

        def fehlbar(quelle, senke):
            zaehler["n"] += 1
            if zaehler["n"] == 2:
                raise OSError("Dateisystem versagt")
            return echt(quelle, senke)

        monkeypatch.setattr(os, "replace", fehlbar)
        with pytest.raises(InstallationsFehler) as befund:
            _installiere_sync(archiv, "theme", "blume", tmp_path)
        bruch = befund.value
        assert bruch.dateien == ("a.yaml",)
        assert str(bruch.pfad) == "themes"
        monkeypatch.undo()

        ergebnis = _installiere_sync(
            archiv, "theme", "blume", tmp_path, fruehere_dateien=bruch.dateien
        )
        assert ergebnis.dateien == ("a.yaml", "b.yaml")
        assert (tmp_path / "themes" / "a.yaml").read_bytes() == b"a"
        assert (tmp_path / "themes" / "b.yaml").read_bytes() == b"b"


class TestAltbestandOhneListe:
    """Befund 2: mit 0.6.3 installiert -- der Stand verzeichnet nur die
    Wurzel, keine Dateiliste. Update und Deinstallation brauchen einen
    Weg, sonst ist der Altbestand eine Sackgasse."""

    def test_update_erbt_die_namen(self, tmp_path: Path):
        """Das Update eines Altbestands ersetzt die gleichnamigen
        Dateien -- der Nachfolger eines Repo, das 0.6.3 ohne Protokoll
        in die Wurzel schrieb. Inhaltsgleichheit allein wuerde genau
        den Normalfall sperren: geaenderte Dateien sind der Grund des
        Updates."""
        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "liebling.yaml").write_bytes(b"alt")
        archiv = _zip({"blume-v1/liebling.yaml": b"neu"})

        ergebnis = _installiere_sync(archiv, "theme", "blume", tmp_path, altbestand=True)

        assert ergebnis.dateien == ("liebling.yaml",)
        assert (themen / "liebling.yaml").read_bytes() == b"neu"

    def test_altbestand_fasst_fremde_namen_nicht_an(self, tmp_path: Path):
        """Erben heisst: nur die Namen, die das neue Archiv BRINGT --
        andere Dateien in der Wurzel bleiben unberuehrt."""
        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "fremd.yaml").write_bytes(b"hand")
        archiv = _zip({"blume-v1/a.yaml": b"a"})

        _installiere_sync(archiv, "theme", "blume", tmp_path, altbestand=True)

        assert (themen / "fremd.yaml").read_bytes() == b"hand"

    def test_rekonstruktion_beanprucht_nur_inhaltsgleiche(self, tmp_path: Path):
        """Fuer die Deinstallation wird die Liste aus dem Archiv der
        INSTALLIERTEN Version abgeleitet: nur was inhaltsgleich daliegt,
        gilt als eigenes -- Veraendertes und Fremdes bleibt."""
        from haigs.installation import _beanspruche_altbestand

        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "liebling.yaml").write_bytes(b"hell")
        (themen / "veraendert.yaml").write_bytes(b"handgeschrieben")
        (themen / "fremd.yaml").write_bytes(b"hand")
        archiv = _zip(
            {
                "blume-v1/liebling.yaml": b"hell",
                "blume-v1/veraendert.yaml": b"original",
                "blume-v1/hacs.json": b'{"name": "Blume"}',
            }
        )

        beansprucht = _beanspruche_altbestand(archiv, "theme", "blume", tmp_path)

        assert beansprucht == ("liebling.yaml",)

    def test_rekonstruktion_und_entfernung_zusammen(self, tmp_path: Path):
        """Der ganze Weg: Liste rekonstruieren, dann deinstallieren --
        die Wurzel bleibt, Fremdes bleibt, das Eigene geht."""
        from haigs.installation import _beanspruche_altbestand

        themen = tmp_path / "themes"
        themen.mkdir()
        (themen / "liebling.yaml").write_bytes(b"hell")
        (themen / "fremd.yaml").write_bytes(b"hand")
        archiv = _zip({"blume-v1/liebling.yaml": b"hell"})

        dateien = _beanspruche_altbestand(archiv, "theme", "blume", tmp_path)
        _deinstalliere_sync("themes", tmp_path, dateien=dateien)

        assert not (themen / "liebling.yaml").exists()
        assert (themen / "fremd.yaml").read_bytes() == b"hand"
        assert themen.is_dir()
