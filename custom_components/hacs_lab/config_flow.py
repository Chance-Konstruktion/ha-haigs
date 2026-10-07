"""Einrichtungsdialog: Anbieter, Host, optionaler Token, Pruefverbindung.

Seit Flug 2088 gehoert der Anbieter zur ersten Frage: GitLab, Forgejo
(Codeberg) oder Gitea -- oder "auto", und die Schmiede erkundet,
was unter der Adresse antwortet (zwei, hoechstens drei Abrufe, siehe
``core/schmiede.py``). Der erkannte (oder gewaehlte) Name reist in
die Eintragsdaten; Eintraege aus der Zeit davor tragen keinen und
gelten als GitLab -- die einzige Schmiedung, die es damals gab.

Die Pruefung geht durch den echten Weg -- Klient, Forge, Kern -- und
nicht durch eine Sonderleitung: schlaegt sie fehl, zeigt der Dialog
genau das, was der Kern zu sagen hat (401/403 → «Token fehlt oder
reicht nicht», kein erkannter Anbieter → «von Hand waehlen»,
alles andere → Klartext). Ein Stacktrace erreicht den Menschen nie.

Dafuer eignet sich die Topic-Suche am besten: sie ist dasselbe Mittel,
mit dem spaeter die Entdeckung laeuft (M6), und sie klappt ohne Token
auf oeffentlichen Instanzen genauso wie mit Token auf eigenen.

Der Optionsdialog verwaltet seit Stufe M3 ausserdem die Liste der
Custom Repositories: volle Adresse eingeben, Identitaet ueber die API
klaeren, Kategorie waehlen (Vorbelegung aus ``hacs-<kategorie>``),
Fehler beim Namen nennen. Doppelte Eintraege weist er ab, bevor er
anlegt; Entfernen geht mit und ohne Deinstallation -- die Dateien
selbst sind Stufe M4.
"""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_ENTWICKLERMODUS,
    ANBIETER_AUTO,
    CONF_ABSTAND_MINUTEN,
    CONF_HOST,
    CONF_PROVIDER,
    CONF_TOKEN,
    DOMAIN,
    STANDARD_ABSTAND_MINUTEN,
    host_normalisieren,
)
from .core.forge import ForgeFehler, NichtGefunden, RepositoryInfo
from .core.http_aiohttp import AiohttpClient
from .core.identity import FORGEJO, GITEA, GITLAB, RepositoryIdentity
from .core.schmiede import AnbieterUnbekannt, erkenne, schmiede
from .core.validierung import KATEGORIEN
from .eintraege import (
    CONF_ADRESSE,
    CONF_DATEIEN_DEINSTALLIEREN,
    CONF_ENTFERNEN,
    CONF_KATEGORIE,
    AdresseUngueltig,
    BereitsVorhanden,
    KategorieUnbekannt,
    adresse_zerlegen,
    kategorie_aus_topics,
)

_LOGGER = logging.getLogger(__name__)

#: Die Auswahl des Anbieters im Dialog. Die Marken sind Eigennamen
#: und brauchen keine Uebersetzung; "auto" ist das Wort der Schmiede
#: (erkennen statt waehlen) und wird im Beschreibungstext je Sprache
#: erklaert.
ANBIETER_WAHL = {
    ANBIETER_AUTO: "auto",
    GITLAB: "GitLab",
    FORGEJO: "Forgejo",
    GITEA: "Gitea",
}

#: Die Namen, die der Eintrag tragen darf -- alles andere weist der
#: Dialog zurueck, bevor es zur Schmiede kommt.
ANBIETER_NAMEN = frozenset(ANBIETER_WAHL)


async def verbindung_pruefen(
    hass: HomeAssistant, host: str, token: str | None, anbieter: str = ANBIETER_AUTO
) -> tuple[list, str]:
    """Ein echter Abruf ueber die Instanz -- beweist Host, API und Token.

    Gelingt er, kommen die Antwort (der Dialog meldet ihre Groesse)
    und der Name des Anbieters zurueck, der dieses Tor geformt hat --
    bei "auto" von der Erkennung geklaert, sonst der gewaehlte.
    Gelingt er nicht, wirft der Kern seine Fehlerarten -- und genau
    die werden im Dialog uebersetzt.
    """
    sitzung = async_get_clientsession(hass)
    klient = AiohttpClient(sitzung, token)
    if anbieter == ANBIETER_AUTO:
        anbieter = await erkenne(klient, host)
    forge = schmiede(klient, host, anbieter)
    # Eine Probe, kein Bestandsabruf: hoechstens ein Eintrag, genau
    # eine Seite. Ohne die Grenze holte ein Klick auf "Absenden"
    # gegen eine grosse Instanz im schlimmsten Fall zwanzigtausend
    # Projekte, bevor der Dialog antwortet (Issue #11).
    funde = await forge.suche_nach_topic(grenze=1)
    return funde, anbieter


class HacsLabFluss(config_entries.ConfigFlow, domain=DOMAIN):
    """Einrichten einer Instanz -- GitLab, Forgejo oder Gitea."""

    VERSION = 1

    async def async_step_user(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        fehler: dict[str, str] = {}
        platzhalter: dict[str, str] = {}

        if benutzereingabe is not None:
            host = host_normalisieren(benutzereingabe[CONF_HOST])
            token = (benutzereingabe.get(CONF_TOKEN) or "").strip() or None
            anbieter = str(benutzereingabe.get(CONF_PROVIDER) or ANBIETER_AUTO)
            if anbieter not in ANBIETER_NAMEN:
                fehler["base"] = "anbieter_unbekannt"
            # Die Leerpruefung steht absichtlich VOR dem Verbindungs-
            # versuch: ein leerer Host ist kein Netzfall und darf nie
            # eine Verbindung kosten (Nachschau zu Issue #13).
            elif not host:
                fehler["base"] = "host_leer"
            else:
                try:
                    funde, erkannt = await verbindung_pruefen(
                        self.hass, host, token, anbieter
                    )
                except AnbieterUnbekannt as fehlgeschlag:
                    fehler["base"] = "anbieter_unerkannt"
                    platzhalter["grund"] = str(fehlgeschlag)
                except ForgeFehler as fehlgeschlag:
                    fehler["base"] = (
                        "token_reicht_nicht"
                        if "Token fehlt oder reicht nicht" in str(fehlgeschlag)
                        else "verbindung_fehlgeschlagen"
                    )
                    platzhalter["grund"] = str(fehlgeschlag)
                except Exception as fehlgeschlag:
                    # Breit mit Absicht: ob der DNS-, TLS- oder Timeout-Fall
                    # eintritt, ist fuer den Menschen einer -- die Instanz
                    # ist nicht erreichbar, und mehr steht nicht im Dialog.
                    fehler["base"] = "host_nicht_erreichbar"
                    platzhalter["grund"] = f"{type(fehlgeschlag).__name__}"
                else:
                    await self.async_set_unique_id(host)
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=host,
                        data={
                            CONF_HOST: host,
                            CONF_TOKEN: token or "",
                            CONF_PROVIDER: erkannt,
                        },
                        description="verbunden",
                        description_placeholders={
                            "host": host,
                            "anzahl": str(len(funde)),
                            "anbieter": ANBIETER_WAHL.get(erkannt, erkannt),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(benutzereingabe or {}).get(CONF_HOST, "gitlab.com"),
                ): str,
                vol.Required(
                    CONF_PROVIDER,
                    default=(benutzereingabe or {}).get(CONF_PROVIDER, ANBIETER_AUTO),
                ): vol.In(ANBIETER_WAHL),
                vol.Optional(CONF_TOKEN, description={"hint": "token_hint"}): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=fehler,
            description_placeholders=platzhalter,
        )

    @staticmethod
    def async_get_options_flow(
        eintrag: config_entries.ConfigEntry,
    ) -> HacsLabOptionen:
        return HacsLabOptionen(eintrag)


class HacsLabOptionen(config_entries.OptionsFlow):
    """Abstand des Herzschlags und die Liste der Custom Repositories.

    Ohne Menue kaeme Stufe M3 in einen Konflikt mit M2: beide gehoeren
    in denselben Dialog, aber nur eins darf das erste Formular sein.
    Das Menue entschaerft das -- jede Stufe haengt ihren Punkt an.
    """

    def __init__(self, eintrag: config_entries.ConfigEntry) -> None:
        self._eintrag = eintrag
        self._adresse: tuple[RepositoryIdentity, RepositoryInfo] | None = None

    def _laufzeit(self) -> Any:
        """Die Laufzeit dieses Eintrags -- oder None, wenn nicht bereit."""
        return self.hass.data.get(DOMAIN, {}).get(self._eintrag.entry_id)

    # -- Menue --------------------------------------------------------
    async def async_step_init(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["abstand", "entwickler", "repository", "eintraege"],
        )

    # -- Bahn M2: Abstand ---------------------------------------------
    async def async_step_abstand(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        if benutzereingabe is not None:
            # Die anderen Optionen bleiben stehen -- ein Formular schreibt
            # nur sein eigenes Feld (Flug 2101: sonst loeschte der Abstand
            # den Entwicklermodus).
            return self.async_create_entry(
                title="",
                data={
                    **self._eintrag.options,
                    CONF_ABSTAND_MINUTEN: int(benutzereingabe[CONF_ABSTAND_MINUTEN]),
                },
            )

        aktuell = self._eintrag.options.get(
            CONF_ABSTAND_MINUTEN, STANDARD_ABSTAND_MINUTEN
        )
        return self.async_show_form(
            step_id="abstand",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ABSTAND_MINUTEN, default=aktuell): vol.All(
                        int, vol.Range(min=1)
                    )
                }
            ),
        )

    # -- Flug 2101: Entwicklermodus -----------------------------------
    async def async_step_entwickler(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        """Statt Releases den juengsten Stand des Standardzweigs laden."""
        if benutzereingabe is not None:
            return self.async_create_entry(
                title="",
                data={
                    **self._eintrag.options,
                    CONF_ENTWICKLERMODUS: bool(benutzereingabe[CONF_ENTWICKLERMODUS]),
                },
            )
        aktuell = bool(self._eintrag.options.get(CONF_ENTWICKLERMODUS, False))
        return self.async_show_form(
            step_id="entwickler",
            data_schema=vol.Schema(
                {vol.Required(CONF_ENTWICKLERMODUS, default=aktuell): bool}
            ),
        )

    # -- Bahn M3: Repository hinzufuegen -------------------------------
    async def async_step_repository(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        fehler: dict[str, str] = {}
        platzhalter: dict[str, str] = {}

        if benutzereingabe is not None:
            try:
                host, pfad = adresse_zerlegen(benutzereingabe.get(CONF_ADRESSE, ""))
            except AdresseUngueltig as fehlgeschlag:
                fehler["base"] = "adresse_ungueltig"
                platzhalter["grund"] = str(fehlgeschlag)
            else:
                if host != self._eintrag.data[CONF_HOST]:
                    fehler["base"] = "anderer_host"
                    platzhalter["host"] = host
                    platzhalter["eigener"] = self._eintrag.data[CONF_HOST]
                else:
                    return await self._pruefen_und_weiter(host, pfad)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ADRESSE,
                    default=(benutzereingabe or {}).get(CONF_ADRESSE, ""),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="repository",
            data_schema=schema,
            errors=fehler,
            description_placeholders=platzhalter,
        )

    async def _pruefen_und_weiter(self, host: str, pfad: str) -> FlowResult:
        """Identitaet klaeren (ein einziger API-Abruf) und weiterreichen.

        Der Forge des LAUFENDEN Eintrags ist der richtige: er traegt
        bereits Host und Token. Der Laufweg entspricht identitaet() des
        Forges, nur ohne den zweiten Abruf.
        """
        fehler: dict[str, str] = {}
        platzhalter: dict[str, str] = {}
        laufzeit = self._laufzeit()

        if laufzeit is None:
            fehler["base"] = "nicht_bereit"
        else:
            try:
                info = await laufzeit.forge.repository(pfad)
            except NichtGefunden as fehlgeschlag:
                fehler["base"] = "nicht_gefunden"
                platzhalter["grund"] = str(fehlgeschlag)
            except ForgeFehler as fehlgeschlag:
                fehler["base"] = "verbindung_fehlgeschlagen"
                platzhalter["grund"] = str(fehlgeschlag)
            except Exception as fehlgeschlag:
                fehler["base"] = "host_nicht_erreichbar"
                platzhalter["grund"] = f"{type(fehlgeschlag).__name__}"
            else:
                identitaet = RepositoryIdentity(
                    provider=laufzeit.forge.provider,
                    host=laufzeit.forge.host,
                    provider_id=info.provider_id,
                    full_name=info.full_name,
                )
                if laufzeit.eintraege.vorhanden(identitaet.storage_key):
                    fehler["base"] = "bereits_vorhanden"
                    platzhalter["grund"] = (
                        identitaet.display_full_name + " steht bereits in der Liste"
                    )
                else:
                    self._adresse = (identitaet, info)
                    return await self.async_step_kategorie()

        schema = vol.Schema({vol.Required(CONF_ADRESSE, default=""): str})
        return self.async_show_form(
            step_id="repository",
            data_schema=schema,
            errors=fehler,
            description_placeholders=platzhalter,
        )

    async def async_step_kategorie(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        if self._adresse is None:
            # Ohne geprueftes Repository gibt es hier nichts zu waehlen.
            return await self.async_step_repository()

        identitaet, info = self._adresse
        fehler: dict[str, str] = {}
        platzhalter: dict[str, str] = {
            "name": identitaet.display_full_name,
            "host": identitaet.host,
            "themen": ", ".join(info.topics) or "-",
        }

        if benutzereingabe is not None:
            kategorie = str(benutzereingabe.get(CONF_KATEGORIE) or "")
            laufzeit = self._laufzeit()
            if laufzeit is None:
                fehler["base"] = "nicht_bereit"
            else:
                try:
                    eintrag = await laufzeit.eintraege.hinzufuegen(identitaet, kategorie)
                except BereitsVorhanden as fehlgeschlag:
                    fehler["base"] = "bereits_vorhanden"
                    platzhalter["grund"] = str(fehlgeschlag)
                except KategorieUnbekannt as fehlgeschlag:
                    fehler["base"] = "kategorie_unbekannt"
                    platzhalter["grund"] = str(fehlgeschlag)
                else:
                    _LOGGER.info(
                        "Custom Repository aufgenommen: %s (%s)",
                        eintrag.anzeigename,
                        eintrag.kategorie,
                    )
                    # Die Optionen bleiben, wie sie sind: der Eintrag
                    # lebt in der Ablage, nicht in den Optionen, und
                    # braucht deshalb keinen Neuanfang des Eintrags.
                    return self.async_create_entry(
                        title="", data=dict(self._eintrag.options)
                    )

        vorbelegung = kategorie_aus_topics(info.topics) or "integration"
        schema = vol.Schema(
            {vol.Required(CONF_KATEGORIE, default=vorbelegung): vol.In(KATEGORIEN)}
        )
        return self.async_show_form(
            step_id="kategorie",
            data_schema=schema,
            errors=fehler,
            description_placeholders=platzhalter,
        )

    # -- Bahn M3: Eintraege verwalten -----------------------------------
    async def async_step_eintraege(
        self, benutzereingabe: dict[str, Any] | None = None
    ) -> FlowResult:
        laufzeit = self._laufzeit()
        liste = list(laufzeit.eintraege) if laufzeit is not None else []

        if not liste:
            return self.async_abort(reason="liste_leer")

        fehler: dict[str, str] = {}
        if benutzereingabe is not None:
            schluessel = str(benutzereingabe.get(CONF_ENTFERNEN) or "")
            mit_dateien = bool(benutzereingabe.get(CONF_DATEIEN_DEINSTALLIEREN))
            if laufzeit is None:  # pragma: no cover -- Liste war eben noch da
                fehler["base"] = "nicht_bereit"
            else:
                try:
                    entfernt = await laufzeit.eintraege.entfernen(schluessel)
                except KeyError:
                    fehler["base"] = "nicht_mehr_da"
                else:
                    if mit_dateien:
                        # Ehrlich statt halb: Dateien entfernen kann erst
                        # Stufe M4. Die Entscheidung des Menschen wird
                        # dokumentiert, nicht verschwiegen.
                        _LOGGER.info(
                            "Dateien von %s mitzuentfernen ist Stufe M4",
                            entfernt.anzeigename,
                        )
                    return self.async_create_entry(
                        title="", data=dict(self._eintrag.options)
                    )

        auswahl = {eintrag.storage_key: eintrag.anzeigename for eintrag in liste}
        schema = vol.Schema(
            {
                vol.Required(CONF_ENTFERNEN): vol.In(auswahl),
                vol.Optional(CONF_DATEIEN_DEINSTALLIEREN, default=False): bool,
            }
        )
        platzhalter = {
            "liste": "\n".join(
                f"{eintrag.anzeigename} ({eintrag.kategorie})" for eintrag in liste
            )
        }
        return self.async_show_form(
            step_id="eintraege",
            data_schema=schema,
            errors=fehler,
            description_placeholders=platzhalter,
        )
