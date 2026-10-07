"""Die Schmiede: der eine Ort, an dem Anbieter zu Forges werden.

Bisher stand ``GitLabForge(...)`` an zwei Stellen (Einrichtungsdialog
und Geruest) -- ein dritter Anbieter haette beide geaendert. Flug 2088
zuegt das an einen Ort: :func:`schmiede` nimmt Klient, Host und
Anbieternamen und liefert die passende Klasse. Kennt ein Eintrag
keinen Anbieter (alle aus der Zeit vor Flug 2088), gilt GitLab --
das war vorher die einzige Schmiedung, also bleibt das Verhalten
dieselben.

:func:`erkenne` ist die Auskunft fuer den Einrichtungsdialog: wer den
Anbieter nicht weiss (``auto``), bekommt hier geklaert, was unter der
Adresse wirklich antwortet. Drei Fragen, jede ein einziger Abruf:

1. ``GET /api/v4/version`` -- antwortet GitLab (200 mit JSON, oder
   401/403, weil das Tor ohne Schluessel verriegelt ist)?
2. ``GET /api/v1/version`` -- antwortet die Gitea-Familie? Die Version
   darin trennt die Geschwister: Forgejo traegt seit April 2024
   eigene Nummern ab 7 (major >= 2), Gitea bleibt bei 1.x.
3. Bei Nummern, die nichts trennen (Gitea 1.x, alte Forgejo 1.x,
   unlesbare Antwort): ein Blick auf die Startseite -- Forgejo und
   Gitea nennen sich dort im Fusstext. Sagt sie nichts, gilt Gitea:
   die API der beiden ist gemeinsam, die Wahl traegt nur das Suffix.

Antwortet weder GitLab noch die Familie, gibt es
:class:`AnbieterUnbekannt` -- der Dialog nennt den Menschen die
Wahrheit und bittet ihn um die Auswahl von Hand. Das ist kein
Fehlerfall zum Verstecken: eine Adresse, hinter der keiner der drei
Anbieter steht, ist keine Instanz, die HAIGS bedienen kann.
"""

from __future__ import annotations

from .forge import Forge, ForgeFehler, HttpClient, NichtGefunden
from .forgejo_forge import ForgejoForge
from .gitea_forge import GiteaForge
from .gitlab_forge import GitLabForge
from .hacs_katalog_forge import HacsKatalogForge
from .http_aiohttp import KeinJson, TorVerriegelt
from .identity import FORGEJO, GITEA, GITHUB, GITLAB

#: Der Name, unter dem die Familien-API (Gitea wie Forgejo) erreicht wird.
FAMILIE_API = "https://{host}/api/v1/version"

#: Dasselbe fuer GitLab -- Version ist das billigste Tor, das mit
#: und ohne Schluessel zwischen "da" und "nicht da" unterscheidet.
GITLAB_API = "https://{host}/api/v4/version"

#: Die Startseite, deren Fusstext die Geschwister nennt. Nur gefragt,
#: wenn die Versionsnummer allein nicht entscheidet.
STARTSEITE = "https://{host}/"

#: Anbietername -> Klasse. Die Schmiede kennt keine Sonderfalle:
#: ein neuer Anbieter ist ein Eintrag hier und sonst nichts.
KLASSEN: dict[str, type] = {
    GITLAB: GitLabForge,
    FORGEJO: ForgejoForge,
    GITEA: GiteaForge,
    # Der offizielle HACS-Katalog (github.com) -- nur ueber den Optionsfluss.
    GITHUB: HacsKatalogForge,
}


class AnbieterUnbekannt(ForgeFehler):
    """Unter dieser Adresse antwortet kein bekannter Anbieter.

    Der Einrichtungsdialog uebersetzt das in die Bitte, den Anbieter
    von Hand zu waehlen -- mehr Ehre als ein geratener.
    """


def schmiede(klient: HttpClient, host: str, anbieter: str = GITLAB) -> Forge:
    """Der Forge zum Anbieternamen -- ein Eintrag in :data:`KLASSEN`.

    ``anbieter`` ist der Wert aus dem Einrichtungsdialog (``provider``
    im Eintrag), niemals eine Anzeige. Unbekannte Namen sind ein
    Fehler, kein Sturz ins Geraten: wer ``"hub"`` schickt, bekommt
    hier die Wahrheit und nirgends ein GitLab.
    """
    klasse = KLASSEN.get(anbieter)
    if klasse is None:
        raise ForgeFehler("unbekannter Anbieter: " + repr(anbieter))
    return klasse(klient, host)


def _hauptversion(version: str) -> int | None:
    """Die grosse Nummer einer Versionsangabe, oder None.

    ``"1.23.8+dev-abc"`` -> 1, ``"11.0.1+gitea-1.22.0"`` -> 11,
    ``"v13.2"`` -> 13. Forgejo nennt seit v7 eigene Nummern (major
    >= 2), Gitea bleibt bei 1.x -- diese eine Ziffer trennt die
    Geschwister zuverlaessig, seit Forgejo nicht mehr mitzaehlt.
    """
    gereinigt = str(version or "").strip().lstrip("vV")
    erste = gereinigt.split(".", 1)[0]
    try:
        return int(erste)
    except ValueError:
        return None


async def _familie_aus_seite(klient: HttpClient, host: str) -> str:
    """Die Startseite sagt es, wenn die Nummer es nicht kann.

    Forgejo und Gitea nennen sich im Fusstext ihrer Seiten. Versagt
    der Abruf (kein Netz, umgeleitet, keine Lust), bleibt Gitea --
    die API ist gemeinsam, die Wahl traegt nur Anzeigename und
    Suffix. Forgejo wird zuerst befragt: Seiten, die beide nennen
    ("Forgejo, ein Fork von Gitea"), meinen Forgejo.
    """
    try:
        roh = await klient.get_bytes(STARTSEITE.format(host=host))
    except Exception:  # noqa: BLE001 - die Seite ist Zweitmeinung, kein Muss
        return GITEA
    seite = roh.decode("utf-8", errors="replace").lower()
    if "forgejo" in seite:
        return FORGEJO
    return GITEA


async def erkenne(klient: HttpClient, host: str) -> str:
    """Welcher Anbieter antwortet unter dieser Adresse?

    Der Reihe nach: GitLab, dann die Familie, dann innerhalb der
    Familie Nummer oder Startseite. Jede Frage ist ein Abruf;
    ab der ersten Antwort steht das Ergebnis fest.
    """
    host = host.rstrip("/").removeprefix("https://").removeprefix("http://")

    # -- Frage 1: GitLab ------------------------------------------------
    try:
        antwort = await klient.get_json(GITLAB_API.format(host=host))
    except NichtGefunden:
        pass  # kein GitLab unter der Adresse -- weiter zur Familie
    except KeinJson:
        # 200, aber HTML statt JSON: ein Captive Portal oder ein Proxy
        # sitzt vor der Adresse. Das ist KEIN GitLab -- frueher stand
        # dieser Fall beim "verriegelten Tor" mit drin und machte aus
        # jedem Hotspot ein angebliches GitLab (Flug 2093).
        pass
    except TorVerriegelt:
        # Das Tor ist da, aber verriegelt (401/403): nur GitLab
        # verschliesst seine Versionsfrage; Gitea und Forgejo 404en
        # einen Pfad, den es fuer sie nicht gibt. Ein 500 oder 429
        # ist KEIN Beweis -- der fliegt ehrlich weiter (Flug 2093).
        return GITLAB
    else:
        if isinstance(antwort, dict):
            return GITLAB
        raise ForgeFehler("die Versionfrage von " + host + " kam zurueck, aber ohne Form")

    # -- Frage 2: die Gitea-Familie --------------------------------------
    try:
        antwort = await klient.get_json(FAMILIE_API.format(host=host))
    except NichtGefunden:
        raise AnbieterUnbekannt(
            "unter " + host + " antwortet weder GitLab (api/v4) "
            "noch Gitea/Forgejo (api/v1) -- den Anbieter von Hand waehlen"
        ) from None
    except KeinJson:
        # Auch das Familien-Tor antwortet mit HTML: dieselbe Wand.
        raise AnbieterUnbekannt(
            "unter " + host + " antwortet kein JSON-API (api/v4 wie api/v1 "
            "bringen HTML -- vermutlich ein Portal oder Proxy vor der "
            "Instanz) -- den Anbieter von Hand waehlen"
        ) from None
    except TorVerriegelt:
        # Tor da, aber verriegelt -- die Familie trotzdem, die Nummer
        # bleibt unbeantwortet; die Startseite entscheidet. Gitea/Forgejo
        # koennen die Versionsfrage hinter der Anmeldung verstecken.
        return await _familie_aus_seite(klient, host)

    version = antwort.get("version") if isinstance(antwort, dict) else None
    haupt = _hauptversion(str(version or ""))
    if haupt is not None and haupt >= 2:
        # Forgejo zaehlt seit v7 selbst (2024); Gitea bleibt bei 1.x.
        return FORGEJO
    # Gitea 1.x, alte Forgejo 1.x, oder unlesbar: die Startseite.
    return await _familie_aus_seite(klient, host)
