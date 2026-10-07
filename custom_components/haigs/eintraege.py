"""Custom Repositories: die Liste, die Stufe M3 anlegt und pflegt.

Ein Custom Repository ist per Definition eines, das jemand von Hand
anstoesst -- die Entdeckung ueber Topics kommt erst in Stufe M6. Diese
Datei fuehrt die Liste: hinzufuegen nach Identitaetspruefung, entfernen
mit und ohne Deinstallation, speichern in der Ablage (Store v1, Feld
``eintraege`` -- das Geruest dafuer steht seit Stufe M2).

Die Dateien eines Repositorys sind Stufe M4: ``entfernen`` nimmt hier
nur den Eintrag aus der Liste. Ob installierte Dateien mitgehen,
entscheidet die Schicht, die M4 mitbringt.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from .core.identity import RepositoryIdentity, strip_suffix
from .core.validierung import KATEGORIEN

if TYPE_CHECKING:
    from .ablage import Ablage

_LOGGER = logging.getLogger(__name__)

#: Einstellfelder des Dialogs (Stufe M3).
CONF_ADRESSE = "adresse"
CONF_KATEGORIE = "kategorie"
CONF_ENTFERNEN = "entfernen"
CONF_DATEIEN_DEINSTALLIEREN = "dateien_deinstallieren"


class AdresseUngueltig(ValueError):
    """Die Eingabe reicht nicht, um ein Repository zu benennen."""


class BereitsVorhanden(ValueError):
    """Genau dieses Repository steht schon in der Liste."""


class NichtVorhanden(KeyError):
    """Dieses Repository steht nicht in der Liste."""


class KategorieUnbekannt(ValueError):
    """Die angegebene Kategorie gibt es nicht."""


def adresse_zerlegen(adresse: str) -> tuple[str, str]:
    """Aus einer vollen Adresse werden Host und Pfad (gruppe/projekt).

    Menschen fegen alles ein, was sie in der Hand haben: Links mit
    ``https://``, Klartext, Untergruppen, den Anzeigenamen mit ``*lab``,
    eine Clone-Endung ``.git``, Anhaengsel wie Anfragen und Fragmente.
    All das wird hier abgetrennt -- was uebrig bleibt, muss immer noch
    Host und mindestens ``gruppe/projekt`` sein, sonst heisst der Fehler
    beim Namen.
    """
    gereinigt = str(adresse or "").strip()
    for praefix in ("https://", "http://"):
        if gereinigt.startswith(praefix):
            gereinigt = gereinigt[len(praefix) :]
            break
    for trenner in ("#", "?"):
        gereinigt = gereinigt.split(trenner, 1)[0]
    if not gereinigt:
        raise AdresseUngueltig("die Adresse ist leer")

    host, *pfad_teile = gereinigt.split("/")
    host = host.strip().lower()
    if not host:
        raise AdresseUngueltig("die Adresse nennt keinen Host")
    if "@" in host:
        raise AdresseUngueltig(
            "das ist eine Clone-Adresse -- bitte die Web-Adresse der Projektseite"
        )
    if not pfad_teile:
        raise AdresseUngueltig("die Adresse nennt keinen Pfad, nur den Host")

    pfad = strip_suffix("/".join(teil.strip() for teil in pfad_teile if teil.strip()))
    if pfad.endswith(".git"):
        pfad = pfad[: -len(".git")]
    if "/" not in pfad:
        raise AdresseUngueltig(
            "der Pfad braucht die Form gruppe/projekt, nicht nur " + pfad
        )
    return host, pfad


def kategorie_aus_topics(topics: tuple[str, ...] | list[str] | None) -> str | None:
    """Vorbelegung der Kategorie aus den Topics des Projekts.

    Sagt der Besitzer mit ``hacs-<kategorie>`` (z. B. ``hacs-plugin``),
    was er plant, glaubt das der Dialog beim Anlegen. Ohne so ein Topic
    bleibt die Wahl beim Menschen -- ``integration`` ist der Normalfall,
    deshalb steht sie in KATEGORIEN zuerst.
    """
    menge = set(topics or ())
    for kategorie in KATEGORIEN:
        if "hacs-" + kategorie in menge:
            return kategorie
    return None


@dataclass(frozen=True)
class Eintrag:
    """Ein beobachtetes Custom Repository: Identitaet plus Kategorie."""

    identitaet: RepositoryIdentity
    kategorie: str
    hinzugefuegt_am: str = ""

    @property
    def storage_key(self) -> str:
        """Identitaetsschluessel -- inklusive Anbieter und Host."""
        return self.identitaet.storage_key

    @property
    def anzeigename(self) -> str:
        """Name fuer die Oberflaeche, z. B. ``gruppe/projekt*lab``."""
        return self.identitaet.display_full_name

    def as_dict(self) -> dict[str, str]:
        """Form fuer die Ablage; aus_dict kehrt sie um."""
        daten = self.identitaet.as_dict()
        daten["kategorie"] = self.kategorie
        daten["hinzugefuegt_am"] = self.hinzugefuegt_am
        return daten

    @classmethod
    def aus_dict(cls, roh: Any) -> Eintrag | None:
        """Liest einen gespeicherten Eintrag; Ungueltiges wird uebersprungen.

        Die Ablage kann aeltere oder fremde Formen enthalten. Statt das
        Richten ganz abbrechen zu lassen (Repair ist Stufe M8), wird der
        einzelne Eintrag uebersprungen und gemeldet.
        """
        if not isinstance(roh, dict):
            return None
        try:
            kategorie = str(roh["kategorie"])
            if kategorie not in KATEGORIEN:
                raise ValueError("unbekannte Kategorie: " + kategorie)
            return cls(
                identitaet=RepositoryIdentity.from_dict(roh),
                kategorie=kategorie,
                hinzugefuegt_am=str(roh.get("hinzugefuegt_am") or ""),
            )
        except (KeyError, TypeError, ValueError) as fehlschlag:
            _LOGGER.warning(
                "Eintrag in der Ablage unlesbar, uebersprungen: %s", fehlschlag
            )
            return None


class Eintraege:
    """Die Liste der Custom Repositories, persistiert in der Ablage.

    Alles, was die Liste veraendert, sichert sofort -- ein Abbruch mitten
    drin darf nie einen halben Stand hinterlassen.
    """

    def __init__(self, ablage: Ablage) -> None:
        self._ablage = ablage
        self._liste: list[Eintrag] = []
        self._beobachter: list[Callable[[str, Eintrag], None]] = []
        #: Wie viele gespeicherte Formen beim letzten Lesen unlesbar
        #: waren und daher fehlen (Stufe M8: Reparatur-Meldung).
        self.unlesbar = 0

    def melde_aenderungen(self, beobachter: Callable[[str, Eintrag], None]) -> None:
        """Laesst sich rufen, wenn die Liste waechst oder schrumpft.

        Stufe M5: die Entities einer Wabe sollen erscheinen und
        verschwinden, sobald jemand einen Eintrag anlegt oder loescht --
        ohne dass die Integration neu geladen werden muss. Der Beobachter
        wird im Ereigniskreis gerufen (alles hier ist eine Koroutine),
        er muss selbst dafuer sorgen, dass er schnell zurueckkehrt.
        """
        self._beobachter.append(beobachter)

    def _melden(self, art: str, eintrag: Eintrag) -> None:
        for beobachter in self._beobachter:
            beobachter(art, eintrag)

    @classmethod
    async def aus_ablage(cls, ablage: Ablage) -> Eintraege:
        """Laedt die Liste; unlesbare und doppelte Eintraege entfallen.

        Wie viele unlesbare Formen uebersprungen wurden, steht danach
        in :attr:`unlesbar` -- die Meldung dafuer ist Stufe M8 und
        gehoert dem Richten des Eintrags, nicht der Liste.
        """
        self = cls(ablage)
        daten = await ablage.laden()
        for roh in daten.get("eintraege") or []:
            eintrag = Eintrag.aus_dict(roh)
            if eintrag is None:
                self.unlesbar += 1
                continue
            if self._finde(eintrag.storage_key) is None:
                self._liste.append(eintrag)
        return self

    def alle(self) -> tuple[Eintrag, ...]:
        """Momentaufnahme der Liste, unveränderbar."""
        return tuple(self._liste)

    def __len__(self) -> int:
        return len(self._liste)

    def __iter__(self) -> Iterator[Eintrag]:
        return iter(self._liste)

    def _finde(self, storage_key: str) -> Eintrag | None:
        for eintrag in self._liste:
            if eintrag.storage_key == storage_key:
                return eintrag
        return None

    def finde(self, storage_key: str) -> Eintrag | None:
        """Der Eintrag zu diesem Schluessel -- oder None.

        Oeffentlich seit Stufe M8: die Waben zeigen Namen und Kategorie
        aus der Liste, damit ein nachgezogener Name sofort erscheint,
        nicht erst nach einem Neustart.
        """
        return self._finde(storage_key)

    async def nachziehen(self, storage_key: str, neuer_pfad: str) -> Eintrag | None:
        """Ersetzt den Namen eines Eintrags -- die Identitaet traegt (Stufe M8).

        Ein umbenanntes Projekt bleibt dasselbe: Anbieter, Host und
        ID unangetastet, nur der Name zieht nach. Der Schluessel aendert
        sich nicht -- Entities und Staende bleiben, wo sie sind. Die
        Beobachter hoeren ``nachgezogen`` mit dem NEUEN Eintrag.
        """
        alt = self._finde(storage_key)
        if alt is None:
            return None
        if neuer_pfad == alt.identitaet.full_name:
            return alt
        neu = Eintrag(
            identitaet=RepositoryIdentity(
                provider=alt.identitaet.provider,
                host=alt.identitaet.host,
                provider_id=alt.identitaet.provider_id,
                full_name=neuer_pfad,
            ),
            kategorie=alt.kategorie,
            hinzugefuegt_am=alt.hinzugefuegt_am,
        )
        stelle = self._liste.index(alt)
        self._liste[stelle] = neu
        await self._sichern()
        self._melden("nachgezogen", neu)
        return neu

    def vorhanden(self, storage_key: str) -> bool:
        """Steht genau dieses Repository (Anbieter, Host, ID) in der Liste?"""
        return self._finde(storage_key) is not None

    async def hinzufuegen(
        self, identitaet: RepositoryIdentity, kategorie: str
    ) -> Eintrag:
        """Nimmt ein Repository auf -- nach Pruefung, mit benannten Fehlern.

        Die Kategorie muss bekannt sein, und das Repository darf unter
        Anbieter, Host und Anbieter-ID noch nicht stehen. Der Name allein
        zaehlt nicht: dasselbe ``gruppe/projekt`` auf einem anderen Host
        ist ein anderes Repository und bleibt daneben bestehen.
        """
        if kategorie not in KATEGORIEN:
            raise KategorieUnbekannt("unbekannte Kategorie: " + kategorie)
        vorhanden = self._finde(identitaet.storage_key)
        if vorhanden is not None:
            raise BereitsVorhanden(
                vorhanden.anzeigename
                + " ("
                + vorhanden.kategorie
                + ") steht bereits in der Liste"
            )
        eintrag = Eintrag(
            identitaet=identitaet,
            kategorie=kategorie,
            hinzugefuegt_am=datetime.now(UTC).isoformat(),
        )
        self._liste.append(eintrag)
        await self._sichern()
        self._melden("hinzugefuegt", eintrag)
        return eintrag

    async def entfernen(self, storage_key: str) -> Eintrag:
        """Nimmt einen Eintrag aus der Liste.

        Installierte Dateien gehoeren nicht dazu -- das ist Stufe M4.
        Der Dialog kann die Entscheidung des Menschen mitgeben; hier
        zaehlt nur der Eintrag.
        """
        eintrag = self._finde(storage_key)
        if eintrag is None:
            raise NichtVorhanden(storage_key)
        self._liste.remove(eintrag)
        await self._sichern()
        self._melden("entfernt", eintrag)
        return eintrag

    async def _sichern(self) -> None:
        # sicher_teil statt sicher: die Ablage teilt sich seit Stufe M5
        # mit dem Stand der Eintraege -- ein ganzer Ersatz wuerde ihn loeschen.
        await self._ablage.sicher_teil(
            "eintraege", [eintrag.as_dict() for eintrag in self._liste]
        )
