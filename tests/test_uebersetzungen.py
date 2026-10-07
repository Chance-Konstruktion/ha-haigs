"""Der Setup-Dialog spricht auch Englisch (Roadmap aus dem README).

Home Assistant sucht Sprachdateien unter ``translations/`` -- die
englischen Texte standen bislang nur in ``strings.json`` (Quelle der
Uebersetzungen, keine angezeigte Datei). Englisch sprach also nur
das Panel, der Dialog blieb stumm oder deutsch.

Diese Pruefungen halten das Versprechen ein und bleiben ehrlich:

* ``en.json`` existiert und nennt fuer jeden Schluessel einen Text,
* alle drei Baeume -- ``strings.json``, ``en.json``, ``de.json`` --
  haben dieselbe Form: kein Schluessel, den nur eine Sprache kennt,
* jede Platzhalter-Stelle (``{grund}``, ``{host}``, ...) erscheint
  in jeder Sprache -- ein vergessener Platzhalter ist kein
  Schoenheitsfehler, sondern stuerzt str.format beim Anzeigen.

Absichtlich ohne Import des Kerns: diese Dateien sind Daten, keine
Logik -- jeder Stand kann sie lesen.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[1] / "custom_components" / "haigs"

#: Die Quelle (Englisch) und die angezeigten Sprachen.
DATEIEN = {
    "strings.json": INTEGRATION / "strings.json",
    "en": INTEGRATION / "translations" / "en.json",
    "de": INTEGRATION / "translations" / "de.json",
}

#: Home Assistant fuellt Uebersetzungen mit str.format -- die
#: Platzhalter-Stellen muessen across Sprachen identisch sein.
_PLATZHALTER = re.compile(r"\{[a-z_]+\}")


def _flach(inhalt: dict, prefix: str = "") -> dict[str, str]:
    """Ebnet ein Uebersetzungs-JSON ab: Schluesselpfad -> Text."""
    ergebnis: dict[str, str] = {}
    for schluessel, wert in inhalt.items():
        pfad = f"{prefix}.{schluessel}" if prefix else schluessel
        if isinstance(wert, dict):
            ergebnis.update(_flach(wert, pfad))
        else:
            ergebnis[pfad] = wert
    return ergebnis


def _lade(name: str) -> dict[str, str]:
    """Liest eine Sprachdatei und gibt sie geebnet zurueck."""
    pfad = DATEIEN[name]
    assert pfad.is_file(), f"{pfad} fehlt -- ohne sie bleibt der Dialog stumm"
    return _flach(json.loads(pfad.read_text(encoding="utf-8")))


def test_englisch_existiert_und_ist_vollstaendig():
    """en.json traegt fuer jeden Schluessel der Quelle einen Text."""
    quelle = _lade("strings.json")
    englisch = _lade("en")

    fehlen = sorted(set(quelle) - set(englisch))
    assert not fehlen, f"en.json kennt diese Schluessel nicht: {fehlen}"

    leer = sorted(k for k, v in englisch.items() if not str(v).strip())
    assert not leer, f"en.json hat leere Texte fuer: {leer}"


def test_alle_sprachen_haben_dieselbe_form():
    """Keine Sprache kennt einen Schluessel, den die anderen nicht kennen."""
    baeume = {name: set(_lade(name)) for name in DATEIEN}
    referenz = baeume["strings.json"]

    for name, schluessel in baeume.items():
        fehlen = sorted(referenz - schluessel)
        zusaetzlich = sorted(schluessel - referenz)
        assert not fehlen, f"{name} fehlt: {fehlen}"
        assert not zusaetzlich, f"{name} kennt Schluessel ohne Quelle: {zusaetzlich}"


def test_platzhalter_stehen_in_jeder_sprache():
    """{grund}, {host} und Co. muessen ueberall identisch auftauchen."""
    quelle = _lade("strings.json")
    for name in ("en", "de"):
        sprache = _lade(name)
        for schluessel, text in sorted(quelle.items()):
            erwartet = sorted(_PLATZHALTER.findall(text))
            bekommt = sorted(_PLATZHALTER.findall(sprache[schluessel]))
            assert bekommt == erwartet, (
                f"{name} bei {schluessel}: Platzhalter {bekommt} "
                f"statt {erwartet} -- str.format stuerzt beim Anzeigen"
            )


def test_json_ist_ladbar_und_zeichensatz_ist_utf8():
    """Alle Dateien sind echtes UTF-8-JSON, keine Escape-Wueste."""
    for name, pfad in DATEIEN.items():
        roh = pfad.read_bytes()
        assert b"\\u" not in roh, (
            f"{name} versteckt Zeichen als \\u-Escape -- "
            "die anderen Dateien tragen echtes UTF-8, gleiche Sprache"
        )
        json.loads(roh.decode("utf-8"))  # doppelte Absicherung: parst
