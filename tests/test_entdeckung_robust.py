"""Entdeckung robust (Ticket #22): eine Kategorie-Quelle, ein Fehler je Kandidat.

Zwei belegte Schwaechen: Die Kategorie kam aus dem ERSTEN ``hacs-*``-
Topic -- die Reihenfolge entschied, und ein Zusatz-Topic wie
``hacs-ready`` machte einen gueltigen Fund ungueltig. Und ein einzelner
Forge-Fehler riss den ganzen Scan ab. Der Kern kann beides besser:
``kategorie_aus_topics`` kennt die Kategorien, und ein kaputtes Repo
wird ein Fund mit Fehlertext statt einer Ausnahme.
"""

import json

import pytest
from haigs.core.entdeckung import entdecke
from haigs.core.forge import ForgeFehler
from haigs.core.gitlab_forge import GitLabForge

from tests.attrappe import projekt
from tests.attrappe_kern import FakeHttp

HOST = "gitlab.example.net"
GUELTIG = json.dumps({"name": "Bar", "render_readme": True})


@pytest.mark.parametrize(
    "topics",
    [
        ("hacs", "hacs-plugin"),
        ("hacs-plugin", "hacs"),
        ("hacs", "hacs-custom", "hacs-plugin"),
        ("hacs-plugin", "hacs-ready", "hacs"),
        ("hacs-ready", "hacs-custom", "hacs-plugin", "hacs"),
    ],
)
@pytest.mark.asyncio
async def test_kategorie_haengt_nicht_an_reihenfolge_noch_zusatz_topics(topics):
    """``hacs-custom`` und ``hacs-ready`` sind keine Kategorien -- die
    Absicht ``hacs-plugin`` setzt sich durch, egal wo sie steht."""
    http = FakeHttp({"/groups/": [projekt(topics=topics)]}, {"hacs.json": GUELTIG})
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde[0].befund.kategorie == "plugin"
    assert funde[0].uebernehmen, funde[0].befund.fehler


@pytest.mark.asyncio
async def test_unbekanntes_topic_allein_ergibt_den_normalfall():
    """Kein bekanntes Kategorie-Topic: ``integration``, der Normalfall."""
    http = FakeHttp(
        {"/groups/": [projekt(topics=("hacs", "hacs-ready"))]},
        {"hacs.json": GUELTIG},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
    assert funde[0].befund.kategorie == "integration"
    assert funde[0].uebernehmen


@pytest.mark.asyncio
async def test_zwei_kategorien_entscheidet_die_liste_nicht_das_topic():
    """``hacs-theme`` und ``hacs-plugin`` zusammen: beide Reihenfolgen
    ergeben dieselbe Kategorie (``plugin`` -- so steht es in KATEGORIEN)."""

    async def kategorie(topics: tuple[str, ...]) -> str:
        http = FakeHttp({"/groups/": [projekt(topics=topics)]}, {"hacs.json": GUELTIG})
        funde = await entdecke(GitLabForge(http, HOST), gruppe="foo")
        return funde[0].befund.kategorie

    erst_theme = await kategorie(("hacs", "hacs-theme", "hacs-plugin"))
    erst_plugin = await kategorie(("hacs", "hacs-plugin", "hacs-theme"))
    assert erst_theme == erst_plugin == "plugin"


@pytest.mark.asyncio
async def test_entwicklungs_topic_wird_nie_zur_kategorie():
    """``hacs-development`` bleibt draussen -- auch neben ``hacs-theme``."""
    http = FakeHttp(
        {"/groups/": [projekt(topics=("hacs", "hacs-development", "hacs-theme"))]},
        {"hacs.json": GUELTIG},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="foo", mit_vorab=True)
    assert funde[0].befund.kategorie == "theme"


@pytest.mark.asyncio
async def test_forge_fehler_bei_einem_kandidaten_kostet_die_anderen_nicht():
    """5xx beim Lesen EINER ``hacs.json``: die uebrigen Funde kommen an,
    der kaputte traegt den Fehlertext."""
    http = FakeHttp(
        {
            "/groups/": [
                projekt(pid=1, full_name="gruppe/gut"),
                projekt(pid=2, full_name="gruppe/kaputt", topics=("hacs", "hacs-plugin")),
                projekt(pid=3, full_name="gruppe/auch-gut"),
            ],
        },
        {"gruppe%2Fgut": GUELTIG, "gruppe%2Fauch-gut": GUELTIG},
        datei_fehler={"gruppe%2Fkaputt": ForgeFehler("500 Internal Server Error")},
    )
    funde = await entdecke(GitLabForge(http, HOST), gruppe="gruppe")
    assert [f.info.full_name for f in funde] == [
        "gruppe/gut",
        "gruppe/kaputt",
        "gruppe/auch-gut",
    ]
    assert [f.uebernehmen for f in funde] == [True, False, True]
    kaputt = funde[1]
    assert kaputt.befund.kategorie == "plugin", "die Kategorie bleibt lesbar"
    assert any("500 Internal Server Error" in f for f in kaputt.befund.fehler), (
        kaputt.befund.fehler
    )


@pytest.mark.asyncio
async def test_toter_scan_bleibt_ein_fehler():
    """Die Heilung gilt je Kandidat: faellt die Suche selbst aus, meldet
    die Entdeckung weiter ehrlich einen Fehler statt leerer Funde."""

    class ToteSuche:
        host = HOST

        async def suche_nach_topic(self, *args, **kwargs):
            raise ForgeFehler("Suchindex nicht erreichbar")

    with pytest.raises(ForgeFehler, match="Suchindex"):
        await entdecke(ToteSuche(), gruppe="foo")
