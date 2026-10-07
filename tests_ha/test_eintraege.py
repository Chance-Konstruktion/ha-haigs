"""Die Liste der Custom Repositories -- ohne Netz, mit echtem Speicher.

Gehoert zu Stufe M3 (Issue #3): das Verhalten der Liste selbst --
Adresse zerlegen, Kategorie vorbelegen, hinzufuegen, entfernen,
persistieren, und der Beweis, dass ein gleichnamiges GitHub-Repo ein
GitLab-Repo nicht verdraengt.
"""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from custom_components.haigs.ablage import Ablage
from custom_components.haigs.const import ABLAGE_VERSION, ablage_schluessel
from custom_components.haigs.core.identity import GITHUB, GITLAB, RepositoryIdentity
from custom_components.haigs.eintraege import (
    AdresseUngueltig,
    BereitsVorhanden,
    Eintraege,
    NichtVorhanden,
    adresse_zerlegen,
    kategorie_aus_topics,
)

SCHLUESSEL = ablage_schluessel("gitlab.example.net")


async def liste(hass: HomeAssistant) -> Eintraege:
    ablage = Ablage(Store(hass, ABLAGE_VERSION, SCHLUESSEL))
    return await Eintraege.aus_ablage(ablage)


def identitaet(
    provider: str = GITLAB,
    host: str = "gitlab.example.net",
    provider_id: str = "789012",
    full_name: str = "foo/bar",
) -> RepositoryIdentity:
    return RepositoryIdentity(
        provider=provider,
        host=host,
        provider_id=provider_id,
        full_name=full_name,
    )


# -- Adresse zerlegen ------------------------------------------------


@pytest.mark.parametrize(
    ("adresse", "erwartet"),
    [
        (
            "https://gitlab.example.net/gruppe/projekt",
            ("gitlab.example.net", "gruppe/projekt"),
        ),
        ("gitlab.example.net/gruppe/projekt", ("gitlab.example.net", "gruppe/projekt")),
        (
            "https://GitLab.Example.Net/gruppe/projekt",
            ("gitlab.example.net", "gruppe/projekt"),
        ),
        ("https://host/gruppe/unter/projekt", ("host", "gruppe/unter/projekt")),
        ("https://host/gruppe/projekt*lab", ("host", "gruppe/projekt")),
        ("https://host/gruppe/projekt.git", ("host", "gruppe/projekt")),
        ("https://host/gruppe/projekt?egal=1#rest", ("host", "gruppe/projekt")),
        ("http://host:8443/gruppe/projekt", ("host:8443", "gruppe/projekt")),
    ],
)
def test_adresse_zerlegen(adresse: str, erwartet: tuple[str, str]) -> None:
    assert adresse_zerlegen(adresse) == erwartet


@pytest.mark.parametrize(
    "adresse",
    [
        "",
        "   ",
        "nur-ein-host",
        "https://host/",
        "https://host/projekt",
        "git@host:gruppe/projekt",
    ],
)
def test_adresse_zerlegen_lehnt_ab(adresse: str) -> None:
    with pytest.raises(AdresseUngueltig):
        adresse_zerlegen(adresse)


def test_kategorie_aus_topics() -> None:
    assert kategorie_aus_topics(("hacs", "hacs-plugin")) == "plugin"
    assert kategorie_aus_topics(["hacs-integration"]) == "integration"
    assert kategorie_aus_topics(("hacs",)) is None
    assert kategorie_aus_topics(None) is None
    # integration steht in KATEGORIEN zuerst und gewinnt Mehrdeutigkeiten.
    assert kategorie_aus_topics(("hacs-theme", "hacs-integration")) == "integration"


# -- Hinzufuegen und Entfernen ---------------------------------------


async def test_hinzufuegen_persistiert(hass: HomeAssistant, hass_storage) -> None:
    eintraege = await liste(hass)
    eintrag = await eintraege.hinzufuegen(identitaet(), "integration")

    assert len(eintraege) == 1
    assert eintrag.anzeigename == "foo/bar*lab"
    assert eintrag.kategorie == "integration"
    assert eintrag.hinzugefuegt_am

    gespeichert = hass_storage[SCHLUESSEL]["data"]["eintraege"]
    assert len(gespeichert) == 1
    assert gespeichert[0]["storage_key"] == "gitlab@gitlab.example.net:789012"
    assert gespeichert[0]["kategorie"] == "integration"


async def test_doppelte_storage_key_abgewiesen(hass: HomeAssistant, hass_storage) -> None:
    eintraege = await liste(hass)
    await eintraege.hinzufuegen(identitaet(), "integration")

    with pytest.raises(BereitsVorhanden):
        await eintraege.hinzufuegen(identitaet(), "plugin")
    assert len(eintraege) == 1


async def test_gleichnamiges_github_repo_verdraengt_nicht(
    hass: HomeAssistant, hass_storage
) -> None:
    """Die Abnahme von Stufe M3, am Kern der Unterscheidung.

    foo/bar auf dem GitLab und foo/bar auf GitHub teilen den Namen --
    und nichts sonst. Beide bleiben in der Liste.
    """
    eintraege = await liste(hass)
    await eintraege.hinzufuegen(identitaet(provider=GITLAB), "integration")
    await eintraege.hinzufuegen(
        identitaet(provider=GITHUB, host="github.com", provider_id="987654"),
        "plugin",
    )

    assert len(eintraege) == 2
    namen = {eintrag.anzeigename for eintrag in eintraege}
    assert namen == {"foo/bar*lab", "foo/bar"}
    schluessel = {eintrag.storage_key for eintrag in eintraege}
    assert "gitlab@gitlab.example.net:789012" in schluessel
    assert "github@github.com:987654" in schluessel


async def test_gleicher_name_anderer_host_bleibt(
    hass: HomeAssistant, hass_storage
) -> None:
    """Auch zwei GitLab-Instanzen trennt der Host im Schluessel."""
    eintraege = await liste(hass)
    await eintraege.hinzufuegen(identitaet(), "integration")
    await eintraege.hinzufuegen(
        identitaet(host="gitlab.example.org", provider_id="123"), "integration"
    )
    assert len(eintraege) == 2


async def test_entfernen(hass: HomeAssistant, hass_storage) -> None:
    eintraege = await liste(hass)
    await eintraege.hinzufuegen(identitaet(), "integration")
    await eintraege.hinzufuegen(
        identitaet(provider_id="4711", full_name="anderes/projekt"), "theme"
    )

    entfernt = await eintraege.entfernen("gitlab@gitlab.example.net:789012")
    assert entfernt.anzeigename == "foo/bar*lab"
    assert len(eintraege) == 1
    assert hass_storage[SCHLUESSEL]["data"]["eintraege"][0]["full_name"] == (
        "anderes/projekt"
    )

    with pytest.raises(NichtVorhanden):
        await eintraege.entfernen("gitlab@gitlab.example.net:789012")


# -- Neustart und Reparatur -------------------------------------------


async def test_eintraege_ueberleben_den_neustart(
    hass: HomeAssistant, hass_storage
) -> None:
    """Was in der Ablage steht, kommt nach dem Richten wieder raus."""
    hass_storage[SCHLUESSEL] = {
        "version": 1,
        "minor_version": 1,
        "key": SCHLUESSEL,
        "data": {
            "eintraege": [
                {
                    "provider": GITLAB,
                    "host": "gitlab.example.net",
                    "provider_id": "789012",
                    "full_name": "foo/bar",
                    "kategorie": "integration",
                    "hinzugefuegt_am": "2026-09-03T20:00:00+00:00",
                }
            ]
        },
    }

    eintraege = await liste(hass)
    assert len(eintraege) == 1
    eintrag = eintraege.alle()[0]
    assert eintrag.anzeigename == "foo/bar*lab"
    assert eintrag.kategorie == "integration"


async def test_unlesbare_eintraege_entfallen(hass: HomeAssistant, hass_storage) -> None:
    hass_storage[SCHLUESSEL] = {
        "version": 1,
        "minor_version": 1,
        "key": SCHLUESSEL,
        "data": {
            "eintraege": [
                "kein objekt",
                {"provider": GITLAB},  # unvollstaendig
                {
                    "provider": GITLAB,
                    "host": "gitlab.example.net",
                    "provider_id": "789012",
                    "full_name": "foo/bar",
                    "kategorie": "gibts-nicht",
                },
                {
                    "provider": GITLAB,
                    "host": "gitlab.example.net",
                    "provider_id": "789012",
                    "full_name": "foo/bar",
                    "kategorie": "integration",
                },
            ]
        },
    }

    eintraege = await liste(hass)
    assert len(eintraege) == 1
    assert eintraege.alle()[0].kategorie == "integration"
