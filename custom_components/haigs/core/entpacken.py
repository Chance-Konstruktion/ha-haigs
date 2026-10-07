"""Ein Zip-Archiv sicher entpacken.

Der gefaehrlichste Moment einer Installation ist das Entpacken: ein
boeses Archiv kann Pfade ausserhalb des Ziels schreiben (Zip-Slip),
Symlinks auf Systemdateien legen oder die Platte mit einem winzig
gepackten Riesen fuellen. Deshalb gilt hier die umgekehrte Reihenfolge
gegenueber dem naiven Entpacken: zuerst wird das **ganze** Archiv
geprueft -- Namen, Eintragstypen, Grenzen, alles aus den Metadaten,
kein Byte geschrieben --, erst danach wird entpackt, und zwar mit
laufender Byte-Zaehlung als zweitem Netz, und bei der Installation
in einem Zwischenverzeichnis, das am Ende getauscht wird. Ein Abbruch
hinterlaesst damit keine halbe Installation.

Das Modul entscheidet selbst ueber **keinen** Pfad. Zwischenlager und
Ziel kommen als Argumente herein (ARCHITEKTUR.md: der Kern schreibt
nur, was die HA-Schicht ihm ausdruecklich vorsetzt), die Berechnung
der Pfade je Kategorie liegt in :mod:`zielpfade`.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import stat
import zipfile
import zlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO

#: Maske fuer die Dateiart in den Unix-Attributen (st_mode ohne Rechte).
#: Bewusst als Zahl, nicht aus ``stat`` geholt: ``stat.S_IFMT`` ist je
#: nach Python-Fassung Konstante oder Funktion, und der Wert steht fest.
_ART_MASKE = 0o170000

#: Blockgroesse beim Schreiben: gross genug fuer Tempo, klein genug,
#: um eine luegende Bombe nach wenigen Megabytes aufzufliegen zu lassen.
_BLOCK = 1024 * 1024

#: Ein Windows-Laufwerk als erster Teil eines Namens: ``C:`` und Verwandte.
_LAUFWERK = re.compile(r"[A-Za-z]:")


@dataclass(frozen=True)
class EntpackGrenzen:
    """Obergrenzen eines Archivs -- gezaehlt in entpackten Bytes.

    Die Werte sind bewusst grosszuegig: HACS-Repositorys sind klein,
    aber niemandem ist mit Abweisungen geholfen, die regulaere
    Integrationen treffen. Boese Archive fallen trotzdem frueher auf:
    ihre Angaben stehen schon in den Metadaten, noch bevor ein Byte
    geschrieben wurde.
    """

    eintraege: int = 4096
    gesamtgroesse: int = 256 * 1024 * 1024
    einzeldatei: int = 128 * 1024 * 1024


class EntpackFehler(Exception):
    """Basisklasse: das Archiv konnte nicht sicher entpackt werden.

    Die HA-Schicht faengt genau diese Art und meldet den Text -- die
    Einzelarten druecken aus, *was* schiefging, ohne dass jemand
    Statuscodes oder Zip-Interna kennen muesste.
    """


class PfadAusbruch(EntpackFehler):
    """Ein Eintrag zeigt ausserhalb des Ziels: ``../``-Teile, absolute
    Pfade, Windows-Laufwerke, UNC-Pfade, Rueckwaerts-Schraegstriche."""


class BoesesArtefakt(EntpackFehler):
    """Ein Eintrag ist keine regulaere Datei und kein Verzeichnis:
    Symlink, Geraetedatei, doppelter Name -- oder untauglicher Name."""


class GrenzeUeberschritten(EntpackFehler):
    """Anzahl oder Groesse der Eintraege liegt ueber den Grenzen --
    das Bild einer Zip-Bombe."""


class ArchivBeschaedigt(EntpackFehler):
    """Das Archiv ist kein Zip, ist verschluesselt oder die Daten
    stimmen nicht mit den Pruefsummen ueberein."""


class Schreibfehler(EntpackFehler):
    """Das Dateisystem hat beim Entpacken oder Tauschen versagt --
    zum Beispiel volles Ziel oder falsches Dateisystem fuer den Tausch."""


@dataclass(frozen=True)
class ArchivEintrag:
    """Ein gepruefter Eintrag aus dem Vorlauf."""

    name: str
    ist_verzeichnis: bool
    groesse: int


@dataclass(frozen=True)
class EntpackErgebnis:
    """Was nach dem Entpacken da liegt."""

    dateien: int = 0
    verzeichnisse: int = 0
    bytes: int = 0


def _pruefe_name(name: str) -> PurePosixPath:
    """Prueft einen Archiv-Namen als reinen relativen Pfad.

    Erhebt :class:`PfadAusbruch` fuer alles, was nach dem Entpacken
    ausserhalb des Ziels landen koennte: absolute Pfade (auch UNC),
    ``..``-Teile, Windows-Laufwerke und Rueckwaerts-Schraegstriche --
    letztere sind im Zip-Format kein Trennzeichen, tauchen aber in
    Windows-gebaeuten Archiven als Tarnung auf.
    """
    if not name:
        raise ArchivBeschaedigt("Eintrag ohne Namen im Archiv")
    if "\x00" in name:
        raise BoesesArtefakt(f"NUL-Byte im Namen: {name!r}")
    pfad = PurePosixPath(name)
    if pfad.is_absolute() or name.startswith(("//", "\\")):
        raise PfadAusbruch(f"absoluter Pfad im Archiv: {name!r}")
    teile = pfad.parts
    if not teile:
        raise BoesesArtefakt(f"Name nennt nur den eigenen Ordner: {name!r}")
    if teile and _LAUFWERK.fullmatch(teile[0]):
        raise PfadAusbruch(f"Windows-Laufwerk im Archiv: {name!r}")
    if "\\" in name:
        raise PfadAusbruch(
            f"Rueckwaerts-Schraegstrich im Namen (Windows-Tarnung): {name!r}"
        )
    if ".." in teile:
        raise PfadAusbruch(f"..-Teil im Namen, Ausbruch moeglich: {name!r}")
    return pfad


def _art_pruefen(info: zipfile.ZipInfo) -> bool:
    """Prueft den Eintragstyp und meldet, ob es ein Verzeichnis ist.

    Erlaubt sind regulaere Dateien und Verzeichnisse, alles Andere --
    Symlinks, Geraete, FIFOs, Sockets -- ist ein :class:`BoesesArtefakt`.
    Unix-Attribute stehen in den oberen 16 Bit von ``external_attr``;
    fehlen sie (0), stammt das Archiv von einem DOS-Zipper und der
    Eintrag gilt als regulaere Datei.
    """
    art = (info.external_attr >> 16) & _ART_MASKE
    if art in (0, stat.S_IFREG, stat.S_IFDIR):
        ist_verzeichnis = info.is_dir() or art == stat.S_IFDIR
        if ist_verzeichnis and art == stat.S_IFREG:
            raise BoesesArtefakt(
                f"Name nennt ein Verzeichnis, die Attribute eine Datei: {info.filename!r}"
            )
        return ist_verzeichnis
    art_oktal = oct(art)[2:].zfill(6)
    raise BoesesArtefakt(
        f"Eintrag ist keine Datei und kein Verzeichnis (Typ {art_oktal}, "
        f"Symlink oder Geraet?): {info.filename!r}"
    )


def _archiv_oeffnen(archiv: Path | bytes | BinaryIO) -> zipfile.ZipFile:
    """Oeffnet das Archiv aus Bytes, aus einem Strom oder vom Pfad.

    Bytes werden in einen Strom gepackt, ein Strom wird vor jedem
    Oeffnen zurueckgespult -- beides gehoert zum Ablauf, dieselbe
    Quelle zweimal zu lesen (Vorlauf, dann Entpacken).
    """
    quelle = io.BytesIO(archiv) if isinstance(archiv, (bytes, bytearray)) else archiv
    if hasattr(quelle, "seek"):
        quelle.seek(0)
    try:
        return zipfile.ZipFile(quelle)
    except zipfile.BadZipFile as schaden:
        raise ArchivBeschaedigt(f"kein lesbares Zip-Archiv: {schaden}") from schaden


def plane(
    archiv: Path | bytes | BinaryIO, grenzen: EntpackGrenzen | None = None
) -> list[ArchivEintrag]:
    """Prueft das ganze Archiv, ohne ein Byte zu schreiben.

    Der Vorlauf ist die eigentliche Abwehr: Namen, Eintragstypen und
    Grenzen stehen alle in den Metadaten. Ein boeses Archiv wird hier
    vollstaendig abgewiesen, bevor das Dateisystem ueberhaupt angeruehrt
    wird. Zurueck kommt der gepruefte Eintragsplan.
    """
    grenzen = grenzen or EntpackGrenzen()
    with _archiv_oeffnen(archiv) as zip_datei:
        eintraege = zip_datei.infolist()
        if len(eintraege) > grenzen.eintraege:
            raise GrenzeUeberschritten(
                f"{len(eintraege)} Eintraege, Grenze ist {grenzen.eintraege}"
            )

        plan: list[ArchivEintrag] = []
        gesehen: set[str] = set()
        gesamt = 0
        for info in eintraege:
            name = info.filename
            if info.flag_bits & 0x1:
                raise ArchivBeschaedigt(f"Eintrag ist verschluesselt: {name!r}")
            _pruefe_name(name)
            ist_verzeichnis = _art_pruefen(info)
            if name in gesehen:
                raise BoesesArtefakt(f"Name kommt doppelt vor: {name!r}")
            gesehen.add(name)
            groesse = 0 if ist_verzeichnis else info.file_size
            if groesse > grenzen.einzeldatei:
                raise GrenzeUeberschritten(
                    f"{name!r} entpackt {groesse} Bytes, Grenze je Datei ist "
                    f"{grenzen.einzeldatei}"
                )
            gesamt += groesse
            if gesamt > grenzen.gesamtgroesse:
                raise GrenzeUeberschritten(
                    f"Archiv entpackt mehr als {grenzen.gesamtgroesse} Bytes "
                    f"(bis {name!r} gezaehlt: {gesamt})"
                )
            plan.append(ArchivEintrag(name, ist_verzeichnis, groesse))
        return plan


def entpacke(
    archiv: Path | bytes | BinaryIO,
    ziel: Path,
    grenzen: EntpackGrenzen | None = None,
    *,
    nur: Collection[str] | Mapping[str, str] | None = None,
) -> EntpackErgebnis:
    """Entpackt ein geprueftes Archiv in ein frisches Verzeichnis.

    Erst :func:`plane` -- ohne Schreiben --, dann das Entpacken mit
    laufender Byte-Zaehlung als zweitem Netz, denn Metadaten koennen
    luegen. ``ziel`` wird angelegt; existiert es schon, muss es leer
    sein. Schlaegt das Entpacken unterwegs fehl, wird das halbfertige
    Verzeichnis wieder entfernt.

    ``nur`` schraenkt ein, was geschrieben wird -- die Pruefung gilt
    trotzdem fuer das **ganze** Archiv, auch eine Bombe hinter einem
    nicht gewaehlten Eintrag fliegt auf. Als schlichte Sammlung von
    Namen behaelt jeder Eintrag seinen Archiv-Namen; als Zuordnung
    (der Kopierplan aus
    :func:`zielpfade.waehle_eintraege`) landet jeder
    Eintrag gleich unter seinem Ziel-Namen.
    """
    grenzen = grenzen or EntpackGrenzen()
    plan = plane(archiv, grenzen)
    if isinstance(nur, Mapping):
        gesucht = set(nur)
        umbenennung = dict(nur)
    elif nur is not None:
        gesucht = set(nur)
        umbenennung = {}
    else:
        gesucht = None
        umbenennung = {}

    ziel.parent.mkdir(parents=True, exist_ok=True)
    if ziel.exists():
        if any(ziel.iterdir()):
            raise Schreibfehler(f"Ziel ist nicht leer: {str(ziel)!r}")
    else:
        ziel.mkdir()

    dateien = verzeichnisse = geschrieben = 0
    try:
        with _archiv_oeffnen(archiv) as zip_datei:
            for eintrag in plan:
                if gesucht is not None and eintrag.name not in gesucht:
                    continue
                pfad = ziel / umbenennung.get(eintrag.name, eintrag.name)
                if eintrag.ist_verzeichnis:
                    pfad.mkdir(parents=True, exist_ok=True)
                    verzeichnisse += 1
                    continue
                pfad.parent.mkdir(parents=True, exist_ok=True)
                dateien += 1
                with (
                    zip_datei.open(eintrag.name) as quelle,
                    pfad.open("wb") as senke,
                ):
                    gezaehlt = 0
                    while stueck := quelle.read(_BLOCK):
                        gezaehlt += len(stueck)
                        if gezaehlt > grenzen.einzeldatei:
                            raise GrenzeUeberschritten(
                                f"{eintrag.name!r} schreibt mehr, als die Metadaten "
                                f"versprachen (ueber {grenzen.einzeldatei} Bytes)"
                            )
                        geschrieben += len(stueck)
                        if geschrieben > grenzen.gesamtgroesse:
                            raise GrenzeUeberschritten(
                                f"geschriebene Bytes uebersteigen die Gesamtgrenze "
                                f"{grenzen.gesamtgroesse}"
                            )
                        senke.write(stueck)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, zlib.error) as schaden:
        shutil.rmtree(ziel, ignore_errors=True)
        raise ArchivBeschaedigt(f"Archiv beim Lesen gescheitert: {schaden}") from schaden
    except OSError as schaden:
        shutil.rmtree(ziel, ignore_errors=True)
        raise Schreibfehler(f"Dateisystem beim Entpacken versagt: {schaden}") from schaden
    except EntpackFehler:
        shutil.rmtree(ziel, ignore_errors=True)
        raise

    return EntpackErgebnis(dateien, verzeichnisse, geschrieben)


def installiere(
    archiv: Path | bytes | BinaryIO,
    zwischenlager: Path,
    ziel: Path,
    grenzen: EntpackGrenzen | None = None,
    *,
    nur: Collection[str] | Mapping[str, str] | None = None,
) -> EntpackErgebnis:
    """Entpackt ins Zwischenlager und tauscht dann in einem Zug.

    Der Tausch: das bisherige ``ziel`` wird wegbenannt, das frisch
    Entpackte rueckt nach, das Alte wird entfernt. Schlaegt der Tausch
    selbst fehl, kehrt das Alte an seinen Platz zurueck -- ein Abbruch
    darf keine halbe Installation hinterlassen. Zwischenlager und Ziel
    muessen auf demselben Dateisystem liegen, sonst kann der Tausch
    nicht in einem Zug geschehen; M4b waehlt das Lager deshalb unter
    der Home-Assistant-Konfiguration.
    """
    if not ziel.name or ziel.name in (".", ".."):
        raise Schreibfehler(f"untauglicher Name fuer ein Ziel: {str(ziel)!r}")

    zwischenlager.mkdir(parents=True, exist_ok=True)
    neu = zwischenlager / (ziel.name + ".neu")
    alt = zwischenlager / (ziel.name + ".alt")
    shutil.rmtree(neu, ignore_errors=True)
    shutil.rmtree(alt, ignore_errors=True)

    ergebnis = entpacke(archiv, neu, grenzen, nur=nur)

    ziel.parent.mkdir(parents=True, exist_ok=True)
    war_da = ziel.exists()
    if war_da:
        try:
            os.replace(ziel, alt)
        except OSError as schaden:
            shutil.rmtree(neu)
            raise Schreibfehler(
                f"das bisherige Ziel laesst sich nicht wegbewegen: {schaden}"
            ) from schaden
    try:
        os.replace(neu, ziel)
    except OSError as schaden:
        if war_da:
            os.replace(alt, ziel)  # Rueckholung -- das Alte gilt wieder
        shutil.rmtree(neu, ignore_errors=True)
        raise Schreibfehler(f"Tausch auf das Ziel gescheitert: {schaden}") from schaden
    if war_da:
        shutil.rmtree(alt, ignore_errors=True)
    return ergebnis
