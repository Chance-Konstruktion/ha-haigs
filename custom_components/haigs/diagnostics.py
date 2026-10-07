"""Diagnose für HAIGS: alles, was ein Mensch zum Helfen braucht, ohne Geheimnisse.

Stufe M8 der Roadmap: «Diagnose-Ausgabe ohne Token im Klartext». Die
Datei ist eine Plattform des Diagnose-Bausteins von Home Assistant --
ihr Vorhandensein genügt, sie wird von selbst gefunden. Geliefert wird
je Eintrag: die eingerichteten Daten mit geschwärztem Token, der
Ablage-Inhalt (Eintraege und Staende) und der Stand des letzten Laufs
je Eintrag -- installierte und neueste Version, Fehlergrund, Quelle.

Das Token ist der einzige Geheimnis-Teil der Einrichtungsdaten; es wird
über :func:`async_redact_data` ersetzt. Danach sucht ein Test das
ganze Wörterbuch nach dem Klartext ab -- Abnahme ist Abnahme.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_TOKEN, DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

    from . import Laufzeit

#: Felder, die niemals im Klartext reisen.
ZU_SCHWAERZEN = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, eintrag: ConfigEntry
) -> dict[str, Any]:
    """Der Diagnose-Bericht eines Eintrags -- ohne Token, mit allem anderen."""
    laufzeit: Laufzeit | None = hass.data.get(DOMAIN, {}).get(eintrag.entry_id)
    if laufzeit is None:
        return {"einrichtung": async_redact_data(dict(eintrag.data), ZU_SCHWAERZEN)}

    ablage = await laufzeit.ablage.laden()
    aktualisierer = getattr(laufzeit, "aktualisierer", None)
    funde = {}
    if aktualisierer is not None:
        for schluessel, fund in (aktualisierer.data or {}).items():
            funde[schluessel] = {
                "installiert": fund.installiert,
                "neueste": fund.neueste,
                "tag": fund.tag,
                "quelle": fund.quelle,
                "veroeffentlicht_am": fund.veroeffentlicht_am,
                "fehler": fund.fehler or "",
                "verfuegbar": fund.verfuegbar,
            }

    return {
        "einrichtung": async_redact_data(dict(eintrag.data), ZU_SCHWAERZEN),
        "ablage": ablage,
        "letzte_laeufe_erfolgreich": (
            aktualisierer.last_update_success if aktualisierer is not None else None
        ),
        "funde": funde,
    }
