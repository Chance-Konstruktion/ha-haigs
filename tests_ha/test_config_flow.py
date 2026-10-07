"""Der Einrichtungsdialog auf der Attrappe -- der echte Weg, ohne Netz."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
import voluptuous as vol
from homeassistant.config_entries import SOURCE_USER, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.haigs.const import (
    CONF_ABSTAND_MINUTEN,
    CONF_HOST,
    CONF_PROVIDER,
    CONF_TOKEN,
    DOMAIN,
)
from custom_components.haigs.eintraege import (
    CONF_ADRESSE,
    CONF_DATEIEN_DEINSTALLIEREN,
    CONF_ENTFERNEN,
    CONF_KATEGORIE,
)
from tests.attrappe import Aufzeichnung, projekt

#: Ein gespeicherter Eintrag, wie ihn Stufe M3 ablegt.
EINTRAG = {
    "provider": "gitlab",
    "host": "gitlab.example.net",
    "provider_id": "789012",
    "full_name": "foo/bar",
    "kategorie": "integration",
    "hinzugefuegt_am": "2026-09-03T20:00:00+00:00",
}


def antwort(anzahl: int = 1) -> Aufzeichnung:
    """Eine Topic-Suche, die ``anzahl`` Projekte meldet."""
    return Aufzeichnung(
        text=json.dumps([projekt() for _ in range(anzahl)]), kopfzeilen={}
    )


def forgejo_antwort(anzahl: int = 1) -> Aufzeichnung:
    """Eine Familien-Suche (API v1), die ``anzahl`` Projekte meldet.

    Gitea wie Forgejo antworten auf ``/repos/search`` mit einem Mantel
    um die Treffer (``data``) -- nicht mit der nackten Liste wie GitLab.
    """
    treffer = {
        "id": 4711,
        "full_name": "foo/bar",
        "description": "ein Testprojekt",
        "default_branch": "main",
        "topics": ["hacs"],
        "stars_count": 7,
        "open_issues_count": 2,
        "archived": False,
        "html_url": "https://gitea.example/foo/bar",
        "avatar_url": "",
    }
    return Aufzeichnung(
        text=json.dumps({"ok": True, "data": [treffer for _ in range(anzahl)]}),
        kopfzeilen={},
    )


async def test_dialog_erscheint(hass: HomeAssistant) -> None:
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "user"
    assert ergebnis["errors"] == {}


async def test_verbindung_gelingt(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    # Zwei Antworten: eine fuer die Pruefung im Dialog, eine fuer den
    # ersten Herzschlag -- Home Assistant richtet den Eintrag nach dem
    # Dialog sofort ein.
    attrappe = sitzung_einpflanzen([antwort(), antwort()])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["title"] == "gitlab.example.net"
    assert ergebnis["data"] == {
        CONF_HOST: "gitlab.example.net",
        CONF_PROVIDER: "gitlab",
        CONF_TOKEN: "",
    }
    assert len(attrappe.abrufe) == 2
    assert attrappe.abrufe[0][0].startswith("https://gitlab.example.net/api/v4/projects")
    # Ohne Token reist keine Berechtigungskopfzeile.
    assert "Authorization" not in (attrappe.abrufe[0][2] or {})
    # Der Eintrag steht: Dialog und erster Herzschlag sind beide durch.
    eintraege = hass.config_entries.async_entries(DOMAIN)
    assert len(eintraege) == 1
    assert eintraege[0].state is ConfigEntryState.LOADED


async def test_probe_holt_hoechstens_eine_seite(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Der Dialog beweist die Verbindung -- er inventarisiert sie nicht.

    Vorher rief die Pruefung ``suche_nach_topic()`` ohne Grenze auf:
    ``per_page=100``, und der HTTP-Zugang verfolgte ``X-Next-Page`` bis
    zu 200 Seiten weiter. Gegen eine grosse Instanz -- gitlab.com steht
    als Vorgabe im Formular -- holte ein Klick auf "Absenden" im
    schlimmsten Fall zwanzigtausend Projekte, bevor der Dialog
    antwortete (Issue #11, Befund b).

    Geprueft wird deshalb beides: die kleine Seite UND dass keine
    Folgeseite geholt wird, obwohl der Anbieter eine anbietet.
    """
    attrappe = sitzung_einpflanzen(
        [
            Aufzeichnung(
                text=json.dumps([projekt() for _ in range(1)]),
                kopfzeilen={"X-Next-Page": "2"},
            ),
            antwort(),  # fuer den ersten Herzschlag nach dem Dialog
        ]
    )

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    url, params, _ = attrappe.abrufe[0]
    assert params["per_page"] == "1", "die Probe darf nur einen Eintrag anfordern"
    # Zwei Abrufe insgesamt: Dialog und Herzschlag. Waere die Folgeseite
    # geholt worden, stuenden hier drei.
    assert len(attrappe.abrufe) == 2


async def test_token_reist_als_kopfzeile(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    attrappe = sitzung_einpflanzen([antwort(0)])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {
            CONF_HOST: "gitlab.example.net",
            CONF_PROVIDER: "gitlab",
            CONF_TOKEN: "geheimes-ding",
        },
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert attrappe.abrufe[0][2]["Authorization"] == "Bearer geheimes-ding"


async def test_eingefuegter_link_wird_zum_host(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    sitzung_einpflanzen([antwort()])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {
            CONF_HOST: "https://GitLab.Example.Net/gruppe/projekt",
            CONF_PROVIDER: "gitlab",
            CONF_TOKEN: "",
        },
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["data"][CONF_HOST] == "gitlab.example.net"


async def test_token_fehlt_gibt_verstaendliche_meldung(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    sitzung_einpflanzen(
        [
            Aufzeichnung(
                status=401,
                text=json.dumps({"message": "401 Unauthorized"}),
                kopfzeilen={},
            )
        ]
    )

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "token_reicht_nicht"}


async def test_anderer_fehler_gibt_verstaendliche_meldung(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    sitzung_einpflanzen([Aufzeichnung(status=500, text="kaputt", kopfzeilen={})])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "verbindung_fehlgeschlagen"}


async def test_toter_host_gibt_verstaendliche_meldung(
    hass: HomeAssistant, tote_sitzung
) -> None:
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "host_nicht_erreichbar"}


async def test_derselbe_host_nur_einmal(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    sitzung_einpflanzen([antwort()])
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY

    sitzung_einpflanzen([antwort()])
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "already_configured"


async def dialog_und_eintrag(
    hass: HomeAssistant, sitzung_einpflanzen, aufzeichnungen: list[Aufzeichnung]
):
    """Richtet den Eintrag per Dialog und liefert ihn mit der Attrappe.

    Alle Aufzeichnungen gehoeren in EINEN Aufruf: der Forge der Laufzeit
    behaelt die Attrappe, die ihm beim Richten gereicht wurde.
    """
    attrappe = sitzung_einpflanzen(aufzeichnungen)
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()
    mock = hass.config_entries.async_entries(DOMAIN)[0]
    assert mock.state is ConfigEntryState.LOADED
    return mock, attrappe


async def menue_waehlen(hass: HomeAssistant, mock, wahl: str):
    """Startet den Optionsfluss und waehlt einen Menuepunkt."""
    ergebnis = await hass.config_entries.options.async_init(mock.entry_id)
    assert ergebnis["type"] is FlowResultType.MENU
    return await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {"next_step_id": wahl}
    )


def projekt_als_antwort(**felder) -> Aufzeichnung:
    """Ein einzelnes Projekt, wie es die Projects-API liefert."""
    return Aufzeichnung(text=json.dumps(projekt(**felder)), kopfzeilen={})


# -- Nachschau zu #13: Leerpruefung VOR dem Verbindungsversuch ---------


async def test_leerer_host_ohne_verbindung(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    attrappe = sitzung_einpflanzen([])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"], {CONF_HOST: "", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "host_leer"}
    # Wichtig ist das NICHT-Geschehene: keine einzige Anfrage.
    assert attrappe.abrufe == []


# -- Flug 2088: die Schmiede im Dialog ---------------------------------


def version_frage(antwort_text: str) -> Aufzeichnung:
    """Die Antwort auf eine Versionfrage (``/api/v*/version``)."""
    return Aufzeichnung(text=json.dumps({"version": antwort_text}), kopfzeilen={})


def weg_404() -> Aufzeichnung:
    """Ein 404, wie jede Forge es auf einen Pfad ohne Tor meldet."""
    return Aufzeichnung(
        status=404, text=json.dumps({"message": "404 Not Found"}), kopfzeilen={}
    )


async def test_auto_erkent_gitlab(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    """auto fragt zuerst die GitLab-Versionfrage -- das offene Tor nennt den Namen."""
    attrappe = sitzung_einpflanzen(
        [version_frage("17.9.0"), antwort(), antwort()]  # Erkennung, Probe, Herzschlag
    )

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "auto", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["data"][CONF_PROVIDER] == "gitlab"
    assert attrappe.abrufe[0][0] == "https://gitlab.example.net/api/v4/version"
    assert len(attrappe.abrufe) == 3


async def test_auto_erkent_forgejo(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    """Forgejo nennt die eigene Nummer (ab v7, 2024) -- die reicht."""
    attrappe = sitzung_einpflanzen(
        [weg_404(), version_frage("13.0.1"), forgejo_antwort(), forgejo_antwort()]
    )

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "forgejo.example.net", CONF_PROVIDER: "auto", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["data"][CONF_PROVIDER] == "forgejo"
    # Die Erkennung: Versionfrage GitLab (404), dann Familie (Nummer 13).
    assert attrappe.abrufe[0][0].endswith("/api/v4/version")
    assert attrappe.abrufe[1][0] == "https://forgejo.example.net/api/v1/version"
    # Die Probe lief durch die Forgejo-Schmiede: das Familien-Tor.
    assert attrappe.abrufe[2][0] == "https://forgejo.example.net/api/v1/repos/search"


async def test_auto_erkent_gitea(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    """Giteas 1.x trennt nichts -- die Startseite nennt den Namen."""
    attrappe = sitzung_einpflanzen(
        [
            weg_404(),
            version_frage("1.23.8"),
            Aufzeichnung(
                rohbytes=b"<html><footer>Powered by Gitea</footer></html>",
                kopfzeilen={},
            ),
            forgejo_antwort(),
            forgejo_antwort(),
        ]
    )

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gitea.example.net", CONF_PROVIDER: "auto", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert ergebnis["data"][CONF_PROVIDER] == "gitea"
    # Das Plaedoyer der Startseite stand zwischen Familie und Probe.
    assert attrappe.abrufe[2][0] == "https://gitea.example.net/"
    # Und die Probe lief durch die Gitea-Tochter: sie allein schickt topic=true.
    url, parameter, _ = attrappe.abrufe[3]
    assert url == "https://gitea.example.net/api/v1/repos/search"
    assert parameter.get("topic") == "true"


async def test_auto_ohne_anbieter_bittet_um_die_hand(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Antwortet dort niemand: der ehrliche Fehler, kein geratenes GitLab."""
    sitzung_einpflanzen([weg_404(), weg_404()])

    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    ergebnis = await hass.config_entries.flow.async_configure(
        ergebnis["flow_id"],
        {CONF_HOST: "gibts.net.example", CONF_PROVIDER: "auto", CONF_TOKEN: ""},
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "anbieter_unerkannt"}


async def test_unbekannter_anbieter_ist_ein_formfehler(
    hass: HomeAssistant,
) -> None:
    """Ein erfundener Name kommt gar nicht erst in den Schritt.

    Das Formular selbst weisst ihn zurueck (vol.In): die Schmiede
    sieht ihn nie, das Netz erst recht nicht. Das hier haelt die
    Auswahl fest, die das Formular anbietet -- auto und die drei
    Schmieden, und nichts sonst.
    """
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert ergebnis["type"] is FlowResultType.FORM
    schema = ergebnis["data_schema"]

    with pytest.raises(vol.Invalid):
        schema({"host": "gitea.example.net", "provider": "hub", "token": ""})

    for name in ("auto", "gitlab", "forgejo", "gitea"):
        gereinigt = schema({"host": "x.example", "provider": name, "token": ""})
        assert gereinigt["provider"] == name


# -- Optionsmenue ------------------------------------------------------


async def test_options_menue_erscheint(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    mock, _ = await dialog_und_eintrag(hass, sitzung_einpflanzen, [antwort(), antwort()])

    ergebnis = await hass.config_entries.options.async_init(mock.entry_id)

    assert ergebnis["type"] is FlowResultType.MENU
    assert ergebnis["step_id"] == "init"
    assert set(ergebnis["menu_options"]) == {
        "abstand",
        "entwickler",
        "repository",
        "eintraege",
        "katalog",
    }


async def test_abstand_ueber_das_menue(hass: HomeAssistant, sitzung_einpflanzen) -> None:
    # Dritte Antwort fuer den Fall, dass der Eintrag neu gerichtet wird.
    mock, _ = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort(), antwort()]
    )

    ergebnis = await menue_waehlen(hass, mock, "abstand")
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "abstand"

    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ABSTAND_MINUTEN: 30}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    koordinator = hass.data[DOMAIN][mock.entry_id].koordinator
    assert koordinator.update_interval == timedelta(minutes=30)


async def test_entwicklermodus_ueber_das_menue(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Flug 2101: der Schalter steht im Menue und laesst den Abstand stehen."""
    mock, _ = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort(), antwort(), antwort()]
    )
    hass.config_entries.async_update_entry(mock, options={CONF_ABSTAND_MINUTEN: 30})
    await hass.async_block_till_done()

    ergebnis = await menue_waehlen(hass, mock, "entwickler")
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "entwickler"

    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {"entwicklermodus": True}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert mock.options["entwicklermodus"] is True
    assert mock.options[CONF_ABSTAND_MINUTEN] == 30


# -- Offizielle HACS-Repos als Quelle -------------------------------------


def katalog_einpflanzen(attrappe) -> None:
    """Die Sitzung antwortet auf die Katalog-Adressen nach Adresse.

    Alles andere laeuft wie bisher aus den aufgezeichneten Antworten
    (und danach mit einer leeren Suche) -- so ist es egal, wie viele
    Laeufe die Optionsaenderung des anderen Eintrags auslost.
    """
    zeilen = {
        "integration": {
            "101": {
                "full_name": "foo/ha-bar",
                "description": "Eine Integration",
                "domain": "bar",
                "stargazers_count": 5,
                "downloads": 1234,
                "last_version": "1.2.3",
                "last_updated": "2026-09-01T10:00:00Z",
                "topics": [],
            }
        },
        "plugin": {},
        "theme": {},
    }
    original = attrappe.get

    async def get(url, params=None, headers=None):
        for kategorie, inhalt in zeilen.items():
            if f"data-v2.hacs.xyz/{kategorie}/" in url:
                attrappe.abrufe.append((url, params, headers))
                return Aufzeichnung(text=json.dumps(inhalt), kopfzeilen={})
        if not attrappe.aufzeichnungen:
            attrappe.aufzeichnungen.append(antwort())
        return await original(url, params, headers)

    attrappe.get = get


async def test_katalog_ein_und_ausschalten(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Der Schalter legt den Katalog-Eintrag an und entfernt ihn wieder."""
    mock, attrappe = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort()]
    )
    katalog_einpflanzen(attrappe)
    hass.config_entries.async_update_entry(mock, options={CONF_ABSTAND_MINUTEN: 30})
    await hass.async_block_till_done()

    ergebnis = await menue_waehlen(hass, mock, "katalog")
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "katalog"
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {"katalog_anzeigen": True}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    # Die anderen Optionen bleiben stehen.
    assert mock.options[CONF_ABSTAND_MINUTEN] == 30
    katalog = [
        e
        for e in hass.config_entries.async_entries(DOMAIN)
        if e.entry_id != mock.entry_id
    ]
    assert len(katalog) == 1
    assert katalog[0].data[CONF_HOST] == "github.com"
    assert katalog[0].data[CONF_PROVIDER] == "github"
    assert katalog[0].state is ConfigEntryState.LOADED
    assert hass.data[DOMAIN][katalog[0].entry_id].forge.provider == "github"

    # Zweiter Durchgang: der Schalter steht auf "an", ausschalten entfernt.
    ergebnis = await menue_waehlen(hass, mock, "katalog")
    assert ergebnis["data_schema"]({})["katalog_anzeigen"] is True
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {"katalog_anzeigen": False}
    )
    await hass.async_block_till_done()
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert [e.entry_id for e in hass.config_entries.async_entries(DOMAIN)] == [
        mock.entry_id
    ]


async def test_katalog_eintrag_hat_ein_eigenes_menue(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    """Der Katalog kennt weder Entwicklermodus noch freie Adressen."""
    katalog_einpflanzen(sitzung_einpflanzen([]))
    ergebnis = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data={}
    )
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    eintrag = hass.config_entries.async_entries(DOMAIN)[0]

    menue = await hass.config_entries.options.async_init(eintrag.entry_id)
    assert set(menue["menu_options"]) == {"abstand", "katalog", "eintraege"}

    # Ein zweiter Import legt keinen zweiten Eintrag an.
    nochmal = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data={}
    )
    assert nochmal["type"] is FlowResultType.ABORT


# -- Repository hinzufuegen ---------------------------------------------


async def test_repository_hinzufuegen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    mock, attrappe = await dialog_und_eintrag(
        hass,
        sitzung_einpflanzen,
        [antwort(), antwort(), projekt_als_antwort(), antwort()],
    )

    ergebnis = await menue_waehlen(hass, mock, "repository")
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "repository"

    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"],
        {CONF_ADRESSE: "https://gitlab.example.net/foo/bar"},
    )
    await hass.async_block_till_done()
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "kategorie"
    assert ergebnis["description_placeholders"]["name"] == "foo/bar*lab"
    # Der Blick ging durch die API, an das echte Projekt.
    assert "foo%2Fbar" in attrappe.abrufe[2][0]

    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_KATEGORIE: "integration"}
    )
    await hass.async_block_till_done()
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY

    laufzeit = hass.data[DOMAIN][mock.entry_id]
    assert len(laufzeit.eintraege) == 1
    assert laufzeit.eintraege.alle()[0].anzeigename == "foo/bar*lab"
    gespeichert = hass_storage["haigs.gitlab_example_net"]["data"]["eintraege"]
    assert gespeichert[0]["storage_key"] == "gitlab@gitlab.example.net:789012"
    assert gespeichert[0]["kategorie"] == "integration"


async def test_kategorie_vorbelegung_aus_topic(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    mock, _ = await dialog_und_eintrag(
        hass,
        sitzung_einpflanzen,
        [antwort(), antwort(), projekt_als_antwort(topics=("hacs", "hacs-plugin"))],
    )

    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"],
        {CONF_ADRESSE: "gitlab.example.net/foo/bar"},
    )
    await hass.async_block_till_done()

    assert ergebnis["step_id"] == "kategorie"
    for feld in ergebnis["data_schema"].schema:
        if feld.schema == CONF_KATEGORIE:
            vorbelegung = feld.default() if callable(feld.default) else feld.default
            assert vorbelegung == "plugin"


async def test_falsche_adresse_wird_benannt(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    mock, attrappe = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort()]
    )

    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ADRESSE: "nur-text-ohne-pfad"}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "repository"
    assert ergebnis["errors"] == {"base": "adresse_ungueltig"}
    assert len(attrappe.abrufe) == 2


async def test_anderer_host_wird_benannt(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    mock, attrappe = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort()]
    )

    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ADRESSE: "https://other.example.net/foo/bar"}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "anderer_host"}
    assert len(attrappe.abrufe) == 2


async def test_nicht_gefunden_wird_benannt(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    nicht_da = Aufzeichnung(
        status=404,
        text=json.dumps({"message": "404 Project Not Found"}),
        kopfzeilen={},
    )
    mock, _ = await dialog_und_eintrag(
        hass, sitzung_einpflanzen, [antwort(), antwort(), nicht_da]
    )

    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ADRESSE: "gitlab.example.net/foo/bar"}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "nicht_gefunden"}


async def test_doppeltes_repository_wird_abgewiesen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    # Die fuenfte und sechste Aufzeichnung gehoeren dem M8-Lauf nach dem
    # Anlegen: erst die Stammdaten ueber die ID, dann die Releases (das
    # Anlegen des Eintrags stoesst sofort eine Update-Runde an,
    # update.py-Beobachter).
    mock, _ = await dialog_und_eintrag(
        hass,
        sitzung_einpflanzen,
        [
            antwort(),
            antwort(),
            projekt_als_antwort(),
            projekt_als_antwort(),
            Aufzeichnung(
                text=json.dumps(
                    [
                        {
                            "tag_name": "v1.0.0",
                            "name": "Version v1.0.0",
                            "description": "",
                            "released_at": "2026-09-01",
                            "assets": {},
                        }
                    ]
                ),
                kopfzeilen={},
            ),
            projekt_als_antwort(),
        ],
    )
    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ADRESSE: "gitlab.example.net/foo/bar"}
    )
    await hass.async_block_till_done()
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_KATEGORIE: "integration"}
    )
    await hass.async_block_till_done()
    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY

    # Zweiter Anlauf mit derselben Adresse: abgewiesen, bevor angelegt wird.
    ergebnis = await menue_waehlen(hass, mock, "repository")
    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"], {CONF_ADRESSE: "https://gitlab.example.net/foo/bar*lab"}
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["errors"] == {"base": "bereits_vorhanden"}
    laufzeit = hass.data[DOMAIN][mock.entry_id]
    assert len(laufzeit.eintraege) == 1


# -- Eintraege entfernen -------------------------------------------------


async def test_repository_entfernen(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    hass_storage["haigs.gitlab_example_net"] = {
        "version": 1,
        "minor_version": 1,
        "key": "haigs.gitlab_example_net",
        "data": {"eintraege": [dict(EINTRAG)]},
    }
    sitzung_einpflanzen([antwort(), antwort()])
    mock = MockConfigEntry(
        domain=DOMAIN,
        title="gitlab.example.net",
        data={CONF_HOST: "gitlab.example.net", CONF_PROVIDER: "gitlab", CONF_TOKEN: ""},
        unique_id="gitlab.example.net",
    )
    mock.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock.entry_id)
    await hass.async_block_till_done()

    ergebnis = await menue_waehlen(hass, mock, "eintraege")
    assert ergebnis["type"] is FlowResultType.FORM
    assert ergebnis["step_id"] == "eintraege"
    assert "foo/bar*lab (integration)" in ergebnis["description_placeholders"]["liste"]

    ergebnis = await hass.config_entries.options.async_configure(
        ergebnis["flow_id"],
        {
            CONF_ENTFERNEN: "gitlab@gitlab.example.net:789012",
            CONF_DATEIEN_DEINSTALLIEREN: True,
        },
    )
    await hass.async_block_till_done()

    assert ergebnis["type"] is FlowResultType.CREATE_ENTRY
    assert len(hass.data[DOMAIN][mock.entry_id].eintraege) == 0
    assert hass_storage["haigs.gitlab_example_net"]["data"]["eintraege"] == []


async def test_entfernen_ohne_eintraege_bricht_ab(
    hass: HomeAssistant, sitzung_einpflanzen
) -> None:
    mock, _ = await dialog_und_eintrag(hass, sitzung_einpflanzen, [antwort(), antwort()])

    ergebnis = await menue_waehlen(hass, mock, "eintraege")

    assert ergebnis["type"] is FlowResultType.ABORT
    assert ergebnis["reason"] == "liste_leer"
