"""Stufe M4b in Home Assistant: Anhang-Quelle, Deinstallation, Neustart.

Alles offline: die Sitzungs-Attrappe spielt die GitLab-Antworten in
Reihenfolge ab (Richten, erster Lauf, dann was der einzelne Test
anstoesst). Der Clou dieser Datei ist der Dogfood-Beweis: der
Release-Anhang ist das ECHTE, mit ``auslieferung/release_bauen.py``
aus diesem Repository gebaute ZIP -- die Abnahme «eine echte
Integration aus dem eigenen GitLab laeuft nach der Installation in
HA» wird hier mit dem eigenen Release gefahren: die gleiche
Integration, die diesen Test gerade als laufende Instanz abwickelt,
liegt danach als Dateien im Konfigurationsverzeichnis.

Deinstallation geht durch den Panel-Befehl ``haigs/deinstallieren``
(WebSocket): Home Assistants update-Entities kennen kein
Uninstall-Konzept, also ist es hier ein Befehl und kein Dienst von
ihnen.
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry

from auslieferung.release_bauen import baue_release
from custom_components.haigs.aktualisierer import _kennung
from custom_components.haigs.const import CONF_HOST, CONF_TOKEN, DOMAIN
from tests.attrappe import Aufzeichnung, projekt

SCHLUESSEL = "haigs.gitlab_example_net"
STORAGE_KEY = "gitlab@gitlab.example.net:789012"
WURZEL = Path(__file__).resolve().parents[1]


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


def release_objekt(tag: str, anhaenge: dict[str, str] | None = None) -> dict:
    objekt = {
        "tag_name": tag,
        "name": "Version " + tag,
        "description": "",
        "released_at": "2026-09-01T10:00:00Z",
        "assets": {},
    }
    if anhaenge:
        objekt["assets"] = {
            "links": [{"name": name, "url": url} for name, url in anhaenge.items()]
        }
    return objekt


def stammdaten(
    full_name: str = "foo/bar", pid: int | str = 789012, topics=("hacs",)
) -> Aufzeichnung:
    return Aufzeichnung(
        text=json.dumps(projekt(pid=pid, full_name=full_name, topics=topics)),
        kopfzeilen={},
    )


def herzschlag() -> Aufzeichnung:
    return Aufzeichnung(text="[]", kopfzeilen={})


def releases(*objekte: dict) -> Aufzeichnung:
    return Aufzeichnung(text=json.dumps(list(objekte)), kopfzeilen={})


def beispiel_integration_zip(domain: str = "beispiel_integration") -> bytes:
    """Ein Mini-Integrations-Release, wie ein Besitzer ihn anhängt.

    Die Dateien stehen in der Wurzel des Anhangs -- genau dafuer ist
    ``zip_release`` in der ``hacs.json`` da (HACS-Konvention: der
    Anhang ist gebaut, nicht gepackt-vom-Quellstand). Ohne die
    Erklaerung wuesste der Installer nicht, dass die Wurzel der
    Inhalt ist.
    """
    archiv = io.BytesIO()
    with zipfile.ZipFile(archiv, "w") as zip_datei:
        zip_datei.writestr(
            "hacs.json",
            json.dumps({"name": "Beispiel", "zip_release": True, "render_readme": False}),
        )
        zip_datei.writestr(
            "manifest.json",
            json.dumps(
                {
                    "domain": domain,
                    "name": "Beispiel",
                    "version": "1.2.0",
                    "documentation": "https://example.net",
                }
            ),
        )
        zip_datei.writestr("__init__.py", "# die Integration\n")
    return archiv.getvalue()


def eigener_release_zip(tmp_path: Path) -> bytes:
    """Das DOGFOOD-ZIP: unser eigener Release, in installierbare Form gebracht.

    Mit ``release_bauen`` gebaut, echte Dateien, echt deterministisch --
    nur der Aeussere kommt ab: das Release-ZIP ist die
    HANDinstallations-Form (``custom_components/haigs/...`` an der
    Wurzel, zum Entpacken ins Konfigurationsverzeichnis), der Installer
    will die HACS-Form (ein Ordner, alles darunter). Beide Formen sind
    Absicht: die eine spricht Menschen, die andere dem Installer. Hier
    wird die eine in die andere gestuelpt -- derselbe Inhalt, dieselben
    Bytes je Datei.
    """
    handform = baue_release(WURZEL, tmp_path / "dist")
    archiv = io.BytesIO()
    with zipfile.ZipFile(handform) as quelle, zipfile.ZipFile(archiv, "w") as ziel:
        for name in quelle.namelist():
            if name.startswith("custom_components/haigs/"):
                ziel.writestr(
                    "haigs/" + name[len("custom_components/haigs/") :],
                    quelle.read(name),
                )
    return archiv.getvalue()


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


def update_entity_id(hass: HomeAssistant) -> str:
    ids = sorted(hass.states.async_entity_ids("update"))
    assert len(ids) == 1, f"eine update-Entity erwartet, gefunden: {ids}"
    return ids[0]


async def frage(client, kennung: int, typ: str, **felder):
    """Eine WebSocket-Nachricht hin und die Antwort zurueck."""
    await client.send_json({"id": kennung, "type": typ, **felder})
    return await client.receive_json()


def neustart_issues(hass: HomeAssistant) -> list[str]:
    register = issue_registry.async_get(hass)
    return sorted(
        kennung
        for (bereich, kennung) in register.issues
        if bereich == DOMAIN and kennung.startswith("neustart_")
    )


# --------------------------------------------------- Anhang-Quelle


async def test_installation_nimmt_den_release_anhang(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """M4b, Quelle: Anhang zuerst -- das Tag-Archiv bleibt unberuehrt."""
    speichern(hass_storage, [eintrag_daten()])
    zip_bytes = beispiel_integration_zip()
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            # Der zweite Abruf gehoert zur Installation (beschaffe_archiv):
            releases(release_objekt("v1.2.0", {"paket.zip": "https://x/paket.zip"})),
            Aufzeichnung(rohbytes=zip_bytes, kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": update_entity_id(hass)},
        blocking=True,
    )
    await hass.async_block_till_done()

    ziel = Path(hass.config.config_dir) / "custom_components" / "beispiel_integration"
    assert (ziel / "manifest.json").exists()
    assert (ziel / "__init__.py").exists()

    # Der Zielweg ist verzeichnet -- die Deinstallation nimmt ihn spaeter.
    gespeichert = hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]
    assert gespeichert["pfad"] == "custom_components/beispiel_integration"
    assert gespeichert["installiert"] == "1.2.0"


async def test_installation_faellt_aufs_tag_archiv_zurueck(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """Kein (eindeutiger) Anhang: das Archiv des Tags liefert."""
    speichern(hass_storage, [eintrag_daten()])
    # Tag-Archiv-Form: alles unter einem Ordner.
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

    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            releases(release_objekt("v1.2.0")),  # kein Anhang
            Aufzeichnung(rohbytes=archiv.getvalue(), kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": update_entity_id(hass)},
        blocking=True,
    )
    await hass.async_block_till_done()

    ziel = Path(hass.config.config_dir) / "custom_components" / "beispiel_integration"
    assert (ziel / "manifest.json").exists()
    assert (
        hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]["pfad"]
        == "custom_components/beispiel_integration"
    )


# ------------------------------------------------------ Dogfooding


async def test_eigener_release_installiert_sich_selbst(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, tmp_path: Path
) -> None:
    """Die Abnahme von M4b, mit dem eigenen Release gefahren.

    Der Anhang ist das echte, deterministisch gebaute ZIP aus diesem
    Repository -- dieselbe Integration, die als laufende Instanz
    gerade diesen Test abwickelt, liegt danach als Dateien im
    Konfigurationsverzeichnis: Kern inklusive, ein Ordner, fertig.
    """
    speichern(hass_storage, [eintrag_daten()])
    eigenes = eigener_release_zip(tmp_path)
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            releases(release_objekt("v1.2.0", {"haigs.zip": "https://x/eigen"})),
            Aufzeichnung(rohbytes=eigenes, kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": update_entity_id(hass)},
        blocking=True,
    )
    await hass.async_block_till_done()

    ziel = Path(hass.config.config_dir) / "custom_components" / "haigs"
    assert (ziel / "manifest.json").exists()
    assert (ziel / "core" / "forge.py").exists()
    assert json.loads((ziel / "manifest.json").read_text())["domain"] == "haigs"
    assert (
        hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]["pfad"]
        == "custom_components/haigs"
    )


# ---------------------------------------------------- Deinstallation


async def test_deinstallation_raeumt_genau_den_weg(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Installieren, deinstallieren: das Ziel ist weg, der Rest bleibt.

    Home Assistants update-Entities kennen kein Uninstall -- der Weg
    hier ist der Panel-Befehl ``haigs/deinstallieren``.
    """
    speichern(hass_storage, [eintrag_daten()])
    nachbar = Path(hass.config.config_dir) / "custom_components" / "andere"
    # exist_ok: der Nachbar bleibt nach dem Test stehen (er BEWEISST, dass
    # die Deinstallation daneben nichts anfasst) -- ein zweiter Lauf im
    # selben Haus darf daran nicht scheitern.
    nachbar.mkdir(parents=True, exist_ok=True)
    (nachbar / "manifest.json").write_text("{}", encoding="utf-8")

    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            releases(release_objekt("v1.2.0", {"paket.zip": "https://x/paket.zip"})),
            Aufzeichnung(rohbytes=beispiel_integration_zip(), kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": update_entity_id(hass)},
        blocking=True,
    )
    await hass.async_block_till_done()

    antwort = await frage(client, 1, "haigs/deinstallieren", storage_key=STORAGE_KEY)
    assert antwort["success"], antwort
    assert antwort["result"]["deinstalliert"] == "foo/bar*lab"
    await hass.async_block_till_done()

    ziel = Path(hass.config.config_dir) / "custom_components" / "beispiel_integration"
    assert not ziel.exists()
    assert (nachbar / "manifest.json").exists()  # der Nachbar bleibt

    stand = hass_storage[SCHLUESSEL]["data"]["stand"][STORAGE_KEY]
    assert stand["installiert"] == ""
    assert stand["pfad"] == ""

    nachher = hass.states.get(update_entity_id(hass))
    assert nachher.attributes["installed_version"] is None
    # Integration deinstalliert: der Neustart-Hinweis steht da.
    assert neustart_issues(hass) == ["neustart_" + _kennung(STORAGE_KEY)]


async def test_deinstallation_ohne_weg_ist_ehrlich(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Vor M4b installiert: kein Weg verzeichnet -- klare Ansage."""
    speichern(
        hass_storage,
        [eintrag_daten()],
        stand={STORAGE_KEY: {"installiert": "1.1.0", "vorabversionen": False}},
    )
    sitzung_einpflanzen([herzschlag(), stammdaten(), releases(release_objekt("v1.2.0"))])
    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    antwort = await frage(client, 1, "haigs/deinstallieren", storage_key=STORAGE_KEY)
    assert not antwort["success"]
    assert "kein installierter Pfad verzeichnet" in antwort["error"]["message"]


async def test_deinstallation_unbekannter_eintrag(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage, hass_ws_client
) -> None:
    """Ein Schluessel aus keiner Liste bekommt seine klare Absage."""
    speichern(hass_storage, [eintrag_daten()])
    sitzung_einpflanzen([herzschlag(), stammdaten(), releases(release_objekt("v1.2.0"))])
    await richten(hass, mock_eintrag())
    client = await hass_ws_client(hass)

    antwort = await frage(
        client, 1, "haigs/deinstallieren", storage_key="gitlab@example:1"
    )
    assert not antwort["success"]
    assert "steht in keiner Liste" in antwort["error"]["message"]


# ------------------------------------------------ Neustart-Hinweis


async def test_integration_installation_stellt_neustart_hinweis(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """Integrationen laden nur beim Start -- das steht aufs Brett."""
    speichern(hass_storage, [eintrag_daten()])
    sitzung_einpflanzen(
        [
            herzschlag(),
            stammdaten(),
            releases(release_objekt("v1.2.0")),
            releases(release_objekt("v1.2.0", {"paket.zip": "https://x/paket.zip"})),
            Aufzeichnung(rohbytes=beispiel_integration_zip(), kopfzeilen={}),
        ]
    )
    await richten(hass, mock_eintrag())
    assert neustart_issues(hass) == []

    await hass.services.async_call(
        "update",
        "install",
        {"entity_id": update_entity_id(hass)},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert neustart_issues(hass) == ["neustart_" + _kennung(STORAGE_KEY)]


async def test_althinweis_verschwindet_beim_laden(
    hass: HomeAssistant, sitzung_einpflanzen, hass_storage
) -> None:
    """Wer laeuft, ist neu gestartet: alte Hinweise gelten als erledigt."""
    speichern(hass_storage, [eintrag_daten()])
    issue_registry.async_create_issue(
        hass,
        DOMAIN,
        "neustart_von_gestern",
        is_fixable=False,
        severity=issue_registry.IssueSeverity.WARNING,
        translation_key="neustart_nach_installation",
        translation_placeholders={
            "name": "alt",
            "version": "0.1.0",
            "aktion": "installation",
        },
    )
    sitzung_einpflanzen([herzschlag(), stammdaten(), releases(release_objekt("v1.2.0"))])
    await richten(hass, mock_eintrag())
    assert neustart_issues(hass) == []
