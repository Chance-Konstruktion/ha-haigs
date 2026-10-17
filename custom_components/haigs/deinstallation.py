"""Der gemeinsame Weg der Deinstallation -- Panel (M4b) und Dialog (#24).

Der Optionsdialog versprach lange ein Mitnehmen der Dateien und logte
statt dessen «ist Stufe M4» -- die Maschinerie (M4b) stand laengst, nur
der Anschluss fehlte. Seit Befund #19 (Theme/python_script) ist auch
die Vorbedingung geheilt: die Deinstallation nimmt bei flachen
Kategorien NUR verzeichnete, inhaltsgleiche Dateien mit und laesst die
geteilte Wurzel allen. Damit kann der Dialog sein Versprechen halten --
hier steht der Kern, den Panel-Befehl und Optionsdialog teilen.

Die Fehler tragen ihren WebSocket-Fehlercode als :attr:`DeinstallationNichtMoeglich.code`
samt Klartext: der Befehl reicht beides direkt weiter, der Dialog
uebersetzt in ein Formular-Feld mit Grund. Einzige Ausnahme ist
:class:`NichtsInstalliert` -- fuer den Befehl ein Fehler (er kennt nur
Dateien), fuer den Dialog kein Fehler (er entfernt den Eintrag trotzdem,
es gibt ja nichts zu holen).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from .core.forge import ForgeFehler
from .core.zielpfade import ist_flach
from .installation import (
    InstallationsFehler,
    deinstalliere_version,
    rekonstruiere_dateiliste,
)
from .neustart import neustart_hinweis

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .eintraege import Eintrag

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeinstallationErgebnis:
    """Was entfernt wurde -- Version und Weg VOR dem Leeren des Stands."""

    version: str
    pfad: str


class DeinstallationNichtMoeglich(Exception):
    """Klartext, warum die Dateien nicht mitgehen koennen.

    ``code`` ist der Fehlercode, den der Panel-Befehl meldet; die
    Botschaft ist fuer Menschen. Der Dialog zeigt dieselbe Botschaft
    als Grund im Formular.
    """

    code = "deinstallation_fehlgeschlagen"


class NichtsInstalliert(DeinstallationNichtMoeglich):
    """Gar nichts im Stand -- es gibt schlicht keine Dateien.

    Fuer den Panel-Befehl ein Fehler, fuer den Dialog einer, der still
    ueberhört wird: der Eintrag verschwindet trotzdem.
    """

    code = "nichts_installiert"


class KeinWeg(DeinstallationNichtMoeglich):
    """Vor M4b installiert: kein Pfad verzeichnet."""

    code = "kein_weg"


class AltbestandUnlesbar(DeinstallationNichtMoeglich):
    """Die Dateiliste des Altbestands laesst sich nicht rekonstruieren."""

    code = "altbestand_unlesbar"


class AltbestandLeer(DeinstallationNichtMoeglich):
    """Keine inhaltsgleiche Datei -- die Wurzel gehoert allen."""

    code = "altbestand_leer"


async def deinstalliere_eintrag(
    hass: HomeAssistant,
    laufzeit: Any,
    eintrag: Eintrag,
    schluessel: str,
) -> DeinstallationErgebnis:
    """Entfernt die Dateien eines Eintrags -- den verzeichneten Weg.

    Der Eintrag bleibt in der Liste (dafuer gibt es ``entfernen``);
    hier verschwinden nur die Dateien, und der Stand vergisst Version
    und Weg. Ein Bruchstueck ohne Version (Review zu !50, Befund 1) ist
    trotzdem ein ehrlicher Fall zum Aufraeumen und wirft
    :class:`NichtsInstalliert`.

    ``laufzeit`` ist die Instanz aus ``hass.data`` -- sie traegt
    ``staende`` (Stand je Eintrag), ``forge`` (fuer die
    Altbestand-Rekonstruktion) und optional ``lager`` (update-Entities).

    Ein Altbestand aus 0.6.3 (Wurzel verzeichnet, keine Dateiliste) ist
    keine Sackgasse: die Liste wird aus dem Archiv der installierten
    Version rekonstruiert (nur INHALTSGLEICHE Dateien gelten als eigene)
    und VOR dem Entfernen verzeichnet -- schlaegt das Entfernen
    mittendrin ab, laesst es sich wiederholen.
    """
    stand = laufzeit.staende.stand(schluessel)
    if not stand.installiert and not stand.dateien:
        raise NichtsInstalliert("nichts installiert")
    if not stand.pfad:
        raise KeinWeg(
            "kein installierter Pfad verzeichnet (installiert vor M4b?) "
            "-- einmal neu installieren, dann laesst sich auch entfernen"
        )
    dateien = stand.dateien
    if not dateien and ist_flach(eintrag.kategorie):
        # Altbestand aus 0.6.3 -- die Liste fehlt, der Weg fuehrt ueber
        # das Archiv der installierten Version.
        try:
            dateien = await rekonstruiere_dateiliste(
                hass, laufzeit.forge, eintrag, stand.installiert
            )
        except (InstallationsFehler, ForgeFehler) as fehlschlag:
            raise AltbestandUnlesbar(
                "die Dateiliste des Altbestands laesst sich nicht mehr "
                "rekonstruieren ("
                + str(fehlschlag)
                + ") -- einmal neu installieren, dann laesst sich auch "
                "sauber entfernen"
            ) from fehlschlag
        if not dateien:
            raise AltbestandLeer(
                "keine Datei in "
                + stand.pfad
                + " ist mit der installierten Version inhaltsgleich -- "
                "veraenderte oder fremde Dateien bleiben liegen, die "
                "Wurzel gehoert allen"
            )
        # Vor dem Entfernen verzeichnet: ein Abbruch dazwischen ist
        # wiederholbar, kein Neubeginn.
        await laufzeit.staende.setzen(schluessel, dateien=list(dateien))
    try:
        await deinstalliere_version(hass, stand.pfad, dateien=dateien)
    except InstallationsFehler as fehlschlag:
        raise DeinstallationNichtMoeglich(str(fehlschlag)) from fehlschlag
    ergebnis = DeinstallationErgebnis(version=stand.installiert, pfad=stand.pfad)
    await laufzeit.staende.setzen(schluessel, installiert="", pfad="", dateien=[])
    lager = getattr(laufzeit, "lager", None)
    if lager is not None:
        await lager.stand_geaendert(schluessel, installiert="", zielweg="")
    neustart_hinweis(hass, eintrag, stand.installiert, "deinstallation", pfad=stand.pfad)
    return ergebnis
