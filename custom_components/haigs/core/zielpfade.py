"""Wohin welche Kategorie gehoert -- reine Berechnung, kein Dateizugriff.

Diese eine Datei kennt die Verzeichnis-Konvention von Home Assistant:
Integrationen leben unter ``custom_components/<domain>/``, Plugins
unter ``www/community/<name>/``, Themes direkt unter ``themes/``.
Zusaetzlich sagt sie, **welcher Ausschnitt** eines Archivs ueberhaupt
in das Ziel wandert -- die drei ``hacs.json``-Felder
``content_in_root``, ``filename`` und ``zip_release`` schalten das um.

Bewusst ohne jede Dateioperation: das Berechnen ist pur, das Schreiben
uebernimmt :mod:`entpacken` mit den hier errechneten
Wegen. So bleibt beides einzeln pruefbar, und die HA-Schicht (M4b)
setzt die Teile zusammen: Forge laden, Zielpfad errechnen, Ausschnitt
waehlen, sicher entpacken, tauschen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .validierung import KATEGORIEN

#: Ein Windows-Laufwerk als erster Teil eines Namens: ``C:`` und Verwandte.
#: Auf POSIX waere ``C:/x`` ein ordentlicher Ordnername -- auf dem echten
#: Ziel (Windows-Installation von Home Assistant) ist es der Sprung auf ein
#: anderes Laufwerk. Der Name bleibt deshalb ueberall verboten.
_LAUFWERK = re.compile(r"[A-Za-z]:")

#: Wurzel je Kategorie, relativ zur Home-Assistant-Konfiguration.
#: ``theme`` und ``python_script`` sind bewusst flach: Home Assistant
#: liest dort jede Datei direkt, ein Unterordner je Repository gehoert
#: nicht ins Bild. ``appdaemon`` und ``template`` bekommen dagegen einen
#: eigenen Ordner -- dort liegen Pakete, die sich sonst uebereinander
#: treten wuerden.
_KATEGORIE_WURZELN = {
    "integration": "custom_components",
    "plugin": "www/community",
    "theme": "themes",
    "python_script": "python_scripts",
    "appdaemon": "apps",
    "template": "templates",
}

#: Kategorien, die einen eigenen Ordner je Repository bekommen.
#: Der Rest (``theme``, ``python_script``) legt seine Dateien direkt
#: in die Wurzel -- dort sammeln sich mehrere Repositorys nebeneinander.
_MIT_EIGENEM_ORDNER = frozenset({"integration", "plugin", "appdaemon", "template"})


class ZielpfadFehler(Exception):
    """Kategorie unbekannt, Name untauglich oder der Ausschnitt eines
    Archivs nicht eindeutig zu bestimmen. Die HA-Schicht meldet den
    Text, ohne dass jemand Zip- oder Pfad-Interna kennen muss."""


@dataclass(frozen=True)
class Ausschnitt:
    """Welcher Teil eines Archivs in das Ziel wandert.

    ``art`` ist eines von:

    * ``"dateien"`` -- nur die in ``dateien`` genannten Eintraege
      wandern, und zwar flach ins Ziel (Plugin-Datei ins eigene
      Verzeichnis, unter eigenem Dateinamen).
    * ``"wurzel"`` -- der Archiv-Inhalt steht in der Wurzel und wandert
      komplett.
    * ``"unterordner"`` -- der Inhalt steckt in einem Ordner, der beim
      Entpacken wegfaellt; ``unterordner`` nennt ihn, oder ist leer,
      wenn er aus dem Archiv abgeleitet werden soll (der Normalfall
      bei Tag-Archiven von GitLab und GitHub: ein einziger Ordner
      wie ``projekt-v1.2.0/`` oben, alles Andere darunter).
    """

    art: str = "unterordner"
    dateien: tuple[str, ...] = ()
    unterordner: str = ""


def zielverzeichnis(kategorie: str, name: str) -> PurePosixPath:
    """Zielpfad eines Repositorys unter der Home-Assistant-Konfiguration.

    ``name`` ist bei ``integration`` die Domain aus der
    ``manifest.json`` (klein geschrieben, kein Schraegstrich), bei den
    anderen Kategorien der Repository- oder Anzeigename. Bei den
    flachen Kategorien (``theme``, ``python_script``) spielt er fuer
    den Pfad keine Rolle, wird aber trotzdem geprueft -- ein untauglicher
    Name soll frueh auffallen, nicht erst beim Schreiben.
    """
    if kategorie not in KATEGORIEN:
        raise ZielpfadFehler(f"unbekannte Kategorie: {kategorie!r}")
    name = (name or "").strip()
    if (
        not name
        or name in (".", "..")
        or "/" in name
        or "\\" in name
        or "\x00" in name
        or name.startswith(".")
    ):
        raise ZielpfadFehler(f"untauglicher Name fuer ein Zielverzeichnis: {name!r}")

    wurzel = PurePosixPath(_KATEGORIE_WURZELN[kategorie])
    if kategorie in _MIT_EIGENEM_ORDNER:
        return wurzel / name
    return wurzel


def ist_zielpfad(pfad: PurePosixPath | str) -> bool:
    """Ist das ein Pfad, den eine Installation von hier geschrieben haben kann?

    Stufe M4b, Deinstallation: der Weg zum Ziel steht in der Ablage --
    Ablagen lassen sich von Hand veraendern, also wird der Weg vor dem
    Loeschen geprueft, nicht geglaubt. Ein gueltiger Weg ist relativ,
    beginnt mit einer bekannten Kategorie-Wurzel (auch einer
    zweiteiligen wie ``www/community``) und enthaelt nichts, was aus
    ihm herausfuehrt. Die Wurzel allein zaehlt dabei -- flache
    Kategorien (``themes``, ``python_scripts``) installieren direkt
    hinein. Alles andere (absolut, ``..``, fremde Wurzel) ist eine
    Absage, kein Fehler -- die Antwort ist Ja/Nein, und der Klartext
    gehoert zum Aufrufer.
    """
    if isinstance(pfad, str):
        try:
            pfad = PurePosixPath(pfad)
        except (ValueError, NotImplementedError):
            return False
    teile = pfad.parts
    if pfad.is_absolute() or not teile:
        return False
    for teil in teile:
        if teil in ("", ".", "..") or "/" in teil or "\\" in teil or "\x00" in teil:
            return False
    wurzeln = sorted(
        PurePosixPath(wurzel).parts for wurzel in _KATEGORIE_WURZELN.values()
    )
    for wurzel in wurzeln:
        if teile[: len(wurzel)] == wurzel:
            return True
    return False


def pruefe_relativen_namen(name: str) -> str:
    """Prueft einen Zielnamen, der aus einer ``hacs.json`` stammt.

    Befund #18 (Zip-Slip ueber den Zielnamen): der Wert hinter
    ``filename`` ist Eingabe von Fremden -- ein absoluter Pfad, ein
    Windows-Laufwerk oder ein ``..``-Teil haette das Schreiben aus dem
    Zielordner hinaus gelenkt (``Path / absoluter Pfad`` verwirft die
    linke Seite). Dasselbe Gesetz gilt seitdem fuer jeden Namen, der
    als Ziel einer Zuordnung dient. Zurueck kommt der gestrippte Name;
    alles Ausbrechende ist ein :class:`ZielpfadFehler` mit Klartext.
    """
    if not isinstance(name, str):
        raise ZielpfadFehler(
            "Zielname muss ein Dateiname als Text sein, nicht " + type(name).__name__
        )
    rein = name.strip()
    if not rein:
        raise ZielpfadFehler("Zielname ist leer")
    if "\x00" in rein:
        raise ZielpfadFehler(f"NUL-Byte im Zielnamen: {name!r}")
    if "\\" in rein:
        raise ZielpfadFehler(
            f"Rueckwaerts-Schraegstrich im Zielnamen (Windows-Tarnung): {name!r}"
        )
    if rein.startswith("/"):
        raise ZielpfadFehler(
            f"Zielname ist absolut -- er wuerde aus dem Zielordner "
            f"hinausschreiben: {name!r}"
        )
    teile = rein.split("/")
    for teil in teile:
        if teil in ("", ".", ".."):
            raise ZielpfadFehler(f"untauglicher Teil {teil!r} im Zielnamen: {name!r}")
    if _LAUFWERK.fullmatch(teile[0]):
        raise ZielpfadFehler(f"Windows-Laufwerk im Zielnamen: {name!r}")
    return rein


def ausschnitt(daten: dict | None) -> Ausschnitt:
    """Bestimmt aus den ``hacs.json``-Feldern den Ausschnitt eines Archivs.

    Die Rangfolge: nennt die ``hacs.json`` ein ``filename``, wandert
    genau diese Datei (Plugin-Normalfall, mit oder ohne
    ``zip_release`` -- im Anhang steht sie in der Wurzel, im
    Quell-Archiv unter dem Tag-Ordner, gefunden wird sie in beiden).
    Sonst bedeuten ``content_in_root`` oder ``zip_release``, dass der
    Inhalt in der Wurzel steht. Ohne alle drei lebt der Inhalt in
    einem Unterordner, der Name wird aus dem Archiv abgeleitet.

    Befund #18: alle drei Felder sind Typ- und Ausbruch-geprueft -- ein
    ``filename``, der woandershin zeigt, und ein Schaltfeld als Text
    (``"false"`` ist wahr in Python) sind Klartextfehler, keine stillen
    Umleitungen mehr.
    """
    daten = daten or {}
    if not isinstance(daten, dict):
        raise ZielpfadFehler("hacs.json enthaelt kein Objekt")

    datei_roh = daten.get("filename")
    if datei_roh is not None and not isinstance(datei_roh, str):
        raise ZielpfadFehler(
            "hacs.json: 'filename' muss ein Dateiname als Text sein, nicht "
            + type(datei_roh).__name__
        )
    datei = (datei_roh or "").strip()
    if datei:
        return Ausschnitt(art="dateien", dateien=(pruefe_relativen_namen(datei),))
    for feld in ("content_in_root", "zip_release"):
        wert = daten.get(feld)
        if wert is not None and not isinstance(wert, bool):
            raise ZielpfadFehler(
                f"hacs.json: '{feld}' muss true oder false sein, nicht {wert!r}"
            )
    if daten.get("content_in_root") or daten.get("zip_release"):
        return Ausschnitt(art="wurzel")
    return Ausschnitt(art="unterordner")


def waehle_eintraege(ausschnitt: Ausschnitt, namen: list[str]) -> dict[str, str]:
    """Ordnet Archiv-Eintraegen ihren Pfad im Zielverzeichnis zu.

    ``namen`` sind die Eintraege des Archivs (nur Dateien, wie sie
    :func:`entpacken.plane` liefert). Zurueck kommt eine
    Zuordnung Archiv-Name zu Ziel-Name; Verzeichnisse entstehen beim
    Entpacken nebenbei aus den Pfaden. Diese Zuordnung ist es, die
    ``entpacke`` als ``nur``-Filter und die HA-Schicht als Kopierplan
    bekommt.
    """
    dateinamen = [n for n in namen if not n.endswith("/")]

    if ausschnitt.art == "dateien":
        zuordnung: dict[str, str] = {}
        for gewuenscht_roh in ausschnitt.dateien:
            # Befund #18, zweite Stufe: der Ausschnitt ist ein dataclass,
            # wer ihn von Hand fuellt, kommt an ausschnitt() vorbei.
            gewuenscht = pruefe_relativen_namen(gewuenscht_roh)
            treffer = [
                n for n in dateinamen if n == gewuenscht or n.endswith("/" + gewuenscht)
            ]
            if not treffer:
                raise ZielpfadFehler(f"Datei fehlt im Archiv: {gewuenscht!r}")
            if len(treffer) > 1:
                raise ZielpfadFehler(
                    f"Datei {gewuenscht!r} liegt mehrfach im Archiv: "
                    + ", ".join(sorted(treffer))
                )
            zuordnung[treffer[0]] = gewuenscht
        return zuordnung

    if ausschnitt.art == "wurzel":
        return {n: n for n in dateinamen}

    if ausschnitt.art == "unterordner":
        if ausschnitt.unterordner:
            praefix = ausschnitt.unterordner.strip("/") + "/"
            innen = [n for n in dateinamen if n.startswith(praefix)]
            if not innen:
                raise ZielpfadFehler(
                    f"Unterordner {ausschnitt.unterordner!r} fehlt im Archiv"
                )
            return {n: n[len(praefix) :] for n in innen}

        oberteile = sorted({n.split("/", 1)[0] for n in dateinamen})
        if len(oberteile) != 1:
            raise ZielpfadFehler(
                "Ausschnitt nicht eindeutig -- kein gemeinsamer Unterordner oben: "
                + ", ".join(oberteile[:5])
            )
        praefix = oberteile[0] + "/"
        innen = [n for n in dateinamen if n.startswith(praefix)]
        if not innen:
            raise ZielpfadFehler(
                f"kein Unterordner {oberteile[0]!r} im Archiv -- steht der Inhalt "
                f"in der Wurzel, fehlt 'content_in_root' in der hacs.json?"
            )
        return {n: n[len(praefix) :] for n in innen}

    raise ZielpfadFehler(f"unbekannte Ausschnitt-Art: {ausschnitt.art!r}")
