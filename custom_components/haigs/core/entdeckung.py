"""Entdeckung: vom Topic zum geprueften Repository.

Ablauf, bewusst zweistufig:

    Topic ``hacs``  ->  Kandidat gefunden
                    ->  hacs.json gelesen und geprueft
                    ->  Kategorie plausibel
                    ->  erst dann aufgenommen

Ein Topic allein nimmt nichts auf. Es sagt nur, dass der Besitzer
gefunden werden moechte.

Stufe M6 ergaenzt die Ansicht: ein Scan ueber eine ganze Instanz oder
eine Gruppe (mit Untergruppen) liefert die Funde **mit letzter
stabiler Version** -- genug fuer eine Ergebnisliste, ohne dass der
Kern auch nur ein Byte schreibt. Die Aufnahme bleibt die Entscheidung
des Menschen.
"""

from __future__ import annotations

from dataclasses import dataclass

from .forge import ForgeFehler, NichtGefunden, RepositoryInfo
from .identity import GITLAB, RepositoryIdentity
from .validierung import Befund, pruefe_hacs_json
from .versionen import waehle_version


@dataclass
class Fund:
    """Ein Kandidat mitsamt Pruefergebnis.

    ``letzte_version`` ist die neueste **stabile** Version (Stufe M6) --
    leer, wenn ein Projekt keine Releases hat oder die Abfrage
    scheitert; der Fund bleibt trotzdem brauchbar. Vorabversionen
    zaehlen bewusst nicht: die Ergebnisliste soll zeigen, was ready
    ist, nicht was kommen koennte.
    """

    identitaet: RepositoryIdentity
    info: RepositoryInfo
    befund: Befund
    letzte_version: str = ""

    @property
    def uebernehmen(self) -> bool:
        return self.befund.gueltig

    @property
    def anzeigename(self) -> str:
        return self.identitaet.display_full_name


def _kategorie_aus_topics(topics: tuple[str, ...]) -> str:
    """Erlaubt ``hacs-plugin`` & Co. als Zusatz-Topic zur Kategorie."""
    for topic in topics:
        klein = topic.lower()
        if klein.startswith("hacs-") and klein != "hacs-development":
            return klein[len("hacs-") :]
    return "integration"


async def entdecke(
    forge,
    gruppe: str | None = None,
    topic: str = "hacs",
    stichwort: str | None = None,
    mit_vorab: bool = False,
    mit_version: bool = True,
    mit_untergruppen: bool = True,
) -> list[Fund]:
    """Sucht Projekte mit dem Topic und prueft jedes einzeln.

    ``mit_vorab`` nimmt zusaetzlich Projekte auf, die sich selbst als
    ``hacs-development`` gekennzeichnet haben. ``mit_version`` holt
    fuer brauchbare Kandidaten die neueste stabile Version -- auf
    Wunsch ausgespart, wenn der Aufrufer nur zaehlen will. Ohne
    ``gruppe`` wird die ganze Instanz durchsucht; ``mit_untergruppen``
    gilt nur fuer Gruppensuchen. ``stichwort`` engt auf Name und
    Beschreibung ein -- die Kopfsuche des Ladens reist hier bis zum
    Anbieter.

    Der Scan vertraut der Themensuche nicht blind: Kandidaten ohne das
    eigene Topic oder archivierte Projekte fallen hier noch einmal
    raus -- was als Treffer gilt, entscheidet der Kern, nicht die
    Gnade der API.
    """
    funde: list[Fund] = []
    kandidaten = await forge.suche_nach_topic(
        topic,
        gruppe=gruppe,
        stichwort=stichwort,
        mit_untergruppen=mit_untergruppen,
    )
    for info in kandidaten:
        if topic not in info.topics or info.archiviert:
            continue
        if not mit_vorab and "hacs-development" in info.topics:
            continue
        fund = await pruefe_kandidat(forge, info)
        if mit_version and fund.uebernehmen:
            fund.letzte_version = await _letzte_version(forge, info.full_name)
        funde.append(fund)
    return funde


async def _letzte_version(forge, pfad: str) -> str:
    """Neueste stabile Version eines Projekts -- oder leer bei Stoerung.

    Ein Projekt ohne Releases ist kein Fehler (Tags sind die
    Rueckfallebene spaeterer Stufen), und ein einzelner Ausfall darf
    einen ganzen Scan nicht abbrechen lassen.
    """
    try:
        aktualisierung = waehle_version(await forge.releases(pfad))
    except (ForgeFehler, NichtGefunden):
        return ""
    return aktualisierung.neueste


async def pruefe_kandidat(forge, info: RepositoryInfo) -> Fund:
    """Liest ``hacs.json`` im Standardzweig und bewertet den Kandidaten."""
    identitaet = RepositoryIdentity(
        provider=getattr(forge, "provider", GITLAB),
        host=forge.host,
        provider_id=info.provider_id,
        full_name=info.full_name,
    )
    kategorie = _kategorie_aus_topics(info.topics)
    try:
        roh = await forge.datei(info.full_name, "hacs.json", info.standardzweig)
    except NichtGefunden:
        return Fund(
            identitaet,
            info,
            Befund(False, kategorie=kategorie, fehler=["hacs.json fehlt"]),
        )
    return Fund(identitaet, info, pruefe_hacs_json(roh, kategorie))
