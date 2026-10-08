"""Das Lager: der Zwischenspeicher des Ladens (Flug 2084).

Der Befund des Imkers war unmissverstaendlich: der Laden ging leer
auf -- beim Betreten stand nichts da, bis jemand den Knopf drueckte,
und nach dem Neustart war alles weg. Die Liste haengt aber nicht am
Takt des Aktualisierers: sie soll voll sein, wenn jemand sie betritt.

Das Lager ist die Antwort: je Instanz eine Datei im Home-Assistant-
Speicher, die die Zeilen der Liste und die Funde des letzten Scans
haelt. Drei Kraefte halten es frisch:

* der Start -- LAGER_START_VERZOEGERUNG_SEK nach dem Richten laeuft
  der erste volle Lauf im Hintergrund (der Laden liest vorher den
  Speicher und ist trotzdem sofort voll);
* der Takt -- im selben Abstand wie Herzschlag und Aktualisierer
  (Option ``abstand_minuten``) laeuft der volle Lauf erneut;
* der Betritt -- ``haigs/erneuern`` (Panel-Oeffnung und Knopf)
  dreht alles sofort herum, siehe ``websocket_api.py``.

Ein scheiternder Teil reisst den Lauf nicht um: Stammdaten, die nicht
kommen, lassen die alte Zeile stehen; ein gescheiterter Scan laesst
die alten Funde. Erst wenn gar nichts kommt, gilt der Lauf als
gescheitert (Wiederholung ueber den Koordinator). Nach jedem Schreiben
feuert das Lager sein Ereignis -- das Panel malt daraufhin von selbst
neu, auch waehrend es offen bleibt.

Die Zeilen hier sind abgeleitetes Wissen: die Ablage bleibt die
Wahrheit (Eintraege, Staelle); alles im Lager laesst sich aus Instanz
und Ablage wiederherstellen. Deshalb ist es eine eigene Datei mit
eigenem Schluessel -- ein geloeschtes Lager ist kein Datenverlust,
nur ein leerer Laden fuer einen Moment.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_ABSTAND_MINUTEN,
    DOMAIN,
    EREIGNIS_AKTUALISIERT,
    LAGER_VERSION,
    STANDARD_ABSTAND_MINUTEN,
    lager_schluessel,
)
from .core.entdeckung import entdecke
from .eintraege import kategorie_aus_topics

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import Laufzeit
    from .core.forge import RepositoryInfo
    from .eintraege import Eintrag

_LOGGER = logging.getLogger(__name__)


class LagerFehler(Exception):
    """Der ganze Lauf scheiterte -- Instanz oder Netz."""


def _entity_id(hass: HomeAssistant, storage_key: str) -> str | None:
    """Die update-Entity eines Eintrags, wie Home Assistant sie nennt."""
    registry = er.async_get(hass)
    return registry.async_get_entity_id("update", "haigs", storage_key)


def _fund_anteil(laufzeit: Laufzeit, storage_key: str) -> dict[str, str]:
    """Was der letzte M5-Lauf zu diesem Eintrag wusste (leer, wenn nichts)."""
    aktualisierer = getattr(laufzeit, "aktualisierer", None)
    daten = aktualisierer.data if aktualisierer is not None else None
    fund = (daten or {}).get(storage_key)
    if fund is None or fund.fehler is not None:
        return {}
    return {
        "neueste": fund.neueste,
        "tag": fund.tag,
        "veroeffentlicht_am": fund.veroeffentlicht_am,
    }


def zeile_aus_eintrag(
    hass: HomeAssistant,
    laufzeit: Laufzeit,
    eintrag: Eintrag,
    info: RepositoryInfo | None,
    alt: dict[str, Any] | None = None,
    grund: str = "",
) -> dict[str, Any]:
    """Eine Zeile der Liste: Identitaet, Stand, Fund und Stammdaten.

    Kommen die Stammdaten nicht (Netz, Rechte, geloeschtes Projekt),
    greift die alte Zeile -- ein Moment Stocken ist besser als eine
    karte, die plotzlich ohne Beschreibung und Zeichen dasteht. Ganz
    ohne alte Zeile steht der Grund als Fehlertext darauf, wie ihn
    auch der frische Blick aus Stufe M7 trug.
    """
    zeile: dict[str, Any] = {
        "storage_key": eintrag.storage_key,
        "name": eintrag.anzeigename,
        "pfad": eintrag.identitaet.full_name,
        "kategorie": eintrag.kategorie,
        "host": laufzeit.forge.host,
        "hinzugefuegt_am": eintrag.hinzugefuegt_am,
        "entity_id": _entity_id(hass, eintrag.storage_key),
    }
    zeile.update(_fund_anteil(laufzeit, eintrag.storage_key))
    staende = getattr(laufzeit, "staende", None)
    stand = staende.stand(eintrag.storage_key) if staende is not None else None
    zeile["installiert"] = stand.installiert if stand else ""
    # Flug 2098: der verzeichnete Zielweg reist mit -- die Sichtbarkeit
    # (Zustand der Installation: Neustart? geladen? eingerichtet?) liest
    # ihn, ohne die Ablage selbst zu befragen. Fehlt er, bleibt er leer
    # -- installiert vor Stufe M4b, der Zustand heisst dann "ungewiss".
    zeile["zielweg"] = stand.pfad if stand else ""
    if info is not None:
        grund = ""
        zeile.update(
            {
                "beschreibung": info.beschreibung,
                "sterne": info.sterne,
                "offene_tickets": info.offene_tickets,
                "web_url": info.web_url,
                "tickets_url": info.tickets_url,
                "releases_url": info.releases_url,
                "avatar_url": info.avatar_url,
                "downloads": info.downloads,
            }
        )
    elif alt is not None:
        # Stammdaten ausgeblieben: die alte Zeile traegt Kosmetik weiter.
        for feld in (
            "beschreibung",
            "sterne",
            "offene_tickets",
            "web_url",
            "tickets_url",
            "releases_url",
            "avatar_url",
            "downloads",
        ):
            if feld in alt:
                zeile[feld] = alt[feld]
        if not grund:
            grund = str(alt.get("fehler") or "")
    zeile["fehler"] = grund
    return zeile


def zeile_aus_fund(laufzeit: Laufzeit, fund: Any) -> dict[str, Any]:
    """Eine Zeile der Funde: der Scan aus Stufe M6, fuer die Liste."""
    info = fund.info
    return {
        "full_name": info.full_name,
        "name": fund.anzeigename,
        "beschreibung": info.beschreibung,
        "sterne": info.sterne,
        "offene_tickets": info.offene_tickets,
        "letzte_version": fund.letzte_version,
        "kategorie": kategorie_aus_topics(info.topics) or "integration",
        "gueltig": fund.befund.gueltig,
        "fehler": "; ".join(fund.befund.fehler),
        "vorhanden": laufzeit.eintraege.vorhanden(fund.identitaet.storage_key),
        "web_url": info.web_url,
        "tickets_url": info.tickets_url,
        "releases_url": info.releases_url,
        "avatar_url": info.avatar_url,
        "downloads": info.downloads,
        "zuletzt_aktiv": info.zuletzt_aktiv,
        "host": laufzeit.forge.host,
    }


def _zeilen_roh(roh: Any) -> list[dict[str, Any]]:
    """Nimmt nur Karten, die Karten sein koennen (tolerantes Lesen)."""
    if not isinstance(roh, list):
        return []
    return [zeile for zeile in roh if isinstance(zeile, dict)]


class Lager(DataUpdateCoordinator[dict[str, Any]]):
    """Der Zwischenspeicher einer Instanz -- Takt, Speicher, Ereignis.

    Der Koordinator-Takt ist derselbe wie bei Herzschlag und Aktuali-
    sierer (Option ``abstand_minuten``). Der ERSTE Lauf kommt nicht
    beim Richten (das wuerde das Hochfahren blockieren), sondern
    ueber die Start-Verzoegerung aus ``__init__.py`` -- danach haengt
    das Lager am Takt.
    """

    def __init__(
        self, hass: HomeAssistant, eintrag: ConfigEntry, laufzeit: Laufzeit
    ) -> None:
        minuten = int(
            eintrag.options.get(CONF_ABSTAND_MINUTEN) or STANDARD_ABSTAND_MINUTEN
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=eintrag,
            name=f"{DOMAIN}_lager_{laufzeit.forge.host}",
            update_interval=timedelta(minutes=minuten),
        )
        self._laufzeit = laufzeit
        self._store = Store(hass, LAGER_VERSION, lager_schluessel(laufzeit.forge.host))
        #: Der stille Zuhoerer, der den Takt haelt (s. _async_refresh_
        #: finished) -- seine Abmeldung verwaist mit dem Lager selbst.
        self._takthalter: Callable[[], None] | None = None
        #: Die Zeilen der Liste (eintraege) -- vollstaendig, wie das
        #: Panel sie zeigt.
        self.zeilen: list[dict[str, Any]] = []
        #: Die Funde des letzten Scans (funde) -- die ganze Instanz.
        self.funde: list[dict[str, Any]] = []
        #: Welche Funde der Nutzer schon geoeffnet hat (full_name) -- wie
        #: bei HACS faellt das new-Flag beim Oeffnen, dauerhaft.
        self.gesehen: set[str] = set()
        #: Wann das Lager zuletzt geschrieben wurde (ISO).
        self.aktualisiert_am: str = ""
        self.data = self.antwort()

    @callback
    def _async_refresh_finished(self) -> None:
        """Der Takt bleibt scharf, auch ohne Zuhoerer (Flug 2084).

        Der Koordinator von Home Assistant haengt seinen Takt an
        Zuhoerer -- Entities, die zuhoeren wollen. Das Lager hat keine:
        es laeuft fuer den Laden, nicht fuer eine Entity. Also haelt es
        sich nach dem ersten Lauf selbst einen stillen Zuhoerer, und
        ab da kuemmert sich der Koordinator um jeden weiteren Takt,
        ganz ohne weiteres Zutun. Erst nach dem ersten Lauf bewusst:
        der Start-Termin aus ``__init__.py`` soll der Erste bleiben,
        nicht schon der Takt von der Richten-Stunde.
        """
        if self._takthalter is None and not self.hass.is_stopping:
            self._takthalter = self.async_add_listener(lambda: None)

    # -- Lesen und Schreiben -----------------------------------------

    async def laden(self) -> None:
        """Liest das Lager aus dem Speicher -- der Griff ohne Netz.

        Das ist der Grund, warum der Laden nach dem Neustart nicht
        leer aufgeht: das Richten laedt diese Datei, und das Panel
        malt daraus, bevor irgendein Lauf stattfand.
        """
        roh = await self._store.async_load()
        if not isinstance(roh, dict):
            return
        self.zeilen = _zeilen_roh(roh.get("eintraege"))
        self.funde = _zeilen_roh(roh.get("funde"))
        gesehen = roh.get("gesehen")
        self.gesehen = (
            {str(n) for n in gesehen if isinstance(n, str)}
            if isinstance(gesehen, list)
            else set()
        )
        self.aktualisiert_am = str(roh.get("aktualisiert_am") or "")
        self.data = self.antwort()

    def antwort(self) -> dict[str, Any]:
        """Der Anteil dieser Instanz an der Antwort der Liste."""
        return {
            "eintraege": self.zeilen,
            "funde": self.funde,
            "aktualisiert_am": self.aktualisiert_am,
            "host": self._laufzeit.forge.host,
        }

    async def _sichern(self) -> None:
        """Schreibt das Lager und feuert das Ereignis fuer das Panel."""
        await self._store.async_save(
            {
                "eintraege": self.zeilen,
                "funde": self.funde,
                "gesehen": sorted(self.gesehen),
                "aktualisiert_am": self.aktualisiert_am,
            }
        )
        self.data = self.antwort()
        self.hass.bus.async_fire(
            EREIGNIS_AKTUALISIERT,
            {"host": self._laufzeit.forge.host, "aktualisiert_am": self.aktualisiert_am},
        )

    async def fund_gesehen(self, full_name: str) -> bool:
        """Merkt einen geoeffneten Fund -- er ist danach nicht mehr "neu".

        Gibt False zurueck, wenn der Scan diesen Fund nicht kennt.
        Geschrieben wird still, ohne Ereignis: die Oberflaeche sortiert
        die Zeile selbst um.
        """
        if not any(f.get("full_name") == full_name for f in self.funde):
            return False
        if full_name not in self.gesehen:
            self.gesehen.add(full_name)
            await self._store.async_save(
                {
                    "eintraege": self.zeilen,
                    "funde": self.funde,
                    "gesehen": sorted(self.gesehen),
                    "aktualisiert_am": self.aktualisiert_am,
                }
            )
        return True

    def _finde(self, storage_key: str) -> dict[str, Any] | None:
        for zeile in self.zeilen:
            if zeile.get("storage_key") == storage_key:
                return zeile
        return None

    # -- Die Laeufe ---------------------------------------------------

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.voller_lauf()
        except LagerFehler as fehler:
            raise UpdateFailed(str(fehler)) from fehler

    async def voller_lauf(self) -> dict[str, Any]:
        """Der frische Lauf: Zeilen ueber die ID, dann der ganze Scan.

        Stammdaten je Eintrag laufen ueber die ID -- der stabile Weg
        aus Stufe M8, und der ETag-Zwischenspeicher macht die Wieder-
        holung billig. Der Scan durchsucht die ganze Instanz (dieselben
        Voreinstellungen wie die Suchzeile im Abschnitt Neu: kein
        Gruppenfilter, mit Untergruppen, ohne Entwicklungsvorab).
        Fund (neueste Version) und Stand (installiert) kommen aus dem
        letzten Lauf des Aktualisierers -- derselbe Takt haelt sie
        frisch.

        Misslingt der Scan, bleiben die alten Funde stehen; misslingt
        eine einzelne Zeile, traegt die alte ihre Kosmetik weiter.
        Misslingt ALLES, gilt der Lauf als gescheitert und der
        Koordinator wiederholt ihn.
        """
        laufzeit = self._laufzeit
        stammdaten_ok = 0
        zeilen: list[dict[str, Any]] = []
        for eintrag in laufzeit.eintraege.alle():
            info = None
            grund = ""
            try:
                info = await laufzeit.forge.repository_nach_id(
                    eintrag.identitaet.provider_id
                )
                stammdaten_ok += 1
            except Exception as fehler:  # noqa: BLE001 - s. Moduldoku
                grund = str(fehler) or fehler.__class__.__name__
                _LOGGER.debug(
                    "Stammdaten zu %s gescheitert: %s", eintrag.anzeigename, grund
                )
            zeilen.append(
                zeile_aus_eintrag(
                    self.hass,
                    laufzeit,
                    eintrag,
                    info,
                    alt=self._finde(eintrag.storage_key),
                    grund=grund,
                )
            )

        scan_grund = ""
        try:
            funde = await entdecke(laufzeit.forge)
            self.funde = [zeile_aus_fund(laufzeit, fund) for fund in funde]
        except Exception as fehler:  # noqa: BLE001 - alte Funde bleiben
            scan_grund = str(fehler) or fehler.__class__.__name__
            _LOGGER.warning(
                "Scan von %s gescheitert: %s", laufzeit.forge.host, scan_grund
            )

        eintraege_da = bool(laufzeit.eintraege.alle())
        alles_tot = bool(scan_grund) and (
            (eintraege_da and stammdaten_ok == 0) or (not eintraege_da and not self.funde)
        )
        if alles_tot:
            raise LagerFehler(scan_grund)

        self.zeilen = zeilen
        self.aktualisiert_am = dt_util.utcnow().isoformat()
        await self._sichern()
        return self.antwort()

    async def live_uebernehmen(self) -> None:
        """Einmal live bauen -- der Notausgang fuer ein leeres Lager.

        Kommt die Liste zum ersten Mal daher (frische Einrichtung,
        der Start-Lauf noch nicht geschehen), baut dieser Lauf die
        Zeilen frisch ueber den Pfad -- wie es die Liste vor dem Lager
        tat. Kein Scan: der gehoert in den vollen Lauf, und der Betritt
        rueckt ihn ohnehin nach.
        """
        laufzeit = self._laufzeit
        zeilen: list[dict[str, Any]] = []
        for eintrag in laufzeit.eintraege.alle():
            info = None
            grund = ""
            try:
                info = await laufzeit.forge.repository(eintrag.identitaet.full_name)
            except Exception as fehler:  # noqa: BLE001 - s. Moduldoku
                grund = str(fehler) or fehler.__class__.__name__
                _LOGGER.debug(
                    "Stammdaten zu %s gescheitert: %s", eintrag.anzeigename, grund
                )
            zeilen.append(
                zeile_aus_eintrag(self.hass, laufzeit, eintrag, info, grund=grund)
            )
        self.zeilen = zeilen
        self.aktualisiert_am = dt_util.utcnow().isoformat()
        await self._sichern()

    # -- Mutationen: das Lager folgt der Liste sofort -----------------

    async def zeile_hinzu(self, eintrag: Eintrag, info: RepositoryInfo) -> None:
        """Ein frisch aufgenommener Eintrag steht sofort im Lager.

        Die Stammdaten sind schon da (die Aufnahme holte sie), also
        kostet der Griff kein Netz. Der Fund des Scans, falls er
        dasselbe Projekt nennt, dreht seine ``vorhanden``-Flagge.
        """
        zeile = zeile_aus_eintrag(
            self.hass,
            self._laufzeit,
            eintrag,
            info,
            alt=self._finde(eintrag.storage_key),
        )
        self.zeilen = [
            z for z in self.zeilen if z.get("storage_key") != eintrag.storage_key
        ]
        self.zeilen.append(zeile)
        for fund in self.funde:
            if fund.get("full_name") == eintrag.identitaet.full_name:
                fund["vorhanden"] = True
        await self._sichern()

    async def zeile_weg(self, eintrag: Eintrag) -> None:
        """Der entfernte Eintrag verschwindet aus dem Lager."""
        self.zeilen = [
            z for z in self.zeilen if z.get("storage_key") != eintrag.storage_key
        ]
        for fund in self.funde:
            if fund.get("full_name") == eintrag.identitaet.full_name:
                fund["vorhanden"] = False
        await self._sichern()

    async def stand_geaendert(
        self, storage_key: str, installiert: str, zielweg: str | None = None
    ) -> None:
        """Der Stand einer Zeile zieht nach (Deinstallation, Stufe M4b).

        Flug 2098: ``zielweg`` None laesst den Weg stehen (Installation
        kennt ihn, die Deinstallation loescht ihn mit). Beide Felder
        wandern zusammen -- ein Weg ohne Version waer gelogen, eine
        Version ohne Weg heisst "ungewiss".
        """
        for zeile in self.zeilen:
            if zeile.get("storage_key") == storage_key:
                zeile["installiert"] = installiert
                if zielweg is not None:
                    zeile["zielweg"] = zielweg
        await self._sichern()
