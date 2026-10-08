"""Flug 2084: das Lager -- voll, gespeichert, von selbst frisch.

Die Wünsche des Imkers, als Abnahme:

* der Laden geht nicht leer auf -- nicht beim Betreten, nicht nach dem
  Neustart: das Richten liest das Lager aus dem Speicher, die Frage
  ``eintraege`` antwortet daraus ohne einen einzigen Netzruf;
* der Hintergrund frischt von selbst: der Start-Lauf (verzögert) und
  danach der Takt füllen das Lager neu und feuern ihr Ereignis;
* Mutationen (hinzufügen, entfernen, deinstallieren) folgen sofort --
  die Zeile wandert mit, ohne weiteren Abruf.
"""

from __future__ import annotations

import json
from datetime import timedelta

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
)

from custom_components.haigs.const import (
    EREIGNIS_AKTUALISIERT,
)
from tests.attrappe import Aufzeichnung

from .test_m5 import eintrag_daten, release_objekt, stammdaten
from .test_m7 import (
    HOST,
    STORAGE_KEY,
    datei_antwort,
    frage,
    mock_eintrag,
    projekt_daten,
    releases,
)

LAGER_KEY = "haigs.lager." + HOST.replace(".", "_")


def lager_daten() -> dict:
    """Ein gefülltes Lager, wie der volle Lauf es schreibt."""
    return {
        "eintraege": [
            {
                "storage_key": STORAGE_KEY,
                "name": "foo/bar*lab",
                "pfad": "foo/bar",
                "kategorie": "integration",
                "host": HOST,
                "hinzugefuegt_am": "2026-09-03T00:00:00+00:00",
                "entity_id": None,
                "neueste": "1.2.0",
                "tag": "v1.2.0",
                "veroeffentlicht_am": "2026-09-01T10:00:00Z",
                "installiert": "1.1.0",
                "fehler": "",
                "beschreibung": "ein Testprojekt",
                "sterne": 7,
                "offene_tickets": 2,
                "web_url": "https://gitlab.example.net/foo/bar",
                "tickets_url": "https://gitlab.example.net/foo/bar/-/issues",
                "releases_url": "https://gitlab.example.net/foo/bar/-/releases",
                "avatar_url": "https://gitlab.example.net/uploads/bar.png",
            }
        ],
        "funde": [
            {
                "full_name": "foo/bar",
                "name": "foo/bar*lab",
                "beschreibung": "ein Testprojekt",
                "sterne": 7,
                "offene_tickets": 2,
                "letzte_version": "1.2.0",
                "kategorie": "integration",
                "gueltig": True,
                "fehler": "",
                "vorhanden": True,
                "web_url": "https://gitlab.example.net/foo/bar",
                "avatar_url": "",
                "host": HOST,
            }
        ],
        "aktualisiert_am": "2026-09-04T08:00:00+00:00",
    }


async def test_nach_dem_neustart_steht_die_liste_sofort_da(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Der Showstopper des Imkers: leerer Laden nach dem Neustart.

    Das Richten liest das Lager aus dem Speicher; die Frage antwortet
    daraus -- kein Netzruf, kein Warten auf irgendeinen Lauf. Der
    Herzschlag beim Richten ist der einzige Abruf.
    """
    from .test_m5 import releases as m5_releases
    from .test_m5 import speichern

    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    hass_storage[LAGER_KEY] = {"version": 1, "data": lager_daten()}
    attrappe = sitzung_einpflanzen(
        [
            Aufzeichnung(text="[]", kopfzeilen={}),  # der Herzschlag
            stammdaten(),  # M5-erster Lauf (Entity)
            m5_releases(release_objekt("v1.2.0")),
        ]
    )
    from .test_m7 import richten

    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    antwort = await frage(client, 1, "haigs/eintraege")
    assert antwort["success"]
    zeile = antwort["result"]["eintraege"][0]
    assert zeile["name"] == "foo/bar*lab"
    assert zeile["installiert"] == "1.1.0"
    assert zeile["neueste"] == "1.2.0"
    assert zeile["avatar_url"] == "https://gitlab.example.net/uploads/bar.png"
    # Die Funde reisen mit -- der Abschnitt Neu ist nach dem Neustart
    # genauso voll wie zuvor.
    assert [f["full_name"] for f in antwort["result"]["funde"]] == ["foo/bar"]
    assert antwort["result"]["funde"][0]["vorhanden"] is True
    # Der Stand des Lagers steht in der Antwort.
    assert antwort["result"]["aktualisiert_am"] == {HOST: "2026-09-04T08:00:00+00:00"}
    # Kein einziger Ruf über die Reihe hinaus: die Liste kam aus dem
    # Speicher, nicht aus dem Netz.
    assert len(attrappe.abrufe) == 3


async def test_der_hintergrund_frucht_von_sich_aus(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Start-Lauf und Takt füllen das Lager -- und feuern das Ereignis.

    Der Start-Lauf kommt LAGER_START_VERZOEGERUNG_SEK nach dem Richten
    (im Vorlauf um zwölf Stunden feuert er zuerst). Danach hängt er am
    Takt: der nächste Vorlauf läuft ihn erneut. Jeder Lauf speichert und
    feuert ``haigs_aktualisiert`` -- das Panel malt daraufhin von
    selbst neu.
    """
    from .test_m5 import speichern
    from .test_m7 import richten

    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    ereignisse: list[dict] = []
    hass.bus.async_listen(EREIGNIS_AKTUALISIERT, lambda e: ereignisse.append(e))

    attrappe = sitzung_einpflanzen(
        [
            Aufzeichnung(text="[]", kopfzeilen={}),  # Herzschlag
            stammdaten(),  # M5 erster Lauf
            releases(release_objekt("v1.2.0")),
            # -- der Start-Lauf des Lagers --
            stammdaten(),  # die Zeile ueber die ID
            Aufzeichnung(  # die Suche ueber die Instanz
                text=json.dumps([projekt_daten()]), kopfzeilen={}
            ),
            datei_antwort(json.dumps({"name": "Bar", "render_readme": True})),
            releases(release_objekt("v1.2.0")),  # letzte Version des Treffers
            # -- der Takt des Aktualisierers --
            stammdaten(),
            releases(release_objekt("v1.2.0")),
        ]
    )
    await richten(hass, mock_eintrag())
    assert ereignisse == []  # noch lief nichts

    # Der Vorlauf feuert den Start-Lauf (vor dem Takt) und den Takt.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=12))
    await hass.async_block_till_done()

    assert len(ereignisse) == 1
    assert ereignisse[0].data["host"] == HOST
    lager = hass_storage[LAGER_KEY]["data"]
    assert [f["full_name"] for f in lager["funde"]] == ["foo/bar"]
    assert lager["funde"][0]["vorhanden"] is True
    assert lager["eintraege"][0]["installiert"] == "1.1.0"
    assert len(attrappe.abrufe) == 9

    # Der NAECHSTE Vorlauf laeuft den Takt des Lagers erneut -- das Lager
    # bleibt von selbst frisch, niemand drueckt einen Knopf. Der Takt
    # des Aktualisierers feuert zuerst (er vollendet seinen Lauf vor
    # dem Lager und bewaffnet sich deshalb zuerst), danach der Takt
    # des Lagers: Zeile ueber die ID, dann die (leere) Suche.
    attrappe.aufzeichnungen.extend(
        [
            stammdaten(),  # Aktualisierer-Takt: Stammdaten ueber die ID
            releases(release_objekt("v1.2.0")),  # Aktualisierer-Takt: der Fund
            stammdaten(),  # Lager-Takt: die Zeile ueber die ID
            Aufzeichnung(text="[]", kopfzeilen={}),  # Lager-Takt: die Suche
        ]
    )
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=24))
    await hass.async_block_till_done()

    assert len(ereignisse) == 2
    assert len(attrappe.abrufe) == 13
    lager_frisch = hass_storage[LAGER_KEY]["data"]
    assert lager_frisch["aktualisiert_am"]
    assert lager_frisch["eintraege"][0]["installiert"] == "1.1.0"


async def test_deinstallation_zieht_den_stand_nach(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Der Deinstallations-Befehl pflegt das Lager gleich mit.

    Ohne weiteren Abruf: die Zeile verliert ihre installierte Version,
    der Rest bleibt -- der Laden zeigt die Wahrheit, bevor irgendein
    Takt laeuft.
    """
    from pathlib import Path

    from .test_m4b import beispiel_integration_zip, update_entity_id
    from .test_m5 import speichern
    from .test_m7 import richten

    speichern(hass_storage, [eintrag_daten()])
    hass_storage[LAGER_KEY] = {"version": 1, "data": lager_daten()}
    attrappe = sitzung_einpflanzen(
        [
            Aufzeichnung(text="[]", kopfzeilen={}),  # Herzschlag
            stammdaten(),  # M5 erster Lauf
            releases(release_objekt("v1.2.0")),
            releases(  # M4b: die Installationsquelle
                release_objekt("v1.2.0", {"paket.zip": "https://x/paket.zip"})
            ),
            Aufzeichnung(  # der Anhang zum Installieren
                rohbytes=beispiel_integration_zip(), kopfzeilen={}
            ),
        ]
    )
    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        "update", "install", {"entity_id": update_entity_id(hass)}, blocking=True
    )
    await hass.async_block_till_done()
    ziel = Path(hass.config.config_dir) / "custom_components" / "beispiel_integration"
    assert ziel.exists()

    antwort = await frage(client, 1, "haigs/deinstallieren", storage_key=STORAGE_KEY)
    assert antwort["success"], antwort
    assert not ziel.exists()  # Dateien sind weg

    lager = hass_storage[LAGER_KEY]["data"]
    assert lager["eintraege"][0]["installiert"] == ""
    assert lager["eintraege"][0]["name"] == "foo/bar*lab"
    # Kein weiterer Abruf: das Lager folgte der Ablage, nicht dem Netz.
    assert len(attrappe.abrufe) == 5


async def test_geoeffneter_fund_wird_dauerhaft_gesehen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """haigs/gesehen merkt den Fund im Lager; eintraege liefert gesehen je Fund."""
    from .test_m5 import releases as m5_releases
    from .test_m5 import speichern
    from .test_m7 import richten

    daten = lager_daten()
    daten["funde"][0]["vorhanden"] = False
    speichern(hass_storage, [eintrag_daten()])
    hass_storage[LAGER_KEY] = {"version": 1, "data": daten}
    sitzung_einpflanzen(
        [
            Aufzeichnung(text="[]", kopfzeilen={}),
            stammdaten(),
            m5_releases(release_objekt("v1.2.0")),
        ]
    )
    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    vorher = await frage(client, 1, "haigs/eintraege")
    assert vorher["result"]["funde"][0]["gesehen"] is False

    antwort = await frage(client, 2, "haigs/gesehen", host=HOST, pfad="foo/bar")
    assert antwort["success"]
    nachher = await frage(client, 3, "haigs/eintraege")
    assert nachher["result"]["funde"][0]["gesehen"] is True
    assert hass_storage[LAGER_KEY]["data"]["gesehen"] == ["foo/bar"]

    # Unbekannter Fund und unbekannte Instanz werden abgewiesen.
    fremd = await frage(client, 4, "haigs/gesehen", host=HOST, pfad="x/y")
    assert not fremd["success"]
    fremd = await frage(client, 5, "haigs/gesehen", host="gibt.es.nicht", pfad="foo/bar")
    assert not fremd["success"]
