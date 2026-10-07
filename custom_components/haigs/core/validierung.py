"""Pruefung, ob ein gefundenes Projekt wirklich ein HACS-Repository ist.

Das Topic ``hacs`` ist nur die Absichtserklaerung des Besitzers. Ob der
Inhalt passt, entscheidet erst diese Pruefung -- sonst landet jedes
falsch gekennzeichnete Projekt in der Liste.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

#: Kategorien wie in HACS. ``integration`` ist der Normalfall.
KATEGORIEN = (
    "integration",
    "plugin",
    "theme",
    "template",
    "appdaemon",
    "python_script",
)


@dataclass
class Befund:
    """Ergebnis einer Pruefung: gueltig, plus alles Auffaellige."""

    gueltig: bool
    kategorie: str = ""
    name: str = ""
    fehler: list[str] = field(default_factory=list)
    hinweise: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.gueltig


def pruefe_hacs_json(roh: bytes | str, kategorie: str = "integration") -> Befund:
    """Prueft den Inhalt einer ``hacs.json``.

    ``kategorie`` ist die vom Benutzer oder von der Entdeckung
    angenommene Kategorie; ``hacs.json`` selbst nennt sie nicht.
    """
    fehler: list[str] = []
    hinweise: list[str] = []

    if kategorie not in KATEGORIEN:
        return Befund(False, fehler=["unbekannte Kategorie: " + str(kategorie)])

    try:
        text = roh.decode("utf-8") if isinstance(roh, bytes) else roh
        # Ein BOM (Windows-Editoren speichern UTF-8 gern mit einer)
        # ist fuer json.loads ein Buchstabe vor der Klammer -- weg damit.
        text = text.lstrip("\ufeff")
        daten = json.loads(text)
    except UnicodeDecodeError:
        return Befund(False, kategorie=kategorie, fehler=["hacs.json ist nicht UTF-8"])
    except json.JSONDecodeError as fehlschlag:
        return Befund(
            False,
            kategorie=kategorie,
            fehler=["hacs.json ist kein gueltiges JSON: " + str(fehlschlag)],
        )

    if not isinstance(daten, dict):
        return Befund(
            False, kategorie=kategorie, fehler=["hacs.json enthaelt kein Objekt"]
        )

    name = str(daten.get("name") or "").strip()
    if not name:
        fehler.append("Pflichtfeld 'name' fehlt")

    if daten.get("render_readme") not in (None, True, False):
        hinweise.append("'render_readme' ist weder true noch false")

    for feld in ("homeassistant", "hacs"):
        wert = daten.get(feld)
        if wert is not None and not isinstance(wert, str):
            fehler.append("'" + feld + "' muss eine Versionsangabe als Text sein")

    if kategorie == "plugin" and "filename" not in daten:
        hinweise.append(
            "'filename' fehlt -- ohne sie muss die Datei ueber den Namen geraten werden"
        )

    return Befund(
        gueltig=not fehler,
        kategorie=kategorie,
        name=name,
        fehler=fehler,
        hinweise=hinweise,
    )


def pruefe_manifest(roh: bytes | str) -> Befund:
    """Prueft die ``manifest.json`` einer Integration."""
    fehler: list[str] = []
    hinweise: list[str] = []
    try:
        text = roh.decode("utf-8") if isinstance(roh, bytes) else roh
        text = text.lstrip("\ufeff")  # BOM siehe pruefe_hacs_json
        daten = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as fehlschlag:
        return Befund(False, fehler=["manifest.json unlesbar: " + str(fehlschlag)])

    if not isinstance(daten, dict):
        return Befund(False, fehler=["manifest.json enthaelt kein Objekt"])

    for pflicht in ("domain", "name", "version"):
        if not str(daten.get(pflicht) or "").strip():
            fehler.append("Pflichtfeld '" + pflicht + "' fehlt")

    if not daten.get("documentation"):
        hinweise.append("'documentation' fehlt -- Home Assistant zeigt dann keinen Link")

    return Befund(
        gueltig=not fehler,
        kategorie="integration",
        name=str(daten.get("name") or ""),
        fehler=fehler,
        hinweise=hinweise,
    )
