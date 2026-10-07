"""Ablage eines Eintrags: Home-Assistant-Speicher, Version 1.

Warum ein duenner Mantel: die Roadmap verlangt fuer die Ablage von
Anfang an eine Migrationsfunktion. Formate aendern sich spaeter gern,
Datenverluste sollen dabei nicht entstehen -- also liegt die Form der
Daten in genau einer Datei, und jede Aenderung daran bekommt hier ihren
eigenen Zweig in :func:`migriere`.

Version 1 kennt zwei Felder: ``eintraege`` (eine Liste, seit Stufe M3)
und ``stand`` (eine Karte je Eintrag, seit Stufe M5 -- installierte
Version und Vorab-Entscheid). Das Fehlen von ``stand`` in aelteren
Speicherstaenden ist keine neue Versionszahl wert: es wird wie fehlende
Felder in ``Eintrag.aus_dict`` toleriert gelesen und ergaenzt. Erst wenn
gespeicherte Daten UMGEDEUTET wuerden, kaeme Version 2 mit richtiger
Migration.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.storage import Store

#: Die leere Form von Version 1.
LEERE_DATEN: dict[str, Any] = {"eintraege": [], "stand": {}}


def _reinige_stand(stand: Any) -> dict[str, Any]:
    """Nimmt nur Schluessel-Wert-Paare, die Karten sein koennen."""
    if not isinstance(stand, dict):
        return {}
    ergebnis: dict[str, Any] = {}
    for schluessel, wert in stand.items():
        if isinstance(schluessel, str) and isinstance(wert, dict):
            ergebnis[schluessel] = wert
    return ergebnis


def migriere(roh: dict[str, Any] | None) -> dict[str, Any]:
    """Bringt eine gespeicherte Form auf den Stand von Version 1.

    Reine Funktion ohne Store: alle Faelle -- nichts gespeichert, alte
    Form (ohne ``stand``), kaputte Form -- landen in der Form von
    Version 1. Spaeteres Format bekommt hier einen eigenen Zweig, *bevor*
    die Versionszahl steigt.
    """
    if not isinstance(roh, dict):
        return {"eintraege": [], "stand": {}}
    eintraege = roh.get("eintraege")
    if not isinstance(eintraege, list):
        return {"eintraege": [], "stand": {}}
    return {"eintraege": eintraege, "stand": _reinige_stand(roh.get("stand"))}


class Ablage:
    """Duenner Mantel um :class:`homeassistant.helpers.storage.Store`."""

    def __init__(self, store: Store) -> None:
        self._store = store

    async def laden(self) -> dict[str, Any]:
        """Laedt und wandelt auf Version 1; nur bei Aenderung wird gespeichert."""
        roh = await self._store.async_load()
        daten = migriere(roh)
        if daten != roh:
            await self.sichern(daten)
        return daten

    async def sichern(self, daten: dict[str, Any]) -> None:
        await self._store.async_save(daten)

    async def sicher_teil(self, feld: str, wert: Any) -> None:
        """Sichert ein Feld, ohne die anderen anzutasten.

        Damit Eintraege und Stand dieselbe Datei teilen koennen, ohne
        sich gegenseitig zu loeschen: lesen, ein Feld setzen, ganze Form
        sichern. Das kleine Zeitfenster zwischen Lesen und Sichern ist
        bekannt und ausbaufaehig -- Robustheit gegen gleichzeitige
        Schreiber ist Stufe M8.
        """
        daten = await self.laden()
        daten[feld] = wert
        await self.sichern(daten)
