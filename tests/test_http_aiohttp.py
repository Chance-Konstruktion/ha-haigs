"""Der HTTP-Klient auf aufgezeichneten Antworten -- ohne Netz, ohne aiohttp.

Geprueft wird die Vereinbarung aus ``forge.py`` (404 -> NichtGefunden,
Unerwartetes -> ForgeFehler), die Klartext-Pfade aus der Roadmap (401/403,
429), das Verfolgen der Seiten ueber ``X-Next-Page`` und den
ETag-Zwischenspeicher.
"""

from __future__ import annotations

import json

import pytest
from haigs.core.forge import ForgeFehler, NichtGefunden
from haigs.core.http_aiohttp import AiohttpClient

from tests.attrappe import Aufzeichnung, SitzungsAttrappe
from tests.echte_antworten import (
    KOPFZEILEN_SEITE_1,
    KOPFZEILEN_SEITE_2,
    SEITE_1,
    SEITE_2,
)

URL = "https://gitlab.example.net/api/v4/projects"


def antwort(daten, status=200, kopfzeilen=None):
    return Aufzeichnung(
        status=status, text=json.dumps(daten), kopfzeilen=kopfzeilen or {}
    )


class WarteProtokoll:
    """Statt zu schlafen: merkt sich die verlangten Sekunden."""

    def __init__(self):
        self.sekunden: list[float] = []

    async def __call__(self, sekunden: float) -> None:
        self.sekunden.append(sekunden)


def klient(aufzeichnungen, token=None, **rest):
    warte = rest.pop("warte", None) or WarteProtokoll()
    sitzung = SitzungsAttrappe(aufzeichnungen)
    k = AiohttpClient(sitzung, token=token, warte=warte, **rest)
    return k, sitzung, warte


# -- Basics ---------------------------------------------------------


@pytest.mark.asyncio
async def test_json_kommt_an():
    k, sitzung, _ = klient([antwort({"id": 7})])
    assert await k.get_json(URL) == {"id": 7}
    assert sitzung.abrufe[0][0] == URL


@pytest.mark.asyncio
async def test_params_reisen_mit_und_bleiben_beim_aufrufer():
    k, sitzung, _ = klient([antwort([{"id": 1}])])
    params = {"per_page": "30"}
    await k.get_json(URL, params)
    assert sitzung.abrufe[0][1] == {"per_page": "30"}
    assert params == {"per_page": "30"}, "die Params des Aufrufers sind heilig"


@pytest.mark.asyncio
async def test_token_reist_in_der_kopfzeile_und_nie_in_der_url():
    k, sitzung, _ = klient([antwort({})], token="geheimer-lese-token")
    await k.get_json(URL)
    url, _, kopfzeilen = sitzung.abrufe[0]
    assert "geheimer-lese-token" not in url
    assert kopfzeilen["Authorization"] == "Bearer geheimer-lese-token"
    assert kopfzeilen["User-Agent"].startswith("HAIGS ")  # wer abfragt, nennt sich


@pytest.mark.asyncio
async def test_ohne_token_keine_authorization_kopfzeile():
    k, sitzung, _ = klient([antwort({})])
    await k.get_json(URL)
    assert "Authorization" not in (sitzung.abrufe[0][2] or {})


@pytest.mark.asyncio
async def test_kein_json_wird_gemeldet():
    k, _, _ = klient([Aufzeichnung(status=200, text="kein json")])
    with pytest.raises(ForgeFehler, match="kein JSON"):
        await k.get_json(URL)


# -- Statusuebersetzung ---------------------------------------------


@pytest.mark.asyncio
async def test_404_wird_zu_nicht_gefunden():
    k, _, _ = klient([Aufzeichnung(status=404, text="")])
    with pytest.raises(NichtGefunden):
        await k.get_json(URL)


@pytest.mark.asyncio
async def test_401_gibt_klartext():
    k, _, _ = klient([Aufzeichnung(status=401, text="")])
    with pytest.raises(ForgeFehler, match="Token fehlt oder reicht nicht"):
        await k.get_json(URL)


@pytest.mark.asyncio
async def test_403_gibt_klartext():
    k, _, _ = klient([Aufzeichnung(status=403, text="")])
    with pytest.raises(ForgeFehler, match="Token fehlt oder reicht nicht"):
        await k.get_json(URL)


@pytest.mark.asyncio
async def test_serverfehler_wird_gemeldet():
    k, _, _ = klient([Aufzeichnung(status=500, text="")])
    with pytest.raises(ForgeFehler, match="500"):
        await k.get_json(URL)


# -- 429: Wartezeit beachten ----------------------------------------


@pytest.mark.asyncio
async def test_429_wartet_die_verlangte_zeit_und_versucht_nocheinmal():
    k, sitzung, warte = klient(
        [
            Aufzeichnung(status=429, text="", kopfzeilen={"Retry-After": "7"}),
            antwort({"ok": True}),
        ]
    )
    assert await k.get_json(URL) == {"ok": True}
    assert warte.sekunden == [7.0]
    assert len(sitzung.abrufe) == 2


@pytest.mark.asyncio
async def test_429_ohne_retry_after_wartet_hoeflich_eine_sekunde():
    k, _, warte = klient([Aufzeichnung(status=429, text=""), antwort({})])
    await k.get_json(URL)
    assert warte.sekunden == [1.0]


@pytest.mark.asyncio
async def test_429_bleibt_nach_drei_warteversuchen_rot():
    stur = Aufzeichnung(status=429, text="", kopfzeilen={"Retry-After": "30"})
    k, sitzung, warte = klient([stur, stur, stur, stur])
    with pytest.raises(ForgeFehler, match="429"):
        await k.get_json(URL)
    assert len(sitzung.abrufe) == 4, "einmal fragen, dreimal nochmal versuchen"
    assert warte.sekunden == [30.0, 30.0, 30.0]


# -- Seiten ueber X-Next-Page ---------------------------------------


@pytest.mark.asyncio
async def test_seiten_werden_bis_zur_letzten_verfolgt():
    k, sitzung, _ = klient(
        [
            antwort(
                [{"id": 1}, {"id": 2}],
                kopfzeilen={"X-Next-Page": "2"},
            ),
            antwort([{"id": 3}], kopfzeilen={"X-Next-Page": ""}),
        ]
    )
    ergebnis = await k.get_json(URL, {"per_page": "2"})
    assert ergebnis == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(sitzung.abrufe) == 2
    assert sitzung.abrufe[1][1] == {"per_page": "2", "page": "2"}


@pytest.mark.asyncio
async def test_seitenanfragen_tragen_weiterhin_den_token():
    k, sitzung, _ = klient(
        [
            antwort([1], kopfzeilen={"X-Next-Page": "2"}),
            antwort([2], kopfzeilen={"X-Next-Page": ""}),
        ],
        token="geheimer-lese-token",
    )
    await k.get_json(URL)
    assert sitzung.abrufe[1][2]["Authorization"] == "Bearer geheimer-lese-token"


@pytest.mark.asyncio
@pytest.mark.parametrize("ende", ["", "0", None])
async def test_fehlende_fortsetzung_zaehlt_als_letzte_seite(ende):
    kopfzeilen = {} if ende is None else {"X-Next-Page": ende}
    k, sitzung, _ = klient([antwort([1], kopfzeilen=kopfzeilen)])
    assert await k.get_json(URL) == [1]
    assert len(sitzung.abrufe) == 1


@pytest.mark.asyncio
async def test_objekt_wird_nicht_seitenweise_behandelt():
    k, sitzung, _ = klient([antwort({"id": 7}, kopfzeilen={"X-Next-Page": "2"})])
    assert await k.get_json(URL) == {"id": 7}
    assert len(sitzung.abrufe) == 1


@pytest.mark.asyncio
async def test_wiederholte_seitennummer_wird_gemeldet():
    k, _, _ = klient(
        [
            antwort([1], kopfzeilen={"X-Next-Page": "2"}),
            antwort([2], kopfzeilen={"X-Next-Page": "2"}),
        ]
    )
    with pytest.raises(ForgeFehler, match="wiederholt sich"):
        await k.get_json(URL)


@pytest.mark.asyncio
async def test_seitenzahl_hat_eine_obergrenze():
    k, _, _ = klient(
        [
            antwort([1], kopfzeilen={"X-Next-Page": "2"}),
            antwort([2], kopfzeilen={"X-Next-Page": "3"}),
            antwort([3], kopfzeilen={"X-Next-Page": "4"}),
        ],
        max_seiten=3,
    )
    with pytest.raises(ForgeFehler, match="mehr als 3 Seiten"):
        await k.get_json(URL)


# -- ETag-Zwischenspeicher ------------------------------------------


@pytest.mark.asyncio
async def test_etag_wird_gesendet_und_304_liefert_den_speicher():
    k, sitzung, _ = klient(
        [
            antwort({"id": 7}, kopfzeilen={"ETag": 'W/"wabe42"'}),
            Aufzeichnung(status=304, text=""),
        ]
    )
    assert await k.get_json(URL) == {"id": 7}
    assert await k.get_json(URL) == {"id": 7}
    assert sitzung.abrufe[1][2]["If-None-Match"] == 'W/"wabe42"'
    assert len(sitzung.abrufe) == 2


@pytest.mark.asyncio
async def test_304_ohne_speicher_ist_ein_fehler():
    k, _, _ = klient([Aufzeichnung(status=304, text="")])
    with pytest.raises(ForgeFehler, match="304"):
        await k.get_json(URL)


@pytest.mark.asyncio
async def test_ohne_etag_keine_bedingte_anfrage():
    k, sitzung, _ = klient([antwort({"id": 7}), antwort({"id": 7})])
    await k.get_json(URL)
    await k.get_json(URL)
    assert "If-None-Match" not in (sitzung.abrufe[1][2] or {})


@pytest.mark.asyncio
async def test_geaenderte_antwort_aktualisiert_den_speicher():
    k, _, _ = klient(
        [
            antwort({"id": 1}, kopfzeilen={"ETag": 'W/"eins"'}),
            antwort({"id": 2}, kopfzeilen={"ETag": 'W/"zwei"'}),
            Aufzeichnung(status=304, text=""),
        ]
    )
    assert await k.get_json(URL) == {"id": 1}
    assert await k.get_json(URL) == {"id": 2}
    assert await k.get_json(URL) == {"id": 2}, "304 liefert den neuen Stand"


@pytest.mark.asyncio
async def test_mehrseitiges_wird_nicht_gespeichert():
    k, sitzung, _ = klient(
        [
            antwort([1], kopfzeilen={"X-Next-Page": "2", "ETag": 'W/"a"'}),
            antwort([2], kopfzeilen={"X-Next-Page": ""}),
            antwort([1], kopfzeilen={"X-Next-Page": "2", "ETag": 'W/"a"'}),
            antwort([2], kopfzeilen={"X-Next-Page": ""}),
        ]
    )
    assert await k.get_json(URL) == [1, 2]
    assert await k.get_json(URL) == [1, 2]
    assert "If-None-Match" not in (sitzung.abrufe[2][2] or {})


@pytest.mark.asyncio
async def test_speicher_wird_nur_als_kopie_herausgegeben():
    k, _, _ = klient(
        [
            antwort([1, 2], kopfzeilen={"ETag": 'W/"wabe"'}),
            Aufzeichnung(status=304, text=""),
        ]
    )
    ergebnis = await k.get_json(URL)
    ergebnis.append(3)  # duerfen wir: es ist unsere Kopie
    assert await k.get_json(URL) == [1, 2], "der Speicher bleibt unberuehrt"


@pytest.mark.asyncio
@pytest.mark.parametrize("schreibung", ["ETag", "etag", "ETAG"])
async def test_kopfzeilen_sind_gross_klein_unempfindlich(schreibung):
    k, sitzung, _ = klient(
        [
            antwort({"id": 7}, kopfzeilen={schreibung: 'W/"w"'}),
            Aufzeichnung(status=304, text=""),
        ]
    )
    await k.get_json(URL)
    await k.get_json(URL)
    assert sitzung.abrufe[1][2]["If-None-Match"] == 'W/"w"'


# -- get_bytes ------------------------------------------------------


@pytest.mark.asyncio
async def test_bytes_kommen_roh_an():
    k, _, _ = klient([Aufzeichnung(status=200, rohbytes=b"\x00\x01\x02")])
    assert await k.get_bytes(URL) == b"\x00\x01\x02"


@pytest.mark.asyncio
async def test_bytes_404_wird_zu_nicht_gefunden():
    k, _, _ = klient([Aufzeichnung(status=404, text="")])
    with pytest.raises(NichtGefunden):
        await k.get_bytes(URL)


@pytest.mark.asyncio
async def test_bytes_etag_wird_beachtet():
    k, sitzung, _ = klient(
        [
            Aufzeichnung(status=200, rohbytes=b"daten", kopfzeilen={"ETag": 'W/"b"'}),
            Aufzeichnung(status=304, text=""),
        ]
    )
    assert await k.get_bytes(URL) == b"daten"
    assert await k.get_bytes(URL) == b"daten"
    assert sitzung.abrufe[1][2]["If-None-Match"] == 'W/"b"'


@pytest.mark.asyncio
async def test_bytes_429_wartet_auch():
    k, _, warte = klient(
        [
            Aufzeichnung(status=429, text="", kopfzeilen={"Retry-After": "4"}),
            Aufzeichnung(status=200, rohbytes=b"daten"),
        ]
    )
    assert await k.get_bytes(URL) == b"daten"
    assert warte.sekunden == [4.0]


# -- Aufzeichnung echter Antworten (gitlab.com, 2026-09-03) ----------

ECHT_URL = "https://gitlab.com/api/v4/projects"
ECHT_PARAMS = {"topic": "hacs", "per_page": "3", "archived": "false"}


@pytest.mark.asyncio
async def test_echte_seitenfolge_laeuft_durch():
    k, sitzung, _ = klient(
        [
            Aufzeichnung(
                status=200, text=json.dumps(SEITE_1), kopfzeilen=KOPFZEILEN_SEITE_1
            ),
            Aufzeichnung(
                status=200, text=json.dumps(SEITE_2), kopfzeilen=KOPFZEILEN_SEITE_2
            ),
        ]
    )
    ergebnis = await k.get_json(ECHT_URL, ECHT_PARAMS)
    assert len(ergebnis) == int(KOPFZEILEN_SEITE_1["x-total"]) == 4
    assert sitzung.abrufe[1][1]["page"] == "2"
    # Echte Projekt-Datensaetze tragen 20 Felder, eins davon verschachtelt:
    assert isinstance(ergebnis[0].get("namespace"), dict)
    assert SEITE_1[0]["path_with_namespace"] in [
        p["path_with_namespace"] for p in ergebnis
    ]


@pytest.mark.asyncio
async def test_echte_etag_und_304():
    # Die zweite Seite ist die letzte, also eine komplette Antwort mit
    # eigenem, echtem ETag -- genau der Fall, den der Speicher annimmt.
    k, sitzung, _ = klient(
        [
            Aufzeichnung(
                status=200, text=json.dumps(SEITE_2), kopfzeilen=KOPFZEILEN_SEITE_2
            ),
            Aufzeichnung(status=304, text=""),
        ]
    )
    params = dict(ECHT_PARAMS, page="2")
    erste = await k.get_json(ECHT_URL, params)
    zweite = await k.get_json(ECHT_URL, params)
    assert zweite == erste == SEITE_2
    assert sitzung.abrufe[1][2]["If-None-Match"] == KOPFZEILEN_SEITE_2["etag"]


# -- Seitengrenze ----------------------------------------------------
#
# Der Seitenverfolger ist richtig, solange jemand die ganze Liste will.
# Wer nur wissen will, OB eine Instanz antwortet, will das nicht: gegen
# eine grosse Instanz kostete eine Probe sonst zwanzigtausend Projekte
# (Issue #11, Befund b).


@pytest.mark.asyncio
async def test_seiten_eins_holt_genau_eine_seite():
    """Mit ``seiten=1`` wird nicht weitergeblaettert -- auch nicht, wenn
    der Anbieter ausdruecklich eine Folgeseite anbietet."""
    k, sitzung, _ = klient(
        [
            antwort([{"id": 1}], kopfzeilen={"X-Next-Page": "2"}),
            antwort([{"id": 2}], kopfzeilen={"X-Next-Page": ""}),
        ]
    )
    daten = await k.get_json(URL, seiten=1)

    assert daten == [{"id": 1}]
    assert len(sitzung.abrufe) == 1, "es darf genau eine Anfrage rausgehen"


@pytest.mark.asyncio
async def test_ohne_grenze_wird_weiterhin_alles_geholt():
    """Die Vorgabe bleibt, wie sie war -- die Grenze ist ein Zusatz,
    keine Verhaltensaenderung."""
    k, sitzung, _ = klient(
        [
            antwort([{"id": 1}], kopfzeilen={"X-Next-Page": "2"}),
            antwort([{"id": 2}], kopfzeilen={"X-Next-Page": ""}),
        ]
    )
    daten = await k.get_json(URL)

    assert daten == [{"id": 1}, {"id": 2}]
    assert len(sitzung.abrufe) == 2


@pytest.mark.asyncio
async def test_grenze_zwei_holt_zwei_seiten_und_hoert_dann_auf():
    """Aufhoeren ist gewollt und leise: kein Fehler, nur Schluss."""
    k, sitzung, _ = klient(
        [
            antwort([1], kopfzeilen={"X-Next-Page": "2"}),
            antwort([2], kopfzeilen={"X-Next-Page": "3"}),
            antwort([3], kopfzeilen={"X-Next-Page": ""}),
        ]
    )
    daten = await k.get_json(URL, seiten=2)

    assert daten == [1, 2]
    assert len(sitzung.abrufe) == 2
