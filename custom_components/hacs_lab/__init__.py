"""Home-Assistant-Schicht von HACS*lab (Stufe M2: das Geruest).

Die Trennung ist Absicht und Architektur-Entscheidung: alles, was ohne
Home Assistant auskommt, liegt in ``core/`` innerhalb dieser
Integration (Form-Entscheidung zu #11, ARCHITEKTUR.md Entscheidung 5)
und bleibt dort ohne HA-Installation testbar. Diese Schicht hier macht
nichts Eigenes -- sie reicht Home Assistants aiohttp-Sitzung an den
HTTP-Klienten weiter (ARCHITEKTUR.md, Entscheidung 3) und haengt die
Bausteine des Kerns an einander.

Wie diese Integration den Kern findet: ueberhaupt nicht suchen. Der
Kern ist ein Unterpaket dieser Integration; die Importe sind relativ
(``from .core.forge import ...``), der Suchpfad bleibt unberuehrt.
Egal ob Entwicklungs-Check-out, entpackter Release oder Handkopie --
das Verzeichnis, das die Integration enthaelt, enthaelt auch den Kern.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import homeassistant.util.dt as dt_util
from homeassistant.components import websocket_api as ha_websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.issue_registry import IssueSeverity
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .ablage import Ablage
from .aktualisierer import _kennung
from .const import (
    ABLAGE_VERSION,
    CONF_ABSTAND_MINUTEN,
    CONF_HOST,
    CONF_PROVIDER,
    CONF_TOKEN,
    DOMAIN,
    LAGER_START_VERZOEGERUNG_SEK,
    STANDARD_ABSTAND_MINUTEN,
    ablage_schluessel,
)
from .core.forge import Forge, ForgeFehler
from .core.http_aiohttp import AiohttpClient
from .core.identity import GITLAB
from .core.schmiede import schmiede
from .eintraege import Eintraege
from .frontend import richten as oberflaeche_richten
from .lager import Lager
from .websocket_api import BEFEHLE

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Einmal je Laden der Komponente: die Oberflaeche (Stufe M7).

    WebSocket-Befehle und Panel werden hier angemeldet, nicht je
    Eintrag -- sie gehoeren der Integration, nicht der Instanz. Das
    Panel bleibt in der Sidebar stehen, auch wenn die letzte Instanz
    entfernt wird; die Liste zeigt dann ehrlich Leere. Der Alias beim
    Import ist Absicht: unser Modul heisst genauso wie das von Home
    Assistant (uebliche Namensgebung fuer Befehl-Dateien).
    """
    await oberflaeche_richten(hass)
    for befehl in BEFEHLE:
        ha_websocket_api.async_register_command(hass, befehl)
    _neustart_hinweise_aufraeumen(hass)
    return True


def _neustart_hinweise_aufraeumen(hass: HomeAssistant) -> None:
    """M4b: ausstehende Neustart-Hinweise gelten mit diesem Laden als erledigt.

    Die Hinweise entstehen, wenn eine Integration installiert oder
    deinstalliert wurde (Stufe M4b): Home Assistant laedt
    ``custom_components`` nur beim Start. Diese Zeile laeuft genau dann,
    wenn genau das passiert ist -- also ist jeder Neustart-Hinweis damit
    historisch. Ohne das Stuendchen wuerde der erste Hinweis fuer immer
    auf dem Reparatur-Brett stehen.
    """
    register = issue_registry.async_get(hass)
    for bereich, kennung in list(register.issues):
        if bereich == DOMAIN and kennung.startswith("neustart_"):
            issue_registry.async_delete_issue(hass, DOMAIN, kennung)


class HacsLabKoordinator(DataUpdateCoordinator[dict[str, int | str]]):
    """Herzschlag gegen die Instanz.

    M2 fragt hier nur, was ohnehin gefragt wird: die Projekte zum Topic
    ``hacs``. Das beweist Sitzung, Token und API auf jedem Takt und
    haelt die Instanz warm -- M5 haengt an dieselbe Stelle die echten
    Update-Laeufe.
    """

    def __init__(self, hass: HomeAssistant, eintrag: ConfigEntry, forge: Forge) -> None:
        minuten = int(
            eintrag.options.get(CONF_ABSTAND_MINUTEN) or STANDARD_ABSTAND_MINUTEN
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=eintrag,
            name=f"{DOMAIN}_{forge.host}",
            update_interval=timedelta(minutes=minuten),
        )
        self.forge = forge

    async def _async_update_data(self) -> dict[str, int | str]:
        try:
            funde = await self.forge.suche_nach_topic()
        except ForgeFehler as fehler:
            raise UpdateFailed(str(fehler)) from fehler
        except Exception as fehler:
            # Breit gefasst mit Absicht: ein stockender Takt darf Home
            # Assistant nie umwerfen, nur einen Wiederholungsversuch
            # ausloesen.
            raise UpdateFailed(f"unerwarteter Fehler: {fehler}") from fehler
        return {
            "instanz": self.forge.host,
            "gefundene_projekte": len(funde),
        }


@dataclass
class Laufzeit:
    """Was ein eingerichteter Eintrag im Arbeitsspeicher braucht.

    Seit Stufe M3 gehoert die Liste der Custom Repositories dazu: sie
    wird beim Richten aus der Ablage gelesen und bleibt fuer den
    Optionsdialog greifbar. Das Lager (Flug 2084) haengt als Naht
    dynamisch dazu -- dieselbe Form wie ``staende`` und
    ``aktualisierer``, bis M0.5 die Form der Laufzeit geklaert hat.
    """

    forge: Forge
    koordinator: HacsLabKoordinator
    ablage: Ablage
    eintraege: Eintraege
    lager: Lager | None = None


def _meldung_unlesbare_ablage(hass: HomeAssistant, host: str, anzahl: int) -> None:
    """Stufe M8: uebersprungene Eintraege gehoeren aufs Reparatur-Brett.

    Frueher war das nur eine Warnung im Protokoll -- unsichtbar fuer jeden,
    der nicht gerade hinschaut. Jetzt steht es als Meldung da, solange
    die Ablage Unlesbares enthaelt, und verschwindet, sobald das Richten
    wieder sauber liest. Entfernt wird nichts: Uebersprungenes bleibt in
    der Datei liegen, bis die Liste das naechste Mal sichert (dann
    schreibt sie nur noch Lesbares).
    """
    meldung = "ablage_unlesbar_" + _kennung(host)
    if anzahl > 0:
        issue_registry.async_create_issue(
            hass,
            DOMAIN,
            meldung,
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="ablage_unlesbar",
            translation_placeholders={"host": host, "anzahl": str(anzahl)},
        )
    else:
        issue_registry.async_delete_issue(hass, DOMAIN, meldung)


async def async_setup_entry(hass: HomeAssistant, eintrag: ConfigEntry) -> bool:
    """Eintrag richten: Sitzung, Klient, Forge, Ablage, Herzschlag.

    Der erste Herzschlag entscheidet: schlaegt er fehl, meldet sich der
    Eintrag als "nicht bereit" und Home Assistant versucht spaeter
    erneut -- ehrlicher als ein scheinbar eingerichteter Eintrag ohne
    Verbindung.
    """
    sitzung = async_get_clientsession(hass)
    klient = AiohttpClient(sitzung, eintrag.data.get(CONF_TOKEN) or None)
    # Die Schmiede formt den Forge nach dem Namen im Eintrag (Flug
    # 2088). Eintraege aus der Zeit davor tragen keinen -- dann gilt
    # GitLab, die einzige Schmiedung, die es damals gab; das Verhalten
    # dieser Eintraege bleibt Stueck fuer Stueck dasselbe.
    forge = schmiede(
        klient, eintrag.data[CONF_HOST], eintrag.data.get(CONF_PROVIDER) or GITLAB
    )

    ablage = Ablage(
        Store(hass, ABLAGE_VERSION, ablage_schluessel(eintrag.data[CONF_HOST]))
    )
    # Geladen und gleich gehalten: Frueher verfiel das Ergebnis hier,
    # die Liste der Eintraege blieb unlesbar -- seit Stufe M3 gehoert
    # sie in die Laufzeit (Nachschau zu #13).
    eintraege = await Eintraege.aus_ablage(ablage)
    _meldung_unlesbare_ablage(hass, forge.host, eintraege.unlesbar)

    koordinator = HacsLabKoordinator(hass, eintrag, forge)
    await koordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[eintrag.entry_id] = laufzeit = Laufzeit(
        forge=forge, koordinator=koordinator, ablage=ablage, eintraege=eintraege
    )
    # Flug 2084: das Lager wird beim Richten aus dem Speicher gelesen
    # -- der Laden ist nach dem Neustart sofort voll, auch bevor der
    # erste volle Lauf ueberhaupt stattfand. Der Start-Lauf kommt
    # verzuegert (unten), der Takt haelt das Lager danach frisch.
    lager = Lager(hass, eintrag, laufzeit)
    await lager.laden()
    laufzeit.lager = lager
    # Stufe M5: die Waben des Vorhabens -- eine update-Entity je Eintrag
    # samt Vorab-Schalter. Erst nach dem Herzschlag: steht die Verbindung
    # nicht, gibt es nichts zu beobachten, und der Eintrag meldet sich
    # ohnehin als nicht bereit.
    await hass.config_entries.async_forward_entry_setups(eintrag, ("update", "switch"))
    eintrag.async_on_unload(eintrag.add_update_listener(_abstand_geaendert))

    @callback
    def _erster_lauf(_jetzt: Any) -> None:
        """Der Start-Lauf des Lagers -- im Hintergrund, ohne Eile."""
        hass.async_create_task(lager.async_refresh())

    eintrag.async_on_unload(
        async_track_point_in_utc_time(
            hass,
            _erster_lauf,
            dt_util.utcnow() + timedelta(seconds=LAGER_START_VERZOEGERUNG_SEK),
        )
    )
    _LOGGER.info("HACS*lab eingerichtet fuer %s", forge.host)
    return True


async def async_unload_entry(hass: HomeAssistant, eintrag: ConfigEntry) -> bool:
    """Eintrag abmelden. Die Sitzung gehoert Home Assistant und bleibt."""
    laufzeit: Laufzeit | None = hass.data.get(DOMAIN, {}).pop(eintrag.entry_id, None)
    waben_entladen = await hass.config_entries.async_unload_platforms(
        eintrag, ("update", "switch")
    )
    if laufzeit is not None:
        await laufzeit.koordinator.async_shutdown()
        aktualisierer = getattr(laufzeit, "aktualisierer", None)
        if aktualisierer is not None:
            await aktualisierer.async_shutdown()
        if laufzeit.lager is not None:
            await laufzeit.lager.async_shutdown()
    return waben_entladen


async def _abstand_geaendert(hass: HomeAssistant, eintrag: ConfigEntry) -> None:
    """Optionswechsel ohne Neustart: alle Takte werden neu gesetzt."""
    laufzeit: Laufzeit | None = hass.data.get(DOMAIN, {}).get(eintrag.entry_id)
    if laufzeit is None:
        return
    minuten = int(eintrag.options.get(CONF_ABSTAND_MINUTEN) or STANDARD_ABSTAND_MINUTEN)
    laufzeit.koordinator.update_interval = timedelta(minutes=minuten)
    if laufzeit.lager is not None:
        laufzeit.lager.update_interval = timedelta(minutes=minuten)
    _LOGGER.info("Abstand fuer %s auf %s Minuten gesetzt", laufzeit.forge.host, minuten)
    # Flug 2101: der Entwicklermodus wechselt, was "neueste" heisst --
    # also gleich frisch pruefen, und das Lager zieht hinterher.
    aktualisierer = getattr(laufzeit, "aktualisierer", None)
    if aktualisierer is not None:
        hass.async_create_task(_frisch_nach_optionen(aktualisierer, laufzeit.lager))


async def _frisch_nach_optionen(aktualisierer: Any, lager: Any) -> None:
    """Ein Lauf nach dem Optionswechsel, danach das Lager."""
    await aktualisierer.async_refresh()
    if lager is not None:
        try:
            await lager.voller_lauf()
        except Exception as fehler:  # noqa: BLE001 - der Takt holt es nach
            _LOGGER.debug("Lager nach Optionswechsel gescheitert: %s", fehler)
