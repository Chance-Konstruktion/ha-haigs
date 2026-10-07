"""Flug 2098 -- die reine Entscheidung des Integrations-Zustands.

Der Befund des Imkers: ueber HAIGS installierte Repos sind unter
«Geräte & Dienste» nicht zu finden. Die Physik hat drei Schichten
(Neustart fehlt, kein Konfigurationseintrag -- oder prinzipiell kein
Dialog, oder das Manifest ist dem System gar nicht bekannt), und der
Chip auf der Karte muss genau EINE davon nennen. Diese Suite prueft
die Rangfolge: jede Wahrheit uebertont die naechst schwaechere, nichts
installiert heisst ueberhaupt kein Chip.

Die Werte selbst liest die HA-Schicht (:mod:`tests_ha.test_sichtbarkeit`);
hier zaehlt nur die Logik, und die ist reine Mathematik auf Worten.
"""

from __future__ import annotations

import pytest
from haigs.core.sichtbarkeit import ZUSTAENDE, integrations_zustand


def basis(**anders: object) -> dict[str, object]:
    """Die neutrale Lage: installiert, Weg da, Dialog bekannt."""
    lage: dict[str, object] = {
        "installiert": "1.2.0",
        "zielweg": "custom_components/beispiel",
        "neustart_offen": False,
        "eingerichtet": False,
        "mit_dialog": True,
    }
    lage.update(anders)
    return lage


def test_nichts_installiert_kein_chip() -> None:
    """Ohne Version ist jede weitere Aussage Spekulation."""
    assert integrations_zustand(**basis(installiert="")) is None


def test_weg_fehlt_heisst_ungewiss() -> None:
    """Installiert vor Stufe M4b: Version ohne Weg, ehrlich ungewiss."""
    assert integrations_zustand(**basis(zielweg="")) == "ungewiss"


def test_neustart_uebertont_alles() -> None:
    """Solange der Start fehlt, ist jede spaetere Frage muessig.

    Eingerichtet, Dialog, unlesbar -- egal: die Dateien sind noch
    nicht einmal in Betracht gezogen worden.
    """
    assert (
        integrations_zustand(**basis(neustart_offen=True, eingerichtet=True))
        == "neustart"
    )
    assert integrations_zustand(**basis(neustart_offen=True)) == "neustart"
    assert (
        integrations_zustand(**basis(neustart_offen=True, mit_dialog=None)) == "neustart"
    )


def test_eingerichtet_kennt_den_dialog_nicht_mehr() -> None:
    """Eintrag oder gelaufener Start: kein Rat noetig, egal was danach."""
    assert integrations_zustand(**basis(eingerichtet=True)) == "eingerichtet"
    assert (
        integrations_zustand(**basis(eingerichtet=True, mit_dialog=False))
        == "eingerichtet"
    )
    assert (
        integrations_zustand(**basis(eingerichtet=True, mit_dialog=None))
        == "eingerichtet"
    )


def test_unlesbares_manifest_heisst_nicht_geladen() -> None:
    """Der Start geschah, aber dem System fehlt die Integration."""
    assert integrations_zustand(**basis(mit_dialog=None)) == "nicht_geladen"


def test_dialog_entscheidet_hinzufuegen_oder_yaml() -> None:
    """Noch nicht eingerichtet: der Dialog sagt, welcher Weg gilt."""
    assert integrations_zustand(**basis(mit_dialog=True)) == "hinzufuegen"
    assert integrations_zustand(**basis(mit_dialog=False)) == "yaml"


@pytest.mark.parametrize(
    ("weg", "domain"),
    [
        ("custom_components/bienentanz", "bienentanz"),
        ("custom_components/a/b/c", "c"),
        ("www/community/datei", "datei"),
        ("custom_components/x/", "x"),
    ],
)
def test_der_weg_traegt_die_domain(weg: str, domain: str) -> None:
    """Nur nebenbei: der Weg endet in der Domain -- die Schicht baut drauf."""
    assert weg.rstrip("/").rsplit("/", 1)[-1] == domain


def test_die_zustaende_sind_vollstaendig_benannt() -> None:
    """Kein Zustand darf der Oberflaeche unbekannt vorbeifliegen."""
    assert ZUSTAENDE == {
        "neustart",
        "eingerichtet",
        "hinzufuegen",
        "yaml",
        "nicht_geladen",
        "ungewiss",
    }
