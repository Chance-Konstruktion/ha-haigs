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
    await antwort.content.read(n) -> bytes

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

Grenzen hat auch die Antwort selbst (Ticket #23): ein Archiv wird
gestueckelt und gedeckelt geladen -- angekuendigte Ueberlaenge fliegt
vor dem ersten Block, unangekuendigte beim Lesen. Und eine
``Retry-After``-Bitte hat einen Deckel, kennt aber die Datumsform.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import urlsplit

from .forge import ForgeFehler, NichtGefunden

#: Wartezeit in Sekunden, wenn der Anbieter bei 429 keine vorgibt.
STANDARD_WARTEZEIT = 1.0

#: Obergrenze fuer eine vom Anbieter verlangte Wartezeit (Ticket #23).
#: Der Anbieter darf um Geduld bitten, aber die Integration nicht
#: stundenlang stilllegen -- danach wird erneut gefragt, und die
#: ``warte_versuche`` bleiben endlich.
HOECHSTE_WARTEZEIT = 60.0

#: Obergrenze fuer eine geladene Antwort in Bytes (Ticket #23).
#: Entspricht der Gesamtgrenze des Entpackers -- was er entpacken
#: wuerde, darf auch geladen werden; mehr aber waechst nicht
#: unbegrenzt in den Speicher.
HOECHSTE_ANTWORT_BYTES = 256 * 1024 * 1024

#: Groesse eines Leseblocks beim gestueckelten Laden.
LESEBLOCK = 64 * 1024


def _host_und_port(adresse: str) -> tuple[str, int] | None:
    """(Host klein, wirksamer Port) einer Adresse -- fuer den Vergleich
    "ist das der eigene Forge-Host?" (Ticket #20).

    ``host`` ohne Schema ist erlaubt (so steht es in der Konfiguration);
    der Standardport wird je Schema ergaenzt, damit ``forge.example``
    und ``forge.example:443`` derselbe Host sind. Gross/Klein und ein
    Punkt am Ende spielen keine Rolle. ``None``, wenn kein Host dasteht
    -- dann reist kein Token.
    """
    text = adresse.strip()
    if "//" not in text:
        text = "//" + text
    teile = urlsplit(text)
    host = (teile.hostname or "").rstrip(".").lower()
    if not host:
        return None
    port = teile.port
    if port is None:
        port = 443 if teile.scheme != "http" else 80
    return host, port


def _ganzzahl(roh: str | None) -> int | None:
    """Eine Kopfzeilen-Zahl, oder ``None`` -- fremde Formen sind kein Fehler."""
    try:
        return int(roh or "")
    except (TypeError, ValueError):
        return None


def _sekunden_aus_retry_after(roh: str) -> float | None:
    """``Retry-After`` in Sekunden -- Zahl oder HTTP-Datum, sonst ``None``.

    Die Datumsform darf auch ohne Zeitzone kommen; dann gilt UTC. Ein
    Zeitpunkt, der schon vorbei ist, ergibt einen negativen Wert --
    der Aufrufer deckelt ihn nach unten auf null.
    """
    try:
        return float(roh)
    except ValueError:
        pass
    try:
        zeitpunkt = parsedate_to_datetime(roh)
    except (TypeError, ValueError):
        return None
    if zeitpunkt is None:
        return None
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=UTC)
    return (zeitpunkt - datetime.now(UTC)).total_seconds()


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


class Inhalt(Protocol):
    """Was der Klient vom Antwortkoerper braucht: gestueckeltes Lesen.

    ``aiohttp`` liefert das als ``antwort.content`` -- so kann der
    Klient eine Obergrenze ziehen, ohne etwas vorauszusetzen, was die
    Sitzung nicht ohnehin anbietet (Ticket #23).
    """

    async def read(self, anzahl: int = -1) -> bytes: ...


class Antwort(Protocol):
    """Was der Klient von einem Antwortobjekt braucht."""

    status: int
    headers: Mapping[str, str]
    content: Inhalt

    async def text(self) -> str: ...


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


#: So meldet sich HAIGS bei jedem Abruf.
BENUTZERKENNUNG = "HAIGS (+https://github.com/Chance-Konstruktion/ha-haigs)"


class AiohttpClient:
    """HttpClient auf einer hereingereichten aiohttp-Sitzung.

    :param sitzung: Sitzung nach dem aiohttp-Massstab, siehe Moduldoku.
    :param token: optionaler Lesetoken. Oeffentliche Projekte gehen ohne;
        er reist als ``Authorization``-Kopfzeile, nie in der URL.
    :param token_host: der Host der konfigurierten Forge. Das Token
        reist NUR dorthin (Ticket #20): Release-Anhaenge duerfen auf
        fremde Adressen zeigen, und ein Token ohne genannten Host wird
        deshalb abgelehnt statt ueberall mitgeschickt.
    :param warte: Ersatz fuer ``asyncio.sleep`` -- vor allem fuer Tests.
    :param warte_versuche: wie oft bei 429 nochmal versucht wird.
    :param max_seiten: Obergrenze beim Verfolgen von ``X-Next-Page``.
    :param max_bytes: Obergrenze fuer eine geladene Antwort (Ticket #23).
    """

    def __init__(
        self,
        sitzung: Sitzung,
        token: str | None = None,
        warte: Callable[[float], Awaitable[None]] | None = None,
        warte_versuche: int = 3,
        max_seiten: int = 200,
        token_host: str | None = None,
        max_bytes: int = HOECHSTE_ANTWORT_BYTES,
    ) -> None:
        if max_bytes <= 0:
            raise ValueError(f"max_bytes muss positiv sein: {max_bytes!r}")
        self.sitzung = sitzung
        if token and not token_host:
            raise ValueError(
                "ein Token ohne token_host wuerde an jede Adresse reisen "
                "(Ticket #20) — den Host der Forge mitgeben"
            )
        self._token = token or None
        self._token_host = _host_und_port(token_host) if token_host else None
        if token and self._token_host is None:
            raise ValueError(f"token_host ohne Host: {token_host!r}")
        # Wer abfragt, nennt sich: die Betreiber von Katalog und Forges
        # sehen sonst nur "HomeAssistant/aiohttp" und keinen Absender.
        self._kopfzeilen: dict[str, str] = {"User-Agent": BENUTZERKENNUNG}
        self._warte = warte or asyncio.sleep
        self.warte_versuche = warte_versuche
        self.max_seiten = max_seiten
        self.max_bytes = max_bytes
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
            url, params, self._kopfzeilen_mit_etag(url, schluessel)
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
                antwort, kopf = await self._anfordern(
                    url, params, self._kopfzeilen_fuer(url)
                )
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
        """Holt rohe Bytes, mit demselben ETag-Zwischenspeicher.

        Gelesen wird gestueckelt und gedeckelt (Ticket #23): eine
        angekuendigte Ueberlaenge wird abgewiesen, bevor der erste
        Block im Speicher landet; ohne Ankuendigung bricht das Lesen
        ab, sobald die Grenze ueberschritten ist. Erst ein
        vollstaendiges, erlaubtes Lesen fuellt den Zwischenspeicher --
        ein abgebrochener Download ist keine gueltige Antwort.
        """
        schluessel: _Schluessel = url
        antwort, kopf = await self._anfordern(
            url, None, self._kopfzeilen_mit_etag(url, schluessel)
        )
        if antwort.status == 304:
            return _kopie(self._aus_speicher(schluessel, url))
        self._pruefen(url, antwort.status, kopf)
        daten = await self._mit_grenze_lesen(url, kopf, antwort)
        etag = kopf.get("etag")
        if etag:
            self._etags[schluessel] = etag
            self._speicher[schluessel] = daten
        return daten

    async def _mit_grenze_lesen(
        self, url: str, kopf: dict[str, str], antwort: Antwort
    ) -> bytes:
        """Der Antwortkoerper, gestueckelt und gedeckelt (Ticket #23)."""
        angekuendigt = _ganzzahl(kopf.get("content-length"))
        if angekuendigt is not None and angekuendigt > self.max_bytes:
            raise ForgeFehler(
                f"{url} kuendigt {angekuendigt} Bytes an, die Obergrenze "
                f"ist {self.max_bytes} -- nicht geladen"
            )
        block = min(LESEBLOCK, self.max_bytes)
        stuecke: list[bytes] = []
        gelesen = 0
        while True:
            stueck = await antwort.content.read(block)
            if not stueck:
                break
            gelesen += len(stueck)
            if gelesen > self.max_bytes:
                raise ForgeFehler(
                    f"{url} liefert mehr als {self.max_bytes} Bytes -- "
                    "abgebrochen, ohne den Rest zu laden"
                )
            stuecke.append(stueck)
        return b"".join(stuecke)

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

    def _kopfzeilen_fuer(self, url: str) -> dict[str, str]:
        """Die Kopfzeilen fuer eine Adresse.

        Der Absender reist immer mit; das Token nur zum eigenen
        Forge-Host (Ticket #20) -- sonst reist es nirgends mit.
        """
        kopfzeilen = dict(self._kopfzeilen)
        if self._token is not None and _host_und_port(url) == self._token_host:
            kopfzeilen["Authorization"] = "Bearer " + self._token
        return kopfzeilen

    def _kopfzeilen_mit_etag(self, url: str, schluessel: _Schluessel) -> dict[str, str]:
        kopfzeilen = self._kopfzeilen_fuer(url)
        etag = self._etags.get(schluessel)
        if etag:
            kopfzeilen["If-None-Match"] = etag
        return kopfzeilen

    def _wartezeit(self, kopf: dict[str, str]) -> float:
        """``Retry-After`` in Sekunden; fehlt er, gilt eine hoefliche Sekunde.

        Zwei Formen sind erlaubt (RFC 9110): die Zahl der Sekunden und
        ein HTTP-Datum. Das Datum wurde vorher zum ``ValueError`` und
        fiel still auf die hoefliche Sekunde zurueck -- jetzt wird es
        gelesen und zum Abstand bis jetzt gerechnet (Ticket #23).
        Gedeckelt wird beides: ``Retry-After: 3600`` waere eine Stunde
        Stillstand fuer einen einzigen Fehlversuch.
        """
        roh = (kopf.get("retry-after") or "").strip()
        if not roh:
            return STANDARD_WARTEZEIT
        sekunden = _sekunden_aus_retry_after(roh)
        if sekunden is None:
            return STANDARD_WARTEZEIT
        return min(HOECHSTE_WARTEZEIT, max(0.0, sekunden))

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
