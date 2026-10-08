"""Das Panel von HAIGS -- Stufe M7: Bedienung ohne YAML.

Zwei Schritte, beide ohne Eintrag in ``configuration.yaml``:

* die JavaScript-Datei wird ueber einen statischen Weg ausgeliefert
  (``/haigs/panel.js``)
* das Panel selbst meldet sich ueber die oeffentliche Hilfe von
  ``panel_custom`` an -- dieselbe Stelle, die sonst die YAML-Sektion
  ``panel_custom:`` bedient, nur eben aus der Integration heraus

Sichtbar wird der Eintrag, sobald die erste Instanz eingerichtet ist
(eine Integration laedt nur mit Konfigurationseintrag). Die Web-
Oberflaeche laedt die Datei als ES-Modul und findet darin das
Element ``haigs-panel``; der Rest des Bedienens laeuft ueber die
WebSocket-Befehle aus :mod:`.websocket_api` und die ganz normalen
Home-Assistant-Dienste.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.components.panel_custom import async_register_panel
from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

#: Der Weg, unter dem der Browser die Panel-Datei bekommt.
PANEL_URL = "/haigs/panel.js"

#: Der Weg zum Iconset -- jede Seite des Frontends laedt es, denn die
#: Seitenleiste zeichnet ihr Zeichen schon bevor das Panel offen ist.
ICONSET_URL = "/haigs/iconset.js"

#: Der Name des Web-Components -- muss zur Definition in panel.js passen.
PANEL_ELEMENT = "haigs-panel"

#: Die Adresse im Frontend (Sidebar): ``/haigs``.
PANEL_PFAD = "haigs"

#: Wie das Panel in der Sidebar heisst -- ein Name, kein uebersetzbarer Satz.
PANEL_TITEL = "HAIGS"

#: Die Fuchskralle -- monochrom, aus ``iconset.js``. Das Zeichen lebt in
#: der eigenen Kollektion ``haigs``, nicht in MDI. Ein eigenes Zeichen:
#: GitLabs Tanuki ist dessen Markenzeichen und gehoert nicht in fremde Logos.
PANEL_ICON = "haigs:kralle"


async def richten(hass: HomeAssistant) -> None:
    """Statischen Weg anlegen und das Panel in die Sidebar setzen.

    Wird aus ``async_setup`` gerufen, also genau einmal pro Laden der
    Komponente -- das Panel ueberlebt das Entfernen einzelner
    Instanz-Eintraege (die Liste kann dann leer sein, das Panel
    bleibt ehrlich und zeigt das).
    """
    ordner = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(PANEL_URL, str(ordner / "panel.js"), cache_headers=False),
            StaticPathConfig(
                ICONSET_URL, str(ordner / "iconset.js"), cache_headers=False
            ),
        ]
    )
    # Das Iconset auf jede Seite: die Seitenleiste fragt ihr Zeichen frueher,
    # als jemand das Panel betreten koennte. add_extra_js_url haengt es an
    # das Grundgeruest des Frontends (dieselbe Oeffentlichkeit, deren sich
    # HACS fuer sein eigenes Zeichen bedient). Steht das Grundgeruest noch
    # nicht (Testhaus ohne Frontend), bleibt es beim Rueckhalt in panel.js
    # -- das Zeichen darf den Laden nie umwerfen.
    try:
        add_extra_js_url(hass, ICONSET_URL)
    except KeyError:  # Frontend noch nicht gerichtet -- siehe oben
        _LOGGER.debug("Iconset wartet: das Frontend ist noch nicht gerichtet")
    await async_register_panel(
        hass,
        frontend_url_path=PANEL_PFAD,
        webcomponent_name=PANEL_ELEMENT,
        module_url=PANEL_URL,
        sidebar_title=PANEL_TITEL,
        sidebar_icon=PANEL_ICON,
        require_admin=True,
    )
    _LOGGER.info("Oberflaeche angemeldet: /%s laedt %s", PANEL_PFAD, PANEL_URL)
