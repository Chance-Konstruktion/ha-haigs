"""Die Sichtbarkeit installierter Integrationen in Home Assistant.

Flug 2098 -- die HA-Haelfte von :mod:`core.sichtbarkeit`. Der Zustands-
Chip je Karte entsteht hier aus Home Assistants eigener Wahrheit:

* **Neustart ausstehend?** Das Issue-Register fuehrt Buch: die
  Neustart-Hinweise aus :mod:`neustart` entstehen bei jeder
  Installation und werden beim Laden der Komponente (also: beim Start)
  abgeraeumt -- steht der Hinweis noch, ist der Start nicht geschehen.
  Das Register ist damit gleichzeitig Flagge und Reparatur-Brett.
* **Eingerichtet?** Ein Konfigurationseintrag der Domain ODER die
  Domain unter den gelaufenen Komponenten -- beides heisst: die
  Integration lebt (erstere ueber den Dialog, letztere ueber die
  configuration.yaml), und der Einrichtungsdialog listet Integrationen
  ohnehin aus dem Manifest-Scan, nicht aus den gelaufenen.
* **Dialog vorhanden?** Die manifest.json DES INSTALLIERTEN ORDners --
  nicht die im Archiv -- sagt ``config_flow``. Gelesen wird sie erst,
  wenn die Antwort den Zustand wandeln koennte: unlesbar heisst
  «nicht geladen», und der Chip sagt das ehrlich.

Rein lesend, nie schreibend, jederzeit frisch fragbar: die Werte
leben im Speicher, die manifest.json ist ein kleiner Griff im
Vorfuehrer. Die Zeilen selbst bleiben unberuehrt -- angereichert wird
eine Kopie, damit niemals ein Zustands-Chip im Lager landet und dort
veraltet (siehe ``_liste`` in :mod:`websocket_api`).
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Any

from homeassistant.helpers import issue_registry

from .aktualisierer import _kennung
from .const import DOMAIN
from .core import zielpfade
from .core.sichtbarkeit import integrations_zustand

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


async def lies_dialog_flag(hass: HomeAssistant, zielweg: str) -> bool | None:
    """``config_flow`` aus der installierten manifest.json -- oder ``None``.

    ``None`` heisst unlesbar (weg, untauglich, kein Weg verzeichnet)
    und ist KEINE Aussage ueber die Integration -- der Aufrufer
    entscheidet, was er daraus macht. Der Weg wird vorher geprueft
    (:func:`zielpfade.ist_zielpfad`): die Ablage ist eine Datei, und ein
    veraenderter Eintrag darf hier nie zu einem Griff ausserhalb der
    Kategorie-Wurzeln fuehren.
    """

    def _lesen() -> bool | None:
        try:
            roh = pfad.read_text(encoding="utf-8-sig")
            daten = json.loads(roh)
        except (OSError, ValueError):
            return None
        if not isinstance(daten, dict):
            return None
        wert = daten.get("config_flow")
        return bool(wert) if isinstance(wert, bool) else False

    if not zielweg or not zielpfade.ist_zielpfad(zielweg):
        return None
    pfad = (
        Path(hass.config.config_dir).joinpath(*PurePosixPath(zielweg).parts)
        / "manifest.json"
    )
    return await hass.async_add_executor_job(_lesen)


def _neustart_offen(hass: HomeAssistant, schluessel: str) -> bool:
    """Steht der Neustart-Hinweis dieses Eintrags noch im Register?"""
    register = issue_registry.async_get(hass)
    return (DOMAIN, "neustart_" + _kennung(schluessel)) in register.issues


async def anreichern(hass: HomeAssistant, zeilen: list[dict[str, Any]]) -> None:
    """Haengt installierten Integrationen ihren Zustand an die Zeile.

    Der Block heisst ``integration`` und traegt zwei Dinge: den
    ``zustand`` (siehe :data:`core.sichtbarkeit.ZUSTAENDE`) und die
    ``domain`` -- der Knopf «In Geräte & Dienste einrichten» braucht
    sie fuer seinen Weg, der YAML-Hinweis fuer sein Beispiel. Zeilen
    ohne installierte Integration bleiben unberuehrt.
    """
    for zeile in zeilen:
        if zeile.get("kategorie") != "integration":
            continue
        installiert = str(zeile.get("installiert") or "")
        if not installiert:
            continue
        schluessel = str(zeile.get("storage_key") or "")
        zielweg = str(zeile.get("zielweg") or "")
        domain = zielweg.rstrip("/").rsplit("/", 1)[-1]
        eingerichtet = bool(domain) and (
            bool(hass.config_entries.async_entries(domain))
            or domain in hass.config.components
        )
        # Die manifest.json wird erst gefragt, wenn ihre Antwort den
        # Zustand wandeln kann: noch nicht eingerichtet. Unlesbar
        # heisst dann «nicht geladen» -- ehrlich, nicht geraten.
        mit_dialog = None
        if not eingerichtet:
            mit_dialog = await lies_dialog_flag(hass, zielweg)
        zustand = integrations_zustand(
            installiert=installiert,
            zielweg=zielweg,
            neustart_offen=_neustart_offen(hass, schluessel),
            eingerichtet=eingerichtet,
            mit_dialog=mit_dialog,
        )
        if zustand is not None:
            zeile["integration"] = {"zustand": zustand, "domain": domain}
