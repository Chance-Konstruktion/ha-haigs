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
#: Die Saat aus ci/forgen_saat.py: Repos, die ein Release auf dem
#: neuesten Tag bekommen. Die erwartete Version wird zur Laufzeit
#: gegen den NEUESTEN TAG des migrierten Repos gewogen, nicht gegen
#: eine gepinnte Zahl: die Saat migriert echte Repos aus dem eigenen
#: GitLab -- jeder neue Tag dort (261008 -> 261016, 17.10.) liesse
#: eine Pin altern und den Job rot stehen (Flug 2820, roter Build
#: in MR !61, Pipeline 23970/23972).
SAAT = (
    "haigs/ha-powerline",
    "haigs/ha-gaming-assistant",  # HAIGS streicht das v
    "haigs/ha-spatial-matter",
)
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

    for pfad in SAAT:
        assert pfad in funde, f"{pfad} fehlt in {sorted(funde)}"
        fund = funde[pfad]
        assert fund.uebernehmen, (pfad, fund.befund.fehler)
        # Die letzte Version ist der NEUESTE Tag -- derselbe, auf den
        # die Saat ihr Release legt. GEMESSEN am lebenden Bestand,
        # nicht an einer gepinnten Zahl, die mit dem naechsten Tag
        # im eigenen GitLab veraltet.
        tags = await forge.tags(pfad)
        assert tags, pfad
        assert fund.letzte_version == tags[0], (pfad, fund.letzte_version, tags[0])
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
    tags = await forge.tags(pfad)
    assert tags, pfad
    # Das Release steht auf dem NEUESTEN Tag (so saet es forgen_saat.py) --
    # drift-robust gewogen, nicht gepinnt.
    assert [r.tag for r in releases] == [tags[0]]
    neuester = tags[0]

    adresse = await forge.archiv_url(pfad, neuester)
    assert adresse.startswith(eingabe + "/"), adresse
    with zipfile.ZipFile(io.BytesIO(await forge.archiv(pfad, neuester))) as archiv:
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
