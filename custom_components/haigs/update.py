"""Update-Entities je Eintrag -- Stufe M5, die sichtbare Seite.

Jedes beobachtete Custom Repository bekommt eine ``update``-Entity:
installierte Version, neueste Version, Release-Notizen, und einen
``install``-Dienst, der den Release-Anhang (sonst das Archiv des Tags)
ueber die Naht an den Zielort tauscht (siehe :mod:`.installation`).
Deinstallation ist bewusst KEIN update-Dienst: Home Assistants update-
Entities kennen kein Uninstall-Konzept -- der Befehl
``haigs/deinstallieren`` (WebSocket, das Panel ruft ihn) nimmt den
verzeichneten Zielweg wieder. Integrationen bekommen danach einen
Neustart-Hinweis aufs Reparatur-Brett (siehe :mod:`.neustart`). Neue
Eintraege erscheinen ohne Neustart als Entity, entfernte verschwinden
-- genau das verlangt die Abnahme: «ein neues Release im GitLab
erscheint ohne Zutun in HA».
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .aktualisierer import HaigsAktualisierer, hole_aktualisierer
from .const import DOMAIN
from .core.aktualisierungen import Fund
from .installation import (
    HalbeInstallation,
    InstallationsFehler,
    installiere_version,
)
from .neustart import neustart_hinweis
from .sichtbarkeit import lies_dialog_flag
from .stand import integrations_domain

if TYPE_CHECKING:
    from . import Laufzeit
    from .eintraege import Eintrag
    from .stand import Staende

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    eintrag: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet die M5-Wabe: Spur holen, Entities anlegen, weiter wachsen."""
    laufzeit: Laufzeit | None = hass.data.get(DOMAIN, {}).get(eintrag.entry_id)
    if laufzeit is None:
        return

    aktualisierer = hole_aktualisierer(hass, eintrag)
    if aktualisierer is None:
        return
    await laufzeit.staende.laden()
    await aktualisierer.async_config_entry_first_refresh()

    entities: dict[str, HaigsUpdateEntity] = {}

    def _anlegen(eintrag_obj: Eintrag) -> None:
        entity = HaigsUpdateEntity(laufzeit, aktualisierer, eintrag_obj)
        entities[eintrag_obj.storage_key] = entity
        async_add_entities([entity])

    for eintrag_obj in laufzeit.eintraege.alle():
        _anlegen(eintrag_obj)

    def _bei_aenderung(art: str, eintrag_obj: Eintrag) -> None:
        if art == "hinzugefuegt":
            _anlegen(eintrag_obj)
            # Frischer Eintrag, frischer Fund: gleich eine Runde ansetzen,
            # statt auf den naechsten Takt zu warten. async_create_task,
            # weil der Beobachter selbst synchron ist.
            hass.async_create_task(aktualisierer.async_request_refresh())
            return
        if art == "nachgezogen":
            # Stufe M8: dasselbe Repository unter neuem Namen -- die Entity
            # bleibt (der Schluessel traegt), sie liest Name und Kategorie
            # je Schreibvorgang frisch aus der Liste.
            entity = entities.get(eintrag_obj.storage_key)
            if entity is not None and entity.hass is not None:
                entity.async_write_ha_state()
            return
        entity = entities.pop(eintrag_obj.storage_key, None)
        if entity is not None and entity.hass is not None:
            hass.async_create_task(entity.async_remove())

    laufzeit.eintraege.melde_aenderungen(_bei_aenderung)


class HaigsUpdateEntity(UpdateEntity):
    """Eine ``update``-Entity je Custom Repository."""

    _attr_should_poll = False

    def __init__(
        self,
        laufzeit: Laufzeit,
        aktualisierer: HaigsAktualisierer,
        eintrag: Eintrag,
    ) -> None:
        self._forge = laufzeit.forge
        self._staende: Staende = laufzeit.staende
        self._eintraege = laufzeit.eintraege
        # Flug 2098: das Lager der Instanz -- die Installation zieht den
        # Stand der Zeile nach (symmetrisch zur Deinstallation), damit die
        # Karte den Zustands-Chip auch OHNE erneuern zeigen kann.
        self._lager = getattr(laufzeit, "lager", None)
        self._eintrag = eintrag
        self._aktualisierer = aktualisierer
        self._attr_unique_id = eintrag.storage_key
        self._attr_supported_features = UpdateEntityFeature.INSTALL
        self._laeuft_gerade = False

    @property
    def _eintrag_aktuell(self) -> Eintrag:
        """Der Eintrag, wie er JETZT in der Liste steht (Stufe M8).

        Ein nachgezogener Name darf nicht auf einen Neustart warten:
        Entities lesen hier frisch, der Schluessel (und damit die
        Entity selbst) bleibt bei einer Umbenennung unberuehrt.
        """
        return self._eintraege.finde(self._eintrag.storage_key) or self._eintrag

    @property
    def name(self) -> str:
        return self._eintrag_aktuell.anzeigename

    @property
    def title(self) -> str:
        return self._eintrag_aktuell.anzeigename

    @property
    def entity_picture(self) -> str | None:
        """Das Zeichen des Repositorys, nicht das von HAIGS (Flug 2101).

        Home Assistant malt eine update-Entity sonst mit dem Icon ihrer
        Plattform -- und das ist haigs, fuer jedes Repository gleich.
        Eine installierte Integration hat ihre eigene Domain im Zielweg
        (``custom_components/<domain>``); ueber denselben Marken-Proxy,
        den HA fuer seine eigenen update-Entities nutzt
        (``/api/brands/integration/<domain>/icon.png``), kommt ihr Icon
        aus dem ``brand/``-Ordner.
        Alles andere zeigt das Projektbild der Schmiede, sonst HA-Standard.
        """
        domain = integrations_domain(self._staende.stand(self._eintrag.storage_key).pfad)
        if domain:
            return f"/api/brands/integration/{domain}/icon.png"
        if self._lager is not None:
            for zeile in self._lager.zeilen:
                if zeile.get("storage_key") == self._eintrag.storage_key:
                    bild = str(zeile.get("avatar_url") or "")
                    if bild:
                        return bild
                    break
        return super().entity_picture

    @property
    def in_progress(self) -> bool:
        """Eigene Fassung statt ``_attr_``: steuerbar waehrend des Laufs."""
        return self._laeuft_gerade

    async def async_added_to_hass(self) -> None:
        """Auf den Takt horchen -- und auf den eigenen Stand (M4b).

        Der Takt bringt neue Funds; der Stand aendert sich auch ohne
        Takt (Deinstallation ueber den Befehl, Vorab-Schalter). Ohne
        das Abonnement stunde die installierte Version in der Entity,
        bis der naechste Herzschlag kaeme.
        """
        self.async_on_remove(self._aktualisierer.async_add_listener(self._schreibe))
        self.async_on_remove(self._staende.beobachte(self._schreibe))

    def _schreibe(self) -> None:
        if self.hass is not None:
            self.async_write_ha_state()

    @property
    def _fund(self) -> Fund | None:
        daten: dict[str, Fund] | None = self._aktualisierer.data
        if daten is None:
            return None
        return daten.get(self._eintrag.storage_key)

    @property
    def available(self) -> bool:
        # Stufe M8: ein Instanz-Ausfall macht die Entity unehrlich-verfuegbar,
        # aber der letzte Fund bleibt im Koordinator -- alte Daten werden
        # behalten, nicht geloescht, und kommen zurueck, sobald es wieder geht.
        if not self._aktualisierer.last_update_success:
            return False
        fund = self._fund
        return fund is None or fund.fehler is None

    @property
    def installed_version(self) -> str | None:
        installiert = self._staende.stand(self._eintrag.storage_key).installiert
        return installiert or None

    @property
    def latest_version(self) -> str | None:
        fund = self._fund
        if fund is None or fund.fehler is not None:
            return None
        return fund.neueste or None

    @property
    def release_summary(self) -> str | None:
        fund = self._fund
        if fund is None or fund.fehler is not None or not fund.notizen:
            return None
        return fund.notizen

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        fund = self._fund
        if fund is None:
            return {}
        return {
            "quelle": fund.quelle,
            "tag": fund.tag,
            "veroeffentlicht_am": fund.veroeffentlicht_am,
            "kategorie": self._eintrag_aktuell.kategorie,
            "vorabversionen": self._staende.stand(
                self._eintrag.storage_key
            ).vorabversionen,
            "fehler": fund.fehler or "",
        }

    async def async_install(
        self, version: str | None = None, backup: bool = False
    ) -> None:
        """Installiert die neueste Version: Anhang zuerst, sonst Tag-Archiv.

        Eine bestimmte aeltere Version zu waehlen ist bewusst noch nicht
        dabei: der Lauf traegt nur die neueste je Eintrag. Das Feld
        ``version`` wird geprueft und abgewiesen, wenn es nicht die
        neueste ist -- lieber ehrlich meckern als heimlich das Falsche
        installieren.

        Stufe M4b: der Zielweg wird mit der Version zusammen verzeichnet
        (ohne Weg keine ehrliche Deinstallation), und bei Integrationen
        landet ein Neustart-Hinweis auf dem Reparatur-Brett.

        Flug 2098: der Hinweis nennt auch den zweiten Schritt -- «Geräte
        & Dienste» oder configuration.yaml, je nachdem, ob die gerade
        installierte manifest.json einen Einrichtungsdialog verspricht.
        Der Flag kommt aus dem Ordner am Ziel, nicht aus dem Archiv:
        was dort liegt, ist die Wahrheit, die Home Assistant lesen wird.
        """
        fund = self._fund
        if fund is None or fund.fehler is not None or not fund.tag:
            raise HomeAssistantError(
                "kein Stand zum Installieren -- der letzte Lauf schlug fehl"
            )
        if version is not None and version != fund.neueste:
            raise HomeAssistantError(
                f"nur die neueste Version ({fund.neueste}) ist installierbar"
            )
        self._laeuft_gerade = True
        self._schreibe()
        # Befund #19: flache Kategorien verzeichnen ihre Dateiliste --
        # der fruehere Stand entscheidet, was ein Update ersetzen darf.
        stand_alt = self._staende.stand(self._eintrag.storage_key)
        try:
            ergebnis = await installiere_version(
                self.hass,
                self._forge,
                self._eintrag_aktuell,
                fund.tag,
                fruehere_dateien=stand_alt.dateien,
            )
        except InstallationsFehler as fehlschlag:
            # Review zu !50, Befund 1: ein Bruchstueck wird verzeichnet,
            # BEVOR der Fehler hochgeht -- der zweite Versuch (und die
            # Deinstallation) scheitern nicht mehr an den eigenen Resten.
            # Die Version bleibt, wie sie ist: der Stand luegt nicht
            # ueber eine Version, die nie ganz ankam.
            if isinstance(fehlschlag, HalbeInstallation):
                await self._staende.setzen(
                    self._eintrag.storage_key,
                    pfad=str(fehlschlag.pfad),
                    dateien=sorted(set(stand_alt.dateien) | set(fehlschlag.dateien)),
                )
            raise HomeAssistantError(str(fehlschlag)) from fehlschlag
        finally:
            self._laeuft_gerade = False
        pfad = str(ergebnis.pfad)
        await self._staende.setzen(
            self._eintrag.storage_key,
            installiert=fund.neueste,
            pfad=pfad,
            dateien=list(ergebnis.dateien),
        )
        # Flug 2098: das Lager zieht nach -- Version UND Zielweg. Ohne
        # diesen Griff bliebe die Zeile "nichts installiert", bis der
        # naechste Lauf sie neu baute; die Karte (und ihr Zustands-Chip)
        # waere eine Erinnerung statt einer Wahrheit.
        if self._lager is not None:
            await self._lager.stand_geaendert(
                self._eintrag.storage_key,
                installiert=fund.neueste,
                zielweg=pfad,
            )
        self._schreibe()
        mit_dialog = (
            await lies_dialog_flag(self.hass, pfad)
            if self._eintrag_aktuell.kategorie == "integration"
            else None
        )
        neustart_hinweis(
            self.hass,
            self._eintrag_aktuell,
            fund.neueste,
            "installation",
            mit_dialog=mit_dialog,
            pfad=pfad,
        )
        _LOGGER.info(
            "%s auf %s installiert",
            self._eintrag_aktuell.anzeigename,
            fund.neueste,
        )
