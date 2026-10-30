"""Ticket #20: das Token reist nur zum eigenen Forge-Host.

Zusammenzug der Befunde #3/#14/#15 aus #17: der Klient schickte den
``Authorization``-Kopf an JEDE Adresse — Release-Anhaenge kommen von
beliebigen Adressen, und die Erkennung fragte mit Token, bevor ein Host
als Forge bestaetigt war. Hier steht die Grenze, scharf und lokal:

* eigener Host: Gross/Klein egal, der Port zaehlt (Standardport =
  ohne Port),
* jeder fremde Host bekommt keinen Berechtigungskopf (der Absender
  ``User-Agent`` bleibt — er verraet nichts),
* ein Token OHNE genannten Host wird gar nicht erst angenommen
  (lieber laut scheitern als leise ueberall senden).

Die Erkennung ohne Token (Einrichtungsdialog) wird in der
Home-Assistant-Bahn geprueft (``tests_ha/test_config_flow.py``), weil
der Dialog dort lebt.
"""

from __future__ import annotations

import pytest
from haigs.core.http_aiohttp import AiohttpClient

from tests.attrappe import Aufzeichnung, SitzungsAttrappe

EIGEN = "gitlab.example.net"
TOKEN = "geheimer-lese-token"


def antwort(text: str = "{}", status: int = 200):
    return Aufzeichnung(status=status, text=text, kopfzeilen={})


def klient(aufzeichnungen, token=None, token_host=None):
    sitzung = SitzungsAttrappe(aufzeichnungen)
    return AiohttpClient(sitzung, token=token, token_host=token_host), sitzung


def _kopf(sitzung, nummer: int = 0) -> dict:
    return sitzung.abrufe[nummer][2] or {}


# -- Der eigene Host bekommt das Token ---------------------------------


async def test_token_geht_zum_eigenen_host():
    k, sitzung = klient([antwort()], token=TOKEN, token_host=EIGEN)
    await k.get_json(f"https://{EIGEN}/api/v4/projects")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN


async def test_token_geht_auch_bei_get_bytes_zum_eigenen_host():
    k, sitzung = klient([antwort("zip")], token=TOKEN, token_host=EIGEN)
    await k.get_bytes(f"https://{EIGEN}/paket.zip")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN


async def test_gross_klein_egal_beim_host():
    k, sitzung = klient([antwort()], token=TOKEN, token_host="GitLab.Example.NET")
    await k.get_json("https://GITLAB.example.net/api/v4/projects")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN


async def test_host_darf_mit_schema_genannt_werden():
    """Wer den Host aus der Adresszeile kopiert, hat ``https://`` davor."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host="https://" + EIGEN + "/")
    await k.get_json(f"https://{EIGEN}/api/v4/projects")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN


async def test_http_forge_mit_schema_bleibt_bei_http():
    """Codex C03, Befund 5: eine selbst gehostete Forge ohne TLS
    (``const.schema_aus_eingabe`` erlaubt http:// ausdruecklich) nennt
    ihren token_host MIT Schema — ``http://`` bleibt bei Port 80 und
    wird nicht still zum https-Nachbarn erhoben."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host="http://" + EIGEN)
    await k.get_json(f"http://{EIGEN}/api/v4/projects")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN


async def test_https_token_reist_nicht_ueber_http():
    """Und andersrum: wer https genannt hat, schickt sein Token nicht
    an die Klartext-Adresse desselben Namens (anderer Dienst, anderer
    Port)."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host="https://" + EIGEN)
    await k.get_json(f"http://{EIGEN}/api/v4/projects")
    assert "Authorization" not in _kopf(sitzung)


def test_token_host_mit_schema():
    """Der Helfer der Bau-Stellen (Einrichtungsdialog und Setup): der
    schemalose Speicher-Host reist MIT dem Schema des Eintrags zum
    Klienten — ohne Schema gilt https wie bisher."""
    from haigs.const import token_host_mit_schema

    assert token_host_mit_schema("forgejo.lan", "http") == "http://forgejo.lan"
    assert token_host_mit_schema("gitlab.com", "https") == "https://gitlab.com"
    assert token_host_mit_schema("gitlab.com", None) == "https://gitlab.com"
    assert token_host_mit_schema("forgejo.lan", "") == "https://forgejo.lan"


async def test_standards_port_ist_derselbe_host():
    """Ohne Port genannt deckt ``:443`` mit ab — und umgekehrt."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host=EIGEN)
    await k.get_json(f"https://{EIGEN}:443/api/v4/projects")
    assert _kopf(sitzung)["Authorization"] == "Bearer " + TOKEN

    k2, sitzung2 = klient([antwort()], token=TOKEN, token_host=EIGEN + ":443")
    await k2.get_json(f"https://{EIGEN}/api/v4/projects")
    assert _kopf(sitzung2)["Authorization"] == "Bearer " + TOKEN


# -- Fremde Hosts bekommen nichts --------------------------------------


async def test_token_geht_nicht_zu_fremden_hosts():
    """Der Anhang-Fall: die Adresse stammt aus den Anhaengen eines
    Releases und darf irgendwohin zeigen — dorthin reist kein Token."""
    k, sitzung = klient([antwort("zip")], token=TOKEN, token_host=EIGEN)
    await k.get_bytes("https://cdn.example.org/paket.zip")
    kopf = _kopf(sitzung)
    assert "Authorization" not in kopf
    assert kopf["User-Agent"].startswith("HAIGS ")  # der Absender bleibt


async def test_auch_json_zu_fremden_hosts_ohne_token():
    k, sitzung = klient([antwort()], token=TOKEN, token_host=EIGEN)
    await k.get_json("https://fremd.example.org/api/v4/projects")
    assert "Authorization" not in _kopf(sitzung)


async def test_der_port_zaehlt():
    """Anderer Port = anderer Dienst auf derselben Maschine."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host=EIGEN)
    await k.get_json(f"https://{EIGEN}:8443/api/v4/projects")
    assert "Authorization" not in _kopf(sitzung)


async def test_unteradresse_des_eigenen_hosts_geht_mit():
    """Subdomain ist ein anderer Name — nicht derselbe Host."""
    k, sitzung = klient([antwort()], token=TOKEN, token_host=EIGEN)
    await k.get_json("https://evil.gitlab.example.net/api/v4/projects")
    assert "Authorization" not in _kopf(sitzung)


# -- Lieber laut scheitern ---------------------------------------------


def test_token_ohne_host_wird_abgelehnt():
    """Ein Token ohne genannten Host wuerde wieder ueberall reisen —
    genau der Befund. Also nicht leise, sondern gar nicht."""
    with pytest.raises(ValueError):
        AiohttpClient(SitzungsAttrappe([]), token=TOKEN)
