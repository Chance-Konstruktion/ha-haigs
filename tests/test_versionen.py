"""Update-Erkennung: der Punkt, an dem die Erweiterung ihren Zweck erfuellt."""

import pytest
from haigs.core.forge import Release
from haigs.core.versionen import (
    ist_vorabversion,
    neuer_als,
    normalisiere,
    vergleiche,
    waehle_version,
)


@pytest.mark.parametrize(
    "roh,erwartet",
    [("v1.2.3", "1.2.3"), ("1.2.3", "1.2.3"), (" v2.0 ", "2.0"), ("version", "version")],
)
def test_fuehrendes_v_faellt_weg(roh, erwartet):
    assert normalisiere(roh) == erwartet


def test_zahlen_werden_als_zahlen_verglichen():
    assert vergleiche("1.10.0", "1.9.0") == 1
    assert vergleiche("2.0.0", "10.0.0") == -1
    assert vergleiche("v1.0.0", "1.0.0") == 0


def test_vorabversion_ist_kleiner_als_die_fertige():
    assert ist_vorabversion("1.0.0-rc1")
    assert ist_vorabversion("2.0b3")
    assert not ist_vorabversion("1.0.0")
    assert vergleiche("1.0.0-rc1", "1.0.0") == -1


def test_erstinstallation_zaehlt_als_verfuegbar():
    assert neuer_als("1.0.0", "")


def test_gleichstand_ist_kein_update():
    assert not neuer_als("1.0.0", "v1.0.0")


def test_waehlt_die_hoechste_fertige_version():
    releases = [
        Release(tag="v1.0.0"),
        Release(tag="v1.2.0"),
        Release(tag="v1.3.0-rc1"),
    ]
    ergebnis = waehle_version(releases, installiert="v1.0.0")
    assert ergebnis.verfuegbar
    assert ergebnis.neueste == "1.2.0"
    assert ergebnis.tag == "v1.2.0"


def test_vorabversionen_nur_auf_wunsch():
    releases = [Release(tag="v1.2.0"), Release(tag="v1.3.0-rc1")]
    assert waehle_version(releases, "v1.2.0").verfuegbar is False
    mit_vorab = waehle_version(releases, "v1.2.0", mit_vorabversionen=True)
    assert mit_vorab.verfuegbar
    assert mit_vorab.tag == "v1.3.0-rc1"


def test_als_vorab_markiertes_release_zaehlt_auch_ohne_kennung_im_tag():
    releases = [Release(tag="v1.2.0"), Release(tag="v2.0.0", vorabversion=True)]
    assert waehle_version(releases, "v1.2.0").verfuegbar is False


def test_ohne_releases_passiert_nichts():
    assert not waehle_version([], installiert="1.0.0")
