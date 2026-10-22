"""Ticket #23 -- Robustheit (HA-Schicht): Lager, erster Lauf, Unload, Herzschlag.

Vier der sieben Punkte des Sammeltickets brauchen Home Assistant:
das Lager-Rennen (Punkt 1), der erste Lauf bei lauter Fehlern
(Punkt 2), das Aufraeumen nach fehlgeschlagenem Entladen (Punkt 3)
und der Herzschlag, der ohne Zuhoerer nicht weitertaktete (Punkt 4).
Die drei Kern-Punkte (Retry-After, Zielname, Download-Grenze) stehen
in ``tests/test_robustheit_23.py``.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
)

from custom_components.haigs import HaigsKoordinator, async_unload_entry
from custom_components.haigs.const import (
    DOMAIN,
    STANDARD_ABSTAND_MINUTEN,
)
from custom_components.haigs.core.gitlab_forge import GitLabForge
from custom_components.haigs.core.http_aiohttp import AiohttpClient
from custom_components.haigs.core.identity import RepositoryIdentity
from custom_components.haigs.eintraege import Eintrag
from custom_components.haigs.lager import Lager
from tests.attrappe import Aufzeichnung, SitzungsAttrappe

from .test_m5 import (
    eintrag_daten,
    mock_eintrag,
    speichern,
    stammdaten,
)
from .test_m7 import richten


def herzschlag() -> Aufzeichnung:
    return Aufzeichnung(text="[]", kopfzeilen={})


# -- Punkt 4: der Herzschlag taktet ohne Entity ----------------------


async def test_herzschlag_taktet_ohne_entity_von_selbst_weiter(
    hass: HomeAssistant,
) -> None:
    """Der Koordinator hatte keinen Zuhoerer -- HA plante keinen Folgetakt.

    ``abstand_minuten`` verspricht einen Takt; ohne Zuhoerer liest
    niemand ``koordinator.data``, und der Takt bleibt aus. Gemessen
    wird ueber die Attrappe: ein zweiter Abruf nach dem Vorlauf
    beweist den Folgetakt.
    """
    attrappe = SitzungsAttrappe([herzschlag(), herzschlag()])
    mock = mock_eintrag()
    mock.add_to_hass(hass)
    forge = GitLabForge(
        AiohttpClient(attrappe, token_host="gitlab.example.net"),
        "gitlab.example.net",
    )
    koordinator = HaigsKoordinator(hass, mock, forge)

    await koordinator.async_refresh()
    assert len(attrappe.abrufe) == 1

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(minutes=STANDARD_ABSTAND_MINUTEN + 1)
    )
    await hass.async_block_till_done()

    assert len(attrappe.abrufe) == 2, "der Herzschlag muss von selbst weitertakten"


# -- Punkt 2: ein einziger fehlerhafter Eintrag kostet nicht die Entity --


async def test_ein_einziger_fehlerhafter_eintrag_ergibt_trotzdem_eine_entity(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """Alle Funde fehlerhaft -- bei einem Eintrag heisst das: der eine.

    Der erste Lauf warf ``UpdateFailed``, und damit scheiterte der
    Aufbau der update-Wabe. Jetzt steht die Entity und meldet ehrlich
    "nicht verfuegbar", bis der Takt es erneut versucht.
    """
    speichern(hass_storage, [eintrag_daten()])
    sitzung_einpflanzen(
        [
            herzschlag(),  # der Herzschlag
            stammdaten(),  # M5: Stammdaten ueber die ID
            Aufzeichnung(status=500, text="{}", kopfzeilen={}),  # Releases scheitern
        ]
    )
    mock = mock_eintrag()
    await richten(hass, mock)

    assert mock.state is ConfigEntryState.LOADED
    ids = sorted(hass.states.async_entity_ids("update"))
    assert len(ids) == 1, f"die update-Entity muss angelegt werden: {ids}"
    assert hass.states.get(ids[0]).state == "unavailable"


# -- Punkt 3: fehlgeschlagenes Entladen raeumt nichts weg -------------


async def test_fehlgeschlagenes_entladen_laesst_die_laufzeit_stehen(
    hass: HomeAssistant, sitzung_einpflanzen, monkeypatch
) -> None:
    """``async_unload_platforms`` kann False liefern -- dann bleibt alles.

    Vorher verschwand die Laufzeit aus ``hass.data`` und die
    Koordinatoren wurden abgeschaltet, obwohl der Eintrag geladen
    blieb: die Integration war danach taub, bis zum Neustart.
    """
    sitzung_einpflanzen([herzschlag()])
    mock = mock_eintrag()
    await richten(hass, mock)
    assert mock.entry_id in hass.data[DOMAIN]

    async def _nein(eintrag, plattformen=None):
        return False

    monkeypatch.setattr(hass.config_entries, "async_unload_platforms", _nein)

    assert await async_unload_entry(hass, mock) is False
    assert mock.entry_id in hass.data[DOMAIN], (
        "nicht entladen heisst: die Laufzeit bleibt stehen"
    )


# -- Punkt 1: das Lager-Rennen ----------------------------------------


class BremsendeForge:
    """Forge-Attrappe, die den Scan anhaelt, bis der Test freigibt.

    Der volle Lauf baut seine Zeilen am Anfang und schreibt sie erst
    nach den Netz-Awaits zurueck -- genau dazwischen haelt diese
    Attrappe ihn fest, damit der Test eine Mutation dazwischenschieben
    kann, wann immer er will.
    """

    host = "gitlab.example.net"

    def __init__(self) -> None:
        self.im_scan = asyncio.Event()
        self.freigabe = asyncio.Event()

    async def repository_nach_id(self, provider_id, pfad=""):
        return None

    async def suche_nach_topic(self, *args, **kwargs):
        self.im_scan.set()
        await self.freigabe.wait()
        return []


class EintraegeAttrappe:
    """Nur die Griffe, die der Zeilenbau und die Mutatoren brauchen."""

    def __init__(self, *eintraege: Eintrag) -> None:
        self._liste = list(eintraege)

    def alle(self):
        return tuple(self._liste)

    def finde(self, storage_key: str):
        return next(
            (e for e in self._liste if e.storage_key == storage_key),
            None,
        )

    def vorhanden(self, storage_key: str) -> bool:
        return self.finde(storage_key) is not None

    def aufnehmen(self, eintrag: Eintrag) -> None:
        self._liste.append(eintrag)

    def entfernen(self, eintrag: Eintrag) -> None:
        self._liste = [e for e in self._liste if e.storage_key != eintrag.storage_key]


class LaufzeitAttrappe:
    """So viel Laufzeit, wie das Lager anfasst."""

    def __init__(self, forge, eintraege: EintraegeAttrappe) -> None:
        self.forge = forge
        self.eintraege = eintraege


def ein_eintrag(pid: str, full_name: str) -> Eintrag:
    return Eintrag(
        identitaet=RepositoryIdentity(
            provider="gitlab",
            host="gitlab.example.net",
            provider_id=pid,
            full_name=full_name,
        ),
        kategorie="integration",
        hinzugefuegt_am="2026-09-03T00:00:00+00:00",
    )


async def _lauf_mitten_im_scan(hass: HomeAssistant, lager: Lager, forge: BremsendeForge):
    """Startet den vollen Lauf und wartet, bis er im Scan haengt."""
    lauf = asyncio.create_task(lager.voller_lauf())
    await asyncio.wait_for(forge.im_scan.wait(), timeout=2)
    return lauf


async def _fertig_machen(forge: BremsendeForge, *aufgaben) -> None:
    forge.freigabe.set()
    await asyncio.wait_for(asyncio.gather(*aufgaben), timeout=2)


async def test_eintrag_waehrend_eines_laufs_geht_nicht_verloren(
    hass: HomeAssistant, hass_storage
) -> None:
    """Der volle Lauf baut die Zeilen am Anfang und ueberschreibt am Ende.

    Ohne Sperre geht eine Aufnahme, die waehrend der Netz-Awaits
    passiert, beim Zurueckschreiben verloren -- die Liste zeigt sie
    nicht mehr, bis der naechste Lauf sie zufaellig wiederfindet.
    """
    alt = ein_eintrag("1", "foo/alt")
    neu = ein_eintrag("2", "foo/neu")
    forge = BremsendeForge()
    eintraege = EintraegeAttrappe(alt)
    lager = Lager(hass, mock_eintrag(), LaufzeitAttrappe(forge, eintraege))

    lauf = await _lauf_mitten_im_scan(hass, lager, forge)

    # Mitten im Lauf: die Liste nimmt einen Eintrag auf, das Lager zieht nach.
    eintraege.aufnehmen(neu)
    mutier = asyncio.create_task(lager.zeile_hinzu(neu, None))
    for _ in range(3):
        await asyncio.sleep(0)

    await _fertig_machen(forge, lauf, mutier)

    schluessel = [z["storage_key"] for z in lager.zeilen]
    assert alt.storage_key in schluessel
    assert neu.storage_key in schluessel, (
        "der waehrend des Laufs aufgenommene Eintrag wurde ueberschrieben"
    )


async def test_entfernung_waehrend_eines_laufs_bleibt_entfernt(
    hass: HomeAssistant, hass_storage
) -> None:
    """Die Gegenrichtung: ein waehrend des Laufs entfernter Eintrag
    darf nicht als Zeile wiederauferstehen, nur weil der Lauf ihn am
    Anfang noch gesehen hat."""
    alt = ein_eintrag("1", "foo/alt")
    forge = BremsendeForge()
    eintraege = EintraegeAttrappe(alt)
    lager = Lager(hass, mock_eintrag(), LaufzeitAttrappe(forge, eintraege))

    lauf = await _lauf_mitten_im_scan(hass, lager, forge)

    # Mitten im Lauf verschwindet der Eintrag.
    eintraege.entfernen(alt)
    mutier = asyncio.create_task(lager.zeile_weg(alt))
    for _ in range(3):
        await asyncio.sleep(0)

    await _fertig_machen(forge, lauf, mutier)

    assert [z["storage_key"] for z in lager.zeilen] == [], (
        "der waehrend des Laufs entfernte Eintrag ist wieder aufgetaucht"
    )


async def test_gespeicherter_bestand_stimmt_nach_dem_rennen(
    hass: HomeAssistant, hass_storage
) -> None:
    """Der Bestand auf der Platte muss nach dem Rennen ebenfalls stimmen.

    Die Zeilen im Speicher sind die eine Haelfte; was der naechste
    Neustart liest, ist die andere.
    """
    alt = ein_eintrag("1", "foo/alt")
    neu = ein_eintrag("2", "foo/neu")
    forge = BremsendeForge()
    eintraege = EintraegeAttrappe(alt)
    lager = Lager(hass, mock_eintrag(), LaufzeitAttrappe(forge, eintraege))

    lauf = await _lauf_mitten_im_scan(hass, lager, forge)

    eintraege.aufnehmen(neu)
    mutier = asyncio.create_task(lager.zeile_hinzu(neu, None))
    for _ in range(3):
        await asyncio.sleep(0)

    await _fertig_machen(forge, lauf, mutier)
    await hass.async_block_till_done()

    gespeichert = hass_storage["haigs.lager.gitlab_example_net"]["data"]
    schluessel = [z["storage_key"] for z in gespeichert["eintraege"]]
    assert alt.storage_key in schluessel
    assert neu.storage_key in schluessel, (
        "der gespeicherte Bestand ist hinter dem Rennen zurueckgeblieben"
    )
