"""Attrappen fuer beide Bahnen -- kernfrei, gemeinsam nutzbar.

Diese Datei enthaelt nur Attrappen, die keinen Kern importieren:
Die aiohttp-Sitzungs-Attrappe (``SitzungsAttrappe``) und die Antworthüllen
(``Aufzeichnung``) laufen in der reinen Bahn UND in der Home-Assistant-
Bahn -- in letzterer unter dem echten Kern-Namen, deshalb darf hier
keine Kern-Klasse auftauchen (keine zweite Identitaet, siehe
``tests/kern_laden.py``). Die Attrappe fuer den HTTP-Zugang des Kerns
liegt dafuer in ``tests/attrappe_kern.py``.
"""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class Aufzeichnung:
    """Eine aufgezeichnete HTTP-Antwort: Status, Kopfzeilen, Koerper.

    Genau das Format, das eine aiohttp-Sitzung liefert -- deshalb kann
    :class:`~http_aiohttp.AiohttpClient` damit geprueft werden,
    ohne dass der Test aiohttp importiert oder das Netz beruehrt.
    """

    def __init__(
        self,
        status: int = 200,
        text: str = "",
        rohbytes: bytes | None = None,
        kopfzeilen: dict[str, str] | None = None,
    ):
        self.status = status
        self.headers = kopfzeilen or {}
        self._text = text
        self._rohbytes = rohbytes

    async def text(self) -> str:
        return self._text

    async def read(self) -> bytes:
        if self._rohbytes is not None:
            return self._rohbytes
        return self._text.encode("utf-8")


class SitzungsAttrappe:
    """Spielt aufgezeichnete Antworten in Reihenfolge ab, merkt sich alles.

    Verbraucht jede Aufzeichnung genau einmal -- ein zweiter Abruf ohne
    neue Aufzeichnung ist ein Testfehler, kein Netzruf.
    """

    def __init__(self, aufzeichnungen: list[Aufzeichnung]):
        self.aufzeichnungen = list(aufzeichnungen)
        self.abrufe: list[tuple[str, dict | None, dict | None]] = []

    async def get(
        self,
        url: str,
        params: dict | None = None,
        headers: dict | None = None,
    ):
        self.abrufe.append((url, params, headers))
        if not self.aufzeichnungen:
            raise AssertionError("keine Aufzeichnung mehr fuer: " + url)
        return self.aufzeichnungen.pop(0)


def projekt(
    pid: int = 789012,
    full_name: str = "foo/bar",
    topics: tuple[str, ...] = ("hacs",),
    **rest,
) -> dict:
    daten = {
        "id": pid,
        "path_with_namespace": full_name,
        "description": "ein Testprojekt",
        "default_branch": "main",
        "topics": list(topics),
        "star_count": 7,
        "open_issues_count": 2,
        "archived": False,
        "web_url": "https://gitlab.example.net/" + full_name,
    }
    daten.update(rest)
    return daten


class LokaleWache:
    """Ein winziger HTTP-Server fuer die Umleitungs-Proben (Ticket #20).

    Laeuft in einem eigenen Faden auf einem freien Loopback-Port. Jede
    Anfrage wird samt Kopfzeilen aufgezeichnet — damit ist beweisbar,
    WELCHE Koepfe tatsaechlich beim Ziel ankamen. Antwortet mit 200 und
    dem Koerper; wer ``umleitung_pfad`` und ``umleitung_ziel`` setzt,
    bekommt auf genau diesem Pfad eine 302 dorthin (die Umleitung darf
    auf denselben oder einen anderen Port zeigen — Port zaehlt als
    fremder Host, genau wie in der echten Welt).
    """

    def __init__(self, koerper: bytes = b"{}") -> None:
        self.koerper = koerper
        self.aufzeichnung: list[tuple[str, dict[str, str]]] = []
        self.umleitung_pfad: str | None = None
        self.umleitung_ziel: str | None = None
        wache = self

        class _Behandler(BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802 - so heisst die Schnittstelle
                wache.aufzeichnung.append(
                    (self.path, {k.lower(): v for k, v in self.headers.items()})
                )
                if wache.umleitung_pfad and self.path == wache.umleitung_pfad:
                    self.send_response(302)
                    self.send_header("Location", wache.umleitung_ziel or "")
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(wache.koerper)))
                self.end_headers()
                self.wfile.write(wache.koerper)

            def log_message(self, *args):
                pass  # keine Logzeilen im Testlauf

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _Behandler)
        self._faden = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._faden.start()

    @property
    def url(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def schliessen(self) -> None:
        self._server.shutdown()
        self._server.server_close()
