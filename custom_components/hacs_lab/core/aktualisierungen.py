"""Der periodische Update-Lauf: je Eintrag ein Fund, Fehler getrennt.

Stufe M5 der Roadmap: «Periodischer Lauf ueber alle Eintraege» und
«Fehler eines Repos darf den Lauf der anderen nicht abbrechen». Diese
Datei ist die Orchestrierung -- der Vergleich selbst bleibt in
:mod:`versionen` (die Abnahme verlangt, dass es die
einzige vergleichende Stelle bleibt).

Reihenfolge pro Eintrag: Releases fragen; gibt es keine, greift die
Rueckfallebene Tags. Die Notizen kommen aus der Beschreibung des
gewaehlten Releases -- Tags haben keine, dort bleibt das Feld leer.
Schaegt ein Eintrag fehl (nicht gefunden, Netz, kaputte Antwort),
landet das als Text im Fund und der Lauf geht weiter; geworfen wird
hier nie.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from .forge import Forge, Release
from .versionen import waehle_version

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pruefauftrag:
    """Was der Lauf ueber einen Eintrag wissen muss.

    ``schluessel`` ist der Speicherschluessel des Eintrags -- der Kern
    weiss nichts von Eintraegen, er bekommt Pfade und reicht Ergebnisse
    unter Schluesseln zurueck.
    """

    schluessel: str
    pfad: str
    installiert: str = ""
    mit_vorabversionen: bool = False
    #: Flug 2101, Entwicklermodus: statt Releases zaehlt der Kopf eines
    #: Zweigs. Leer heisst: der Standardzweig des Projekts.
    entwicklung: bool = False
    zweig: str = ""


@dataclass(frozen=True)
class Fund:
    """Das Ergebnis zu einem Eintrag -- auch das Scheitern ist eins."""

    schluessel: str
    verfuegbar: bool
    installiert: str
    neueste: str
    tag: str = ""
    notizen: str = ""
    quelle: str = ""
    veroeffentlicht_am: str = ""
    fehler: str | None = None

    def __bool__(self) -> bool:
        return self.verfuegbar


def _notizen_zu(releases: list[Release], tag: str) -> str:
    """Beschreibung des gewaehlten Releases, wenn es sie gibt."""
    for eintrag in releases:
        if eintrag.tag == tag:
            return eintrag.beschreibung
    return ""


def _veroeffentlicht_zu(releases: list[Release], tag: str) -> str:
    for eintrag in releases:
        if eintrag.tag == tag:
            return eintrag.veroeffentlicht_am
    return ""


async def pruefe(forge: Forge, auftrag: Pruefauftrag) -> Fund:
    """Fragt einen Eintrag ab -- ohne je zu werfen.

    Fehler werden in den Fund geschrieben, damit ein kaputtes oder
    verschwundenes Repository den Lauf der anderen nicht abbricht.
    Der Rueckfall auf Tags gilt auch dann, wenn die Releases nicht
    gelingen: erst wenn beides scheitert, ist der Fund ein Fehler-Fund.
    """
    if auftrag.entwicklung:
        return await _pruefe_zweig(forge, auftrag)

    fehler_text: str | None = None
    try:
        releases = await forge.releases(auftrag.pfad)
    except Exception as fehler:  # noqa: BLE001 - Absicht, s. Moduldoku
        releases = []
        fehler_text = str(fehler) or fehler.__class__.__name__
        _LOGGER.debug("Releases zu %s gescheitert: %s", auftrag.pfad, fehler_text)

    quelle = "releases"
    if not releases:
        quelle = "tags"
        try:
            tagnamen = await forge.tags(auftrag.pfad)
        except Exception as fehler:  # noqa: BLE001
            fehler_text = fehler_text or (str(fehler) or fehler.__class__.__name__)
            _LOGGER.debug("Tags zu %s gescheitert: %s", auftrag.pfad, fehler_text)
            return Fund(
                schluessel=auftrag.schluessel,
                verfuegbar=False,
                installiert=auftrag.installiert,
                neueste="",
                fehler=fehler_text,
            )
        releases = [Release(tag=tag) for tag in tagnamen]

    wahl = waehle_version(releases, auftrag.installiert, auftrag.mit_vorabversionen)
    return Fund(
        schluessel=auftrag.schluessel,
        verfuegbar=wahl.verfuegbar,
        installiert=wahl.installiert,
        neueste=wahl.neueste,
        tag=wahl.tag,
        notizen=_notizen_zu(releases, wahl.tag),
        quelle=quelle,
        veroeffentlicht_am=_veroeffentlicht_zu(releases, wahl.tag),
    )


def zweig_version(zweig: str, sha: str) -> str:
    """Die Version eines Zweigstands, wie sie Mensch und Entity sehen."""
    return f"{zweig}@{sha[:7]}"


async def _pruefe_zweig(forge: Forge, auftrag: Pruefauftrag) -> Fund:
    """Der Entwicklermodus (Flug 2101): der Kopf des Zweigs ist die Version.

    Kein Release, kein Tag -- wer entwickelt, will den Stand von eben
    testen. Die Version heisst ``zweig@sha7``, der volle SHA ist der Ref
    fuer das Archiv. Wie :func:`pruefe` wirft auch dieser Weg nie.
    """
    try:
        zweig = auftrag.zweig
        if not zweig:
            zweig = (await forge.repository(auftrag.pfad)).standardzweig or "main"
        kopf = await forge.zweig_stand(auftrag.pfad, zweig)
    except Exception as fehler:  # noqa: BLE001 - Absicht, s. Moduldoku
        text = str(fehler) or fehler.__class__.__name__
        _LOGGER.debug("Zweigstand zu %s gescheitert: %s", auftrag.pfad, text)
        return Fund(
            schluessel=auftrag.schluessel,
            verfuegbar=False,
            installiert=auftrag.installiert,
            neueste="",
            fehler=text,
        )
    neueste = zweig_version(zweig, kopf.sha)
    return Fund(
        schluessel=auftrag.schluessel,
        verfuegbar=neueste != auftrag.installiert,
        installiert=auftrag.installiert,
        neueste=neueste,
        tag=kopf.sha,
        notizen=kopf.nachricht,
        quelle="zweig",
        veroeffentlicht_am=kopf.datum,
    )


async def lauf(forge: Forge, auftraege: list[Pruefauftrag]) -> dict[str, Fund]:
    """Laeuft alle Auftraege der Reihe nach ab.

    Der Reihe nach mit Absicht: ein Anbieter mit Grenzen (429) soll
    nicht durch einen Schlag gleichzeitiger Abfragen gestraft werden,
    und der Abstand zwischen zwei Laeufern ist ohnehin halbt tags.
    """
    ergebnis: dict[str, Fund] = {}
    for auftrag in auftraege:
        ergebnis[auftrag.schluessel] = await pruefe(forge, auftrag)
    return ergebnis
