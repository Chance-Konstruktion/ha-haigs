"""Flug 2100 -- der Laden traegt die Kleider von HACS.

Wer HACS*lab oeffnet, soll sich fragen, ob er im Original-HACS steht.
Das geht nur, wenn das Panel dasselbe Material nimmt wie HACS -- nicht
ein Nachbau, sondern die Bausteine des Hauses. Diese Pruefungen halten
fest, dass das so bleibt; gelesen wird die Datei, nicht geraten.
"""

from __future__ import annotations

from pathlib import Path

PANEL = Path(__file__).resolve().parents[1] / (
    "custom_components/hacs_lab/frontend/panel.js"
)


def panel_text() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_die_liste_ist_die_datentabelle_des_hauses() -> None:
    text = panel_text()
    assert 'document.createElement("hass-tabs-subpage-data-table")' in text
    assert 'tabelle.initialGroupColumn = "status_text"' in text
    assert "tabelle.hasFilters = true" in text
    assert 'slot: "filter-pane"' in text
    assert 'slot: "toolbar-icon"' in text


def test_die_gruppen_heissen_wie_bei_hacs() -> None:
    text = panel_text()
    for wort in (
        "Ausstehende Aktualisierung",
        "Heruntergeladen",
        "Verfügbar zum Herunterladen",
        "Pending update",
        "Available for download",
    ):
        assert wort in text, wort


def test_die_detailseite_hat_eine_eigene_adresse() -> None:
    """Zurueck im Browser fuehrt zur Liste, ein Link fuehrt zum Repository."""
    text = panel_text()
    assert '"/hacs-lab/repository/" + encodeURIComponent(z.id)' in text
    assert "_folge_route()" in text


def test_die_detailseite_nimmt_das_material_von_hacs() -> None:
    text = panel_text()
    assert '"ha-markdown"' in text
    assert '"ha-assist-chip"' in text
    assert '"ha-icon-overflow-menu"' in text
    assert 'class: "hl-fab"' in text


def test_die_quelle_steht_wo_hacs_die_downloads_zaehlt() -> None:
    """Der eigene Ton: die Spalte Quelle macht den Mehrschmieden-Laden sichtbar."""
    text = panel_text()
    assert 'spalte_quelle: "Quelle"' in text
    assert 'spalte_quelle: "Source"' in text
    assert "--hl-akzent: #fc6d26" in text


def test_ohne_release_kein_download_knopf() -> None:
    text = panel_text()
    assert "const fab_text = !z.neueste" in text
    assert "kein_release" in text


def test_relative_readme_adressen_zeigen_auf_die_schmiede() -> None:
    text = panel_text()
    assert "/-/raw/${zweig}/" in text
    assert "/raw/branch/${zweig}/" in text
    assert "replace(/^\\uFEFF/" in text


def test_icons_kommen_aus_dem_brand_ordner() -> None:
    """HACS 2.0 fragt nur den zentralen brands-Server -- HACS*lab nimmt HAs Proxy.

    Seit 2026 bringen Integrationen ihr Icon im eigenen ``brand/``-Ordner
    mit; Home Assistant liefert es ueber ``/api/brands`` mit eigenem Token.
    """
    text = panel_text()
    assert '"brands/access_token"' in text
    assert "/api/brands/integration/" in text
    marke = PANEL.parents[1] / "brand"
    for datei in ("icon.png", "icon@2x.png", "logo.png", "logo@2x.png"):
        assert (marke / datei).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", datei


def test_benutzerdefinierte_repositories_wie_in_hacs() -> None:
    """Hinzufuegen im Laden selbst, nicht ueber den Optionsfluss."""
    text = panel_text()
    assert 'benutzerdefiniert: "Benutzerdefinierte Repositories"' in text
    assert 'benutzerdefiniert: "Custom repositories"' in text
    assert "_benutzerdefiniert()" in text
    assert 'type: "hacs_lab/hinzufuegen", host: ziel.host' in text
    # Adressen aus der Adresszeile: /-/tree/main, /src/branch, .git fallen weg.
    assert ".replace(/\/-\/.*$/" in text
    assert "(src|tree|blob|releases|issues)" in text


def test_update_entities_tragen_das_icon_des_repositorys() -> None:
    """Nicht jedes Update mit dem HACS*lab-Zeichen: die Domain waehlt das Icon."""
    text = (PANEL.parents[1] / "update.py").read_text(encoding="utf-8")
    assert "def entity_picture(self)" in text
    assert 'f"/api/brands/integration/{teile[1]}/icon.png"' in text
    assert "avatar_url" in text
