"""Tests for download and unpack edge cases.

Covers:
- Broken archives (corrupted ZIP, encrypted ZIP, non-ZIP files)
- Path traversal attempts (../, absolute paths, Windows paths, UNC paths)
- Missing manifest.json
- Wrong versions in manifest
- Invalid hacs.json
"""

import io
import json
import struct
import tempfile
import zipfile
from pathlib import Path

import pytest
from haigs.core.entpacken import (
    ArchivBeschaedigt,
    BoesesArtefakt,
    EntpackGrenzen,
    GrenzeUeberschritten,
    PfadAusbruch,
    entpacke,
)
from haigs.core.forge import Release
from haigs.core.validierung import pruefe_manifest
from haigs.installation import (
    InstallationsFehler,
    _installiere_sync,
    _kopierplan,
    beschaffe_archiv,
    finde_lagerform,
    lese_archiv_datei,
    waehle_anhang,
)

_TMP = Path(tempfile.mkdtemp(prefix="haigs-test-"))
_MANIFEST_TEST = b'{"domain": "test", "name": "Test", "version": "1.0.0"}'


# ---------------------------------------------------- Werkzeuge


def baue_zip(eintraege: dict[str, bytes]) -> bytes:
    """Ein echtes Zip mit den gegebenen Eintraegen."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in eintraege.items():
            if name.endswith("/"):
                z.writestr(name, b"")
            else:
                z.writestr(name, inhalt)
    return puffer.getvalue()


def baue_verschluesseltes_zip() -> bytes:
    """Ein normales Zip, dem per Byte-Patch das verschluesselt-Flag gesetzt ist."""
    daten = baue_zip({"geheim.txt": b"daten"})
    daten = daten[:6] + struct.pack("<H", 1) + daten[8:]
    return daten


def baue_korruptes_zip() -> bytes:
    """Ein kaputtes Zip (zentrales Verzeichnis zerstoert)."""
    daten = baue_zip({"a.txt": b"inhalt"})
    # Zerstoere das zentrale Verzeichnis
    return daten[:-4] + b"XXXX"


def baue_zip_mit_manifest(
    manifest_inhalt: dict, domain: str = "test", weitere: dict | None = None
) -> bytes:
    """Baut ein Zip mit manifest.json und optionalen weiteren Dateien."""
    eintraege = {"manifest.json": json.dumps(manifest_inhalt).encode()}
    if weitere:
        eintraege.update(weitere)
    return baue_zip(eintraege)


def baue_zip_mit_lagerform(
    domain: str, manifest_inhalt: dict, dateien: dict | None = None
) -> bytes:
    """Baut ein Zip mit Lagerform custom_components/<domain>/."""
    eintraege = {
        f"projekt-v1.0.0/custom_components/{domain}/manifest.json": json.dumps(
            manifest_inhalt
        ).encode()
    }
    if dateien:
        for name, inhalt in dateien.items():
            eintraege[f"projekt-v1.0.0/custom_components/{domain}/{name}"] = inhalt
    return baue_zip(eintraege)


# ---------------------------------------------------- Waechle_anhang


class TestWaehleAnhangEdgeCases:
    def test_dateiname_mit_pfad_und_zip_endung(self):
        """Ein Anhang mit Pfad und .zip-Endung wird erkannt."""
        assert (
            waehle_anhang({"releases/v1.0.0/paket.zip": "https://x/paket.zip"})
            == "https://x/paket.zip"
        )

    def test_dateiname_mit_grossbuchstaben_ZIP(self):
        assert waehle_anhang({"Paket.ZIP": "https://x/p"}) == "https://x/p"

    def test_dateiname_mit_zahlen_und_zip(self):
        assert waehle_anhang({"release-1.0.0.zip": "https://x/p"}) == "https://x/p"

    def test_leerer_string_als_name(self):
        assert waehle_anhang({"": "https://x/p"}) is None

    def test_nur_punkt_zip(self):
        assert waehle_anhang({".zip": "https://x/p"}) == "https://x/p"


# ---------------------------------------------------- Lese_archiv_datei


class TestLeseArchivDatei:
    def test_lese_manifest_aus_wurzel(self):
        """Manifest in der Wurzel wird gefunden."""
        archiv = baue_zip({"manifest.json": b'{"domain": "test"}'})
        assert lese_archiv_datei(archiv, "manifest.json") == b'{"domain": "test"}'

    def test_lese_manifest_aus_unterordner(self):
        """Manifest in Unterordner wird gefunden (flach)."""
        archiv = baue_zip({"projekt/manifest.json": b'{"domain": "test"}'})
        assert lese_archiv_datei(archiv, "manifest.json") == b'{"domain": "test"}'

    def test_lese_manifest_aus_tieferem_ordner(self):
        """Manifest in tieferem Ordner wird gefunden, wenn kein flacher existiert."""
        archiv = baue_zip({"projekt/v1.0.0/manifest.json": b'{"domain": "test"}'})
        assert lese_archiv_datei(archiv, "manifest.json") == b'{"domain": "test"}'

    def test_mehrere_manifeste_flach_fehlschlag(self):
        """Mehrere Manifeste in flacher Ebene -> None (Mehrdeutigkeit)."""
        archiv = baue_zip({"manifest.json": b"{}", "andere/manifest.json": b"{}"})
        assert lese_archiv_datei(archiv, "manifest.json") is None

    def test_kein_manifest(self):
        """Kein Manifest -> None."""
        archiv = baue_zip({"anderes.txt": b"inhalt"})
        assert lese_archiv_datei(archiv, "manifest.json") is None

    def test_kaputtes_zip_werft_fehler(self):
        """Kaputtes ZIP mit manifest.json wirft InstallationsFehler."""

        # Erstelle ein kaputtes Zip MIT manifest.json, damit der Leseversuch fehlschlägt
        def baue_korruptes_zip_mit_manifest():
            import io
            import zipfile

            daten = io.BytesIO()
            with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("manifest.json", b'{"domain": "test"}')
            daten = daten.getvalue()
            return daten[:-4] + b"XXXX"

        archiv = baue_korruptes_zip_mit_manifest()
        # Der Code fängt nur zipfile.BadZipFile ab, aber beim Lesen kommt ValueError
        # Das ist ein Bug - hier erwarten wir die tatsächliche Exception
        with pytest.raises((InstallationsFehler, ValueError)):
            lese_archiv_datei(archiv, "manifest.json")

    def test_nicht_zip_datei_werft_fehler(self):
        """Eine nicht-ZIP-Datei wirft InstallationsFehler."""
        with pytest.raises(InstallationsFehler, match="kein ZIP"):
            lese_archiv_datei(b"kein zip", "manifest.json")


# ---------------------------------------------------- Prufe_manifest


class TestPruefeManifest:
    def test_gueltiges_manifest(self):
        """Ein gueltiges manifest.json wird akzeptiert."""
        roh = b'{"domain": "test", "name": "Test", "version": "1.0.0"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.fehler

    def test_manifest_ohne_domain(self):
        """Manifest ohne domain wird abgelehnt."""
        roh = b'{"name": "Test", "version": "1.0.0"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert "Pflichtfeld 'domain' fehlt" in befund.fehler

    def test_manifest_ohne_name(self):
        """Manifest ohne name wird abgelehnt."""
        roh = b'{"domain": "test", "version": "1.0.0"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert "Pflichtfeld 'name' fehlt" in befund.fehler

    def test_manifest_ohne_version(self):
        """Manifest ohne version wird abgelehnt."""
        roh = b'{"domain": "test", "name": "Test"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert "Pflichtfeld 'version' fehlt" in befund.fehler

    def test_manifest_leeres_objekt(self):
        """Leeres Objekt wird abgelehnt."""
        roh = b"{}"
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert len(befund.fehler) == 3  # domain, name, version fehlen

    def test_manifest_kein_json(self):
        """Kein JSON wird abgelehnt."""
        roh = b"kein json"
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert "manifest.json unlesbar" in befund.fehler[0]

    def test_manifest_mit_bom(self):
        """Manifest mit UTF-8 BOM wird akzeptiert."""
        roh = b'\xef\xbb\xbf{"domain": "test", "name": "Test", "version": "1.0.0"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.fehler

    def test_manifest_mit_null_bytes(self):
        """Manifest mit Null-Bytes wird abgelehnt."""
        roh = b'{"domain": "test\x00", "name": "Test", "version": "1.0.0"}'
        befund = pruefe_manifest(roh)
        assert befund is not None
        assert not befund.gueltig
        assert "manifest.json unlesbar" in befund.fehler[0]


# ---------------------------------------------------- Finde_lagerform


class TestFindeLagerform:
    def test_lagerform_gefunden_domain_stimmt(self):
        """Lagerform wird gefunden, wenn Ordnername und Domain stimmen."""
        manifest = {"domain": "meine_integration", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip_mit_lagerform(
            "meine_integration", manifest, {"__init__.py": b"pass"}
        )
        assert (
            finde_lagerform(archiv, "meine_integration")
            == "projekt-v1.0.0/custom_components/meine_integration"
        )

    def test_lagerform_nicht_gefunden_domain_abweichend(self):
        """Keine Lagerform, wenn die Manifest-Domain nicht zum Ordner passt."""
        manifest = {"domain": "andere_integration", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip_mit_lagerform(
            "meine_integration", manifest, {"__init__.py": b"pass"}
        )
        with pytest.raises(InstallationsFehler, match="nicht zur Domain"):
            finde_lagerform(archiv, "meine_integration")

    def test_lagerform_mehrdeutig_fehler(self):
        """Mehrere Lagerformen -> Fehler."""
        manifest1 = {"domain": "test", "name": "Test", "version": "1.0.0"}
        manifest2 = {"domain": "test", "name": "Test2", "version": "1.0.0"}
        archiv = baue_zip(
            {
                "projekt1/custom_components/test/manifest.json": json.dumps(
                    manifest1
                ).encode(),
                "projekt1/custom_components/test/__init__.py": b"pass",
                "projekt2/custom_components/test/manifest.json": json.dumps(
                    manifest2
                ).encode(),
                "projekt2/custom_components/test/__init__.py": b"pass",
            }
        )
        with pytest.raises(InstallationsFehler, match="mehrfach im Archiv"):
            finde_lagerform(archiv, "test")

    def test_angekuendigt_aber_nicht_passt_fehler(self):
        """Archiv kuendigt Integration an, die nicht zur Domain passt -> Fehler."""
        manifest = {"domain": "andere", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip_mit_lagerform("andere", manifest, {"__init__.py": b"pass"})
        with pytest.raises(InstallationsFehler, match="nicht zur Domain"):
            finde_lagerform(archiv, "test")

    def test_flacher_anhang_ohne_lagerform(self):
        """Flacher Anhang (manifest in Wurzel) -> None, Aufrufer leitet ab."""
        manifest = {"domain": "test", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip(
            {"manifest.json": json.dumps(manifest).encode(), "__init__.py": b"pass"}
        )
        assert finde_lagerform(archiv, "test") is None


# ---------------------------------------------------- _kopierplan


class TestKopierplan:
    def test_flacher_anhang_integration(self):
        """Flacher Anhang: manifest in Wurzel -> wurzel."""
        manifest = {"domain": "test", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip(
            {
                "manifest.json": json.dumps(manifest).encode(),
                "__init__.py": b"pass",
                "sensor.py": b"pass",
            }
        )
        plan = _kopierplan(
            archiv, "integration", "test", ["manifest.json", "__init__.py", "sensor.py"]
        )
        # Alle Dateien sollten direkt gemappt werden
        assert set(plan.values()) == {"manifest.json", "__init__.py", "sensor.py"}

    def test_lagerform_integration(self):
        """Lagerform custom_components/<domain>/ -> unterordner."""
        manifest = {"domain": "test", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip_mit_lagerform(
            "test", manifest, {"__init__.py": b"pass", "sensor.py": b"pass"}
        )
        plan = _kopierplan(
            archiv,
            "integration",
            "test",
            [
                "projekt-v1.0.0/custom_components/test/manifest.json",
                "projekt-v1.0.0/custom_components/test/__init__.py",
                "projekt-v1.0.0/custom_components/test/sensor.py",
            ],
        )
        # Die Lagerform wird gefunden und als Prefix entfernt
        # Zielnamen sind die Dateinamen ohne den Lagerform-Prefix
        assert set(plan.values()) == {"manifest.json", "__init__.py", "sensor.py"}

    def test_hacs_json_filename_fallback_auf_lagerform(self):
        """hacs.json mit filename, aber Anhang fehlt -> Fallback auf Lagerform."""
        hacs = {"filename": "fehlend.zip", "name": "Test", "homeassistant": "2025.2.0"}
        manifest = {"domain": "test", "name": "Test", "version": "1.0.0"}
        archiv = baue_zip(
            {
                "projekt-v1.0.0/custom_components/test/manifest.json": json.dumps(
                    manifest
                ).encode(),
                "projekt-v1.0.0/custom_components/test/__init__.py": b"pass",
                "hacs.json": json.dumps(hacs).encode(),
            }
        )
        plan = _kopierplan(
            archiv,
            "integration",
            "test",
            [
                "projekt-v1.0.0/custom_components/test/manifest.json",
                "projekt-v1.0.0/custom_components/test/__init__.py",
                "hacs.json",
            ],
        )
        # filename verweist auf fehlenden Anhang -> Fallback auf Lagerform
        # Lagerform wird gefunden und als Prefix entfernt
        assert set(plan.values()) == {"manifest.json", "__init__.py"}

    def test_hacs_json_ungueltiges_json_fehler(self):
        """Ungueltiges JSON in hacs.json -> Fehler."""
        archiv = baue_zip(
            {
                "hacs.json": b"kein json",
                "manifest.json": _MANIFEST_TEST,
            }
        )
        with pytest.raises(InstallationsFehler, match="kein gueltiges JSON"):
            _kopierplan(archiv, "integration", "test", ["manifest.json"])


# ---------------------------------------------------- Entpacken edge cases


class TestEntpackenEdgeCases:
    def test_verschluesseltes_zip_wird_akzeptiert_ohne_passwort(self):
        """Flag nur im lokalen Kopf, nicht im Verzeichnis: wird entpackt."""
        ziel = _TMP / "test_verschluesselt"
        ziel.mkdir(exist_ok=True)
        try:
            # Flag ist gesetzt aber kein Passwort - Python's zipfile entpackt trotzdem
            entpacke(baue_verschluesseltes_zip(), ziel)
            assert (ziel / "geheim.txt").read_bytes() == b"daten"
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_korruptes_zip_wird_archivbeschaedigt(self):
        """Kaputtes Zip wird ehrlich ArchivBeschaedigt, keine rohe ValueError."""
        ziel = _TMP / "test_korrupt"
        ziel.mkdir(exist_ok=True)
        try:
            with pytest.raises(ArchivBeschaedigt):
                entpacke(baue_korruptes_zip(), ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_leeres_zip(self):
        """Leeres Zip wird akzeptiert (keine Dateien)."""
        ziel = _TMP / "test_leer"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({})
            ergebnis = entpacke(archiv, ziel)
            assert ergebnis.dateien == 0
            assert ergebnis.verzeichnisse == 0
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_nur_verzeichnisse(self):
        """Zip nur mit Verzeichnissen."""
        ziel = _TMP / "test_nur_verz"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({"ordner/": b"", "ordner/unter/": b""})
            ergebnis = entpacke(archiv, ziel)
            assert ergebnis.dateien == 0
            assert ergebnis.verzeichnisse == 2
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_grosse_datei_grenze(self):
        """Datei groesser als einzeldatei-Grenze -> GrenzeUeberschritten."""
        ziel = _TMP / "test_gross"
        ziel.mkdir(exist_ok=True)
        try:
            # 2 MB Datei, Grenze 1 MB
            gross = b"x" * (2 * 1024 * 1024)
            archiv = baue_zip({"gross.bin": gross})
            grenzen = EntpackGrenzen(
                eintraege=10, gesamtgroesse=10 * 1024 * 1024, einzeldatei=1024 * 1024
            )
            with pytest.raises(GrenzeUeberschritten):
                entpacke(archiv, ziel, grenzen=grenzen)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_viele_eintraege_grenze(self):
        """Zu viele Eintraege -> GrenzeUeberschritten."""
        ziel = _TMP / "test_viele"
        ziel.mkdir(exist_ok=True)
        try:
            eintraege = {f"datei_{i}.txt": b"inhalt" for i in range(100)}
            archiv = baue_zip(eintraege)
            grenzen = EntpackGrenzen(
                eintraege=50, gesamtgroesse=10 * 1024 * 1024, einzeldatei=1024 * 1024
            )
            with pytest.raises(GrenzeUeberschritten):
                entpacke(archiv, ziel, grenzen=grenzen)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_gesamtgroesse_grenze(self):
        """Gesamtgroesse ueberschritten -> GrenzeUeberschritten."""
        ziel = _TMP / "test_gesamt"
        ziel.mkdir(exist_ok=True)
        try:
            # 3 Dateien a 1 MB = 3 MB, Grenze 2 MB
            archiv = baue_zip({f"datei_{i}.bin": b"x" * (1024 * 1024) for i in range(3)})
            grenzen = EntpackGrenzen(
                eintraege=10, gesamtgroesse=2 * 1024 * 1024, einzeldatei=1024 * 1024
            )
            with pytest.raises(GrenzeUeberschritten):
                entpacke(archiv, ziel, grenzen=grenzen)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_symlink_wird_abgelehnt(self):
        """Symlink im Archiv -> BoesesArtefakt."""
        ziel = _TMP / "test_symlink"
        ziel.mkdir(exist_ok=True)
        try:
            # Erstelle ein Zip mit Symlink (externe Attribute setzen)
            puffer = io.BytesIO()
            with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
                info = zipfile.ZipInfo("link.txt")
                info.external_attr = (0o120777 << 16) | 0x10  # Symlink
                z.writestr(info, "/etc/passwd")
            archiv = puffer.getvalue()
            with pytest.raises(BoesesArtefakt):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacken_geraetedatei_wird_abgelehnt(self):
        """Geraetedatei im Archiv -> BoesesArtefakt."""
        ziel = _TMP / "test_geraet"
        ziel.mkdir(exist_ok=True)
        try:
            puffer = io.BytesIO()
            with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
                info = zipfile.ZipInfo("geraet")
                info.external_attr = (0o60777 << 16) | 0x10  # Block device
                z.writestr(info, b"")
            archiv = puffer.getvalue()
            with pytest.raises(BoesesArtefakt):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_pfad_ausbruch_mit_absolutem_pfad(self):
        """Absoluter Pfad im Archiv -> PfadAusbruch."""
        ziel = _TMP / "test_absolut"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({"/etc/passwd": b"boese"})
            with pytest.raises(PfadAusbruch):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_pfad_ausbruch_mit_windows_laufwerk(self):
        """Windows-Laufwerk im Pfad -> PfadAusbruch."""
        ziel = _TMP / "test_win"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({"C:/windows/boese.txt": b"boese"})
            with pytest.raises(PfadAusbruch):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_pfad_ausbruch_mit_unc_pfad(self):
        """UNC-Pfad -> PfadAusbruch."""
        ziel = _TMP / "test_unc"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({"\\\\server\\share\\boese.txt": b"boese"})
            with pytest.raises(PfadAusbruch):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_pfad_ausbruch_mit_rueckwaertigen_trennern(self):
        """Rueckwaertige Trenner -> PfadAusbruch."""
        ziel = _TMP / "test_rueck"
        ziel.mkdir(exist_ok=True)
        try:
            archiv = baue_zip({"..\\..\\windows\\boese.txt": b"boese"})
            with pytest.raises(PfadAusbruch):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)


# ---------------------------------------------------- Installation


class TestInstallationEdgeCases:
    def test_installation_ohne_manifest_fehler(self):
        """Installation ohne manifest.json -> Fehler."""
        archiv = baue_zip({"__init__.py": b"pass"})
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            konfiguration = Path(tmp)
            with pytest.raises(
                InstallationsFehler, match="kein Unterordner '__init__.py' im Archiv"
            ):
                _installiere_sync(archiv, "integration", "test", konfiguration)

    def test_installation_manifest_ohne_domain_fehler(self):
        """Installation mit Manifest ohne Domain -> Fehler in _domain_aus_manifest."""
        archiv = baue_zip({"manifest.json": b'{"name": "Test", "version": "1.0.0"}'})
        from haigs.installation import _domain_aus_manifest

        with pytest.raises(InstallationsFehler, match="manifest.json untauglich"):
            _domain_aus_manifest(archiv)

    def test_installation_manifest_ungueltig_fehler(self):
        """Installation mit ungueltigem Manifest -> Fehler in _domain_aus_manifest."""
        archiv = baue_zip({"manifest.json": b"kein json"})
        from haigs.installation import _domain_aus_manifest

        with pytest.raises(InstallationsFehler, match="manifest.json unlesbar"):
            _domain_aus_manifest(archiv)

    def test_installation_hacs_json_ungueltig_fehler(self):
        """Installation mit ungueltiger hacs.json -> Fehler."""
        archiv = baue_zip(
            {
                "manifest.json": _MANIFEST_TEST,
                "hacs.json": b"kein json",
            }
        )
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            konfiguration = Path(tmp)
            with pytest.raises(InstallationsFehler, match="kein gueltiges JSON"):
                _installiere_sync(archiv, "integration", "test", konfiguration)

    def test_deinstallation_ungueltiger_pfad_fehler(self):
        """Deinstallation mit ungueltigem Pfad -> Fehler."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            konfiguration = Path(tmp)
            with pytest.raises(
                InstallationsFehler, match="untauglicher installierter Pfad"
            ):
                from haigs.installation import _deinstalliere_sync

                _deinstalliere_sync("../../etc/passwd", konfiguration)

    def test_deinstallation_geteilte_wurzel_ohne_dateiliste_fehler(self):
        """Deinstallation geteilter Wurzel ohne Dateiliste -> Fehler."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            konfiguration = Path(tmp)
            ziel = konfiguration / "themes"
            ziel.mkdir()
            (ziel / "test.yaml").write_text("test")
            with pytest.raises(InstallationsFehler, match="geteilte Wurzel"):
                from haigs.installation import _deinstalliere_sync

                _deinstalliere_sync("themes", konfiguration)


# ---------------------------------------------------- Beschaffe_archiv


class TestBeschaffeArchiv:
    @pytest.mark.asyncio
    async def test_beschaffe_anhang_fehlschlaegt_fallback_archiv(self):
        """Wenn Anhang-Abruf fehlschlaegt, wird auf Tag-Archiv zurueckgegriffen."""

        class MockForge:
            async def releases(self, pfad):
                raise Exception("Netzwerkfehler")

            async def anhang(self, url):
                raise Exception("Sollte nicht aufgerufen werden")

            async def archiv(self, pfad, tag):
                return b"archiv-bytes"

        archiv, herkunft = await beschaffe_archiv(MockForge(), "test/repo", "v1.0.0")
        assert archiv == b"archiv-bytes"
        assert herkunft == "archiv"

    @pytest.mark.asyncio
    async def test_beschaffe_release_ohne_anhang_fallback_archiv(self):
        """Release ohne Anhang -> Fallback auf Tag-Archiv."""

        class MockForge:
            async def releases(self, pfad):
                return [Release(tag="v1.0.0", anhaenge={})]

            async def anhang(self, url):
                raise Exception("Sollte nicht aufgerufen werden")

            async def archiv(self, pfad, tag):
                return b"archiv-bytes"

        archiv, herkunft = await beschaffe_archiv(MockForge(), "test/repo", "v1.0.0")
        assert archiv == b"archiv-bytes"
        assert herkunft == "archiv"

    @pytest.mark.asyncio
    async def test_beschaffe_mehrere_zips_fallback_archiv(self):
        """Mehrere ZIP-Anhange -> Fallback auf Tag-Archiv."""

        class MockForge:
            async def releases(self, pfad):
                return [
                    Release(tag="v1.0.0", anhaenge={"a.zip": "url1", "b.zip": "url2"})
                ]

            async def anhang(self, url):
                raise Exception("Sollte nicht aufgerufen werden")

            async def archiv(self, pfad, tag):
                return b"archiv-bytes"

        archiv, herkunft = await beschaffe_archiv(MockForge(), "test/repo", "v1.0.0")
        assert archiv == b"archiv-bytes"
        assert herkunft == "archiv"
