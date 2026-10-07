"""Der Neustart-Hinweis fuer Integrationen (Stufe M4b, Flug 2098).

Home Assistant laedt ``custom_components`` beim Start -- Dateien, die
danach erscheinen oder verschwinden, aendern am laufenden nichts.
Darum steht nach jeder Installation oder Deinstallation einer
Integration ein Hinweis auf dem Reparatur-Brett; er verschwindet, sobald
der Neustart passiert ist (das Laden der Komponente raeumt jeden
Neustart-Hinweis ab, siehe ``__init__.py``).

Flug 2098 haengt zwei Stuecke dazu, weil der Imker-Befund lautete:
installierte Repos sind unter «Geräte & Dienste» nicht zu finden.

* **Die dauerhafte Benachrichtigung.** Das Reparatur-Brett ist ehrlich,
  aber man muss es besuchen. Die Benachrichtigung ( Glocke im Kopf der
  Oberflaeche) erreicht die Bedienung ueberall -- dasselbe Mittel,
  dessen sich HACS fuer seinen Neustart-Hinweis bedient. Sie nennt
  nicht nur den Neustart, sondern auch den ZWEITEN Schritt, den kein
  Dialog der Welt abnimmt: nach dem Start die Integration unter
  «Geräte & Dienste» hinzufuegen -- oder, ohne Einrichtungsdialog,
  ueber die configuration.yaml einrichten. Welcher von beiden, sagt
  die manifest.json des gerade installierten Ordners (``mit_dialog``).
* **Das Register als Flagge.** Der Hinweis im Issue-Register ist
  zugleich das Gedraechtnis «Start noch nicht geschehen» -- die
  Sichtbarkeit (:mod:`sichtbarkeit`) liest ihn fuer den Zustands-Chip
  der Karte. Installation setzt ihn, der naechste Start loest ihn auf.

Andere Kategorien (Themes, Plugins, Skripte) brauchen keinen Neustart
-- dort bleibt das Brett still und die Glocke stumm. Das ist Physik,
nicht Nachlaessigkeit.

Ein eigenes Modul, weil zwei Stellen ihn rufen (update-Entities und der
WebSocket-Befehl zum Deinstallieren) und die HA-Schicht des Pakets
selbst ihn beim Aufraeumen nicht importieren darf -- ein Import aus
``__init__`` waere ein Kreis.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.persistent_notification import (
    async_create as dauerhafte_meldung,
)
from homeassistant.helpers import issue_registry
from homeassistant.helpers.issue_registry import IssueSeverity

from .aktualisierer import _kennung
from .const import DOMAIN
from .stand import integrations_domain

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .eintraege import Eintrag


def neustart_hinweis(
    hass: HomeAssistant,
    eintrag: Eintrag,
    version: str,
    aktion: str,
    mit_dialog: bool | None = None,
    pfad: str = "",
) -> None:
    """Stellt den Hinweis fuer eine Integration auf alle zwei Bretaer.

    ``aktion`` ist fuer Menschen ``"installation"`` oder
    ``"deinstallation"`` -- die Uebersetzung baelt daraus den Satz.
    ``mit_dialog`` sagt (bei der Installation), ob die Integration
    ueberhaupt einen Einrichtungsdialog hat: dann nennt die
    Benachrichtigung den Weg ueber «Geräte & Dienste», sonst den ueber
    die configuration.yaml. ``None`` heisst unbekannt -- dann bleibt es
    beim Neustart-Satz ohne zweiten Schritt.
    """
    if eintrag.kategorie != "integration":
        return
    issue_registry.async_create_issue(
        hass,
        DOMAIN,
        "neustart_" + _kennung(eintrag.storage_key),
        is_fixable=False,
        issue_domain=integrations_domain(pfad),
        severity=IssueSeverity.WARNING,
        translation_key="neustart_nach_installation",
        translation_placeholders={
            "name": eintrag.anzeigename,
            "version": version,
            "aktion": aktion,
        },
    )
    _benachrichtige(hass, eintrag, version, aktion, mit_dialog)


def _benachrichtige(
    hass: HomeAssistant,
    eintrag: Eintrag,
    version: str,
    aktion: str,
    mit_dialog: bool | None,
) -> None:
    """Die dauerhafte Meldung -- Glocke statt Brett (Flug 2098)."""
    name = eintrag.anzeigename
    deutsch = str(hass.config.language or "").lower().startswith("de")
    if aktion == "installation":
        titel = (
            f"{name} {version} installiert" if deutsch else f"{name} {version} installed"
        )
        if deutsch:
            kern = (
                "Home Assistant lädt die Integration erst beim nächsten "
                "Start — jetzt neu starten."
            )
            if mit_dialog is True:
                fortsetzung = (
                    "Nach dem Neustart unter **Einstellungen → Geräte & Dienste** "
                    "über **Integration hinzufügen** einrichten."
                )
            elif mit_dialog is False:
                fortsetzung = (
                    "Diese Integration hat keinen Einrichtungsdialog — sie wird "
                    "über die configuration.yaml eingerichtet und erscheint "
                    "nicht unter «Geräte & Dienste»."
                )
            else:
                fortsetzung = "Nach dem Neustart ist die Integration bereit."
        else:
            kern = (
                "Home Assistant loads integrations on startup only — "
                "restart now to load it."
            )
            if mit_dialog is True:
                fortsetzung = (
                    "After the restart, set it up via **Settings → Devices & "
                    "services → Add integration**."
                )
            elif mit_dialog is False:
                fortsetzung = (
                    "This integration has no setup dialog — it is configured "
                    "via configuration.yaml and does not show up under "
                    "“Devices & services”."
                )
            else:
                fortsetzung = "The integration is ready after the restart."
    else:
        titel = (
            f"{name} {version} deinstalliert"
            if deutsch
            else f"{name} {version} uninstalled"
        )
        kern = (
            "Home Assistant behält die Integration bis zum nächsten "
            "Start — jetzt neu starten."
            if deutsch
            else "Home Assistant keeps the integration until the next "
            "restart — restart now."
        )
        fortsetzung = ""
    nachricht = kern + (("\n\n" + fortsetzung) if fortsetzung else "")
    dauerhafte_meldung(
        hass,
        nachricht,
        title=titel,
        notification_id="haigs_neustart_" + _kennung(eintrag.storage_key),
    )
