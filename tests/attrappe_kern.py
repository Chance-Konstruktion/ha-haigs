"""Eine HTTP-Attrappe fuer den Kern: Antworten statt Netz, Fehlerart echt.

Diese Attrappe gehoert allein der reinen Bahn (``tests/``): sie
ersetzt den HTTP-Zugang, den der Kern hereingereicht bekommt. In der
Home-Assistant-Bahn wird sie nie benutzt -- dort laeuft der Kern unter
seinem echten Namen, und eine zweite Identitaet seiner Klassen waere
ein Fehler, kein Werkzeug (siehe ``tests/kern_laden.py``).
"""

from __future__ import annotations

import json

from haigs.core.forge import NichtGefunden


class FakeHttp:
    """Antworten werden ueber ein Praefix der URL zugeordnet."""

    def __init__(self, json_antworten: dict | None = None, dateien: dict | None = None):
        self.json_antworten = json_antworten or {}
        self.dateien = dateien or {}
        self.aufrufe: list[tuple[str, dict]] = []
        self.seitenwuensche: list[int | None] = []

    async def get_json(
        self,
        url: str,
        params: dict | None = None,
        *,
        seiten: int | None = None,
    ):
        # ``seiten`` wird mit aufgezeichnet, damit ein Test belegen
        # kann, dass eine Probe wirklich nur eine Seite anfordert.
        self.aufrufe.append((url, params or {}))
        self.seitenwuensche.append(seiten)
        for schluessel, wert in self.json_antworten.items():
            if schluessel in url:
                return wert
        return {"message": "404 Project Not Found"}

    async def get_bytes(self, url: str) -> bytes:
        self.aufrufe.append((url, {}))
        for schluessel, wert in self.dateien.items():
            if schluessel in url:
                if isinstance(wert, bytes):
                    return wert
                if isinstance(wert, str):
                    return wert.encode("utf-8")
                return json.dumps(wert).encode("utf-8")
        # Wie ein echter Anbieter bei 404: der Aufrufer soll nur eine
        # Fehlerart kennen muessen.
        raise NichtGefunden(url)
