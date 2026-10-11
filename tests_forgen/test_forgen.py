"""HAIGS gegen echte Forgen: Gitea und Forgejo, beide ohne TLS.

Der Fall aus GitHub #1, Schritt fuer Schritt wie im Einrichtungsdialog
und im Laden: Adresse mit http:// eintippen, Anbieter erkennen, Forge
formen, die Instanz durchsuchen, Kandidaten pruefen, Version, Datei und
Archiv holen. Kein einziger Ruf darf dabei https sprechen.
"""

from __future__ import annotations

import io
import json
import zipfile

from haigs.const import host_normalisieren, schema_aus_eingabe
from haigs.core.entdeckung import entdecke
from haigs.core.identity import FORGEJO, GITEA
from haigs.core.schmiede import erkenne, schmiede

ERWARTET = {"gitea": GITEA, "forgejo": FORGEJO}
#: Die Saat aus ci/forgen_saat.py: Repo -> erwartete letzte Version.
SAAT = {
    "haigs/ha-powerline": "261008",
    "haigs/ha-gaming-assistant": "261011",  # HAIGS streicht das v
    "haigs/ha-spatial-matter": "",
}
LOCKVOGEL = "haigs/kein-hacs-json"


async def _forge(eingabe: str, klient):
    host, schema = host_normalisieren(eingabe), schema_aus_eingabe(eingabe)
    assert schema == "http"
    assert ":" in host, "der eigene Port muss im Host bleiben"
    anbieter = await erkenne(klient, host, schema)
    return anbieter, schmiede(klient, host, anbieter, schema)


async def test_erkennung_nennt_das_richtige_geschwister(
    forge_name, eingabe, klient_und_spur
):
    klient, spur = klient_und_spur
    anbieter, forge = await _forge(eingabe, klient)
    assert anbieter == ERWARTET[forge_name]
    assert forge.api == eingabe + "/api/v1"
    assert spur and all(url.startswith("http://") for url in spur), spur


async def test_entdeckung_findet_die_saat_und_verwirft_den_lockvogel(
    eingabe, klient_und_spur
):
    klient, spur = klient_und_spur
    _, forge = await _forge(eingabe, klient)
    funde = {fund.info.full_name: fund for fund in await entdecke(forge)}

    for pfad, version in SAAT.items():
        assert pfad in funde, f"{pfad} fehlt in {sorted(funde)}"
        fund = funde[pfad]
        assert fund.uebernehmen, (pfad, fund.befund.fehler)
        assert fund.letzte_version == version, pfad
    assert LOCKVOGEL in funde
    assert not funde[LOCKVOGEL].uebernehmen, "ohne hacs.json darf nichts durch"
    assert all(url.startswith("http://") for url in spur), spur


async def test_datei_zweig_und_archiv_ueber_http(eingabe, klient_und_spur):
    klient, spur = klient_und_spur
    _, forge = await _forge(eingabe, klient)
    pfad = "haigs/ha-powerline"

    info = await forge.repository(pfad)
    hacs = json.loads(await forge.datei(pfad, "hacs.json", info.standardzweig))
    assert hacs.get("name")

    kopf = await forge.zweig_stand(pfad, info.standardzweig)
    assert len(kopf.sha) == 40

    releases = await forge.releases(pfad)
    assert [r.tag for r in releases] == ["261008"]
    assert "261008" in await forge.tags(pfad)

    adresse = await forge.archiv_url(pfad, "261008")
    assert adresse.startswith(eingabe + "/"), adresse
    with zipfile.ZipFile(io.BytesIO(await forge.archiv(pfad, "261008"))) as archiv:
        assert any(
            n.endswith("custom_components/") or "/custom_components/" in n
            for n in archiv.namelist()
        )

    assert all(url.startswith("http://") for url in spur), spur


async def test_repository_nach_id_findet_dasselbe(eingabe, klient_und_spur):
    """Die Identitaet haengt an der Anbieter-ID -- sie muss zurueckfuehren."""
    klient, _ = klient_und_spur
    _, forge = await _forge(eingabe, klient)
    info = await forge.repository("haigs/ha-gaming-assistant")
    # Ohne Token ist das ID-Tor zu (401, wie auf codeberg.org und
    # gitea.com) -- der bekannte Pfad traegt, die ID muss stimmen.
    wieder = await forge.repository_nach_id(info.provider_id, pfad=info.full_name)
    assert wieder.full_name == info.full_name
    assert wieder.provider_id == info.provider_id
