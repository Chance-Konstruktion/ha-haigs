"""Der Zustand einer installierten Integration -- reine Entscheidung.

Flug 2098. Der Befund des Imkers: ueber HAIGS hinzugefuegte Repos
sind unter «Geräte & Dienste» nicht zu finden. Die Physik dahinter
gehoert Home Assistant selbst, und sie hat drei Schichten:

* ``custom_components`` scannt Home Assistant beim Start (und beim
  ersten Griff danach, gecacht fuer den Lauf) -- Dateien, die danach
  erscheinen, sieht der Einrichtungsdialog nicht, bis der Start
  geschieht. Der Neustart-Hinweis auf dem Reparatur-Brett sagte das
  schon seit Stufe M4b, aber versteckt.
* Der Einrichtungsdialog listet Integrationen ueber die gescannten
  Manifeste -- nur solche mit ``config_flow: true``. Die Karte unter
  «Geräte & Dienste» entsteht aber erst durch den KONFIGURATIONSEIN-
  TRAG, den die Bedienung nach dem Hinzufuegen anlegt. Kein Wort im
  Laden sagte das bislang.
* Integrationen OHNE Einrichtungsdialog koennen dort UEBERHAUPT nicht
  auftauchen -- sie leben von der configuration.yaml. Das ist kein
  Fehler der Integration, aber ohne Hinweis sieht es fuer die Bedienung
  so aus.

Diese Datei entscheidet nur, WELCHER Zustand gilt -- als reine
Funktion auf plainen Werten, damit die Kern-Suite sie ohne Home
Assistant pruefen kann. Die Werte selbst (Neustart noch ausstehend?
eingerichtet? Dialog vorhanden?) liest die HA-Schicht in
:mod:`custom_components.haigs.sichtbarkeit` und haengt sie als
``integration``-Block an jede Zeile der Liste.

Die Zustaende -- Rueckgabe ``None`` heisst: kein Chip, die Zeile ist
keine installierte Integration:

* ``"neustart"`` -- installiert, aber der Start fehlt noch: solange
  der fehlt, ist jede spaetere Frage Spekulation.
* ``"eingerichtet"`` -- es gibt einen Konfigurationseintrag ODER die
  Integration lief hoch (configuration.yaml): die Karte lebt, oder die
  Integration arbeitet -- kein Rat noetig.
* ``"hinzufuegen"`` -- Dialog vorhanden (``config_flow: true`` im
  installierten Manifest), noch kein Eintrag: jetzt «Integration
  hinzufügen» waehlen -- der Chip ist der Knopf dorthin.
* ``"yaml"`` -- OHNE Dialog: diese Integration richtet sich ueber die
  configuration.yaml ein und KANN nie unter «Geräte & Dienste»
  erscheinen.
* ``"nicht_geladen"`` -- das installierte Manifest ist unlesbar oder
  weg: dem System fehlt die Integration, das Protokoll sagt warum.
* ``"ungewiss"`` -- installiert, aber ohne verzeichneten Weg (vor
  Stufe M4b): erst neu installieren, dann weiss auch das wieder.
"""

from __future__ import annotations

#: Die bekannten Zustaende -- die Oberflaeche rendert sie, alles andere
#: ist ein Fehler im Draht und bleibt ohne Chip.
ZUSTAENDE = frozenset(
    {"neustart", "eingerichtet", "hinzufuegen", "yaml", "nicht_geladen", "ungewiss"}
)


def integrations_zustand(
    *,
    installiert: str,
    zielweg: str,
    neustart_offen: bool,
    eingerichtet: bool,
    mit_dialog: bool | None,
) -> str | None:
    """Der Zustand einer installierten Integration, sonst ``None``.

    Die Reihenfolge ist die Rangfolge der Wahrheit: nichts installiert
    heisst keine Aussage (``None``); der fehlende Start uebertont
    alles, denn solange er fehlt, ist jede spaetere Frage Spekulation;
    ein Eintrag (oder ein gelaufener Start) braucht keinen Rat mehr;
    und zuletzt entscheidet der Dialog -- ``mit_dialog`` ``None``
    heisst unlesbar und damit «nicht geladen», ``True`` nennt den Weg
    ueber «Integration hinzufügen», ``False`` den ueber die
    configuration.yaml.
    """
    if not installiert:
        return None
    if not zielweg:
        return "ungewiss"
    if neustart_offen:
        return "neustart"
    if eingerichtet:
        return "eingerichtet"
    if mit_dialog is None:
        return "nicht_geladen"
    return "hinzufuegen" if mit_dialog else "yaml"
