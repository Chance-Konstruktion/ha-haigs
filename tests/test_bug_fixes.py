"""Tests for the three bug fixes - RED before fix, GREEN after."""

import io
import tempfile
import zipfile
from pathlib import Path

import pytest
from haigs.core.entpacken import (
    ArchivBeschaedigt,
    entpacke,
)
from haigs.installation import (
    InstallationsFehler,
    lese_archiv_datei,
)

_TMP = Path(tempfile.mkdtemp(prefix="haigs-test-"))


# ---------------------------------------------------- Werkzeuge


def baue_korruptes_zip_mit_manifest() -> bytes:
    """Ein kaputtes ZIP mit manifest.json - zentrales Verzeichnis zerstoert."""
    daten = io.BytesIO()
    with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", b'{"domain": "test"}')
    daten = daten.getvalue()
    # Zerstoere das zentrale Verzeichnis
    return daten[:-4] + b"XXXX"


def baue_korruptes_zip_mit_eintraegen() -> bytes:
    """Ein kaputtes ZIP mit mehreren Eintraegen."""
    daten = io.BytesIO()
    with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("a.txt", b"inhalt")
        z.writestr("b.txt", b"mehr")
    daten = daten.getvalue()
    # Zerstoere das zentrale Verzeichnis
    return daten[:-4] + b"XXXX"


def _setze_verschluesselungs_flag(daten: bytes) -> bytes:
    """Setzt das Verschluesselungs-Flag (Bit 0) im zentralen Verzeichnis eines ZIP."""
    daten = bytearray(daten)
    # Finde das zentrale Verzeichnis (PK\\x01\\x02)
    for i in range(len(daten) - 4):
        if daten[i : i + 4] == b"PK\x01\x02":
            # Offset 8 im zentralen Verzeichnis-Header: general purpose bit flag
            # (2 Bytes, LE)
            daten[i + 8] |= 0x01
            break
    return bytes(daten)


def baue_verschluesseltes_zip() -> bytes:
    """Ein ZIP mit gesetztem Verschluesselungs-Flag aber ohne echtes Passwort."""
    daten = io.BytesIO()
    with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("geheim.txt", b"daten")
    daten = daten.getvalue()
    return _setze_verschluesselungs_flag(daten)


def baue_zip_mit_verschluesseltem_eintrag() -> bytes:
    """Ein ZIP wo ein Eintrag das Verschluesselungs-Flag hat."""
    return baue_verschluesseltes_zip()


# ---------------------------------------------------- Fix 1: lese_archiv_datei


class TestFix1LeseArchivDatei:
    """Bug 1: lese_archiv_datei fing nur BadZipFile; ValueError bei kaputtem
    ZIP flog durch."""

    def test_lese_archiv_datei_kaputtes_zip_wirft_installationsfehler(self):
        """Kaputtes ZIP mit manifest.json -> InstallationsFehler (nicht ValueError)."""
        archiv = baue_korruptes_zip_mit_manifest()
        with pytest.raises(InstallationsFehler, match="kein ZIP"):
            lese_archiv_datei(archiv, "manifest.json")

    def test_lese_archiv_datei_zlib_error_wirft_installationsfehler(self):
        """ZIP mit zlib-Fehler -> InstallationsFehler."""
        # Erstelle ein ZIP mit zerstoertem zlib-Stream
        daten = io.BytesIO()
        with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("manifest.json", b'{"domain": "test"}')
        daten = daten.getvalue()
        # Korrumpiere die komprimierten Daten
        korrupt = daten[:30] + b"XXXX" + daten[34:]
        with pytest.raises(InstallationsFehler, match="kein ZIP"):
            lese_archiv_datei(korrupt, "manifest.json")


# ---------------------------------------------------- Fix 2: entpacke


class TestFix2Entpacke:
    """Bug 2: entpacke fing nur BadZipFile/LargeZipFile/zlib.error;
    ValueError beim Lesen flog durch."""

    def test_entpacke_kaputtes_zip_wirft_archivbeschaedigt(self):
        """Kaputtes ZIP beim Entpacken -> ArchivBeschaedigt (nicht ValueError)."""
        archiv = baue_korruptes_zip_mit_eintraegen()
        ziel = _TMP / "test_entpacke_kaputt"
        ziel.mkdir(exist_ok=True)
        try:
            with pytest.raises(ArchivBeschaedigt, match="Archiv beim Lesen gescheitert"):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacke_eof_error_wirft_archivbeschaedigt(self):
        """ZIP mit abgeschnittenen Daten (EOFError) -> ArchivBeschaedigt."""
        daten = io.BytesIO()
        with zipfile.ZipFile(daten, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("a.txt", b"inhalt")
        daten = daten.getvalue()
        # Schneide das ZIP ab
        abgeschnitten = daten[: len(daten) // 2]
        ziel = _TMP / "test_entpacke_eof"
        ziel.mkdir(exist_ok=True)
        try:
            with pytest.raises(ArchivBeschaedigt, match="kein lesbares Zip-Archiv"):
                entpacke(abgeschnitten, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)


# ---------------------------------------------------- Fix 3: verschluesselte Eintraege


class TestFix3VerschluesselteEintraege:
    """Kein Bug: verschluesselte Eintraege (flag_bits & 0x1) im zentralen
    Verzeichnis werden schon abgewiesen; die Tests halten das fest."""

    def test_entpacke_verschluesseltes_zip_wirft_archivbeschaedigt(self):
        """ZIP mit globalem Verschluesselungs-Flag -> ArchivBeschaedigt."""
        archiv = baue_verschluesseltes_zip()
        ziel = _TMP / "test_verschluesselt"
        ziel.mkdir(exist_ok=True)
        try:
            with pytest.raises(ArchivBeschaedigt, match="verschluesselt"):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)

    def test_entpacke_eintrag_mit_verschluesselungsflag_wirft_archivbeschaedigt(self):
        """Einzelner Eintrag mit Verschluesselungs-Flag -> ArchivBeschaedigt."""
        archiv = baue_zip_mit_verschluesseltem_eintrag()
        ziel = _TMP / "test_eintrag_verschluesselt"
        ziel.mkdir(exist_ok=True)
        try:
            with pytest.raises(ArchivBeschaedigt, match="verschluesselt"):
                entpacke(archiv, ziel)
        finally:
            import shutil

            shutil.rmtree(ziel, ignore_errors=True)
