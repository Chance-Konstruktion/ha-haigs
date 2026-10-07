"""Versionen unter Folter -- der Vergleich darf nirgendwo stolpern.

Die Fluege davor prueften den Normalfall. Diese Suite fuegt die
Randgaenge hinzu, die echten Servern tatsaechlich passieren: Tags mit
fuenf und mehr Gliedern (Build-Zaehler!), Datums-Versionen, riesige
Nummern, Leerzeichen, BOM-artiger Muell, Vorab-Leitern und die
Verwandlung grosser ``V``.

Zwei dieser Faelle waren echte Fehler und sind mit Flug 2093 geheilt:

* ``1.2.3.4.10`` gegen ``1.2.3.4.9`` -- der alte Schluessel kappte
  nach vier Gliedern und liess den String-Rueckhalt entscheiden, und
  als Text ist ``"1"`` kleiner als ``"9"``: die 10 sortierte VOR die
  9. Jetzt ziehen acht Glieder in den Schluessel.
* Build-Metadaten und ungleiche Tiefen bleiben Gleichstand, wie es
  SemVer verspricht (``1.2`` == ``1.2.0`` == ``1.2.0.0``).
"""

import pytest
from haigs.core.forge import Release
from haigs.core.versionen import (
    ist_vorabversion,
    neuer_als,
    normalisiere,
    vergleiche,
    waehle_version,
)


def rel(tag: str, vorab: bool = False) -> Release:
    return Release(tag=tag, name="R " + tag, vorabversion=vorab)


# ------------------------------------------------------------------
# Tiefe und Gleichstand
# ------------------------------------------------------------------


def test_ungleiche_tiefe_ist_gleichstand():
    """1.2 == 1.2.0 == 1.2.0.0 -- SemVer-Versprechen ohne packaging."""
    assert vergleiche("1.2", "1.2.0") == 0
    assert vergleiche("1.2", "1.2.0.0") == 0
    assert vergleiche("1.2.0", "1.2.0.0") == 0


def test_fuenf_glieder_zaehlen_numerisch():
    """Der alte Fehler: .10 sortierte vor .9, weil Text-Vergleich."""
    assert vergleiche("1.2.3.4.10", "1.2.3.4.9") == 1
    assert vergleiche("1.2.3.4.9", "1.2.3.4.10") == -1
    assert vergleiche("1.2.3.4.10", "1.2.3.4.11") == -1


def test_fuenftes_glied_entscheidet_nur_wenn_stattfindend():
    """1.2.3.4 < 1.2.3.4.1 -- das fehlende Glied zaehlt als 0."""
    assert vergleiche("1.2.3.4", "1.2.3.4.1") == -1
    assert vergleiche("1.2.3.4", "1.2.3.4.0") == 0


def test_build_metadaten_sind_gleichstand():
    """1.0.0+build1 == 1.0.0 -- Metadaten zaehlen nach SemVer nicht."""
    assert vergleiche("1.0.0+build1", "1.0.0") == 0
    assert vergleiche("1.0.0+build1", "1.0.0+build2") == 0


# ------------------------------------------------------------------
# Vorabversionen
# ------------------------------------------------------------------


def test_die_vorab_leiter_steigt_in_der_reihenfolge():
    """alpha < beta < rc < fertig -- die klassische Leiter."""
    assert vergleiche("1.0.0-alpha", "1.0.0-beta") == -1
    assert vergleiche("1.0.0-beta", "1.0.0-rc1") == -1
    assert vergleiche("1.0.0-rc1", "1.0.0-rc2") == -1
    assert vergleiche("1.0.0-rc2", "1.0.0") == -1


def test_vorab_gilt_auch_fuer_lange_nummern():
    """2024.01.05-rc1 bleibt kleiner als 2024.01.05."""
    assert vergleiche("2024.01.05-rc1", "2024.01.05") == -1


def test_vorabversion_2_0b3_steht_unter_2_0():
    """``2.0b3`` (Pythons alte Schreibweise) ist Vorab von ``2.0``."""
    assert ist_vorabversion("2.0b3")
    assert vergleiche("2.0b3", "2.0") == -1
    assert vergleiche("2.0b4", "2.0b3") == 1


# ------------------------------------------------------------------
# Muell, Grosses, Leeres
# ------------------------------------------------------------------


def test_grosses_v_wird_auch_entfernt():
    """``V2.0`` -- manche tippen das grosse V. Auch das verschwindet."""
    assert normalisiere("V2.0") == "2.0"
    assert vergleiche("V2.0", "2.0") == 0


def test_v_ohne_zahl_bleibt_stehen():
    """``v`` allein oder vor Buchstaben ist Text, kein Praefix."""
    assert normalisiere("v") == "v"
    assert normalisiere("vBeta") == "vBeta"
    assert normalisiere(" v1.0 ") == "1.0"


def test_leere_und_wort_versionen_stuerzen_nicht():
    """'beta', '', None-artiger Muell: kein Crash, nur Text."""
    assert vergleiche("beta", "beta") == 0
    assert vergleiche("", "") == 0
    assert ist_vorabversion("beta") is True
    assert ist_vorabversion("") is False


def test_riesige_zahlen_bleichen_nicht():
    """Python-Ints kennen keine 32-Bit-Grenze -- 20 Stellen sind okay."""
    assert vergleiche("1.99999999999999999999.2", "1.9999999999999999999.9") == 1


def test_version_mit_nur_text_ist_nicht_neuer():
    """Ein reiner Text-Tag zaehlt NICHT als Update gegen 1.0.0.

    Ohne Zahlenkopf sortiert der Text unter jeder Zahl -- das ist
    die richtige Antwort: ``beta`` als neuestes Release gegen eine
    installierte 1.0.0 ist kein Update, sondern Muell.
    """
    assert neuer_als("irgendwas", "1.0.0") is False
    assert vergleiche("irgendwas", "1.0.0") == -1


# ------------------------------------------------------------------
# waehle_version unter Folter
# ------------------------------------------------------------------


def test_waehle_version_mit_fuenf_gliedern_nimmt_die_zehn():
    """Der Beweis des geheilten Fehlers, durch die ganze Wahl gegangen."""
    ergebnis = waehle_version([rel("1.2.3.4.9"), rel("1.2.3.4.10"), rel("1.2.3.4.2")])
    assert ergebnis.neueste == "1.2.3.4.10"
    assert ergebnis.tag == "1.2.3.4.10"


def test_waehle_version_ignoriert_leere_tags():
    """Ein leeres Tag-Release stuerzt die Wahl nicht."""
    ergebnis = waehle_version([rel(""), rel("1.0.0")])
    assert ergebnis.neueste == "1.0.0"


def test_waehle_version_mit_allem_muell():
    """Leer, Text, Vorab, fuenf Glieder -- die Wahl bleibt ruhig."""
    ergebnis = waehle_version([rel(""), rel("beta"), rel("2.0.0-rc1"), rel("1.2.3.4.10")])
    assert ergebnis.neueste == "1.2.3.4.10"
    # Nichts installiert: die erste Installation ist verfuegbar
    # (derselbe Vertrag wie test_erstinstallation_zaehlt_als_verfuegbar).
    assert ergebnis.verfuegbar is True


@pytest.mark.parametrize(
    ("a", "b", "c"),
    [
        ("1.0.0", "1.2.0", "1.10.0"),
        ("1.0.0-rc1", "1.0.0-rc2", "1.0.0"),
        ("1.2.3.4.9", "1.2.3.4.10", "1.2.3.5"),
        ("2024.1.1", "2024.10.1", "2025.1.1"),
    ],
)
def test_vergleich_ist_transitiv(a, b, c):
    """Sortieren verlangt Transitivitaet: a<b, b<c -> a<c."""
    assert vergleiche(a, b) == -1
    assert vergleiche(b, c) == -1
    assert vergleiche(a, c) == -1


def test_sortieren_eines_grossen_haufens_ist_konsistent():
    """100 zufaellige Versionen: nach Schluessel sortiert bleibt sortiert."""
    import random

    from haigs.core.versionen import _schluessel

    random.seed(2093)
    versionen = []
    for _ in range(100):
        tiefe = random.randint(1, 5)
        versionen.append(".".join(str(random.randint(0, 30)) for _ in range(tiefe)))
    geordnet = sorted(versionen, key=_schluessel)
    schluessel = [_schluessel(v) for v in geordnet]
    assert schluessel == sorted(schluessel)  # nie absteigend
    # Paarweise: sortieren widerspricht keinem direkten Vergleich.
    for i in range(len(geordnet) - 1):
        for j in range(i + 1, min(i + 5, len(geordnet))):
            assert vergleiche(geordnet[i], geordnet[j]) <= 0
