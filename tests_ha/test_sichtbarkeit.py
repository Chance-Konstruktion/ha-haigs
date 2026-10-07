"""Flug 2098 -- die Sichtbarkeit installierter Integrationen (HA-Bahn).

Der Befund des Imkers: ueber HAIGS installierte Repos sind unter
«Geräte & Dienste» nicht zu finden. Die Antwort hat zwei Haelften:

* die WAHRHEIT je Karte -- der Zustands-Chip aus
  :mod:`custom_components.haigs.sichtbarkeit`, der hier ueber den
  echten Befehl ``haigs/eintraege`` geprueft wird: Neustart noch
  ausstehend, nicht geladen, bereit zum Hinzufuegen, eingerichtet,
  YAML-Weg, ungewiss;
* die BENACHRICHTIGUNG -- die dauerhafte Meldung, die Installation und
  Deinstallation begleitet und den zweiten Schritt nennt, den kein
  Dialog abnimmt.

Alles offline: die Attrappe liefert die Antworten, der Zustand kommt
aus Home Assistant selbst (Issue-Register, geladene Komponenten,
Konfigurationseintraege, manifest.json am Zielweg).
"""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haigs.aktualisierer import _kennung
from custom_components.haigs.const import DOMAIN
from custom_components.haigs.neustart import neustart_hinweis

from .test_m5 import (
    eintrag_daten,
    herzschlag,
    release_objekt,
    speichern,
    stammdaten,
)
from .test_m7 import STORAGE_KEY, frage, mock_eintrag, releases, richten, zip_aufzeichnung

DOMAIN_BEISPIEL = "beispiel_integration"
ZIELWEG = "custom_components/" + DOMAIN_BEISPIEL


async def richten_mit_installation(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, **stand: object
) -> None:
    """Eine Instanz mit einem installierten Eintrag -- offline.

    Der Stand traegt Version und Zielweg; die Aufzeichnungen decken
    Herzschlag, den ersten M5-Lauf und den einmaligen Live-Bau des
    Lagers (``eintraege`` auf leerem Lager baut die Zeilen frisch).
    """
    lage = {"installiert": "1.1.0", "vorabversionen": False, "pfad": ZIELWEG}
    lage.update(stand)
    speichern(hass_storage, [eintrag_daten()], stand={STORAGE_KEY: lage})
    sitzung_einpflanzen(
        [
            herzschlag(),  # Herzschlag beim Richten
            stammdaten(),  # erster M5-Lauf: Stammdaten ueber die ID
            releases(release_objekt("v1.2.0")),  # erster M5-Lauf: Releases
            stammdaten(),  # eintraege: Lager leer, einmal live bauen
        ]
    )
    await richten(hass, mock_eintrag())


async def zeile_holen(hass: HomeAssistant, client) -> dict:
    """Die (einzige) Zeile der Liste, wie das Panel sie bekommt."""
    antwort = await frage(client, 1, "haigs/eintraege")
    assert antwort["success"], antwort
    zeilen = antwort["result"]["eintraege"]
    assert len(zeilen) == 1, zeilen
    return zeilen[0]


def manifest_schreiben(hass: HomeAssistant, config_flow: bool) -> None:
    """Die manifest.json am Zielweg -- die Wahrheit nach dem Entpacken."""
    ordner = Path(hass.config.config_dir) / ZIELWEG
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "manifest.json").write_text(
        json.dumps(
            {
                "domain": DOMAIN_BEISPIEL,
                "name": "Beispiel",
                "version": "1.1.0",
                "config_flow": config_flow,
            }
        ),
        encoding="utf-8",
    )


def geladen(hass: HomeAssistant, domain: str = DOMAIN_BEISPIEL) -> None:
    """Die YAML-Einrichtung: der Start lief hoch, ohne Karte im Dialog.

    Der Einrichtungsdialog listet Integrationen aus dem Manifest-Scan
    -- NICHT aus den gelaufenen Komponenten. Erst wenn die Domain unter
    den gelaufenen steht (configuration.yaml) oder ein Eintrag existiert,
    gilt die Integration als eingerichtet.
    """
    hass.config.components.add(domain)


async def test_nach_der_installation_steht_der_neustart_an(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Frisch installiert: der Start fehlt, der Chip sagt es -- und die
    dauerhafte Meldung nennt beide Schritte."""
    await async_setup_component(hass, "persistent_notification", {})
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    laufzeit = next(iter(hass.data[DOMAIN].values()))
    eintrag = laufzeit.eintraege.alle()[0]
    neustart_hinweis(hass, eintrag, "1.2.0", "installation", mit_dialog=True)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"] == {"zustand": "neustart", "domain": DOMAIN_BEISPIEL}

    # Die Glocke: dauerhaft, mit dem Weg nach dem Neustart.
    hass.config.language = "de"
    neustart_hinweis(hass, eintrag, "1.2.0", "installation", mit_dialog=True)
    meldungen = hass.data["persistent_notification"]
    eintrag_id = "haigs_neustart_" + _kennung(STORAGE_KEY)
    assert eintrag_id in meldungen
    assert "Geräte & Dienste" in meldungen[eintrag_id]["message"]
    assert "neu starten" in meldungen[eintrag_id]["message"]


async def test_ohne_dialog_nennt_die_meldung_den_yaml_weg(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Integrationen ohne Einrichtungsdialog koennen unter «Geräte &
    Dienste» nie auftauchen -- die Meldung sagt den ehrlichen Weg."""
    await async_setup_component(hass, "persistent_notification", {})
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    laufzeit = next(iter(hass.data[DOMAIN].values()))
    eintrag = laufzeit.eintraege.alle()[0]
    hass.config.language = "de"
    neustart_hinweis(hass, eintrag, "1.2.0", "installation", mit_dialog=False)
    meldung = hass.data["persistent_notification"][
        "haigs_neustart_" + _kennung(STORAGE_KEY)
    ]
    assert "configuration.yaml" in meldung["message"]
    assert "Integration hinzufügen" not in meldung["message"]


async def test_nach_dem_start_bereit_zum_hinzufuegen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Start geschehen, Dialog da, kein Eintrag: der Chip ist der
    Knopf -- der Einrichtungsdialog findet die Integration ueber den
    Manifest-Scan, auch ohne dass sie je geladen wurde."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    manifest_schreiben(hass, config_flow=True)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "hinzufuegen"
    assert zeile["integration"]["domain"] == DOMAIN_BEISPIEL


async def test_ohne_dialog_heisst_der_weg_yaml(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Geladen oder nicht: ohne Dialog kein «Hinzufügen», nur YAML."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    manifest_schreiben(hass, config_flow=False)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "yaml"


async def test_yaml_einrichtung_laufen_heisst_eingerichtet(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """configuration.yaml brachte sie hoch: ohne Karte, aber eingerichtet."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    manifest_schreiben(hass, config_flow=False)
    geladen(hass)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "eingerichtet"


async def test_mit_eintrag_ist_eingerichtet(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Konfigurationseintrag da: die Karte unter Geräte & Dienste lebt."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    manifest_schreiben(hass, config_flow=True)
    geladen(hass)
    MockConfigEntry(domain=DOMAIN_BEISPIEL, title="Beispiel").add_to_hass(hass)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "eingerichtet"


async def test_nach_dem_start_nicht_geladen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Start geschehen, aber das Manifest ist unlesbar: dem System
    fehlt die Integration -- rot, Protokoll statt Rat."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    # kein Issue, kein Eintrag -- und am Zielweg liegt Muell statt
    # einer lesbaren manifest.json (kaputt oder halbe Installation).
    ordner = Path(hass.config.config_dir) / ZIELWEG
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / "manifest.json").write_text("{kein json", encoding="utf-8")

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "nicht_geladen"


async def test_ohne_weg_heisst_es_ungewiss(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Installiert vor Stufe M4b: Version ohne Weg, ehrlich ungewiss."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage, pfad="")

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"] == {"zustand": "ungewiss", "domain": ""}


async def test_nicht_installiert_tragt_keinen_chip(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Beobachtet, aber nichts heruntergeladen: keine Aussage, kein Chip."""
    speichern(hass_storage, [eintrag_daten()])
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            stammdaten(),
        ]
    )
    await richten(hass, mock_eintrag())

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert "integration" not in zeile


async def test_der_chip_reist_nicht_ins_lager(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Der Zustand ist eine Aussage ueber JETZT -- er gehoert nicht in
    den Speicher. Die Antwort traegt Kopien; das Lager bleibt nackt."""
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    manifest_schreiben(hass, config_flow=True)

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["integration"]["zustand"] == "hinzufuegen"

    laufzeit = next(iter(hass.data[DOMAIN].values()))
    lager_zeile = laufzeit.lager.zeilen[0]
    assert "integration" not in lager_zeile
    assert lager_zeile["zielweg"] == ZIELWEG


async def test_deinstallation_meldet_sich_ohne_dialog_frage(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Auch die Deinstallation klingelt -- ohne zweiten Schritt."""
    await async_setup_component(hass, "persistent_notification", {})
    await richten_mit_installation(hass, sitzung_einpflanzen, hass_storage)
    laufzeit = next(iter(hass.data[DOMAIN].values()))
    eintrag = laufzeit.eintraege.alle()[0]
    hass.config.language = "de"
    neustart_hinweis(hass, eintrag, "1.1.0", "deinstallation")
    meldung = hass.data["persistent_notification"][
        "haigs_neustart_" + _kennung(STORAGE_KEY)
    ]
    assert "deinstalliert" in meldung["title"]
    assert "bis zum nächsten Start" in meldung["message"]
    # Der Neustart-Hinweis steht zusaetzlich auf dem Reparatur-Brett.
    register = issue_registry.async_get(hass)
    assert (DOMAIN, "neustart_" + _kennung(STORAGE_KEY)) in register.issues


async def test_installation_zieht_das_lager_und_die_glocke_mit(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Der install-Dienst allein (Updates-Seite, kein Panel!) macht die
    Zeile ehrlich: Version und Zielweg stehen sofort, der Chip sagt
    «neustart», und die Glocke nennt den Weg (ohne Dialog: YAML)."""
    await async_setup_component(hass, "persistent_notification", {})
    speichern(hass_storage, [eintrag_daten()])
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            releases(release_objekt("v1.2.0")),  # die Installation fragt noch mal
            zip_aufzeichnung(),  # das Tag-Archiv
            stammdaten(),  # eintraege: Lager leer, einmal live bauen
        ]
    )
    await richten(hass, mock_eintrag())
    hass.config.language = "de"

    update_id = sorted(hass.states.async_entity_ids("update"))[0]
    await hass.services.async_call(
        "update", "install", {"entity_id": update_id}, blocking=True
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    zeile = await zeile_holen(hass, client)
    assert zeile["installiert"] == "1.2.0"
    assert zeile["zielweg"] == ZIELWEG
    assert zeile["integration"]["zustand"] == "neustart"

    meldung = hass.data["persistent_notification"][
        "haigs_neustart_" + _kennung(STORAGE_KEY)
    ]
    assert "1.2.0" in meldung["title"]
    assert "configuration.yaml" in meldung["message"]
