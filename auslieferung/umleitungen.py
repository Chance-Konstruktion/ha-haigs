"""Umleitungen ohne Token (Ticket #20).

Die Verkuendigungs-Skripte tragen ``JOB-TOKEN`` bzw. ``Authorization``;
die Standardbibliothek reicht Kopfzeilen bei einer Umleitung weiter --
auch an ein fremdes Ziel, wo ein Repo-Besitzer sie abgreifen koennte.
Der Handler hier wirft die Berechtigungskoepfe weg, sobald das Ziel
einen anderen Host hat (der Port zaehlt mit: ein anderer Dienst auf
derselben Maschine ist ein anderer Host); im eigenen Haus bleibt alles
wie es war. Die Regel ist dieselbe wie im Kern (Ticket #20,
``core/http_aiohttp.py``) -- hier noch einmal, weil die Skripte ohne
den Kern laufen.
"""

from __future__ import annotations

import urllib.parse
import urllib.request

#: Diese Koepfe reisen nie zu einem fremden Umleitungsziel. ``cookie``
#: steht dabei, obwohl keins gesetzt wird -- wer hier je eines ergaenzt,
#: erbt die Grenze, statt sie neu zu vergessen.
BERECHTIGUNGSKOEPFE = ("job-token", "authorization", "private-token", "cookie")


def host_und_port(adresse: str) -> tuple[str, int]:
    """(Host klein, wirksamer Port) einer Adresse -- die Vergleichsregel.

    Der Standardport wird je Schema ergaenzt, damit ``forge.example``
    und ``forge.example:443`` derselbe Host sind.
    """
    teile = urllib.parse.urlsplit(adresse)
    host = (teile.hostname or "").rstrip(".").lower()
    port = teile.port
    if port is None:
        port = 443 if teile.scheme == "https" else 80
    return host, port


class UmleitungOhneToken(urllib.request.HTTPRedirectHandler):
    """Folgt Umleitungen -- aber ohne Berechtigungskoepfe im Gepaeck."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        neu = super().redirect_request(req, fp, code, msg, headers, newurl)
        if neu is None:
            return None
        if host_und_port(newurl) != host_und_port(req.full_url):
            for name in list(neu.headers) + list(neu.unredirected_hdrs):
                if name.lower() in BERECHTIGUNGSKOEPFE:
                    neu.headers.pop(name, None)
                    neu.unredirected_hdrs.pop(name, None)
        return neu


def oeffner() -> urllib.request.OpenerDirector:
    """Ein Opener mit dieser Grenze; sonst wie ``urlopen``."""
    return urllib.request.build_opener(UmleitungOhneToken())
