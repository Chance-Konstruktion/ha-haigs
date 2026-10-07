"""Die Schnittstelle, an der spaeter jeder Anbieter haengt.

Absicht: kein ``if provider == "gitlab":`` irgendwo im Ablauf. Wer einen
dritten Anbieter anschliessen will (Codeberg, Forgejo), schreibt eine
weitere Klasse und sonst nichts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class ForgeFehler(Exception):
    """Der Anbieter konnte nicht beantworten, was gefragt wurde."""


class NichtGefunden(ForgeFehler):
    """Das Repository gibt es nicht, oder der Zugang reicht nicht."""


@dataclass(frozen=True)
class Release:
    """Eine veroeffentlichte Version."""

    tag: str
    name: str = ""
    beschreibung: str = ""
    veroeffentlicht_am: str = ""
    vorabversion: bool = False
    anhaenge: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class Commit:
    """Der Kopf eines Zweigs -- was der Entwicklermodus installiert."""

    sha: str
    datum: str = ""
    nachricht: str = ""


@dataclass(frozen=True)
class RepositoryInfo:
    """Was ein Anbieter ueber ein Repository verraet.

    ``tickets_url`` und ``releases_url`` sind die Web-Ansichten von
    Tickets und Releases -- pures Anbieterwissen, darum gehoert das
    Fuellen in die Anbieterklasse (und nirgendwo sonst, Stufe M7).
    Ein Anbieter ohne solche Ansichten laesst beide leer; die
    Oberflaeche versteckt die Verweise dann stillschweigend.
    """

    provider_id: str
    full_name: str
    beschreibung: str = ""
    standardzweig: str = "main"
    topics: tuple[str, ...] = ()
    sterne: int = 0
    offene_tickets: int = 0
    archiviert: bool = False
    web_url: str = ""
    tickets_url: str = ""
    releases_url: str = ""
    #: Adresse des Bildzeichens des Projekts (Flug 2084: der Laden
    #: zeigt die Zeichen seiner Karten). Anbieter ohne Bild lassen
    #: das Feld leer; die Oberflaeche faellt auf einen Buchstaben
    #: zurueck, nicht auf ein kaputtes Bild.
    avatar_url: str = ""


class HttpClient(Protocol):
    """Minimaler HTTP-Zugang, damit der Kern ohne Netz testbar bleibt.

    Vereinbarung: bei 404 wirft die Umsetzung :class:`NichtGefunden`,
    bei allem anderen Unerwarteten :class:`ForgeFehler`. Der Kern kennt
    keine Statuscodes und keine HTTP-Bibliothek.
    """

    async def get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        seiten: int | None = None,
    ):
        """``seiten`` begrenzt das Verfolgen von Folgeseiten.

        Ohne Angabe wird die Liste vollstaendig geholt. ``seiten=1``
        heisst: genau eine Seite, kein Weiterblaettern. Das braucht
        jede Stelle, die nur wissen will *ob* etwas antwortet --
        eine Probe darf nicht so teuer sein wie die Sache selbst.
        """

    async def get_bytes(self, url: str) -> bytes: ...


class Forge(Protocol):
    """Was HAIGS von einem Anbieter braucht -- mehr nicht."""

    provider: str
    host: str

    async def repository(self, pfad: str) -> RepositoryInfo:
        """Stammdaten zu ``gruppe/projekt``.

        Der Pfad ist die Adresse des Menschen -- und genau deshalb
        vergaenglich: Projekte werden umbenannt, Pfade wiederverwendet.
        Wer wissen will, wo ein Projekt HEUTE wohnt, fragt die ID.
        """

    async def repository_nach_id(self, anbieter_id: str) -> RepositoryInfo:
        """Stammdaten ueber die Anbieter-ID -- der Name darf sich aendern, sie nicht.

        Stufe M8: umbenannte Projekte. Die ID ist das eine, das bei einer
        Umbenennung traegt; ueber sie kommt der aktuelle Name zurueck und
        wird nachgezogen. Die Antwort ist Stammdaten wie bei
        :meth:`repository` -- nur der Weg dorthin ist der stabile.
        """

    async def releases(self, pfad: str) -> list[Release]:
        """Veroeffentlichte Versionen, neueste zuerst."""

    async def tags(self, pfad: str) -> list[str]:
        """Tags als Rueckfallebene, wenn ein Projekt keine Releases pflegt.

        Stufe M5: die Update-Erkennung greift darauf zurueck. Wer einen
        Anbieter anbindet, liefert hier einfach die Tagnamen.
        """

    async def zweig_stand(self, pfad: str, zweig: str) -> Commit:
        """Der juengste Commit eines Zweigs (Flug 2101, Entwicklermodus).

        Wer entwickelt, will nicht auf ein Release warten: der Kopf des
        Zweigs ist dann die Version, sein SHA der Ref fuer das Archiv.
        """

    async def datei(self, pfad: str, datei: str, ref: str) -> bytes:
        """Inhalt einer Datei auf einem Zweig oder Tag."""

    async def archiv(self, pfad: str, ref: str) -> bytes:
        """Das Quell-Archiv einer Version als Bytes.

        Stufe M5: der Installations-Dienst der update-Entities holt hier
        das Archiv -- die Adresse kennt nur der Anbieter, sie bleibt
        hinter dieser Naht.
        """

    async def archiv_url(self, pfad: str, ref: str) -> str:
        """Adresse des Quell-Archivs fuer eine Version."""

    async def anhang(self, url: str) -> bytes:
        """Laedt einen Release-Anhang -- die bevorzugte Installationsquelle.

        Stufe M4b: hat der Besitzer einem Release ein ZIP beigelegt, ist
        das die Quelle Nummer eins -- es ist gebaut, nicht gepackt-vom-
        Quellstand, und der Besitzer hat es dorthin gelegt. Die Adresse
        kam aus :attr:`Release.anhaenge`, gehoert also zum Anbieter --
        auch das Laden bleibt hinter dieser Naht.
        """

    async def suche_nach_topic(
        self,
        topic: str,
        gruppe: str | None = None,
        stichwort: str | None = None,
        mit_untergruppen: bool = True,
        grenze: int | None = None,
    ) -> list[RepositoryInfo]:
        """Alle Projekte, deren Besitzer sie mit ``topic`` gekennzeichnet hat.

        ``stichwort`` greift das Wort im Namen oder der Beschreibung auf
        -- die Kopfsuche des Ladens reist so bis zum Anbieter. Die
        Themen-Filterung bleibt scharf: das Wort engt ein, das Topic
        entscheidet. ``grenze`` deckelt den Abruf: hoechstens so viele
        Eintraege, genau eine Seite. Gedacht fuer die Pruefverbindung im
        Einrichtungsdialog -- die will beweisen, dass Host, API und
        Token stimmen, und nicht die halbe Instanz herunterladen.
        """
