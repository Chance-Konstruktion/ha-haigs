"""HTTP-Zugang auf der aiohttp-Sitzung.

Umsetzung von :class:`~forge.HttpClient`. Die Sitzung wird
hineingereicht und nicht importiert -- dieselbe Verkehrung, die auch den
Kern frei von Home Assistant haelt (ARCHITEKTUR.md, Entscheidung 3).
In Home Assistant kommt die Sitzung spaeter von
``homeassistant.helpers.aiohttp_client``, in den Tests ist es eine
Attrappe, die aufgezeichnete Antworten abspielt. Deshalb importiert
dieses Modul keine HTTP-Bibliothek: Es spricht nur die Schnittstelle an,
die eine aiohttp-Sitzung ohnehin bietet.

Von der Sitzung wird genau dies verlangt::

    antwort = await sitzung.get(url, params=..., headers=...)
    antwort.status                    # int
    antwort.headers                   # Abbildung, Gross-/Kleinschreibung egal
    await antwort.text() -> str
    await antwort.read() -> bytes

Nach der Vereinbarung aus ``forge.py`` kennt der Kern keine Statuscodes
-- die Uebersetzung wohnt hier: 404 wirft :class:`NichtGefunden`, bei
401/403 gibt es Klartext (Token fehlt oder reicht nicht), bei 429 wird
die verlangte Wartezeit beachtet und nochmal versucht. Ausserdem wohnen
hier zwei Dinge, die der Kern nicht wissen soll: das Verfolgen der
Seiten ueber ``X-Next-Page`` und ein ETag-Zwischenspeicher
(``If-None-Match``), damit ein Update-Lauf ueber viele Repos nicht
jedes Mal alles neu holt.

Zwei bewusste Grenzen des Zwischenspeichers: Nur Antworten, die auf
einer Seite auskamen, werden gespeichert -- ein mehrseitiges Ergebnis
kann sich zwischen den Seiten aendern, also wird es immer neu geholt.
Und wer den Zwischenspeicher loswerden will, baut einen neuen Klienten;
die Sitzung gehoert dem Aufrufer und wird von hier nie geschlossen.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from typing import Protocol

from .forge import ForgeFehler, NichtGefunden

#: Wartezeit in Sekunden, wenn der Anbieter bei 429 keine vorgibt.
STANDARD_WARTEZEIT = 1.0


class KeinJson(ForgeFehler):
    """Der Server antwortete 200, aber nicht mit JSON.

    Fuer die meisten Aufrufer ist das ein gewoehnlicher Fehler. Nur
    die Schmiede hoert genauer hin: 200-mit-HTML ist kein verriegeltes
    GitLab-Tor (401/403), sondern ein Captive Portal oder ein Proxy,
    der vor der Instanz sitzt -- so eine Adresse ist KEIN GitLab,
    auch wenn die Statuszeile es fast verspricht.
    """


class TorVerriegelt(ForgeFehler):
    """401/403 -- das Tor ist da, aber der Schluessel fehlt oder reicht nicht.

    Nur dieser Fall duerfen die Schmiede als "hier wohnt ein GitLab"
    lesen: GitLab verschliesst seine Versionsfrage, Gitea und Forgejo
    404en sie. Ein 500 oder ein 429 ist KEIN Beweis fuer GitLab --
    bis Flug 2093 zaehlte jeder ForgeFehler als verriegeltes Tor,
    und ein halbtoter Server haette als GitLab gegolten.
    """


_Schluessel = str | tuple[str, tuple[tuple[str, str], ...]]


class Antwort(Protocol):
    """Was der Klient von einem Antwortobjekt braucht."""

    status: int
    headers: Mapping[str, str]

    async def text(self) -> str: ...

    async def read(self) -> bytes: ...


class Sitzung(Protocol):
    """Was der Klient von der aiohttp-Sitzung braucht."""

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Antwort: ...


def _kopie(daten):
    """Schutz fuer den Zwischenspeicher: nie dasselbe Objekt herausgeben."""
    if isinstance(daten, list):
        return list(daten)
    if isinstance(daten, dict):
        return dict(daten)
    return daten


class AiohttpClient:
    """HttpClient auf einer hereingereichten aiohttp-Sitzung.

    :param sitzung: Sitzung nach dem aiohttp-Massstab, siehe Moduldoku.
    :param token: optionaler Lesetoken. Oeffentliche Projekte gehen ohne;
        er reist als ``Authorization``-Kopfzeile, nie in der URL.
    :param warte: Ersatz fuer ``asyncio.sleep`` -- vor allem fuer Tests.
    :param warte_versuche: wie oft bei 429 nochmal versucht wird.
    :param max_seiten: Obergrenze beim Verfolgen von ``X-Next-Page``.
    """

    def __init__(
        self,
        sitzung: Sitzung,
        token: str | None = None,
        warte: Callable[[float], Awaitable[None]] | None = None,
        warte_versuche: int = 3,
        max_seiten: int = 200,
    ) -> None:
        self.sitzung = sitzung
        self._kopfzeilen: dict[str, str] = {}
        if token:
            self._kopfzeilen["Authorization"] = "Bearer " + token
        self._warte = warte or asyncio.sleep
        self.warte_versuche = warte_versuche
        self.max_seiten = max_seiten
        self._etags: dict[_Schluessel, str] = {}
        self._speicher: dict[_Schluessel, object] = {}

    # -- die vereinbarte Schnittstelle --------------------------------

    async def get_json(
        self,
        url: str,
        params: dict[str, str] | None = None,
        *,
        seiten: int | None = None,
    ):
        """Holt JSON; Listen werden ueber ``X-Next-Page`` ganz geholt.

        Ein in ``params`` bereits gesetztes ``page`` gilt als Startseite.

        ``seiten`` begrenzt das Weiterblaettern fuer diesen einen Aufruf.
        ``seiten=1`` holt genau eine Seite. Ohne Angabe gilt weiterhin
        ``max_seiten`` -- die Obergrenze gegen Endlosschleifen, nicht
        gegen Menge.
        """
        params = dict(params or {})
        schluessel: _Schluessel = (url, tuple(sorted(params.items())))
        antwort, kopf = await self._anfordern(
            url, params, self._kopfzeilen_mit_etag(schluessel)
        )
        if antwort.status == 304:
            return _kopie(self._aus_speicher(schluessel, url))
        self._pruefen(url, antwort.status, kopf)
        daten = await self._als_json(url, antwort)

        if isinstance(daten, list):
            naechste = kopf.get("x-next-page", "")
            gesehene_seiten = 1
            while naechste not in ("", "0", None):
                if seiten is not None and gesehene_seiten >= seiten:
                    # Die gewollte Grenze ist erreicht. Kein Fehler:
                    # der Aufrufer hat genau das bestellt.
                    break
                if naechste == params.get("page"):
                    raise ForgeFehler(
                        f"Seitennummer von {url} wiederholt sich: {naechste!r}"
                    )
                if gesehene_seiten >= self.max_seiten:
                    # Die Notbremse gegen Endlosschleifen bleibt scharf --
                    # wer keine Grenze nennt, will die ganze Liste, und eine
                    # Liste ohne Ende ist ein Fehler, kein Ergebnis.
                    raise ForgeFehler(f"{url} liefert mehr als {self.max_seiten} Seiten")
                params["page"] = naechste
                antwort, kopf = await self._anfordern(url, params, self._kopfzeilen)
                self._pruefen(url, antwort.status, kopf)
                seite = await self._als_json(url, antwort)
                if not isinstance(seite, list):
                    raise ForgeFehler(f"Seite {naechste} von {url} ist keine Liste")
                daten.extend(seite)
                gesehene_seiten += 1
                naechste = kopf.get("x-next-page", "")
            if gesehene_seiten > 1:
                # Mehrseitiges wird bewusst nicht gespeichert: zwischen zwei
                # Seiten kann sich die Liste aendern.
                self._etags.pop(schluessel, None)
                self._speicher.pop(schluessel, None)
                return daten

        etag = kopf.get("etag")
        if etag:
            self._etags[schluessel] = etag
            self._speicher[schluessel] = _kopie(daten)
        else:
            self._etags.pop(schluessel, None)
            self._speicher.pop(schluessel, None)
        return daten

    async def get_bytes(self, url: str) -> bytes:
        """Holt rohe Bytes, mit demselben ETag-Zwischenspeicher."""
        schluessel: _Schluessel = url
        antwort, kopf = await self._anfordern(
            url, None, self._kopfzeilen_mit_etag(schluessel)
        )
        if antwort.status == 304:
            return _kopie(self._aus_speicher(schluessel, url))
        self._pruefen(url, antwort.status, kopf)
        daten = await antwort.read()
        etag = kopf.get("etag")
        if etag:
            self._etags[schluessel] = etag
            self._speicher[schluessel] = daten
        return daten

    # -- intern -------------------------------------------------------

    async def _anfordern(
        self, url: str, params: dict[str, str] | None, kopfzeilen: dict[str, str]
    ) -> tuple[Antwort, dict[str, str]]:
        """Ein Abruf; bei 429 wird die verlangte Wartezeit beachtet."""
        versuch = 0
        while True:
            antwort = await self.sitzung.get(url, params=params, headers=kopfzeilen)
            kopf = {name.lower(): wert for name, wert in antwort.headers.items()}
            if antwort.status != 429 or versuch >= self.warte_versuche:
                return antwort, kopf
            await self._warte(self._wartezeit(kopf))
            versuch += 1

    def _kopfzeilen_mit_etag(self, schluessel: _Schluessel) -> dict[str, str]:
        kopfzeilen = dict(self._kopfzeilen)
        etag = self._etags.get(schluessel)
        if etag:
            kopfzeilen["If-None-Match"] = etag
        return kopfzeilen

    def _wartezeit(self, kopf: dict[str, str]) -> float:
        """``Retry-After`` in Sekunden; fehlt er, gilt eine hoefliche Sekunde."""
        try:
            return float(kopf.get("retry-after", ""))
        except (TypeError, ValueError):
            return STANDARD_WARTEZEIT

    def _pruefen(self, url: str, status: int, kopf: dict[str, str]) -> None:
        """Wirft die vereinbarte Ausnahme, wenn der Status keine Arbeit zulaesst."""
        if status == 200:
            return
        if status == 404:
            raise NichtGefunden(f"nicht gefunden: {url}")
        if status in (401, 403):
            raise TorVerriegelt(f"Token fehlt oder reicht nicht (HTTP {status}): {url}")
        if status == 429:
            sekunden = kopf.get("retry-after", "?")
            raise ForgeFehler(
                f"HTTP 429: {sekunden} Sekunden verlangt, "
                f"nach {self.warte_versuche} Versuchen abgebrochen: {url}"
            )
        raise ForgeFehler(f"unerwartete Antwort HTTP {status}: {url}")

    def _aus_speicher(self, schluessel: _Schluessel, url: str):
        if schluessel not in self._speicher:
            raise ForgeFehler(f"HTTP 304 ohne ETag-Speicher: {url}")
        return self._speicher[schluessel]

    async def _als_json(self, url: str, antwort: Antwort):
        text = await antwort.text()
        try:
            return json.loads(text)
        except ValueError as fehler:
            raise KeinJson(f"Antwort von {url} ist kein JSON: {text[:50]!r}") from fehler
