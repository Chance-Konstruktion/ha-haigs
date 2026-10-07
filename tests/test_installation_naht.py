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

        assert weg == PurePosixPath("custom_components/bienentanz")
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

        assert weg == PurePosixPath("custom_components/bienentanz")
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

        assert weg == PurePosixPath("custom_components/vistapool")
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

        assert weg == PurePosixPath("custom_components/powerline")
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
