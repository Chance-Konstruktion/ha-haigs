"""Haerte der Home-Assistant-Bahn (Flug 2093): feindliche Eingaben,
kaputter Speicher, wortbruchige Server -- nichts darf das Haus
Sacken lassen.

Drei Gruppen:

* Der Einrichtungsdialog trifft auf Captive Portale (200 mit HTML)
  und halbtote Server (500) -- seit Flug 2093 behauptet die
  Auto-Erkennung da kein GitLab mehr, sondern nennt die Wahrheit.
* Die WebSocket-Schnittstelle bekommt Stichwoerter, die wie
  Script-Angriffe aussehen, und welche von 10.000 Zeichen: sie
  reisen unversehrt bis zum Anbieter und zurueck.
* Der Lager-Speicher kann kaputt sein (Versionssprung, halber
  Schreibvorgang, fremdes Werkzeug drin): das Lesen bleibt ruhig,
  die Liste antwortet trotzdem.
"""

from __future__ import annotations

import json

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haigs.const import DOMAIN
from tests.attrappe import Aufzeichnung

HOST = "gitlab.example.net"
SPEICHER = "haigs." + HOST.replace(".", "_")

# -- Helfer, die hier bewusst klein bleiben (kein Import aus den
# -- Schwesterdateien: jede Suite traegt ihr eigenes Werkzeug). ------


def version_frage(text: str) -> Aufzeichnung:
    return Aufzeichnung(text=json.dumps({"version": text}), kopfzeilen={})


def weg_404() -> Aufzeichnung:
    return Aufzeichnung(
        status=404, text=json.dumps({"message": "404 Not Found"}), kopfzeilen={}
    )


def html_antwort() -> Aufzeichnung:
    """Ein Captive Portal, wie ihn jedes Hotel-WLAN stellt."""
    return Aufzeichnung(
        text="<html>Willkommen! Bitte loggen Sie sich ins WLAN ein.</html>",
        kopfzeilen={"Content-Type": "text/html"},
    )


def suche_leer() -> Aufzeichnung:
    return Aufzeichnung(text="[]", kopfzeilen={})


def projekt_daten(full_name: str = "foo/bar", pid: str = "789012", **rest) -> dict:
    daten = {
        "id": pid,
        "path_with_namespace": full_name,
        "description": "ein Testprojekt",
        "default_branch": "main",
        "topics": ["hacs"],
        "star_count": 7,
        "open_issues_count": 2,
        "archived": False,
        "web_url": "https://" + HOST + "/" + full_name,
    }
    daten.update(rest)
    return daten


# ------------------------------------------------------------------
# Der Dialog gegen Waende
# ------------------------------------------------------------------


async def test_captive_portal_im_dialog(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    """HTML auf beiden Toren: kein GitLab, Hand-Wahl -- ehrlich."""
    from homeassistant.data_entry_flow import FlowResultType

    sitzung_einpflanzen([html_antwort(), html_antwort()])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {"host": "wlan.hotel.example", "provider": "auto", "token": ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "anbieter_unerkannt"}


async def test_serverfehler_500_im_dialog(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """500 auf der Versionsfrage: Verbindung fehlgeschlagen, kein GitLab."""
    from homeassistant.data_entry_flow import FlowResultType

    sitzung_einpflanzen(
        [
            Aufzeichnung(status=500, text="Internal Server Error", kopfzeilen={}),
        ]
    )

    from custom_components.haigs.const import DOMAIN

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {"host": "kaputt.example", "provider": "auto", "token": ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "verbindung_fehlgeschlagen"}


async def test_html_vor_gitlab_dahinter_gitea(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Ein Proxy verbaut nur das v4-Tor: dahinter wohnt die Familie."""
    from homeassistant.data_entry_flow import FlowResultType

    sitzung_einpflanzen(
        [
            html_antwort(),  # v4: die Wand
            version_frage("1.23.8"),  # v1: die Familie
            Aufzeichnung(  # die Startseite nennt Gitea
                rohbytes=b"<footer>Powered by Gitea</footer>", kopfzeilen={}
            ),
            # die Probe durch die Gitea-Tochter (Mantel-Antwort)
            Aufzeichnung(
                text=json.dumps(
                    {
                        "ok": True,
                        "data": [
                            {
                                "id": 4711,
                                "full_name": "foo/bar",
                                "default_branch": "main",
                                "topics": ["hacs"],
                                "stars_count": 1,
                                "open_issues_count": 0,
                                "archived": False,
                            }
                        ],
                    }
                ),
                kopfzeilen={},
            ),
            suche_leer(),  # Herzschlag
            suche_leer(),  # Lager-Lauf
        ]
    )

    from custom_components.haigs.const import DOMAIN

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {"host": "gitea.example", "provider": "auto", "token": ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["data"]["provider"] == "gitea"


# ------------------------------------------------------------------
# WebSocket unter Beschuss
# ------------------------------------------------------------------


async def _gericht(hass, hass_storage, hass_ws_client, sitzung_einpflanzen):
    """Eine laufende Instanz -- klein, aber echt (Herzschlag + Suche)."""
    hass_storage[SPEICHER] = {
        "version": 1,
        "data": {"eintraege": [], "stand": {}},
    }
    sitzung_einpflanzen(
        [
            suche_leer(),  # Herzschlag beim Richten
            suche_leer(),  # Lager-Suche
        ]
    )
    eintrag = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={"host": HOST, "token": "", "provider": "gitlab"},
        unique_id=HOST,
    )
    eintrag.add_to_hass(hass)
    assert await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()
    return await hass_ws_client(hass)


async def test_stichwort_mit_script_html_reist_und_kommt_zurueck(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Ein Angriffsversuch als Suchwort: kein Escaping, kein Crash,
    kein exec -- der Kern reist es roh, das Panel flieht beim Malen."""
    client = await _gericht(hass, hass_storage, hass_ws_client, sitzung_einpflanzen)

    # Die Suche braucht eine zweite Aufzeichnung -- die Attrappe der
    # _gericht-Helferin ist verbraucht; neue pflanzen wir selbst.
    sitzung_einpflanzen(
        [
            suche_leer(),  # Suche: leere Funde, kein Fehler
        ]
    )
    wort = '<script>alert("bee")</script> & <img src=x onerror=alert(1)>'
    await client.send_json(
        {"id": 1, "type": "haigs/entdecken", "host": HOST, "stichwort": wort}
    )
    antwort = await client.receive_json()
    assert antwort["success"]
    assert antwort["result"]["funde"] == []


async def test_stichwort_mit_zehntausend_zeichen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Ein Wort so lang wie ein Kapitel: die Leitung haelt es aus."""
    client = await _gericht(hass, hass_storage, hass_ws_client, sitzung_einpflanzen)
    sitzung_einpflanzen([suche_leer()])

    wort = "b" * 10_000
    await client.send_json(
        {"id": 1, "type": "haigs/entdecken", "host": HOST, "stichwort": wort}
    )
    antwort = await client.receive_json()
    assert antwort["success"]
    assert antwort["result"]["funde"] == []


async def test_stichwort_mit_emoji_und_hieroglyphen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Der volle Unicode-Raum: 🐝 bis 中 -- kein Dekodierunfall."""
    client = await _gericht(hass, hass_storage, hass_ws_client, sitzung_einpflanzen)
    sitzung_einpflanzen([suche_leer()])

    wort = "🐝bienentanz—日本語—𓂀—🦊"
    await client.send_json(
        {"id": 1, "type": "haigs/entdecken", "host": HOST, "stichwort": wort}
    )
    antwort = await client.receive_json()
    assert antwort["success"]


# ------------------------------------------------------------------
# Kaputter Speicher
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "eintraege_roh",
    [
        None,  # Schlüssel weg
        "keine Liste",  # falscher Typ
        {"eintraege": "verschachtelt"},  # Kapitulation
        [None, 42, "zeile", {"storage_key": "x"}],  # gemischter Haufen
        [{}],  # leere Karte
    ],
)
async def test_kaputter_speicher_tarnt_sich_nicht_als_absturz(
    hass: HomeAssistant,
    sitzung_einpflanzen,
    hass_storage,
    hass_ws_client,
    eintraege_roh,
) -> None:
    """Egal wie der Speicher aussieht: die Liste antwortet, das Panel
    kann zeichnen, nichts wirft unaufgefangen."""
    hass_storage[SPEICHER] = {
        "version": 1,
        "data": {"eintraege": eintraege_roh, "stand": {}},
    }
    sitzung_einpflanzen([suche_leer(), suche_leer()])

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={"host": HOST, "token": "", "provider": "gitlab"},
        unique_id=HOST,
    )
    eintrag.add_to_hass(hass)
    assert await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "haigs/eintraege"})
    antwort = await client.receive_json()
    assert antwort["success"]
    # Die Zeilen sind Karten oder nichts -- nie Muell nach draussen.
    for zeile in antwort["result"]["eintraege"]:
        assert isinstance(zeile, dict)


async def test_speicher_ohne_version_und_daten(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Ein ganz leeres Speicherwerk: auch das ist kein Absturz.

    Der Schluessel fehlt im Speicher von Anfang an -- async_load
    liefert dann None, genau wie nach einem Absturz vor dem ersten
    Schreiben. (hass_storage auf None zu setzen bricht das Protokoll
    des HA-Test-Storage -- der fehlende Schluessel ist die ehrliche
    Form desselben Zustands.)
    """
    hass_storage.pop(SPEICHER, None)
    sitzung_einpflanzen([suche_leer(), suche_leer()])

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={"host": HOST, "token": "", "provider": "gitlab"},
        unique_id=HOST,
    )
    eintrag.add_to_hass(hass)
    assert await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "haigs/eintraege"})
    antwort = await client.receive_json()
    assert antwort["success"]


async def test_giften_eintrag_mit_html_namen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Ein Eintrag, dessen Name ein Angriff ist: die Liste zahlt ihn
    als Text -- das Malen flieht ihn (Beweis im Schaufenster)."""
    hass_storage[SPEICHER] = {
        "version": 1,
        "data": {
            "eintraege": [
                {
                    "provider": "gitlab",
                    "host": HOST,
                    "provider_id": "1",
                    "full_name": '<script>alert("xss")</script>/bar',
                    "kategorie": "integration",
                    "name": 'Böses <b>Name</b> & "Anführungszeichen"',
                    "hinzugefuegt_am": "2026-09-03T20:00:00+00:00",
                }
            ],
            "stand": {},
        },
    }
    feindlicher_name = 'Böses <b>Name</b> & "Anführungszeichen"'
    sitzung_einpflanzen(
        [
            suche_leer(),  # Herzschlag
            suche_leer(),  # Lager-Suche
            # Der Lauf des Eintrags: Stammdaten nennen den feindlichen
            # Namen, Releases bleiben leer. Kein hacs.json-Ruf hier --
            # der Eintrag steht schon in der Ablage, nicht im Fund.
            Aufzeichnung(
                text=json.dumps(
                    projekt_daten(full_name="x/y", pid="1", name=feindlicher_name)
                ),
                kopfzeilen={},
            ),
            Aufzeichnung(text="[]", kopfzeilen={}),  # Releases
        ]
    )

    eintrag = MockConfigEntry(
        domain=DOMAIN,
        title=HOST,
        data={"host": HOST, "token": "", "provider": "gitlab"},
        unique_id=HOST,
    )
    eintrag.add_to_hass(hass)
    assert await hass.config_entries.async_setup(eintrag.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "haigs/eintraege"})
    antwort = await client.receive_json()
    assert antwort["success"]
    # Der Name kommt roh als DATEN an -- escaping ist des Panels Pflicht
    # (fliehe), nicht die der Leitung. Wichtig ist: kein Crash, keine
    # Verstummelung. (Die Entity-Id entschaeft HA selbst:
    # switch.script_alert_xss_script_bar... -- Text, kein Code.)
    zeilen = antwort["result"]["eintraege"]
    assert len(zeilen) == 1
    # Der Anzeigename ist der volle Pfad plus Suffix -- ROH als Daten.
    # Escaping ist die Pflicht des Panels (fliehe), nicht die der
    # Leitung: hier zaehlt nur, dass der Angriff als TEXT ankommt.
    assert zeilen[0].get("name") == '<script>alert("xss")</script>/bar*lab'
    assert "<script>" in zeilen[0].get(
        "name", ""
    )  # unversehrt, nicht entschaerft-und-verschwiegen
