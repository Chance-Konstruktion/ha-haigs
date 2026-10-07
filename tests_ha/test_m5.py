"""Stufe M5 in Home Assistant: update-Entities, Vorab-Schalter, Installation.

Alles offline: die Sitzungs-Attrappe spielt die GitLab-Antworten in
Reihenfolge ab. Die Reihenfolge ist der Herzschlag zuerst (Richten des
Eintrags), dann der erste Lauf der Stufe M5 (Richten der Waben), danach
alles, was der einzelne Test anstoesst.
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import timedelta
from pathlib import Path

import homeassistant.util.dt as dt_util
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.haigs.const import CONF_HOST, CONF_TOKEN, DOMAIN
from custom_components.haigs.core.identity import RepositoryIdentity
from tests.attrappe import Aufzeichnung, projekt

SCHLUESSEL = "haigs.gitlab_example_net"
STORAGE_KEY = "gitlab@gitlab.example.net:789012"


def eintrag_daten(full_name: str = "foo/bar", pid: str = "789012") -> dict:
    """Die gespeicherte Form eines Eintrags, wie M3 sie schreibt."""
    return {
        "provider": "gitlab",
        "host": "gitlab.example.net",
        "provider_id": pid,
        "full_name": full_name,
        "uid": "gitlab:" + pid,
        "storage_key": "gitlab@gitlab.example.net:" + pid,
        "display_full_name": full_name + "*lab",
        "kategorie": "integration",
        "hinzugefuegt_am": "2026-09-03T00:00:00+00:00",
    }


def release_objekt(tag: str, beschreibung: str = "") -> dict:
    return {
        "tag_name": tag,
        "name": "Version " + tag,
        "description": beschreibung,
        "released_at": "2026-09-01T10:00:00Z",
        "assets": {},
    }


def stammdaten(
    full_name: str = "foo/bar", pid: int | str = 789012, topics=("hacs",), **rest
) -> Aufzeichnung:
    """Die Antwort auf die Stammdatenfrage ueber die ID (Stufe M8).

    Der Lauf fragt je Eintrag zuerst hier -- die ID traegt -- und erst
    dann die Releases unter dem Namen, den diese Antwort nennt.
    """
    return Aufzeichnung(
        text=json.dumps(projekt(pid=pid, full_name=full_name, topics=topics, **rest)),
        kopfzeilen={},
    )


def herzschlag() -> Aufzeichnung:
    return Aufzeichnung(text="[]", kopfzeilen={})


def releases(*objekte: dict) -> Aufzeichnung:
    return Aufzeichnung(text=json.dumps(list(objekte)), kopfzeilen={})


def nicht_gefunden() -> Aufzeichnung:
    return Aufzeichnung(
        status=404, text='{"message": "404 Project Not Found"}', kopfzeilen={}
    )


def mock_eintrag() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="gitlab.example.net",
        data={CONF_HOST: "gitlab.example.net", CONF_TOKEN: ""},
        unique_id="gitlab.example.net",
    )


def speichern(hass_storage, eintraege, stand=None) -> None:
    hass_storage[SCHLUESSEL] = {
        "version": 1,
        "data": {"eintraege": list(eintraege), "stand": stand or {}},
    }


async def richten(hass: HomeAssistant, mock: MockConfigEntry) -> None:
    mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock.entry_id)
    await hass.async_block_till_done()


def zustand(hass: HomeAssistant, domain: str):
    ids = sorted(hass.states.async_entity_ids(domain))
    assert len(ids) == 1, f"eine {domain}-Entity erwartet, gefunden: {ids}"
    return hass.states.get(ids[0])


async def test_update_entity_zeigt_beide_versionen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    sitzung_einpflanzen(
        [herzschlag(), stammdaten(), releases(release_objekt("v1.2.0", "Die Notizen"))]
    )
    await richten(hass, mock_eintrag())

    zustand_update = zustand(hass, "update")
    assert zustand_update.state == "on"
    assert zustand_update.attributes["installed_version"] == "1.1.0"
    assert zustand_update.attributes["latest_version"] == "1.2.0"
    assert zustand_update.attributes["release_summary"] == "Die Notizen"
    assert zustand_update.attributes["title"] == "foo/bar*lab"
    assert zustand_update.attributes["tag"] == "v1.2.0"
    assert zustand_update.attributes["quelle"] == "releases"

    zustand_schalter = zustand(hass, "switch")
    assert zustand_schalter.state == "off"
    assert zustand_schalter.attributes["friendly_name"] == (
        "foo/bar*lab — Vorabversionen"
    )


async def test_neues_release_erscheint_ohne_zutun(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """Die Abnahme von Stufe M5, in einem Satz geprueft."""
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    # Beim Vorlauf um den Takt feuert der Lager-Start von Flug 2084
    # zuerst (sein Termin liegt frueher), danach der Aktualisierer.
    # Der Lager-Lauf fragt die Zeile ueber die ID und durchsucht dann
    # die Instanz (Suche, hacs.json, letzte Version); der Takt fragt
    # wieder Stammdaten und Releases. Jede Runde zaehlt: drei Abrufe
    # in der ersten, vier fuer das Lager, zwei in der zweiten Runde.
    attrappe = sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            stammdaten(),  # Lager: Zeile ueber die ID
            Aufzeichnung(  # Lager: die Suche ueber die ganze Instanz
                text=json.dumps([projekt()]), kopfzeilen={}
            ),
            Aufzeichnung(  # Lager: hacs.json des Kandidaten
                rohbytes=b'{"name": "Bar"}', kopfzeilen={}
            ),
            releases(release_objekt("v1.2.0")),  # Lager: letzte Version
            stammdaten(),
            releases(release_objekt("v1.3.0", "Frisch")),
        ]
    )
    await richten(hass, mock_eintrag())

    assert zustand(hass, "update").attributes["latest_version"] == "1.2.0"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(hours=12))
    await hass.async_block_till_done()

    frisch = zustand(hass, "update")
    assert frisch.attributes["latest_version"] == "1.3.0"
    assert frisch.attributes["release_summary"] == "Frisch"
    assert frisch.state == "on"
    assert len(attrappe.abrufe) == 9
    # Das Lager hat den Scan ueberlebt: der Kandidat steht als Fund
    # darin, und er ist als vorhanden verzeichnet.
    lager = hass_storage["haigs.lager.gitlab_example_net"]["data"]
    assert [f["full_name"] for f in lager["funde"]] == ["foo/bar"]
    assert lager["funde"][0]["vorhanden"] is True
    assert lager["eintraege"][0]["installiert"] == "1.1.0"


async def test_vorab_schalter_dreht_die_auswahl(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.2.0", "vorabversionen": False}},
    )
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.3.0-rc1", "Vorsicht")),
            stammdaten(),
            releases(release_objekt("v1.3.0-rc1", "Vorsicht")),
        ]
    )
    await richten(hass, mock_eintrag())

    # Ohne Schalter ist die Vorabversion unsichtbar: kein Update gemeldet.
    assert zustand(hass, "update").state == "off"

    schalter_id = sorted(hass.states.async_entity_ids("switch"))[0]
    await hass.services.async_call(
        "switch", "turn_on", {"entity_id": schalter_id}, blocking=True
    )
    await hass.async_block_till_done()

    gedreht = zustand(hass, "update")
    assert gedreht.state == "on"
    assert gedreht.attributes["latest_version"] == "1.3.0-rc1"
    assert gedreht.attributes["release_summary"] == "Vorsicht"
    assert zustand(hass, "switch").state == "on"
    gespeichert = hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]
    assert gespeichert["vorabversionen"] is True


async def test_installations_dienst_tauscht_die_dateien(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )

    archiv = io.BytesIO()
    with zipfile.ZipFile(archiv, "w") as zip_datei:
        zip_datei.writestr(
            "foo-bar-v1.2.0/manifest.json",
            json.dumps(
                {
                    "domain": "beispiel_integration",
                    "name": "Beispiel",
                    "version": "1.2.0",
                    "documentation": "https://example.net",
                }
            ),
        )
        zip_datei.writestr("foo-bar-v1.2.0/__init__.py", "# die Integration\n")
        zip_datei.writestr("foo-bar-v1.2.0/README.md", "# Beispiel\n")

    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            # M4b: die Installation fragt vor dem Archiv noch einmal die
            # Releases ab -- der Anhang ist die bevorzugte Quelle. Ohne
            # Anhang (wie hier) faellt sie aufs Tag-Archiv zurueck.
            releases(release_objekt("v1.2.0")),
            Aufzeichnung(rohbytes=archiv.getvalue(), kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())

    update_id = sorted(hass.states.async_entity_ids("update"))[0]
    assert zustand(hass, "update").state == "on"

    await hass.services.async_call(
        "update", "install", {"entity_id": update_id}, blocking=True
    )
    await hass.async_block_till_done()

    ziel = Path(hass.config.config_dir) / "custom_components" / "beispiel_integration"
    assert (ziel / "manifest.json").exists()
    assert (ziel / "__init__.py").exists()
    assert json.loads((ziel / "manifest.json").read_text())["domain"] == (
        "beispiel_integration"
    )
    # Die Zwischenlager bleibt, die halbfertigen Reste darin nicht.
    zwischen = Path(hass.config.config_dir) / ".haigs_zwischenlager"
    assert not (zwischen / "custom_components.beispiel_integration.neu").exists()
    assert not (zwischen / "custom_components.beispiel_integration.alt").exists()

    nachher = zustand(hass, "update")
    assert nachher.state == "off"
    assert nachher.attributes["installed_version"] == "1.2.0"
    gespeichert = hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]
    assert gespeichert["installiert"] == "1.2.0"


async def test_kaputtes_repo_wirft_die_andere_entity_nicht_um(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    kaputt = eintrag_daten(full_name="kaputt/bar", pid="111")
    speichern(
        hass_storage,
        [eintrag_daten(), kaputt],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    sitzung_einpflanzen(
        [
            herzschlag(),
            # Stammdaten je Eintrag: foo/bar lebt, kaputt/bar gibt es unter
            # der ID nicht mehr -- der Lauf faellt auf den gespeicherten
            # Pfad zurueck und findet auch dort nichts.
            stammdaten(),
            nicht_gefunden(),
            releases(release_objekt("v1.2.0")),
            nicht_gefunden(),
            nicht_gefunden(),
        ]
    )
    await richten(hass, mock_eintrag())

    ids = sorted(hass.states.async_entity_ids("update"))
    assert len(ids) == 2

    gesund = hass.states.get(ids[0])  # foo/bar kommt vor kaputt/bar
    kaputte = hass.states.get(ids[1])
    assert gesund.state == "on"
    assert gesund.attributes["latest_version"] == "1.2.0"
    # kaputt/bar ist ehrlich "unavailable" -- Home Assistant zeigt von
    # solchen Entities keine Attribute; der Grund steht als Warnung im
    # Protokoll (aktualisierer.py).
    assert kaputte.state == "unavailable"


async def test_neuer_eintrag_erscheint_ohne_neustart(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    speichern(hass_storage, [])
    sitzung_einpflanzen(
        [herzschlag(), stammdaten(), releases(release_objekt("v1.2.0", "Frisch dabei"))]
    )
    await richten(hass, mock_eintrag())
    assert hass.states.async_entity_ids("update") == []

    laufzeit = hass.data[DOMAIN][hass.config_entries.async_entries(DOMAIN)[0].entry_id]
    identitaet = RepositoryIdentity(
        provider="gitlab",
        host="gitlab.example.net",
        provider_id="789012",
        full_name="foo/bar",
    )
    await laufzeit.eintraege.hinzufuegen(identitaet, "integration")
    await hass.async_block_till_done()

    neu = zustand(hass, "update")
    assert neu.attributes["latest_version"] == "1.2.0"
    assert neu.attributes["release_summary"] == "Frisch dabei"
    # Noch nichts installiert: Home Assistant zeigt "unknown", solange die
    # installierte Version fehlt -- ehrlich; die neueste Version steht da,
    # und der Installations-Dienst nimmt sie trotzdem an.
    assert neu.attributes["installed_version"] is None
    assert neu.state == "unknown"
    assert zustand(hass, "switch").state == "off"

    await laufzeit.eintraege.entfernen(STORAGE_KEY)
    await hass.async_block_till_done()

    # Das Entfernen hinterlaesst die praechtige Rest-Markierung der Registry
    # -- leben darf nichts mehr.
    for eid in hass.states.async_entity_ids("update"):
        st = hass.states.get(eid)
        assert st is None or st.state == "unavailable"
    for eid in hass.states.async_entity_ids("switch"):
        st = hass.states.get(eid)
        assert st is None or st.state == "unavailable"


async def test_entladen_nimmt_die_waben_mit(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    sitzung_einpflanzen([herzschlag(), stammdaten(), releases(release_objekt("v1.2.0"))])
    mock = mock_eintrag()
    await richten(hass, mock)
    update_id = sorted(hass.states.async_entity_ids("update"))[0]

    assert await hass.config_entries.async_unload(mock.entry_id)
    await hass.async_block_till_done()

    assert mock.state is ConfigEntryState.NOT_LOADED
    rest = hass.states.get(update_id)
    # Registry-Entities hinterlassen eine "restored"-Markierung, die nur
    # praechtig "unavailable" ist -- eine lebende Entity ist das nicht mehr.
    assert rest is None or rest.state == "unavailable"
    for eid in hass.states.async_entity_ids("switch"):
        st = hass.states.get(eid)
        assert st is None or st.state == "unavailable"
