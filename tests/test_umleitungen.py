"""Ticket #20: Umleitungen reichen das Token nicht weiter.

Die Verkuendigungs-Skripte tragen ``JOB-TOKEN`` bzw. ``Authorization``
ueber die Standardbibliothek; die reicht Kopfzeilen bei einer Umleitung
auch an ein fremdes Ziel weiter — dort koennte ein Repo-Besitzer sie
abgreifen. Hier laufen zwei winzige lokale Server auf verschiedenen
Loopback-Ports (der Port zaehlt als fremder Host, genau wie draussen):
der Umleiter zeigt weiter, das Ziel schreibt auf, WELCHE Koepfe
ankamen. Kein Byte verlaesst die Maschine, und kein Test hier braucht
ein Netz-Modul (die Wache in der Pipeline verbietet das in ``tests/``
aus gutem Grund).
"""

from __future__ import annotations

from auslieferung.github_verkuenden import _ruf
from auslieferung.verkuendigen import rufe
from tests.attrappe import LokaleWache

TOKEN = "geheimer-job-token"


def test_verkuendigung_umleitung_zu_fremdem_host_verliert_das_job_token():
    ziel = LokaleWache(koerper=b"ok")
    umleiter = LokaleWache()
    umleiter.umleitung_pfad = "/start"
    umleiter.umleitung_ziel = ziel.url + "/ziel"
    try:
        status, koerper = rufe("GET", umleiter.url + "/start", token=TOKEN)
    finally:
        umleiter.schliessen()
        ziel.schliessen()
    assert status == 200
    assert koerper == b"ok"
    # Der Umleiter selbst ist der eigene Host -- er hat das Token gesehen.
    assert umleiter.aufzeichnung[0][1]["job-token"] == TOKEN
    # Beim fremden Ziel kam die Anfrage an — aber ohne das Job-Token.
    assert "job-token" not in ziel.aufzeichnung[0][1]


def test_verkuendigung_umleitung_im_eigenen_haus_behaelt_das_job_token():
    wache = LokaleWache(koerper=b"ok")
    wache.umleitung_pfad = "/start"
    wache.umleitung_ziel = wache.url + "/ziel"
    try:
        status, koerper = rufe("GET", wache.url + "/start", token=TOKEN)
    finally:
        wache.schliessen()
    assert status == 200
    assert koerper == b"ok"
    # Beide Spruenge auf demselben Host samt Port: das Token bleibt.
    assert wache.aufzeichnung[0][1]["job-token"] == TOKEN
    assert wache.aufzeichnung[1][1]["job-token"] == TOKEN


def test_github_umleitung_zu_fremdem_host_verliert_den_bearer():
    ziel = LokaleWache(koerper=b"{}")
    umleiter = LokaleWache(koerper=b"{}")
    umleiter.umleitung_pfad = "/start"
    umleiter.umleitung_ziel = ziel.url + "/ziel"
    try:
        _ruf(umleiter.url + "/start", token=TOKEN)
    finally:
        umleiter.schliessen()
        ziel.schliessen()
    assert umleiter.aufzeichnung[0][1]["authorization"] == "Bearer " + TOKEN
    assert "authorization" not in ziel.aufzeichnung[0][1]


def test_github_umleitung_im_eigenen_haus_behaelt_den_bearer():
    wache = LokaleWache(koerper=b"{}")
    wache.umleitung_pfad = "/start"
    wache.umleitung_ziel = wache.url + "/ziel"
    try:
        _ruf(wache.url + "/start", token=TOKEN)
    finally:
        wache.schliessen()
    assert wache.aufzeichnung[0][1]["authorization"] == "Bearer " + TOKEN
    assert wache.aufzeichnung[1][1]["authorization"] == "Bearer " + TOKEN
