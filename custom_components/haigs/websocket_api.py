"""Die Befehle der Oberflaeche -- Stufe M7.

Das Panel (``frontend/panel.js``) redet mit Home Assistant, nicht mit
der Welt: Diese Datei ist die ganze Schnittstelle zwischen beiden.
Sieben Befehle, mehr braucht kein Laden:

* ``haigs/eintraege`` -- die Liste der beobachteten Repositories,
  aus dem Lager gelesen (Flug 2084): sofort, ohne einen einzigen
  Netzruf. Steht das Lager noch leer (frische Einrichtung, der Start-
  Lauf noch nicht geschehen), wird es einmal live gebaut und danach
  ebenfalls aus dem Speicher gereicht. Funde, Stand und Instanzen
  reisen mit.
* ``haigs/erneuern`` -- der frische Lauf: jeder Aktualisierer wird
  herumgedreht, dann das Lager neu befuellt (Zeilen und Scan). Die
  Bedienung ruft das, sobald der Laden betreten wird -- die Liste
  haengt dann nicht am Takt. Scheiternde Teile reissen die Antwort
  nicht um: die Instanz steht mit Grund in ``gescheitert``, die Liste
  kommt trotzdem (aus dem letzten erfolgreichen Stand).
* ``haigs/entdecken`` -- der Scan aus Stufe M6: ganze Instanz oder
  Gruppe, Ergebnisliste mit allem, was die Oberflaeche zeigt
* ``haigs/detail`` -- Stammdaten, README und Releases eines
  Repositorys
* ``haigs/hinzufuegen`` -- ein Fund aufnehmen (derselbe Weg wie der
  Dialog: Identitaet klaeren, Kategorie pruefen, Eintrag anlegen)
* ``haigs/entfernen`` -- einen Eintrag aus der Liste nehmen
* ``haigs/deinstallieren`` -- Stufe M4b: die installierten Dateien
  wegnehmen, den verzeichneten Weg entlang. Home Assistants
  update-Entities kennen kein Uninstall -- deshalb ist das hier ein
  Befehl, nicht ein Dienst von ihnen.

Installieren und aktualisieren geht bewusst NICHT durch diese Datei:
dafuer gibt es die update-Entities aus Stufe M5 mit ihrem
install-Dienst. Das Panel ruft den ganz normalen Home-Assistant-Dienst
-- genau wie jede andere Oberflaeche auch. Die drei Befehle, die die
Liste veraendern (hinzufuegen, entfernen, deinstallieren), pflegen das
Lager gleich mit -- ohne Netz, die Stammdaten sind ja schon da.

Bahn-Disziplin aus #13: ``config_flow.py`` und ``eintraege.py`` werden
hier nicht angefasst, nur ihre oeffentlichen Stuecke aufgerufen. Der
Scan schreibt nichts (Stufe M6), die Aufnahme bleibt die Entscheidung
der Bedienung.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant

from .aktualisierer import hole_aktualisierer
from .const import DOMAIN
from .core.aktualisierungen import Pruefauftrag
from .core.aktualisierungen import lauf as kern_lauf
from .core.entdeckung import entdecke
from .core.forge import ForgeFehler, NichtGefunden
from .core.identity import SUFFIX, RepositoryIdentity
from .core.validierung import KATEGORIEN
from .core.zielpfade import ist_flach
from .eintraege import (
    BereitsVorhanden,
    KategorieUnbekannt,
    NichtVorhanden,
)
from .installation import (
    InstallationsFehler,
    deinstalliere_version,
    rekonstruiere_dateiliste,
)
from .lager import LagerFehler, _entity_id, zeile_aus_fund
from .neustart import neustart_hinweis
from .sichtbarkeit import anreichern

if TYPE_CHECKING:
    from homeassistant.components.websocket_api.connection import ActiveConnection

    from . import Laufzeit
    from .eintraege import Eintrag

_LOGGER = logging.getLogger(__name__)

#: Kandidaten fuer die Projektbeschreibung, in dieser Reihenfolge
#: gefragt. Dateinamen sind keine Anbieterkenntnis -- jede Forge hat
#: Dateien, die Reihenfolge ist schlicht Gewohnheit.
README_KANDIDATEN = ("README.md", "readme.md", "Readme.md", "README.rst")


def _laufzeiten(hass: HomeAssistant) -> dict[str, Laufzeit]:
    """Die eingerichteten Instanzen, nach Host geordnet.

    Mehrere Instanzen (gitlab.com und die eigene) stehen nebeneinander
    -- genau dafuer traegt der storage_key den Host. Die Oberflaeche
    bekommt sie alle zu sehen.
    """
    karte: dict[str, Laufzeit] = {}
    for laufzeit in hass.data.get("haigs", {}).values():
        forge = getattr(laufzeit, "forge", None)
        if forge is not None:
            karte[forge.host] = laufzeit
    return karte


def _laufzeit_nach_host(hass: HomeAssistant, host: str) -> Laufzeit | None:
    return _laufzeiten(hass).get(host)


def _anzeigename(full_name: str, provider: str) -> str:
    """Der Name mit Kennzeichnung -- der Suffix gehoert dem Anbieter.

    GitLab traegt ``*lab``, Forgejo ``*forge`` (Stufe M9). Die Stelle
    hier fragt nach, statt beides zu wissen.
    """
    return full_name + SUFFIX.get(provider, "")


async def _liste(hass: HomeAssistant) -> dict[str, Any]:
    """Die Antwort der Eintraege: alles aus den Lagern, ohne Netz.

    Zwei Befehle schicken sie -- ``eintraege`` direkt, ``erneuern``
    nach dem frischen Lauf. Beide greifen aufs Lager zu (Flug 2084):
    was gestern geholt wurde, steht heute sofort da, auch nach dem
    Neustart -- der Laden geht nicht mehr leer auf. Steht das Lager
    noch leer, obwohl Eintraege da sind, wird es einmal live gebaut
    (der ETag-Zwischenspeicher macht das wiederholt billig); danach
    kommt alles aus dem Speicher. Funde und Zeitstempel reisen mit,
    damit die Oberflaeche Alter und Herkunft zeigen kann.
    """
    zeilen: list[dict[str, Any]] = []
    funde: list[dict[str, Any]] = []
    staende_am: dict[str, str] = {}
    anbieter: dict[str, str] = {}
    entwicklung: dict[str, bool] = {}
    for host, laufzeit in sorted(_laufzeiten(hass).items()):
        anbieter[host] = laufzeit.forge.provider
        aktualisierer = getattr(laufzeit, "aktualisierer", None)
        entwicklung[host] = bool(
            aktualisierer is not None and getattr(aktualisierer, "entwicklermodus", False)
        )
        lager = getattr(laufzeit, "lager", None)
        if lager is None:
            continue
        if not lager.zeilen and laufzeit.eintraege.alle():
            await lager.live_uebernehmen()
        # Flug 2098: Kopien, nicht die Zeilen selbst -- der Zustands-Chip
        # (Neustart? geladen? eingerichtet?) ist eine Aussage ueber JETZT
        # und gehoert nicht ins Lager. Die Originale bleiben, wie der
        # Takt sie schrieb; die Antwort traegt die Wahrheit des Augen-
        # blicks dazu.
        zeilen.extend(dict(zeile) for zeile in lager.zeilen)
        funde.extend(
            dict(fund, gesehen=fund.get("full_name") in lager.gesehen)
            for fund in lager.funde
        )
        if lager.aktualisiert_am:
            staende_am[host] = lager.aktualisiert_am

    await anreichern(hass, zeilen)
    return {
        "eintraege": zeilen,
        "funde": funde,
        "instanzen": sorted(_laufzeiten(hass)),
        "anbieter": anbieter,
        "entwicklermodus": entwicklung,
        "kategorien": list(KATEGORIEN),
        "aktualisiert_am": staende_am,
    }


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "haigs/eintraege"})
@websocket_api.async_response
async def ws_eintraege(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Die Liste alles Beobachteten -- sofort, aus dem Lager.

    Flug 2084: kein einziger Netzruf hier. Was das Lager kennt, steht
    sofort da -- auch nach dem Neustart, auch ohne jeden Takt. Frische
    Werte (Sterne, Beschreibung, Funde) bringt der naechste volle
    Lauf, der beim Betritt oder im Takt geschieht und das Panel ueber
    das Ereignis zum Neuzeichnen bringt.
    """
    connection.send_result(msg["id"], await _liste(hass))


@websocket_api.require_admin
@websocket_api.websocket_command({vol.Required("type"): "haigs/erneuern"})
@websocket_api.async_response
async def ws_erneuern(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Der frische Lauf: Aktualisierer herumdrehen, Lager neu fuellen.

    Das Panel ruft das, sobald jemand den Laden betritt -- die Liste
    soll nicht am Takt haengen (der Minuten oder Stunden spaeter
    schlaegt). Der Lauf ist zweigeteilt: zuerst der M5-Lauf je
    Instanz (Stammdaten ueber die ID, Kern-Lauf, Reparaturen), dann
    der volle Lauf des Lagers (Zeilen ueber die ID, Scan der ganzen
    Instanz, Speichern und Ereignis). Instanzen ohne Aktualisierer
    (leere Liste, nie eine update-Entity) bekommen ihren ersten --
    :func:`hole_aktualisierer` legt ihn idempotent an.

    Ein scheiternder Teil reisst die Antwort nicht um: die Instanz
    steht mit Grund in ``gescheitert``, die Liste kommt trotzdem (aus
    dem letzten erfolgreichen Stand des Lagers).
    """
    gescheitert: dict[str, str] = {}
    eintraege_karte: dict[str, Any] = hass.data.get(DOMAIN, {})
    for eintrag_id, laufzeit in sorted(
        eintraege_karte.items(), key=lambda paar: paar[1].forge.host
    ):
        eintrag = hass.config_entries.async_get_entry(eintrag_id)
        if eintrag is None:
            continue
        aktualisierer = hole_aktualisierer(hass, eintrag)
        if aktualisierer is not None:
            await aktualisierer.async_refresh()
            if not aktualisierer.last_update_success:
                gescheitert[laufzeit.forge.host] = (
                    str(aktualisierer.last_exception)
                    if aktualisierer.last_exception is not None
                    else "unerwarteter Fehler"
                )
                _LOGGER.warning(
                    "Frischer Lauf fuer %s gescheitert: %s",
                    laufzeit.forge.host,
                    gescheitert[laufzeit.forge.host],
                )
        lager = getattr(laufzeit, "lager", None)
        if lager is not None:
            try:
                await lager.voller_lauf()
            except LagerFehler as fehler:
                gescheitert.setdefault(laufzeit.forge.host, str(fehler))
                _LOGGER.warning(
                    "Lager-Lauf fuer %s gescheitert: %s", laufzeit.forge.host, fehler
                )

    antwort = await _liste(hass)
    antwort["gescheitert"] = gescheitert
    connection.send_result(msg["id"], antwort)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/entdecken",
        vol.Required("host"): str,
        vol.Optional("gruppe", default=""): str,
        vol.Optional("stichwort", default=""): str,
        vol.Optional("mit_untergruppen", default=True): bool,
        vol.Optional("mit_entwicklung", default=False): bool,
    }
)
@websocket_api.async_response
async def ws_entdecken(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Die Suche hinter der Kopfsuche des Ladens: finden, nicht aufnehmen.

    Der Lauf schreibt nichts -- was davon in die Liste soll, entscheidet
    die Bedienung danach. Projekte mit ``hacs-development``-Topic
    bleiben aussen vor, ausser sie werden ausdruecklich gewuenscht.
    Eine Suche, deren Gruppe oder Stichwort niemand kennt, ist KEIN
    Fehler: sie zahlt ehrlich leere Funde -- die Kopfsuche darf
    falsch getippte Worte nicht als Instanz-Stoerung melden.
    """
    laufzeit = _laufzeit_nach_host(hass, str(msg["host"]))
    if laufzeit is None:
        connection.send_error(
            msg["id"], "unbekannte_instanz", str(msg["host"]) + " ist nicht eingerichtet"
        )
        return

    try:
        funde = await entdecke(
            laufzeit.forge,
            gruppe=str(msg["gruppe"]) or None,
            stichwort=str(msg["stichwort"]) or None,
            mit_untergruppen=bool(msg["mit_untergruppen"]),
            mit_vorab=bool(msg["mit_entwicklung"]),
        )
    except NichtGefunden:
        funde = []
    except ForgeFehler as fehler:
        connection.send_error(msg["id"], "forge_fehler", str(fehler))
        return

    ergebnis = [zeile_aus_fund(laufzeit, fund) for fund in funde]
    connection.send_result(msg["id"], {"funde": ergebnis})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/detail",
        vol.Required("host"): str,
        vol.Required("pfad"): str,
    }
)
@websocket_api.async_response
async def ws_detail(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stammdaten, README und Releases eines Repositorys.

    Die Beschreibung wird als Klartext geliefert und im Panel gerendert
    -- welches Format sie hat, entscheidet das Projekt, nicht wir. Die
    Liste der Releases ist die gleiche, die der Update-Lauf sieht.
    """
    laufzeit = _laufzeit_nach_host(hass, str(msg["host"]))
    if laufzeit is None:
        connection.send_error(
            msg["id"], "unbekannte_instanz", str(msg["host"]) + " ist nicht eingerichtet"
        )
        return
    pfad = str(msg["pfad"])

    try:
        info = await laufzeit.forge.repository(pfad)
    except NichtGefunden as fehler:
        connection.send_error(msg["id"], "nicht_gefunden", str(fehler))
        return
    except ForgeFehler as fehler:
        connection.send_error(msg["id"], "forge_fehler", str(fehler))
        return

    releases: list[dict[str, Any]] = []
    try:
        releases = [
            {
                "tag": release.tag,
                "name": release.name,
                "beschreibung": release.beschreibung,
                "veroeffentlicht_am": release.veroeffentlicht_am,
                "vorabversion": release.vorabversion,
            }
            for release in await laufzeit.forge.releases(pfad)
        ]
    except Exception as fehler:  # noqa: BLE001 - Releases fehlen, Rest bleibt
        _LOGGER.debug("Releases zu %s gescheitert: %s", pfad, fehler)

    readme: str | None = None
    readme_datei = ""
    for kandidat in README_KANDIDATEN:
        try:
            roh = await laufzeit.forge.datei(pfad, kandidat, info.standardzweig)
        except ForgeFehler:
            continue
        readme = roh.decode("utf-8", errors="replace")
        readme_datei = kandidat
        break

    connection.send_result(
        msg["id"],
        {
            "info": {
                "full_name": info.full_name,
                "name": _anzeigename(info.full_name, laufzeit.forge.provider),
                "beschreibung": info.beschreibung,
                "sterne": info.sterne,
                "offene_tickets": info.offene_tickets,
                "archiviert": info.archiviert,
                "topics": list(info.topics),
                "standardzweig": info.standardzweig,
                "web_url": info.web_url,
                "tickets_url": info.tickets_url,
                "releases_url": info.releases_url,
                "avatar_url": info.avatar_url,
            },
            "readme": readme,
            "readme_datei": readme_datei,
            "releases": releases,
        },
    )


async def _erster_fund(
    hass: HomeAssistant, laufzeit: Laufzeit, eintrag: Eintrag, pfad: str
) -> None:
    """Ein einzelner Pruefauftrag frisch nach dem Aufnehmen (Flug 2096).

    Der Weg fuehrt ueber die Fabrik des Aktualisierers -- sie legt die
    Spur an, falls noch keine Entity sie je geholt hat, und haengt sie
    an die Laufzeit. Das Einspeisen geschieht ueber
    ``async_set_updated_data``: der Bestand wachst um DEN einen Fund,
    der Rest bleibt stehen, und die Entities hoeren auf den Aufruf wie
    auf jeden Takt.
    """
    config_eintrag = None
    for entry_id, laufz in hass.data.get(DOMAIN, {}).items():
        if laufz is laufzeit:
            config_eintrag = hass.config_entries.async_get_entry(entry_id)
            break
    if config_eintrag is None:
        return
    aktualisierer = hole_aktualisierer(hass, config_eintrag)
    if aktualisierer is None:
        return
    stand = aktualisierer.staende.stand(eintrag.storage_key)
    auftrag = Pruefauftrag(
        schluessel=eintrag.storage_key,
        pfad=pfad,
        installiert=stand.installiert,
        mit_vorabversionen=stand.vorabversionen,
        entwicklung=aktualisierer.entwicklermodus,
    )
    try:
        funde = await kern_lauf(laufzeit.forge, [auftrag])
    except Exception as fehlschlag:  # noqa: BLE001 - Zugabe, keine Pflicht
        _LOGGER.debug(
            "Erster Fund zu %s gescheitert (der Takt kommt, wie er immer kam): %s",
            pfad,
            fehlschlag,
        )
        return
    fund = funde.get(eintrag.storage_key)
    if fund is None:
        return
    bestand = dict(aktualisierer.data or {})
    bestand[eintrag.storage_key] = fund
    aktualisierer.async_set_updated_data(bestand)


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/hinzufuegen",
        vol.Required("host"): str,
        vol.Required("pfad"): str,
        vol.Required("kategorie"): str,
    }
)
@websocket_api.async_response
async def ws_hinzufuegen(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Ein Repository aufnehmen -- derselbe Weg wie der Dialog aus M3.

    Identitaet klaeren (ein einziger API-Abruf, wie im Dialog), dann
    der Liste uebergeben: doppelte storage_key werden abgewiesen,
    unbekannte Kategorien ebenso. Die update-Entity entsteht durch den
    Beobachter aus Stufe M5 von selbst -- ohne Neustart.
    """
    laufzeit = _laufzeit_nach_host(hass, str(msg["host"]))
    if laufzeit is None:
        connection.send_error(
            msg["id"], "unbekannte_instanz", str(msg["host"]) + " ist nicht eingerichtet"
        )
        return
    pfad = str(msg["pfad"])

    try:
        info = await laufzeit.forge.repository(pfad)
    except NichtGefunden as fehler:
        connection.send_error(msg["id"], "nicht_gefunden", str(fehler))
        return
    except ForgeFehler as fehler:
        connection.send_error(msg["id"], "forge_fehler", str(fehler))
        return

    identitaet = RepositoryIdentity(
        provider=laufzeit.forge.provider,
        host=laufzeit.forge.host,
        provider_id=info.provider_id,
        full_name=info.full_name,
    )
    try:
        eintrag = await laufzeit.eintraege.hinzufuegen(identitaet, str(msg["kategorie"]))
    except BereitsVorhanden as fehler:
        connection.send_error(msg["id"], "bereits_vorhanden", str(fehler))
        return
    except KategorieUnbekannt as fehler:
        connection.send_error(msg["id"], "kategorie_unbekannt", str(fehler))
        return

    _LOGGER.info(
        "Custom Repository ueber die Oberflaeche aufgenommen: %s (%s)",
        eintrag.anzeigename,
        eintrag.kategorie,
    )
    # Der Beobachter aus Stufe M5 legt die update-Entity gleich an; noch
    # einen Herzschlag warten, dann kennt die Registry die Nummer.
    await hass.async_block_till_done()
    # Flug 2084: der neue Eintrag steht sofort im Lager -- die Stammdaten
    # sind schon geholt, kein weiterer Ruf noetig.
    lager = getattr(laufzeit, "lager", None)
    if lager is not None:
        await lager.zeile_hinzu(eintrag, info)

    # Flug 2096, Wunde 3a aus dem 3-System-Test: der erste Fund reist
    # mit. Ohne ihn bleibt die neueste Version der update-Entity leer
    # bis zum naechsten Takt -- und ein sofortiger Install-Ruf endet
    # in Home Assistants "No update available", weil der Dienst dort
    # installiert gegen neueste vergleicht, BEVOR er uns fragt. Ein
    # einzelner Auftrag (nicht der ganze Takt) bringt die Antwort in
    # den Bestand des Aktualisierers; die Entities zeichnen darauf von
    # selbst neu. Misslingt der Fund (Netz, Rechte), bleibt alles beim
    # alten -- der Takt kommt, wie er immer kam.
    await _erster_fund(hass, laufzeit, eintrag, pfad)
    connection.send_result(
        msg["id"],
        {
            "eintrag": {
                "storage_key": eintrag.storage_key,
                "name": eintrag.anzeigename,
                "kategorie": eintrag.kategorie,
                "host": laufzeit.forge.host,
                "entity_id": _entity_id(hass, eintrag.storage_key),
            }
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/entfernen",
        vol.Required("storage_key"): str,
    }
)
@websocket_api.async_response
async def ws_entfernen(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Einen Eintrag aus der Liste nehmen -- installierte Dateien bleiben.

    Dateien mitzuentfernen ist Stufe M4 (und wird dort ehrlich
    geloest); hier verschwindet nur die Beobachtung. Die zugehoerige
    update-Entity nimmt der Beobachter aus Stufe M5 mit.
    """
    schluessel = str(msg["storage_key"])
    for laufzeit in _laufzeiten(hass).values():
        if not laufzeit.eintraege.vorhanden(schluessel):
            continue
        try:
            entfernt = await laufzeit.eintraege.entfernen(schluessel)
        except NichtVorhanden as fehler:
            connection.send_error(msg["id"], "nicht_mehr_da", str(fehler))
            return
        _LOGGER.info(
            "Custom Repository ueber die Oberflaeche entfernt: %s",
            entfernt.anzeigename,
        )
        lager = getattr(laufzeit, "lager", None)
        if lager is not None:
            await lager.zeile_weg(entfernt)
        connection.send_result(
            msg["id"], {"entfernt": entfernt.anzeigename, "host": laufzeit.forge.host}
        )
        return

    connection.send_error(
        msg["id"], "nicht_mehr_da", schluessel + " steht in keiner Liste"
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/deinstallieren",
        vol.Required("storage_key"): str,
    }
)
@websocket_api.async_response
async def ws_deinstallieren(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Installierte Dateien entfernen -- den verzeichneten Weg (M4b).

    Der Eintrag bleibt in der Liste (dafuer gibt es ``entfernen``);
    hier verschwinden nur die Dateien, und der Stand vergisst Version
    und Weg. Ohne verzeichneten Weg (installiert vor M4b) kommt die
    ehrliche Ansage: erst neu installieren, dann laesst sich auch
    sauber entfernen.

    Review zu !50, Befund 2: ein Altbestand aus 0.6.3 (Wurzel
    verzeichnet, keine Dateiliste) ist keine Sackgasse mehr -- die
    Liste wird aus dem Archiv der installierten Version
    rekonstruiert (nur INHALTSGLEICHE Dateien gelten als eigene) und
    VOR dem Entfernen verzeichnet: schlaegt das Entfernen mittendrin
    ab, laesst es sich wiederholen.
    """
    schluessel = str(msg["storage_key"])
    for laufzeit in _laufzeiten(hass).values():
        eintrag = laufzeit.eintraege.finde(schluessel)
        if eintrag is None:
            continue
        stand = laufzeit.staende.stand(schluessel)
        if not stand.installiert and not stand.dateien:
            # Ein Bruchstueck ohne Version (Review zu !50, Befund 1) ist
            # trotzdem ein ehrlicher Grund aufzuraeumen -- die Liste ist
            # ja verzeichnet, nur die Version kam nie ganz an.
            connection.send_error(msg["id"], "nichts_installiert", "nichts installiert")
            return
        if not stand.pfad:
            connection.send_error(
                msg["id"],
                "kein_weg",
                "kein installierter Pfad verzeichnet (installiert vor M4b?) "
                "-- einmal neu installieren, dann laesst sich auch "
                "entfernen",
            )
            return
        dateien = stand.dateien
        if not dateien and ist_flach(eintrag.kategorie):
            # Altbestand aus 0.6.3 -- die Liste fehlt, der Weg fuehrt
            # ueber das Archiv der installierten Version.
            try:
                dateien = await rekonstruiere_dateiliste(
                    hass, laufzeit.forge, eintrag, stand.installiert
                )
            except (InstallationsFehler, ForgeFehler) as fehlschlag:
                connection.send_error(
                    msg["id"],
                    "altbestand_unlesbar",
                    "die Dateiliste des Altbestands laesst sich nicht mehr "
                    "rekonstruieren ("
                    + str(fehlschlag)
                    + ") -- einmal neu installieren, dann laesst sich auch "
                    "sauber entfernen",
                )
                return
            if not dateien:
                connection.send_error(
                    msg["id"],
                    "altbestand_leer",
                    "keine Datei in "
                    + stand.pfad
                    + " ist mit der installierten Version inhaltsgleich -- "
                    "veraenderte oder fremde Dateien bleiben liegen, die "
                    "Wurzel gehoert allen",
                )
                return
            # Vor dem Entfernen verzeichnet: ein Abbruch dazwischen ist
            # wiederholbar, kein Neubeginn.
            await laufzeit.staende.setzen(schluessel, dateien=list(dateien))
        try:
            await deinstalliere_version(hass, stand.pfad, dateien=dateien)
        except InstallationsFehler as fehlschlag:
            connection.send_error(
                msg["id"], "deinstallation_fehlgeschlagen", str(fehlschlag)
            )
            return
        await laufzeit.staende.setzen(schluessel, installiert="", pfad="", dateien=[])
        lager = getattr(laufzeit, "lager", None)
        if lager is not None:
            await lager.stand_geaendert(schluessel, installiert="", zielweg="")
        neustart_hinweis(
            hass, eintrag, stand.installiert, "deinstallation", pfad=stand.pfad
        )
        _LOGGER.info(
            "Custom Repository ueber die Oberflaeche deinstalliert: %s",
            eintrag.anzeigename,
        )
        connection.send_result(
            msg["id"], {"deinstalliert": eintrag.anzeigename, "host": laufzeit.forge.host}
        )
        return

    connection.send_error(
        msg["id"], "nicht_mehr_da", schluessel + " steht in keiner Liste"
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "haigs/gesehen",
        vol.Required("host"): str,
        vol.Required("pfad"): str,
    }
)
@websocket_api.async_response
async def ws_gesehen(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Ein Fund wurde geoeffnet -- er faellt aus "Neu" (wie das new-Flag bei HACS)."""
    laufzeit = _laufzeit_nach_host(hass, str(msg["host"]))
    lager = getattr(laufzeit, "lager", None) if laufzeit is not None else None
    if lager is None:
        connection.send_error(msg["id"], "unbekannte_instanz", str(msg["host"]))
        return
    if not await lager.fund_gesehen(str(msg["pfad"])):
        connection.send_error(msg["id"], "nicht_gefunden", str(msg["pfad"]))
        return
    connection.send_result(msg["id"], {"host": msg["host"], "pfad": msg["pfad"]})


#: Alle Befehle dieser Datei -- ``__init__.py`` meldet sie der Reihe nach an.
BEFEHLE = (
    ws_eintraege,
    ws_erneuern,
    ws_entdecken,
    ws_detail,
    ws_hinzufuegen,
    ws_entfernen,
    ws_deinstallieren,
    ws_gesehen,
)
