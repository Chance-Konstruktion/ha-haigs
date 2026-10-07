"""Der Stand und seine Beobachter (M4b).

Veraendert nicht die eigene Entity den Stand -- zum Beispiel der
Deinstallations-Befehl --, wuesste sie sonst erst beim naechsten
Herzschlag davon. Diese Pruefungen halten das Abonnement ehrlich:
melden bei jeder Aenderung, abmelden ohne Spuren, kein Werfen.
"""

from __future__ import annotations

from haigs.stand import Staende, Stand


class AblageAttrappe:
    """Sichert Teile sofort -- genug fuer Stand-Pruefungen."""

    def __init__(self) -> None:
        self.teile: dict[str, dict] = {}

    async def laden(self) -> dict:
        return {"stand": {}}

    async def sicher_teil(self, feld: str, inhalt: dict) -> None:
        self.teile[feld] = inhalt


async def test_beobachter_hoeren_jede_aenderung():
    ablage = AblageAttrappe()
    staende = Staende(ablage)
    gehoert: list[str] = []
    staende.beobachte(lambda: gehoert.append("ruf"))

    await staende.setzen("a", installiert="1.2.0", pfad="custom_components/a")
    await staende.setzen("a", installiert="", pfad="")

    assert gehoert == ["ruf", "ruf"]
    assert staende.stand("a") == Stand(installiert="", pfad="")


async def test_abmeldung_meldet_nicht_mehr():
    ablage = AblageAttrappe()
    staende = Staende(ablage)
    gehoert: list[str] = []
    abmelden = staende.beobachte(lambda: gehoert.append("ruf"))
    abmelden()
    abmelden()  # doppelt abmelden ist keine Schuld

    await staende.setzen("a", installiert="1.0")

    assert gehoert == []


async def test_laden_feuert_nicht():
    """Das Laden baut den Anfangsstand -- Beobachter sind spaeter dran."""
    ablage = AblageAttrappe()
    staende = Staende(ablage)
    gehoert: list[str] = []
    staende.beobachte(lambda: gehoert.append("ruf"))

    await staende.laden()

    assert gehoert == []
