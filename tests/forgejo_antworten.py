"""Aufgezeichnete Antworten einer echten Forgejo-Instanz: codeberg.org.

Quelle (2026-09-03, urllib, ohne Token -- die Abfragen sind oeffentlich)::

    GET https://codeberg.org/api/v1/repos/search?q=hacs&limit=10
    GET https://codeberg.org/api/v1/repos/jelmer/HA-Thames-Water
    GET https://codeberg.org/api/v1/repos/jelmer/HA-Thames-Water/raw/hacs.json?ref=main
    GET https://codeberg.org/api/v1/repos/touero/HaVacation/raw/hacs.json?ref=main
    GET https://codeberg.org/api/v1/repos/Etuldan/hassio-dyndns/raw/hacs.json?ref=master
    GET https://codeberg.org/api/v1/repos/jelmer/HA-Thames-Water/tags?limit=5
    GET https://codeberg.org/api/v1/repos/forgejo/forgejo/releases?limit=1

Die Koerper in ``aufzeichnungen/`` sind unveraendert, bytegenau wie die
Instanz sie geschickt hat -- ebenso wie die gitlab.com-Aufzeichnungen
aus M1. Damit faellt auch auf, was echte Forgejo-Datensaetze an Feldern
mitbringen (60 Stueck, inklusive ``owner`` und Merge-Einstellungen),
was handgebaute Attrappen nie zeigen.

Drei Befunde aus dem Material, die in
:class:`~haigs.core.forgejo_forge.ForgejoForge` eingearbeitet sind:

* Zehn Stichwort-Treffer fuer ``hacs``, aber nur **drei** tragen das
  Topic wirklich -- der ``topic``-Parameter der Such-API wird von
  Codeberg ignoriert, die exakte Filterung passiert client-seitig.
* Alle drei Topic-Treffer haben eine gueltige ``hacs.json`` --
  Etuldan/hassio-dyndns auf dem Zweig ``master``: Forgejo-Projekte
  nennen ihren Standardzweig selbst, der Ablauf fragt ihn ab, statt
  ``main`` festzunageln.
* ``jelmer/HA-Thames-Water`` hat **keine** Releases (HTTP 404) und
  dafuer Tags als Rueckfallebene.
* ``forgejo/forgejo`` v16.0.3 liefert 21 echte Anhaenge mit
  ``browser_download_url`` -- die Release-Form von Forgejo ist die
  von GitLab aehnlich genug, dass dieselbe Uebersetzung greift.
"""

from __future__ import annotations

import json
from pathlib import Path

_ORDNER = Path(__file__).parent / "aufzeichnungen"


def _lade(name: str):
    with open(_ORDNER / name, encoding="utf-8") as datei:
        return json.load(datei)


def _lade_bytes(name: str) -> bytes:
    """Rohdaten einer Datei -- bytegenau, nicht ueber JSON.

    Fuer Dateiinhalte (``hacs.json``) ist der Koerper selbst das
    Ergebnis, nicht seine JSON-Form.
    """
    return (_ORDNER / name).read_bytes()


#: Die Stichwort-Suche der Instanz: zehn Treffer, drei mit Topic ``hacs``.
SUCHE = _lade("forgejo-suche-q-hacs-seite-1.json")

#: Stammdaten des Projekts, das die Abnahme von M9 durchlaeuft.
REPO_THAMES = _lade("forgejo-repo-ha-thames-water.json")

#: Die echte ``hacs.json`` von jelmer/HA-Thames-Water, bytegenau.
HACS_JSON_THAMES = _lade_bytes("forgejo-hacs-json-ha-thames-water.json")

#: Die echte ``hacs.json`` von touero/HaVacation, bytegenau.
HACS_JSON_HAVACATION = _lade_bytes("forgejo-hacs-json-havacation.json")

#: Die echte ``hacs.json`` von Etuldan/hassio-dyndns (Zweig master).
HACS_JSON_DYNDNS = _lade_bytes("forgejo-hacs-json-hassio-dyndns.json")

#: Tags von jelmer/HA-Thames-Water: die Rueckfallebene ohne Releases.
TAGS_THAMES = _lade("forgejo-tags-ha-thames-water.json")

#: Ein Release mit 21 echten Anhaengen (forgejo/forgejo v16.0.3).
RELEASES_MIT_ANHAENGEN = _lade("forgejo-releases-mit-anhaengen.json")
