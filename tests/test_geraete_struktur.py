"""Flug 2098/2100 -- der Zustands-Hinweis im Panel.

Das Panel ist eine Datei fuer den Browser; was davon in Python pruefbar
ist, sind die Verdrahtungen: die Klassen, die Knopf-Aktion, der Weg in
den Einrichtungsdialog und die Texte beider Sprachen. Dasselbe Mittel
wie bei Markenbild und Fusszeile (Flug 2092, 2097) -- gelesen wird die
Datei, nicht geraten.
"""

from __future__ import annotations

from pathlib import Path

PANEL = Path(__file__).resolve().parents[1] / (
    "custom_components/haigs/frontend/panel.js"
)


def panel_text() -> str:
    return PANEL.read_text(encoding="utf-8")


def test_jeder_zustand_hat_sein_wort() -> None:
    """Jeder Zustand hat sein Wort in beiden Sprachen."""
    text = panel_text()
    for zustand in (
        "neustart",
        "nicht_geladen",
        "eingerichtet",
        "hinzufuegen",
        "yaml",
        "ungewiss",
    ):
        assert text.count(f'{zustand}: "') >= 2, zustand


def test_hinzufuegen_fuehrt_zu_geraete_und_diensten() -> None:
    """Der einrichtbare Zustand traegt einen Knopf mit Weg.

    Der Weg: die Seite von Geräte & Dienste -- der Einrichtungsdialog
    des Frontend laesst sich von aussen nicht vorbelegen (der Router
    kuerzt /add?domain= still, bewiesen in Flug 2098).
    """
    text = panel_text()
    assert 'i.zustand === "hinzufuegen"' in text
    assert '"/config/integrations/dashboard"' in text


def test_die_farben_des_hinweises() -> None:
    """Rot fuer nicht geladen, Gelb fuer Neustart, sonst Info -- HAs eigene Hinweise."""
    text = panel_text()
    assert '"nicht_geladen" ? "error"' in text
    assert '"neustart" ? "warning" : "info"' in text
    assert "ha-alert" in text


def test_die_detailseite_traegt_den_hinweis() -> None:
    """Die Detailseite ruft den Hinweis ueber ihren Chips auf."""
    assert "this._zustand_hinweis(z)" in panel_text()


def test_neustart_hat_einen_knopf() -> None:
    """Steht ein Neustart an, startet der Knopf ihn -- wie bei HACS."""
    assert 'callService("homeassistant", "restart")' in panel_text()


def test_die_texte_nennen_geraete_und_dienste() -> None:
    """Beide Sprachen sagen den Ort, wo die Integration zu finden ist."""
    text = panel_text()
    assert "In Geräte & Dienste einrichten" in text
    assert "Set up in Devices & services" in text
    assert "configuration.yaml" in text
