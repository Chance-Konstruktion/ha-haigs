"""Baut den Auslieferungs-ZIP fuer HAIGS -- deterministisch.

Stufe M10 (Nach draussen): Wer HAIGS haben will, bekommt es aus
einem Release -- nicht aus einem Git-Clone in sein Konfigurations-
verzeichnis. Der ZIP spiegelt das Lager: entpackt im Home-Assistant-
Konfigurationsverzeichnis landet jeder Ordner dort, wo er hingehoert.

Warum ein eigenes Werkzeug und nicht ``git archive``:

* Der ZIP soll auch ohne Git funktionieren -- der CI-Runner checkt
  aus, was er auscheckt, und ein spaeterer Bau auf einem entpackten
  Stand muss dasselbe Ergebnis liefern.
* Muell bleibt draussen: ``tests/``, ``__pycache__``, Caches. Ein
  Fremder soll nicht unsere Testfantasien mit installieren.
* Die Bytes sind reproduzierbar: feste Zeitstempel, sortierte
  Eintraege, feste Rechte. Zwei Bauten aus demselben Stand ergeben
  dieselbe Datei -- pruefbar per SHA-256, ohne ''glauben''.

Form-adaptiv, bewusst: der Kern von HAIGS wohnt seit M0.5 in der
Integration (``custom_components/haigs/core``). Aeltere Staende
tragen ihn noch als eigenstaendiges ``haigs`` an der Wurzel. Der
Bauer erkennt die Form am ausgecheckten Stand und packt, was da ist
-- so bleibt die Merge-Reihenfolge mit jener Umstellung gleichgueltig,
und die Entpack-Anleitung stimmt in beiden Formen: ZIP ins
Konfigurationsverzeichnis entpacken, fertig.
"""

from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

#: Anzeigename fuer die Datei -- der Domain-Name mit Bindestrich,
#: so nennen Menschen das Projekt (der Stern aus ``HAIGS`` ist
#: kein erlaubter Dateiname-Bestandteil auf jedem Dateisystem).
ANZEIGENAME = "haigs"

#: Die Home-Assistant-Schicht -- immer im ZIP.
INTEGRATION = Path("custom_components/haigs")

#: Der Kern in der ALTEN Form (vor M0.5): eigenstaendig an der Wurzel.
#: Existiert das Verzeichnis, gehoert es mit in den ZIP.
KERN_ALT = Path("haigs")

#: Fester Zeitstempel fuer jeden Eintrag: 1980-01-01 00:00:00.
#: ZIP-Zeitstempel leben im MS-DOS-Format, und dieses Datum ist die
#: aelteste ueberhaupt darstellbare Stunde -- niemand verwechselt ihn
#: mit einer echten Bauzeit, und er ist auf jedem Bau identisch.
_FESTE_ZEIT = (1980, 1, 1, 0, 0, 0)

#: Verzeichnisse, die nie in den ZIP wandern.
_IGNORIEREN = frozenset({"__pycache__", ".pytest_cache", ".ruff_cache", ".git"})


class BauFehler(Exception):
    """Der Release-ZIP liess sich nicht bauen -- der Text ist fuer Menschen."""


def normalisiere_version(version: str) -> str:
    """Nimmt fuehrende ``v``/``V`` weg, wenn eine Ziffer folgt.

    Tags heissen ``v0.1.0``, die manifest.json nennt ``0.1.0`` -- hier
    treffen die beiden Schreibweisen aufeinander. Bewusst ohne Import
    des Kerns: das Werkzeug muss auch auf Staenden laufen, auf denen
    der Kern noch nicht an der importierbaren Stelle wohnt.
    """
    v = (version or "").strip()
    if v[:1] in ("v", "V") and v[1:2].isdigit():
        v = v[1:]
    return v


def lies_version(wurzel: Path) -> str:
    """Liest die Version aus der manifest.json der Integration."""
    roh = wurzel / INTEGRATION / "manifest.json"
    try:
        daten = json.loads(roh.read_text(encoding="utf-8"))
    except FileNotFoundError as fehlschlag:
        raise BauFehler(
            f"manifest.json fehlt unter {INTEGRATION} -- ohne sie kennt Home "
            "Assistant keine Version und keine Integration"
        ) from fehlschlag
    except (json.JSONDecodeError, UnicodeDecodeError) as fehlschlag:
        raise BauFehler(f"manifest.json ist unlesbar: {fehlschlag}") from fehlschlag
    version = str(daten.get("version") or "").strip()
    if not version:
        raise BauFehler("manifest.json nennt keine Version -- nichts zu benennen")
    return normalisiere_version(version)


def form(wurzel: Path) -> str:
    """Welche Lagerform liegt vor -- Text fuer Menschen und Tests."""
    if (wurzel / KERN_ALT).is_dir():
        return "alte Form (Kern an der Wurzel)"
    return "neue Form (Kern in der Integration)"


def dateien_fuer(wurzel: Path) -> list[Path]:
    """Sammelt die Dateien fuer den ZIP, relativ zur Wurzel, sortiert.

    Fehler frueh und mit Klartext: eine Integration ohne Verzeichnis
    oder ohne manifest.json ist kein Release, sondern ein Unfall.
    """
    if not (wurzel / INTEGRATION).is_dir():
        raise BauFehler(f"Integration fehlt: {INTEGRATION} existiert nicht an der Wurzel")
    if not (wurzel / INTEGRATION / "manifest.json").is_file():
        raise BauFehler("manifest.json fehlt in der Integration -- kein Release")

    grundlagen = [INTEGRATION]
    if (wurzel / KERN_ALT).is_dir():
        grundlagen.append(KERN_ALT)

    ergebnis: list[Path] = []
    for basis in grundlagen:
        basis_abs = wurzel / basis
        for datei in basis_abs.rglob("*"):
            if not datei.is_file():
                continue
            relativ = datei.relative_to(wurzel)
            if any(teil in _IGNORIEREN for teil in relativ.parts):
                continue
            if datei.suffix == ".pyc":
                continue
            ergebnis.append(relativ)
    if not ergebnis:
        raise BauFehler("nichts zu packen -- die Integration ist leer")
    return sorted(ergebnis)


def baue_release(
    wurzel: Path, ziel_verzeichnis: Path, version: str | None = None
) -> Path:
    """Baut den ZIP und liefert seinen Pfad zurueck.

    ``version`` (der CI-Tag) und die manifest.json muessen dieselbe
    Version nennen -- stimmen sie nicht ueberein, wird nicht gebaut.
    Ein Release, der im Namen v0.9.0 verspricht und als 0.1.0
    installiert, ist eine Falle fuer den, der ihm vertraut. Der Name
    entsteht immer hier, nie beim Aufrufer -- so heissen alle Releases
    gleich.
    """
    eintraege = dateien_fuer(wurzel)
    manifest_version = lies_version(wurzel)
    version = normalisiere_version(version) if version else manifest_version
    if version != manifest_version:
        raise BauFehler(
            f"Version {version} (uebergeben) und {manifest_version} "
            "(manifest.json) stimmen nicht ueberein -- erst angleichen, dann bauen"
        )

    ziel_verzeichnis.mkdir(parents=True, exist_ok=True)
    ziel = ziel_verzeichnis / f"{ANZEIGENAME}-v{version}.zip"

    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as archiv:
        for relativ in eintraege:
            info = zipfile.ZipInfo(filename=relativ.as_posix(), date_time=_FESTE_ZEIT)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix -- sonst frisst ZIP die Rechte
            info.external_attr = 0o644 << 16  # lesbar fuer alle, sonst nichts
            archiv.writestr(info, (wurzel / relativ).read_bytes())
    return ziel


def fingerabdruck(pfad: Path) -> str:
    """SHA-256 als Hex -- klein genug, um ihn neben den Anhang zu schreiben."""
    return hashlib.sha256(pfad.read_bytes()).hexdigest()


def haupt(argv: list[str] | None = None) -> int:
    """Kommandozeile: ``python auslieferung/release_bauen.py [ziel] [--version X]``."""
    argv = list(sys.argv[1:] if argv is None else argv)
    version: str | None = None
    ziel_verzeichnis = Path("dist")
    rest: list[str] = []
    it = iter(argv)
    for arg in it:
        if arg == "--version":
            try:
                version = next(it)
            except StopIteration:
                print("FEHLER: --version verlangt eine Angabe", file=sys.stderr)
                return 2
        else:
            rest.append(arg)
    if len(rest) > 1:
        print("FEHLER: hoechstens ein Zielverzeichnis", file=sys.stderr)
        return 2
    if rest:
        ziel_verzeichnis = Path(rest[0])

    wurzel = Path(__file__).resolve().parents[1]
    try:
        ziel = baue_release(wurzel, ziel_verzeichnis, version)
        groesse = ziel.stat().st_size
        menge = len(dateien_fuer(wurzel))
    except BauFehler as fehlschlag:
        print(f"FEHLER: {fehlschlag}", file=sys.stderr)
        return 1

    print(f"{ziel.name}")
    print(f"  Form: {form(wurzel)}")
    print(f"  Dateien: {menge}")
    print(f"  Bytes: {groesse}")
    print(f"  SHA-256: {fingerabdruck(ziel)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(haupt())
