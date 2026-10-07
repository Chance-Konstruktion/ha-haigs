"""Richten, Herzschlag, Ablage, Abstand, Entfernen -- alles offline."""

from __future__ import annotations

import json
from datetime import timedelta

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haigs.const import (
    CONF_ABSTAND_MINUTEN,
    CONF_HOST,
    CONF_TOKEN,
    DOMAIN,
    STANDARD_ABSTAND_MINUTEN,
)
from tests.attrappe import Aufzeichnung, projekt


def antwort(anzahl: int = 1) -> Aufzeichnung:
    return Aufzeichnung(
        text=json.dumps([projekt() for _ in range(anzahl)]), kopfzeilen={}
    )


def eintrag(host: str = "gitlab.example.net", **rest) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title=host,
        data={CONF_HOST: host, CONF_TOKEN: ""},
        unique_id=host,
        **rest,
    )


async def richten(hass: HomeAssistant, mock: MockConfigEntry) -> None:
    mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock.entry_id)
    await hass.async_block_till_done()


async def test_eintrag_richtet_sich(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    attrappe = sitzung_einpflanzen([antwort()])
    mock = eintrag()
    await richten(hass, mock)

    assert mock.state is ConfigEntryState.LOADED
    laufzeit = hass.data[DOMAIN][mock.entry_id]
    assert laufzeit.koordinator.data == {
        "instanz": "gitlab.example.net",
        "gefundene_projekte": 1,
    }
    # Der Herzschlag lief genau einmal, durch die Attrappe.
    assert len(attrappe.abrufe) == 1


async def test_ablage_tragt_den_host_im_schluessel(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    sitzung_einpflanzen([antwort()])
    await richten(hass, eintrag())

    assert "haigs.gitlab_example_net" in hass_storage
    gespeichert = hass_storage["haigs.gitlab_example_net"]
    assert gespeichert["version"] == 1
    assert gespeichert["data"] == {"eintraege": [], "stand": {}}


async def test_zwei_instanzen_nebeneinander(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    sitzung_einpflanzen([antwort(), antwort(2)])
    mock_eins = eintrag(host="gitlab.com")
    mock_zwei = eintrag(host="gitlab.example.net")
    await richten(hass, mock_eins)
    await richten(hass, mock_zwei)

    assert mock_eins.state is ConfigEntryState.LOADED
    assert mock_zwei.state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][mock_eins.entry_id].koordinator.data["instanz"] == (
        "gitlab.com"
    )
    assert (
        hass.data[DOMAIN][mock_zwei.entry_id].koordinator.data["gefundene_projekte"] == 2
    )
    # Zwei Ablagen, getrennt durch den Host im Schluessel.
    assert "haigs.gitlab_com" in hass_storage
    assert "haigs.gitlab_example_net" in hass_storage


async def test_ablage_wandelt_alte_form(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    hass_storage["haigs.gitlab_example_net"] = {
        "version": 1,
        "minor_version": 1,
        "key": "haigs.gitlab_example_net",
        "data": {"irgendwas_altes": 7},
    }
    sitzung_einpflanzen([antwort()])
    await richten(hass, eintrag())

    assert hass_storage["haigs.gitlab_example_net"]["data"] == {
        "eintraege": [],
        "stand": {},
    }


async def test_kaputte_instanz_meldet_wiederholung(
    hass: HomeAssistant, tote_sitzung
) -> None:
    mock = eintrag()
    mock.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock.entry_id)
    await hass.async_block_till_done()
    assert mock.state is ConfigEntryState.SETUP_RETRY


async def test_standardabstand_und_umstellung(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    sitzung_einpflanzen([antwort()])
    mock = eintrag()
    await richten(hass, mock)
    koordinator = hass.data[DOMAIN][mock.entry_id].koordinator
    assert koordinator.update_interval == timedelta(minutes=STANDARD_ABSTAND_MINUTEN)

    hass.config_entries.async_update_entry(mock, options={CONF_ABSTAND_MINUTEN: 60})
    await hass.async_block_till_done()
    assert koordinator.update_interval == timedelta(minutes=60)


async def test_abstand_aus_optionen_von_anfang_an(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    sitzung_einpflanzen([antwort()])
    mock = eintrag(options={CONF_ABSTAND_MINUTEN: 45})
    await richten(hass, mock)
    koordinator = hass.data[DOMAIN][mock.entry_id].koordinator
    assert koordinator.update_interval == timedelta(minutes=45)


async def test_eintrag_entfernt_sich(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    sitzung_einpflanzen([antwort()])
    mock = eintrag()
    await richten(hass, mock)

    await hass.config_entries.async_remove(mock.entry_id)
    await hass.async_block_till_done()

    assert mock.state is ConfigEntryState.NOT_LOADED
    assert mock.entry_id not in hass.data.get(DOMAIN, {})
