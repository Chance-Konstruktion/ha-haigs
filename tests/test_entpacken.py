"""Entpacken: der Pruefstand mit selbst gebauten Zip-Dateien.

Vier boesartige Archive gehoeren zum Abnahmekriterium von #12:
Pfadausbruch ueber ``../``, absoluter Pfad, Symlink auf ``/etc`` und
eine klein gepackte Bombe. Jede muss abgewiesen werden, und zwar
**bevor** etwas geschrieben wurde -- deshalb pruefen diese Faelle
nicht nur die Fehlerart, sondern auch, dass hinterher nichts auf der
Platte liegt.
"""

import io
import struct
import zipfile

import pytest
from haigs.core.entpacken import (
    ArchivBeschaedigt,
    BoesesArtefakt,
    EntpackErgebnis,
    EntpackFehler,
    EntpackGrenzen,
    GrenzeUeberschritten,
    PfadAusbruch,
    Schreibfehler,
    entpacke,
    installiere,
    plane,
)

# ---------------------------------------------------------------- Werkzeuge


def baue_zip(eintraege: dict[str, bytes]) -> bytes:
    """Ein ehrliches Zip: Name zu Inhalt, Schraegstrich am Ende nennt
    ein Verzeichnis."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in eintraege.items():
            if name.endswith("/"):
                info = zipfile.ZipInfo(name)
                info.external_attr = 0o40755 << 16 | 0x10
                z.writestr(info, b"")
            else:
                z.writestr(name, inhalt)
    return puffer.getvalue()


def baue_zip_mit_attribut(name: str, modus: int, inhalt: bytes) -> bytes:
    """Ein Eintrag mit freigewaehlten Unix-Attributen -- fuer Symlinks
    und Geraetedateien, die es in einem ehrlichen Zip nicht gibt."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w") as z:
        info = zipfile.ZipInfo(name)
        info.external_attr = modus << 16
        z.writestr(info, inhalt)
    return puffer.getvalue()


def baue_bombe(bloecke: int = 8) -> bytes:
    """8 MiB Nullen, gepackt unter 10 KiB -- das Bild einer Bombe."""
    nullen = b"\x00" * (1024 * 1024)
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        with z.open("riesig.bin", "w") as f:
            for _ in range(bloecke):
                f.write(nullen)
    return puffer.getvalue()


def luege_groesse(daten: bytes, versprochen: int) -> bytes:
    """Schreibt die unkomprimierte Groesse in lokaler Kopfzeile und
    Zentralverzeichnis um -- die Metadaten versprechen weniger, als die
    Bombe entpackt."""
    wert = struct.pack("<I", versprochen)
    daten = daten[:22] + wert + daten[26:]
    mitte = daten.find(b"PK\x01\x02")
    assert mitte > 0, "Zentralverzeichnis nicht gefunden"
    return daten[: mitte + 24] + wert + daten[mitte + 28 :]


def korrumpiere_daten(daten: bytes) -> bytes:
    """Zerstoert ein Byte mitten in den komprimierten Daten -- die
    Pruefsumme des Eintrags kann danach nicht mehr stimmen."""
    namen_laenge = struct.unpack("<H", daten[26:28])[0]
    extra_laenge = struct.unpack("<H", daten[28:30])[0]
    anfang = 30 + namen_laenge + extra_laenge
    ende = daten.find(b"PK\x01\x02")
    assert ende > anfang, "Zentralverzeichnis vor den Daten?"
    mitte = (anfang + ende) // 2
    boese = bytearray(daten)
    boese[mitte] ^= 0xFF
    return bytes(boese)


def baue_verschluesseltes_zip() -> bytes:
    """Ein normales Zip, dem per Byte-Patch das verschluesselt-Flag
    gesetzt ist -- anfassen darf es nur, wer ein Passwort hat."""
    daten = baue_zip({"geheim.txt": b"daten"})
    daten = daten[:6] + struct.pack("<H", 1) + daten[8:]
    mitte = daten.find(b"PK\x01\x02")
    return daten[: mitte + 8] + struct.pack("<H", 1) + daten[mitte + 10 :]


# ------------------------------------------------------------ der Vorlauf


def test_vorlauf_liefert_den_plan_ohne_zu_schreiben(tmp_path):
    plan = plane(baue_zip({"a.txt": b"inhalt", "ordner/b.txt": b"mehr"}))
    namen = [(e.name, e.ist_verzeichnis, e.groesse) for e in plan]
    assert ("a.txt", False, 6) in namen
    assert ("ordner/b.txt", False, 4) in namen
    assert list(tmp_path.iterdir()) == []


def test_kein_zip_wird_vor_dem_ersten_zugriff_erkannt():
    with pytest.raises(ArchivBeschaedigt):
        plane(b"das ist gewiss kein Zip")


# ------------------------------------------- die boesartigen Faelle, #12


def test_boes_ausbruch_ueber_mutterverzeichnis(tmp_path):
    ziel = tmp_path / "entpackt"
    with pytest.raises(PfadAusbruch):
        entpacke(baue_zip({"../ausbruch.txt": b"boese"}), ziel)
    assert not ziel.exists()


def test_boes_absoluter_pfad(tmp_path):
    ziel = tmp_path / "entpackt"
    with pytest.raises(PfadAusbruch):
        entpacke(baue_zip({"/etc/passwd": b"boese"}), ziel)
    assert not ziel.exists()


def test_boes_symlink_auf_etc(tmp_path):
    ziel = tmp_path / "entpackt"
    boese = baue_zip_mit_attribut("link", 0o120777, b"/etc/passwd")
    with pytest.raises(BoesesArtefakt):
        entpacke(boese, ziel)
    assert not ziel.exists()


def test_boes_bombe_klein_gepackt_riesig_entpackt(tmp_path):
    ziel = tmp_path / "entpackt"
    grenzen = EntpackGrenzen(
        eintraege=100, gesamtgroesse=4 * 1024 * 1024, einzeldatei=2 * 1024 * 1024
    )
    with pytest.raises(GrenzeUeberschritten):
        entpacke(baue_bombe(), ziel, grenzen)
    assert not ziel.exists()
    assert list(tmp_path.iterdir()) == []


def test_boes_windows_laufwerk(tmp_path):
    ziel = tmp_path / "entpackt"
    with pytest.raises(PfadAusbruch):
        entpacke(baue_zip({"C:/windows/boese.txt": b"boese"}), ziel)
    assert not ziel.exists()


def test_boes_unc_pfad_und_rueckwaertige_trenner(tmp_path):
    ziel = tmp_path / "entpackt"
    with pytest.raises(PfadAusbruch):
        entpacke(baue_zip({"\\\\server\\freigabe\\boese.txt": b"boese"}), ziel)
    with pytest.raises(PfadAusbruch):
        entpacke(baue_zip({"..\\..\\windows\\boese.txt": b"boese"}), ziel)
    assert not ziel.exists()


def test_boes_geraetedatei(tmp_path):
    ziel = tmp_path / "entpackt"
    boese = baue_zip_mit_attribut("platte", 0o020600, b"\x00")
    with pytest.raises(BoesesArtefakt):
        entpacke(boese, ziel)
    assert not ziel.exists()


def test_boes_verschluesseltes_archiv(tmp_path):
    ziel = tmp_path / "entpackt"
    with pytest.raises(ArchivBeschaedigt):
        entpacke(baue_verschluesseltes_zip(), ziel)
    assert not ziel.exists()


def test_boes_doppelter_name(tmp_path):
    ziel = tmp_path / "entpackt"
    puffer = io.BytesIO()
    with pytest.warns(UserWarning, match="Duplicate"):
        with zipfile.ZipFile(puffer, "w") as z:
            z.writestr("zweimal.txt", b"erstens")
            z.writestr("zweimal.txt", b"zweitens")
    with pytest.raises(BoesesArtefakt):
        entpacke(puffer.getvalue(), ziel)
    assert not ziel.exists()


def test_boes_luegende_bombe_wird_beim_lesen_aufgehalten(tmp_path):
    """Die Metadaten versprechen 1 MiB, die Bombe entpackt 8 MiB. Das
    zweite Netz (laufende Zaehlung und Pruefsummen) haelt sie auf, und
    das halbfertige Ziel wird wieder entfernt."""
    ziel = tmp_path / "entpackt"
    boese = luege_groesse(baue_bombe(), 1024 * 1024)
    with pytest.raises(EntpackFehler):
        entpacke(boese, ziel)
    assert not ziel.exists()


# ------------------------------------------------------------- das Gute


def test_gutes_archiv_entpackt_dateien_und_verzeichnisse(tmp_path):
    ziel = tmp_path / "entpackt"
    ergebnis = entpacke(
        baue_zip(
            {
                "manifest.json": b"{}",
                "integration/__init__.py": b"pass\n",
                "integration/leer/": b"",
            }
        ),
        ziel,
    )
    assert (ziel / "manifest.json").read_bytes() == b"{}"
    assert (ziel / "integration/__init__.py").read_bytes() == b"pass\n"
    assert (ziel / "integration/leer").is_dir()
    assert isinstance(ergebnis, EntpackErgebnis)
    assert ergebnis.dateien == 2
    assert ergebnis.verzeichnisse == 1
    assert ergebnis.bytes == 7


def test_pfad_und_bytes_fuehren_zum_selben_ergebnis(tmp_path):
    daten = baue_zip({"a.txt": b"gleich"})
    als_datei = tmp_path / "archiv.zip"
    als_datei.write_bytes(daten)
    eins = entpacke(daten, tmp_path / "eins")
    zwei = entpacke(als_datei, tmp_path / "zwei")
    assert eins == zwei
    assert (tmp_path / "eins/a.txt").read_bytes() == (
        tmp_path / "zwei/a.txt"
    ).read_bytes()


def test_nur_filter_waehlt_eintraege(tmp_path):
    ziel = tmp_path / "entpackt"
    archiv = baue_zip({"a.txt": b"1", "b.txt": b"2", "c.txt": b"3"})
    entpacke(archiv, ziel, nur=["a.txt", "c.txt"])
    assert (ziel / "a.txt").exists()
    assert not (ziel / "b.txt").exists()
    assert (ziel / "c.txt").exists()


def test_nur_filter_prueft_trotzdem_das_ganze_archiv(tmp_path):
    """Auch wer nur eine harmlose Datei waehlt, bekommt das ganze Archiv
    geprueft -- eine Bombe hinter einem nicht gewaehlten Eintrag fliegt
    genauso auf."""
    ziel = tmp_path / "entpackt"
    grenzen = EntpackGrenzen(
        eintraege=100, gesamtgroesse=2 * 1024 * 1024, einzeldatei=1024 * 1024
    )
    with pytest.raises(GrenzeUeberschritten):
        entpacke(baue_bombe(), ziel, grenzen, nur=["liesmich.txt"])
    assert not ziel.exists()


def test_ziel_muss_leer_sein(tmp_path):
    ziel = tmp_path / "besetzt"
    ziel.mkdir()
    (ziel / "alte_datei.txt").write_bytes(b"x")
    with pytest.raises(Schreibfehler):
        entpacke(baue_zip({"neu.txt": b"y"}), ziel)
    assert (ziel / "alte_datei.txt").read_bytes() == b"x"


def test_eintraege_grenze_und_einzeldatei_grenze(tmp_path):
    ziel = tmp_path / "entpackt"
    grenzen = EntpackGrenzen(eintraege=2, gesamtgroesse=1024, einzeldatei=2)
    with pytest.raises(GrenzeUeberschritten):
        entpacke(baue_zip({"a.txt": b"123"}), ziel, grenzen)


def test_grenzfall_genau_an_der_grenze_zieht_noch(tmp_path):
    ziel = tmp_path / "entpackt"
    grenzen = EntpackGrenzen(eintraege=2, gesamtgroesse=3, einzeldatei=2)
    entpacke(baue_zip({"a.txt": b"12", "b.txt": b"1"}), ziel, grenzen)
    assert (ziel / "a.txt").read_bytes() == b"12"


# --------------------------------------------------- Installation und Tausch


def test_installieren_auf_frisches_ziel(tmp_path):
    lager = tmp_path / "lager"
    ziel = tmp_path / "config" / "custom_components" / "haigs"
    ergebnis = installiere(baue_zip({"__init__.py": b"pass\n"}), lager, ziel)
    assert (ziel / "__init__.py").exists()
    assert ergebnis.dateien == 1
    assert list(lager.iterdir()) == []


def test_installieren_ersetzt_und_hinterlaesst_keine_resten(tmp_path):
    lager = tmp_path / "lager"
    ziel = tmp_path / "haigs"
    ziel.mkdir()
    (ziel / "alt.txt").write_bytes(b"veraltet")
    installiere(baue_zip({"neu.txt": b"frisch"}), lager, ziel)
    assert not (ziel / "alt.txt").exists()
    assert (ziel / "neu.txt").read_bytes() == b"frisch"
    assert list(lager.iterdir()) == []


def test_installieren_scheitert_das_alte_ziel_bleibt(tmp_path):
    """Das Abnahmekriterium: ein Abbruch hinterlaesst keine halbe
    Installation. Das korrupte Archiv fliegt beim Entpacken auf, das
    bisherige Ziel bleibt unangetastet stehen."""
    lager = tmp_path / "lager"
    ziel = tmp_path / "haigs"
    ziel.mkdir()
    (ziel / "funktioniert.txt").write_bytes(b"weiterhin")
    boese = korrumpiere_daten(baue_zip({"riesig.bin": b"\x00" * 4096}))
    with pytest.raises(EntpackFehler):
        installiere(boese, lager, ziel)
    assert (ziel / "funktioniert.txt").read_bytes() == b"weiterhin"
    assert [pfad.name for pfad in ziel.iterdir()] == ["funktioniert.txt"]
    assert list(lager.iterdir()) == []


def test_installieren_taucht_und_holt_zurueck(tmp_path, monkeypatch):
    """Schlaegt der Tausch selbst -- hier erzwungen --, kehrt das alte
    Ziel an seinen Platz zurueck, bevor jemand etwas merkt."""
    import os

    lager = tmp_path / "lager"
    ziel = tmp_path / "haigs"
    ziel.mkdir()
    (ziel / "alt.txt").write_bytes(b"das bleibt")
    aufrufe = []

    echter_tausch = os.replace

    def taeuschender_tausch(von, nach):
        aufrufe.append((str(von), str(nach)))
        if len(aufrufe) == 2:  # der zweite Tausch: neu soll auf das Ziel
            raise OSError("Dateisystem erfindet hier einen Fehler")
        return echter_tausch(von, nach)

    monkeypatch.setattr(os, "replace", taeuschender_tausch)
    with pytest.raises(Schreibfehler):
        installiere(baue_zip({"neu.txt": b"neu"}), lager, ziel)
    assert (ziel / "alt.txt").read_bytes() == b"das bleibt"
    assert len(aufrufe) == 3  # wegbenannt, gescheitert, zurueckgeholt


# ------------------------------------------------------ Zusammenspiel, M4


def test_zusammenspiel_mit_zielpfaden_vollstaendige_installation(tmp_path):
    """Der Ablauf, den M4b spaeter faehrt: hacs.json-Angaben in einen
    Ausschnitt uebersetzen, den Kopierplan aus ``waehle_eintraege``
    direkt als Umbenenn-Zuordnung entpacken -- am Ziel liegt danach die
    Integration, ohne dass jemand Dateien einzeln verschiebt."""
    from haigs.core.zielpfade import Ausschnitt, waehle_eintraege

    archiv = baue_zip(
        {
            "mein-projekt-v1.2.0/manifest.json": b"{}",
            "mein-projekt-v1.2.0/__init__.py": b"pass\n",
            "mein-projekt-v1.2.0/README.md": b"doku",
        }
    )
    plan = plane(archiv)
    dateinamen = [e.name for e in plan if not e.ist_verzeichnis]
    zuordnung = waehle_eintraege(Ausschnitt(), dateinamen)
    ziel = tmp_path / "staging" / "mein-projekt"
    entpacke(archiv, ziel, nur=zuordnung)
    assert (ziel / "manifest.json").read_bytes() == b"{}"
    assert (ziel / "__init__.py").read_bytes() == b"pass\n"
    assert (ziel / "README.md").read_bytes() == b"doku"
    assert not (ziel / "mein-projekt-v1.2.0").exists()
