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


# -------------------------- Dateiliste (Befund #19: flache Kategorien)


class RundreiseAblage:
    """Sichert Teile und gibt sie beim Laden wieder -- fuer den
    Speicherweg einer Dateiliste."""

    def __init__(self) -> None:
        self.teile: dict[str, dict] = {}

    async def laden(self) -> dict:
        return {"stand": self.teile.get("stand", {})}

    async def sicher_teil(self, feld: str, inhalt: dict) -> None:
        self.teile[feld] = inhalt


async def test_dateiliste_ueberlebt_den_speicherweg():
    ablage = RundreiseAblage()
    staende = Staende(ablage)

    await staende.setzen(
        "blume",
        installiert="1.2.0",
        pfad="themes",
        dateien=["hell.yaml", "g/gruppe.yaml"],
    )

    frisch = Staende(ablage)
    await frisch.laden()
    stand = frisch.stand("blume")
    assert stand.dateien == ("hell.yaml", "g/gruppe.yaml")
    assert stand.pfad == "themes"
    assert stand.installiert == "1.2.0"


async def test_dateiliste_laeert_beim_deinstallieren():
    ablage = AblageAttrappe()
    staende = Staende(ablage)

    await staende.setzen("blume", installiert="1.0", pfad="themes", dateien=["a.yaml"])
    await staende.setzen("blume", installiert="", pfad="", dateien=[])

    assert staende.stand("blume") == Stand(installiert="", pfad="", dateien=())


async def test_dateiliste_verdraegt_muell_in_der_ablage():
    """Die Ablage ist eine Datei -- Listen mit Muell darin liest die
    Rueckreise still als leer."""
    ablage = RundreiseAblage()
    ablage.teile["stand"] = {
        "blume": {
            "installiert": "1.0",
            "pfad": "themes",
            "dateien": [5, None, "gut.yaml"],
        }
    }
    staende = Staende(ablage)
    await staende.laden()
    assert staende.stand("blume").dateien == ("gut.yaml",)
