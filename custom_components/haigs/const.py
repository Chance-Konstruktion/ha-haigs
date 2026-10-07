"""Konstanten der Home-Assistant-Schicht von HAIGS."""

from __future__ import annotations

#: Domain der Integration -- Home Assistant verlangt sie hier, das
#: Manifest nennt denselben Wert.
DOMAIN = "haigs"

#: Einstellfelder des Einrichtungsdialogs.
CONF_HOST = "host"
CONF_TOKEN = "token"
CONF_PROVIDER = "provider"

#: Der Wert "auto" im Dialog: die Schmiede soll erkennen, welcher
#: Anbieter unter der Adresse antwortet (Flug 2088). Die anderen
#: Werte sind die Namen aus ``core.identity`` -- hier steht nur das
#: eine Wort, das kein Anbieter ist.
ANBIETER_AUTO = "auto"

#: Option im Optionsfluss: die offiziellen HACS-Repositories als eigene
#: Quelle anzeigen (Katalog-Eintrag anlegen oder entfernen). Der Wert
#: lebt nicht in den Optionen, sondern darin, ob der Eintrag existiert.
CONF_KATALOG = "katalog_anzeigen"

#: Option des Herzschlags: Abstand in Minuten (ROADMAP M2:
#: "DataUpdateCoordinator mit einstellbarem Abstand").
CONF_ABSTAND_MINUTEN = "abstand_minuten"

#: Option des Entwicklermodus (Flug 2101): statt Releases installiert
#: HAIGS den juengsten Stand des Standardzweigs -- fuer alle
#: Repositories dieser Instanz. Aus ist die Voreinstellung.
CONF_ENTWICKLERMODUS = "entwicklermodus"

#: Standardabstand des Herzschlags -- ein halber Tag. GitLab bemerkt
#: das nicht, Menschen bekommen Updates am gleichen Tag noch mit.
STANDARD_ABSTAND_MINUTEN = 720

#: Version der Ablage (homeassistant.helpers.storage). Die 1 ist
#: ernst gemeint: jede Form-Aenderung bekommt eine Migration und erst
#: dann eine neue Zahl (siehe ablage.py).
ABLAGE_VERSION = 1

#: Version des Lagers (Flug 2084) -- der Zwischenspeicher des Ladens.
#: Dieselbe Ernsthaftigkeit wie bei der Ablage: die Form ist neu, die
#: 1 ist ihr Anfang; jede kuenftige Umdeutung bekommt eine Migration.
LAGER_VERSION = 1

#: Das Ereignis, das der Laden feuert, sobald das Lager frisch liegt.
#: Das Panel hoert darauf und malt neu, ohne dass jemand einen Knopf
#: drueckt -- offen bleiben und zuschauen genuegt.
EREIGNIS_AKTUALISIERT = DOMAIN + "_aktualisiert"

#: Wie lange nach dem Start der erste Hintergrund-Lauf des Lagers
#: kommt (Sekunden). Der Laden soll nach dem Neustart nicht leer
#: aufgehen; 45 Sekunden geben Home Assistant Zeit, zuerst alles
#: andere anzustellen, bevor die Instanz durchsucht wird.
LAGER_START_VERZOEGERUNG_SEK = 45


def host_normalisieren(host: str) -> str:
    """Bringt jede Menscheneingabe auf die Form ``gitlab.example.net``.

    Nebeneffekt mit Absicht: Wer den Link eines Projekts einfuegt
    (``https://GitLab.Example.Net/gruppe/projekt``), bekommt daraus den
    Host -- das Projekt selbst ist Stufe M3. Kleinschreibung, weil es
    fuer Hosts egal ist, fuer Speicherschluessel aber nicht.
    """
    gereinigt = host.strip()
    for praefix in ("https://", "http://"):
        if gereinigt.startswith(praefix):
            gereinigt = gereinigt[len(praefix) :]
            break
    return gereinigt.split("/", 1)[0].lower()


def ablage_schluessel(host: str) -> str:
    """Speicherschlüssel der Ablage für eine Instanz.

    Der Host steckt drin, damit mehrere Instanzen nebeneinander
    existieren (gitlab.com und die eigene) ohne sich zu verdraengen --
    dieselbe Unterscheidung wie im storage_key des Kerns.
    """
    return DOMAIN + "." + host.replace(".", "_").replace(":", "_")


def lager_schluessel(host: str) -> str:
    """Speicherschluessel des Lagers fuer eine Instanz (Flug 2084).

    Das Lager ist der Zwischenspeicher des Ladens: die Zeilen der
    Liste und die Funde des letzten Scans, damit der Laden nie leer
    aufgeht -- nicht beim Betreten, nicht nach dem Neustart. Es liegt
    in einer eigenen Datei neben der Ablage, weil es abgeleitetes
    Wissen ist: alles darin laesst sich aus Instanz und Ablage
    wiederherstellen, die Ablage bleibt die Wahrheit.
    """
    return DOMAIN + ".lager." + host.replace(".", "_").replace(":", "_")
