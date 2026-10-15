"""Der Nachtrag wird zerlegt, nicht als Text gewogen (Ticket #21).

Die Belege aus #21: ``rc10`` galt als kleiner denn ``rc2``, ``1.2.3-10``
als kleiner denn ``1.2.3-9``, ``beta.11`` als kleiner denn ``beta.2`` —
weil der Nachtrag als Zeichenkette in den Sortierschluessel ging.

Haus-Regel, die dabei sichtbar bleibt (Super Zs Fall B): rein
numerische Nachträge sind FINALE Fassungen (``1.2.3-10`` ist eine
fertige Version, keine Vorabversion) und ordnen ÜBER der reinen
Fassung — ``ist_vorabversion("1.0.0-1") is False`` bleibt deshalb so
gepinnt. Die SemVer-Regel «Ziffer vor Buchstabe» gilt innerhalb des
Nachtrags.
"""

from itertools import pairwise

import pytest
from haigs.core.forge import Release
from haigs.core.versionen import (
    ist_vorabversion,
    neuer_als,
    vergleiche,
    waehle_version,
)

# ------------------------------------------------------------------
# Die Belege aus #21
# ------------------------------------------------------------------


@pytest.mark.parametrize(
    "links,rechts,erwartet",
    [
        ("1.0.0-rc2", "1.0.0-rc10", -1),
        ("1.2.3-10", "1.2.3-9", 1),
        ("1.0.0-beta.2", "1.0.0-beta.11", -1),
    ],
)
def test_nachtrag_wird_numerisch_gewogen(links, rechts, erwartet):
    assert vergleiche(links, rechts) == erwartet
    assert vergleiche(rechts, links) == -erwartet


def test_die_semver_leiter_steht():
    """Die Kette aus der SemVer-Spezifikation, Glied für Glied."""
    leiter = [
        "1.0.0-alpha",
        "1.0.0-alpha.1",
        "1.0.0-alpha.beta",
        "1.0.0-beta",
        "1.0.0-beta.2",
        "1.0.0-beta.11",
        "1.0.0-rc.1",
        "1.0.0",
    ]
    for kleiner, groesser in pairwise(leiter):
        assert vergleiche(kleiner, groesser) == -1, f"{kleiner} !< {groesser}"
        assert vergleiche(groesser, kleiner) == 1


# ------------------------------------------------------------------
# Fall B bleibt Haus-Regel: numerischer Nachtrag ist final
# ------------------------------------------------------------------


def test_numerischer_nachtrag_ist_final_und_zaehlt_hoch():
    assert ist_vorabversion("1.2.3-10") is False
    assert neuer_als("1.2.3-10", "1.2.3-9")
    assert vergleiche("1.0.0-1", "1.0.0") == 1
    assert ist_vorabversion("1.0.0-1") is False


def test_nachtrag_tiefer_zaehler_schlaegt_oberflaeche():
    """Zweistellige Zähler dürfen die einstelligen nicht mehr kippen."""
    assert vergleiche("0.6.4-10", "0.6.4-9") == 1
    assert vergleiche("0.6.4-100", "0.6.4-99") == 1
    assert vergleiche("0.6.4-9", "0.6.4-10") == -1


# ------------------------------------------------------------------
# Die Auswahl (waehle_version) — Fall A mit Schalter, Fall B ohne
# ------------------------------------------------------------------


def _rel(tag: str, vorab: bool = False) -> Release:
    return Release(tag=tag, name="R " + tag, vorabversion=vorab)


def test_waehle_version_findet_rc10_nicht_rc9():
    releases = [_rel("v1.0.0-rc2"), _rel("v1.0.0-rc9"), _rel("v1.0.0-rc10")]
    ergebnis = waehle_version(releases, installiert="1.0.0-rc2", mit_vorabversionen=True)
    assert ergebnis.tag == "v1.0.0-rc10"


def test_waehle_version_holt_das_finale_nachtrags_update():
    """Fall B in der Standard-Konfiguration (kein Schalter nötig)."""
    releases = [_rel("1.2.3-9"), _rel("1.2.3-10")]
    ergebnis = waehle_version(releases, installiert="1.2.3-9")
    assert ergebnis.verfuegbar
    assert ergebnis.neueste == "1.2.3-10"


def test_fertige_fassung_schlaegt_ihre_vorabversionen():
    releases = [_rel("v2.0.0-rc10"), _rel("v2.0.0")]
    ergebnis = waehle_version(releases, installiert="v1.0.0", mit_vorabversionen=True)
    assert ergebnis.tag == "v2.0.0"
