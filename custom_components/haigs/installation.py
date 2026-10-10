"""Installationsnaht: Release-Anhang oder Tag-Archiv an den Zielort tauschen.

Stufe M4b rundet die Naht ab, die M5 fuer den ``install``-Dienst
gezogen hat. Vier Dinge kommen dazu:

* **Quelle:** der Anhang des Releases, wenn der Besitzer dem Tag ein
  ZIP beigelegt hat (gebaut, nicht gepackt-vom-Quellstand), sonst das
  Archiv des Tags. Die Auswahl ist streng: genau EIN Zip-Anhang wird
  genommen, null oder mehrere bedeuten Rueckfall aufs Tag-Archiv --
  Raterei beim Installieren hilft niemandem.
* **Tiefe:** seit Befund #15 (Entschluss b) erkennt die Naht die
  Lagerform ``custom_components/<domain>/`` in jeder Tiefe des
  Archivs. Tag-Quell-Archive der ueblichen HACS-Repo-Struktur
  installieren damit ohne gebauten Anhang, und Anhaenge, die den
  ``custom_components``-Praefix behalten (wie der von haigs
  selbst), ebenso.
* **Protokoll:** die Installation vermerkt den Zielweg in der Ablage
  (``stand.pfad``). Ohne Weg keine ehrliche Deinstallation -- und mit
  ihm ist die Rueckwaerts-Frage eine Ja/Nein-Pruefung, kein Globbing.
* **Deinstallation:** was der Tausch hingelegt hat, geht in einem Zug
  weg -- erst wegbenennen, dann entfernen. Ein Abbruch dazwischen
  hinterlaesst kein halbes Verzeichnis im Ziel.

Metadaten (manifest.json, hacs.json) werden hier nur GELESEN, nie
entpackt -- das Schreiben bleibt allein beim geprueften Weg des Kerns.
"""

from __future__ import annotations

import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING

from .core import entpacken, zielpfade
from .core.forge import Release
from .core.validierung import pruefe_manifest

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .core.forge import Forge
    from .eintraege import Eintrag

#: Zwischenlager unter der Konfiguration -- dasselbe Dateisystem wie das
#: Ziel, das verlangt der atomare Tausch aus M4a.
ZWISCHENLAGER_NAME = ".haigs_zwischenlager"

#: Der Name der Integrations-Beschreibung im Archiv.
_MANIFEST = "manifest.json"

#: Der Name der HACS-Beschreibung im Archiv.
_HACS_JSON = "hacs.json"


@dataclass(frozen=True)
class InstallationsErgebnis:
    """Weg und Dateiliste einer gelandeten Installation.

    ``pfad`` (relativ zur Konfiguration) ist das Protokoll fuer die
    Deinstallation seit M4b. ``dateien`` (Befund #19) kommt bei flachen
    Kategorien dazu: ``themes`` und ``python_scripts`` gehoeren allen
    Installationen gemeinsam, die Deinstallation nimmt nur genau diese
    Dateien wieder mit -- Ordner-Kategorien tragen die leere Liste.
    """

    pfad: PurePosixPath
    dateien: tuple[str, ...] = ()


class InstallationsFehler(Exception):
    """Die Installation ist gescheitert -- der Text ist für Menschen."""


class HalbeInstallation(InstallationsFehler):
    """Die flache Installation brach mittendrin ab (Review zu !50).

    ``pfad`` (relativ zur Konfiguration) und ``dateien`` nennen, was
    von dieser Installation schon auf der Platte liegt -- zusammen mit
    der frueheren verzeichneten Liste, denn die beiden Mengen gehoeren
    jetzt dem Eintrag. Der Aufrufer protokolliert beides, BEVOR er den
    Fehler weiterreicht: so scheitert der zweite Versuch nicht an den
    eigenen Resten, und die Deinstallation findet auch ein Bruchstueck
    ehrlich weg. Ohne das Protokoll wäre ein Abbruch eine Sackgasse
    (Kollision beim ersten Versuch, keine Liste beim zweiten).

    Die Ausnahme entsteht nur auf dem flachen Weg -- der Ordnerweg
    tauscht in einem Zug und kennt keine halben Zustaende.
    """

    def __init__(self, text: str, pfad: PurePosixPath, dateien: tuple[str, ...]) -> None:
        super().__init__(text)
        self.pfad = pfad
        self.dateien = tuple(dateien)


# ----------------------------------------------------------- Quelle


def waehle_anhang(anhaenge: dict[str, str]) -> str | None:
    """Die Adresse des einzigen ZIP-Anhangs, sonst ``None``.

    Ein Anhang zaehlt, wenn sein Name auf ``.zip`` endet (Gross-/
    Kleinschreibung egal) und eine Adresse dabeisteht. Gibt es genau
    einen, liefert er die Installation; gibt es keinen, greift der
    Rueckfall aufs Tag-Archiv; gibt es mehrere, ebenfalls -- zwischen
    zwei Zips zu wuerfeln ist Raterei, und genau die ruiniert
    Installationen. Andere Dateien (Signaturen, Pruefsummen, Tarbaelle)
    bleiben unberuehrt: sie sind Zusatz, nicht Konkurrenz.
    """
    treffer = [
        adresse
        for name, adresse in (anhaenge or {}).items()
        if name.lower().endswith(".zip") and adresse
    ]
    if len(treffer) == 1:
        return treffer[0]
    return None


async def beschaffe_archiv(forge: Forge, pfad: str, tag: str) -> tuple[bytes, str]:
    """Das Archiv zur Version -- Anhang zuerst, Tag-Archiv sonst.

    Zurueck kommen die Bytes und die Herkunft (``"anhang"`` oder
    ``"archiv"``) -- die Herkunft wandert ins Protokoll, weil sie beim
    Rueckwaertsdebuggen den Unterschied erklaert zwischen dem, was der
    Besitzer gebaut hat, und dem, was der Anbieter aus dem Quellstand
    gepackt hat.
    """
    try:
        releases: list[Release] = await forge.releases(pfad)
    except Exception:  # Anhang ist Bevorzugung, keine Pflicht
        releases = []
    for release in releases:
        if release.tag != tag:
            continue
        adresse = waehle_anhang(release.anhaenge)
        if adresse:
            return await forge.anhang(adresse), "anhang"
        break  # der passende Release ohne Anhang -- weiter macht kein Sinn
    return await forge.archiv(pfad, tag), "archiv"


# ------------------------------------------------- Ziel und Tausch


def lese_archiv_datei(archiv: bytes, name: str) -> bytes | None:
    """Liest eine Datei aus dem Archiv, ohne etwas zu entpacken.

    GitLab-Tag-Archive packen alles unter einen Ordner
    (``projekt-v1.2.0/...``), Release-Anhaenge stehen je nach Bauart in
    der Wurzel oder ebenfalls unter einem Ordner. Gesucht wird der
    Name in jeder Tiefe, gewaehlt in zwei Stufen (Befund #15): genau
    EIN flacher Treffer -- Wurzel oder ein Ordner -- gewinnt, auch
    wenn daneben tiefe Treffer liegen (die hacs.json an der
    Repo-Wurzel zaehlt mehr als eine, die zufaellig tief steckt). Gibt
    es keinen flachen Treffer, zaehlt genau EIN tiefer -- so liegt die
    manifest.json der ueblichen HACS-Struktur unter
    ``<projekt>/custom_components/<domain>/``. Mehrdeutigkeit ist in
    beiden Stufen ein Fehlschlag: Raterei beim Installieren hilft
    niemandem.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(archiv)) as zip_datei:
            treffer = [
                info.filename
                for info in zip_datei.infolist()
                if not info.is_dir() and (info.filename or "").split("/")[-1] == name
            ]
            flach = [t for t in treffer if len(t.split("/")) <= 2]
            if len(flach) == 1:
                return zip_datei.read(flach[0])
            if not flach and len(treffer) == 1:
                return zip_datei.read(treffer[0])
    except zipfile.BadZipFile as fehlschlag:
        raise InstallationsFehler(
            "das Archiv ist kein ZIP -- ein Release-Anhang, der kein ZIP "
            "ist, wird nicht installiert (Befund M4b)"
        ) from fehlschlag
    return None


def _manifest_ordner(archiv: bytes) -> list[tuple[str, bytes]]:
    """Alle ``manifest.json`` im Archiv: ihr Ordner und ihr roher Inhalt.

    Jede Tiefe -- hier entscheidet nicht die Tiefe, sondern Ordner und
    Inhalt gemeinsam (siehe :func:`finde_lagerform`). Die Wurzel zaehlt
    als Ordner ``""`` mit: ``content_in_root``-Repos haben ihre
    manifest.json dort, sind aber keine Lagerform.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(archiv)) as zip_datei:
            fund: list[tuple[str, bytes]] = []
            for info in zip_datei.infolist():
                if info.is_dir() or (info.filename or "").split("/")[-1] != _MANIFEST:
                    continue
                ordner = (info.filename or "").rsplit("/", 1)[0]
                fund.append((ordner, zip_datei.read(info.filename)))
            return fund
    except zipfile.BadZipFile as fehlschlag:
        raise InstallationsFehler(
            "das Archiv ist kein ZIP -- ein Release-Anhang, der kein ZIP "
            "ist, wird nicht installiert (Befund M4b)"
        ) from fehlschlag


def finde_lagerform(archiv: bytes, domain: str) -> str | None:
    """Der Archiv-Ordner, dessen Inhalt nach ``custom_components/<domain>/`` gehoert.

    Befund #15, Entschluss b: Tag-Quell-Archive tragen die uebliche
    HACS-Repo-Struktur ``<projekt>/custom_components/<domain>/``, und
    auch gebaute Anhaenge behalten den ``custom_components``-Praefix
    manchmal (der von haigs selbst tut es). Gesucht wird der Ordner
    ueber zwei Zeichen, die zusammen nur die echte Lagerform tragen:
    er HEISST wie die Domain, und die manifest.json IN ihm NENNT
    dieselbe. Der Ordner allein genuegt nicht -- Repokopien heissen
    manchmal wie die Domain --, das Manifest allein auch nicht -- es
    kann irgendwo als Vorlage liegen.

    Genau ein Treffer liefert seinen Pfad als Praefix, das beim
    Entpacken wegfaellt. Kein Treffer liefert ``None`` -- der Aufrufer
    bleibt bei der hergebrachten Ableitung ueber den gemeinsamen
    Oberordner. Mehrere Treffer sind Raterei und werden abgewiesen.
    Und kuendigt das Archiv unter ``custom_components/`` eine
    Integration an, die nicht zur gesuchten Domain passt, gibt es
    Klartext statt stiller Fehlinstallation -- Home Assistant laedt
    keine Integration aus einem Ordner, der nicht zur Domain gehoert.
    """
    treffer: list[str] = []
    angekuendigt: set[str] = set()
    for ordner, roh in _manifest_ordner(archiv):
        befund = pruefe_manifest(roh)
        genannt = str(json.loads(roh).get("domain") or "") if befund else ""
        name = ordner.split("/")[-1]
        if genannt == domain and name == domain:
            treffer.append(ordner)
            continue
        if "custom_components" in ordner.split("/"):
            angekuendigt.add(name or "?")
    if len(treffer) > 1:
        raise InstallationsFehler(
            f"die Integration {domain!r} liegt mehrfach im Archiv: "
            + ", ".join(sorted(treffer))
        )
    if treffer:
        return treffer[0]
    if angekuendigt:
        raise InstallationsFehler(
            "im Archiv kuendigt custom_components/"
            + ", ".join(sorted(angekuendigt))
            + "/ eine Integration an, die nicht zur Domain "
            + f"{domain!r} passt -- Ordnername und manifest.json muessen "
            "dasselbe sagen"
        )
    return None


def _manifest_in_wurzel(namen: list[str]) -> bool:
    """Liegt eine manifest.json direkt in der Archiv-Wurzel?

    Flache Anhaenge: manche Besitzer zippen den Inhalt von
    ``custom_components/<domain>/`` ohne jeden Ordner -- HACS nimmt
    das an, weil die Integration keine Ordnerhuelle braucht, um sich
    zu erkennen. Die Domain sagt ohnehin die manifest.json, und der
    Zielname ist laengst aus ihr gelesen.
    """
    return any(n == _MANIFEST for n in namen)


def _domain_aus_manifest(archiv: bytes) -> str:
    roh = lese_archiv_datei(archiv, _MANIFEST)
    if roh is None:
        raise InstallationsFehler(
            "die manifest.json fehlt im Archiv oder liegt mehrfach -- ohne "
            "sie kennt Home Assistant keine Integration"
        )
    befund = pruefe_manifest(roh)
    if not befund:
        raise InstallationsFehler("manifest.json untauglich: " + "; ".join(befund.fehler))
    domain = str(json.loads(roh).get("domain") or "")
    if not domain:
        raise InstallationsFehler("manifest.json nennt keine Domain")
    return domain


def _zielname(eintrag: Eintrag, archiv: bytes) -> str:
    """Der Verzeichnisname im Ziel: Domain bei Integrationen, sonst Projektname."""
    if eintrag.kategorie == "integration":
        return _domain_aus_manifest(archiv)
    name = eintrag.identitaet.full_name.rsplit("/", 1)[-1]
    return name or eintrag.identitaet.full_name


#: Dateien, die das Repository beschreiben -- sie gehoeren nicht in die
#: geteilte Wurzel (Befund #19): Home Assistant liest sie dort nicht,
#: und jede zweite Installation wuerde an ihnen kollidieren.
_QUELL_BESCHREIBUNGEN = frozenset(
    {
        "hacs.json",
        "README.md",
        "README.rst",
        "README.txt",
        "LICENSE",
        "LICENSE.md",
        "LICENSE.txt",
    }
)


def _installiere_flach(
    archiv: bytes,
    zwischenlager: Path,
    ziel: Path,
    zuordnung: dict[str, str],
    fruehere: tuple[str, ...],
    altbestand: bool = False,
) -> tuple[str, ...]:
    """Flacher Weg fuer geteilte Wurzeln (Befund #19): je Datei.

    ``theme`` und ``python_script`` teilen sich ihre Wurzel mit allen
    anderen Installationen -- sie zu tauschen (wie es der Ordnerweg
    tut) waere Datenverlust: jede neue Installation frae die voherige,
    jede Deinstallation den ganzen Ordner. Stattdessen: entpacken ins
    Zwischenlager (dort gilt weiterhin die ganze Archiv-Abwehr), dann
    JEDE Datei einzeln an ihren Platz schieben -- atomar je Datei,
    ueberschrieben wird nur, was der eigenen frueheren Installation
    gehoerte. Fremde Dateien sind Kollisionen und werden mit Klartext
    abgewiesen, nicht still ueberschrieben.

    ``altbestand`` (Review zu !50, Befund 2): der Stand verzeichnet
    eine Installation aus 0.6.3 -- Version ja, Dateiliste nein. Die
    gleichnamigen Dateien des Archivs erben dann den Platz: ein
    Inhaltsgleichheits-Beweis wuerde gerade den Normalfall sperren
    (geaenderte Dateien sind der Grund eines Updates), die Namens-
    gleichheit mit dem eigenen Nachfolger ist der beste verfuegbare
    Nachweis der Zugehoerigkeit. Namen, die das Archiv nicht bringt,
    bleiben Kollisionen -- Fremdes wird auch so nicht angeruehrt.

    Zurueck kommt die Liste der geschriebenen Dateien -- sie wandert
    ins Protokoll (``Stand.dateien``) und macht die Deinstallation
    zur Rundreise ueber genau diese Liste.
    """
    zwischenlager.mkdir(parents=True, exist_ok=True)
    neu = zwischenlager / (ziel.name + ".neu")
    shutil.rmtree(neu, ignore_errors=True)
    entpacke = entpacken.entpacke
    try:
        entpacke(archiv, neu, nur=zuordnung)
    except entpacken.EntpackFehler as fehlschlag:
        shutil.rmtree(neu, ignore_errors=True)
        raise InstallationsFehler(str(fehlschlag)) from fehlschlag

    # Die geteilte Wurzel traegt die Dateien der Installation, nicht die
    # Beschreibung der Quelle: jedes Tag-Archiv bringt hacs.json, README
    # und Lizenz mit -- ohne diesen Filter kollidierte jede zweite
    # flache Installation an denselben Beschreibungen, und genau das
    # Testedikt ('zwei Themes nacheinander') verbietet es.
    neu_namen = sorted(
        name
        for name in zuordnung.values()
        if PurePosixPath(name).name not in _QUELL_BESCHREIBUNGEN
    )
    alt_namen = set(fruehere)

    # Review zu !50, Befund 1: JEDE Kollision wird geprueft, BEVOR das
    # erste os.replace laeuft. Vorher wanderte die Schleife Datei fuer
    # Datei und traf die fremde Datei erst mittendrin -- die schon
    # verschobenen eigenen blieben liegen, das Protokoll blieb leer,
    # und der zweite Versuch sperrte sich selbst an den eigenen Resten.
    # Altbestand erbt die Namen (Befund 2): keine Pruefung, Ersetzung.
    if not altbestand:
        for name in neu_namen:
            if (ziel / name).exists() and name not in alt_namen:
                shutil.rmtree(neu, ignore_errors=True)
                raise InstallationsFehler(
                    f"{ziel.name}/{name} existiert schon und gehoert nicht zu "
                    "dieser Installation -- erst die andere Installation "
                    "entfernen oder die Datei umbenennen"
                )

    geschrieben: list[str] = []
    try:
        for name in neu_namen:
            quelle = neu / name
            senke = ziel / name
            senke.parent.mkdir(parents=True, exist_ok=True)
            os.replace(quelle, senke)
            geschrieben.append(name)

        # Dateien, die die neue Version nicht mehr mitbringt, gehoeren
        # weder dem Archiv noch der Wurzel -- weg mit ihnen.
        for name in sorted(alt_namen - set(neu_namen)):
            (ziel / name).unlink(missing_ok=True)
            _raeume_leere_eltern(ziel, ziel / name)
    except OSError as fehlschlag:
        # Review zu !50, Befund 1: das Bruchstueck reist in der Ausnahme
        # -- eigene Reste plus fruehere Liste, denn alles das gehoert
        # jetzt dem Eintrag. Der Aufrufer protokolliert es, bevor der
        # Fehler hochgeht, und der zweite Versuch laeuft durch.
        raise HalbeInstallation(
            f"Dateisystem beim Verteilen in {ziel.name} versagte: {fehlschlag}",
            PurePosixPath(*ziel.parts),
            tuple(sorted(alt_namen | set(geschrieben))),
        ) from fehlschlag
    finally:
        shutil.rmtree(neu, ignore_errors=True)
    return tuple(geschrieben)


def _raeume_leere_eltern(wurzel: Path, datei: Path) -> None:
    """Entfernt die (dann leeren) Ordner oberhalb einer Datei -- nur
    bis zur Wurzel, nur wenn leer. Fremde Dateien halten ihre Ordner."""
    ordner = datei.parent
    while ordner != wurzel and ordner.is_dir():
        try:
            ordner.rmdir()
        except OSError:
            return  # nicht leer oder sonstwie blockiert -- stehen lassen
        ordner = ordner.parent


def _installiere_sync(
    archiv: bytes,
    kategorie: str,
    zielname: str,
    konfiguration: Path,
    fruehere_dateien: tuple[str, ...] | list[str] | None = None,
    altbestand: bool = False,
) -> InstallationsErgebnis:
    """Der schreibende Teil -- laeuft im Vorfuehrer (Executor), nie im Kreis.

    Zurueck kommt der Zielweg (relativ zur Konfiguration) fuer das
    Protokoll: die Deinstallation nimmt genau diesen Weg wieder.
    ``altbestand`` (Review zu !50, Befund 2) gilt Installationen aus
    0.6.3, deren Stand keine Dateiliste traegt -- dort erben die
    gleichnamigen Dateien des Archivs den Platz (siehe
    :func:`_installiere_flach`).
    """
    plan = entpacken.plane(archiv)
    namen = [eintrag.name for eintrag in plan if not eintrag.ist_verzeichnis]
    zuordnung = _kopierplan(archiv, kategorie, zielname, namen)

    ziel = konfiguration / zielpfade.zielverzeichnis(kategorie, zielname)
    zwischenlager = konfiguration / ZWISCHENLAGER_NAME
    ziel_weg = PurePosixPath(*ziel.relative_to(konfiguration).parts)

    # Befund #19: geteilte Wurzeln (themes, python_scripts) werden nie
    # als Ordner getauscht -- dort gilt der flache, dateiweise Weg.
    if zielpfade.ist_flach(kategorie):
        try:
            dateien = _installiere_flach(
                archiv,
                zwischenlager,
                ziel,
                zuordnung,
                tuple(fruehere_dateien or ()),
                altbestand=altbestand,
            )
        except HalbeInstallation as bruch:
            # Der flache Weg kennt nur den absoluten Ort -- hier oben
            # wird die Adresse ehrlich: relativ zur Konfiguration,
            # genau wie sie ins Protokoll gehoert.
            raise HalbeInstallation(str(bruch), ziel_weg, bruch.dateien) from bruch
        return InstallationsErgebnis(pfad=ziel_weg, dateien=dateien)

    try:
        entpacken.installiere(archiv, zwischenlager, ziel, nur=zuordnung)
    except entpacken.EntpackFehler as fehlschlag:
        raise InstallationsFehler(str(fehlschlag)) from fehlschlag
    return InstallationsErgebnis(pfad=ziel_weg)


def _kopierplan(
    archiv: bytes, kategorie: str, zielname: str, namen: list[str]
) -> dict[str, str]:
    """Der Kopierplan: welcher Ausschnitt des Archivs wohin wandert.

    Einheitlich gerechnet und einheitlich geprueft -- Installation und
    Rekonstruktion des Altbestands (Review zu !50, Befund 2) lesen
    denselben Plan, damit beide ueber dieselben Dateien sprechen.
    """
    hacs_roh = lese_archiv_datei(archiv, _HACS_JSON)
    hacs_daten: dict | None = None
    if hacs_roh is not None:
        try:
            hacs_daten = json.loads(hacs_roh)
        except json.JSONDecodeError as fehlschlag:
            raise InstallationsFehler(
                f"hacs.json ist kein gueltiges JSON: {fehlschlag}"
            ) from fehlschlag

    # Befund #15, Entschluss b: schweigt die hacs.json ueber die
    # Lagerform, kann das Archiv sie selbst zeigen -- der Ordner
    # custom_components/<domain>/ in jeder Tiefe. Nur bei Integrationen:
    # nur sie haben eine Domain und damit eine Lagerform. Was die
    # hacs.json ausdruecklich sagt (filename, content_in_root,
    # zip_release), bleibt vorrangig.
    #
    # Befund #18: schnitt muss VOR dem Versuch stehen -- wirft
    # ausschnitt() (hacs.json als Liste, Typfehler, Ausbruch im
    # Zielnamen), laesst der Rueckweg sonst ein ungeborenes schnitt.art
    # lesen (UnboundLocalError statt Klartext).
    schnitt: zielpfade.Ausschnitt | None = None
    try:
        schnitt = zielpfade.ausschnitt(hacs_daten)
        if (
            kategorie == "integration"
            and schnitt.art == "unterordner"
            and not schnitt.unterordner
        ):
            lagerform = finde_lagerform(archiv, zielname)
            if lagerform is not None:
                schnitt = zielpfade.Ausschnitt(art="unterordner", unterordner=lagerform)
            elif _manifest_in_wurzel(namen):
                # Flacher Anhang (3-System-Test, Flug 2096): keine
                # Lagerform, keine Ordnerhuelle, aber die Integration
                # liegt komplett offen da. Die Wurzel IST die Lagerform.
                schnitt = zielpfade.Ausschnitt(art="wurzel")
        zuordnung = zielpfade.waehle_eintraege(schnitt, namen)
    except zielpfade.ZielpfadFehler as fehlschlag:
        # Flug 2096, Wunde B aus dem 3-System-Test: manche hacs.json
        # nennt einen ``filename`` (ha-powerline: powerline.zip) -- das
        # ist HACS-Sprech fuer den GEBAUTEN Anhang des Releases. Fehlt
        # der Anhang, war das Tag-Archiv die Quelle -- und in ihm lebt
        # die Integration als custom_components/<domain>/ (Lagerform).
        # Die Integration kommt dann aus dem Ordner statt aus der
        # Raterei nach einer Datei, die nie im Archiv war. Andere
        # Kategorien und echte Mehrdeutigkeiten bleiben Fehler.
        # Befund #18: wirft ausschnitt() selbst (hacs.json kein Objekt,
        # Typfehler, Ausbruch im Zielnamen), ist schnitt None -- dann
        # gibt es nichts zu retten, nur den Klartext weiterzureichen.
        lagerform = (
            finde_lagerform(archiv, zielname)
            if kategorie == "integration"
            and schnitt is not None
            and schnitt.art == "dateien"
            else None
        )
        if lagerform is not None:
            schnitt = zielpfade.Ausschnitt(art="unterordner", unterordner=lagerform)
            zuordnung = zielpfade.waehle_eintraege(schnitt, namen)
        else:
            raise InstallationsFehler(str(fehlschlag)) from fehlschlag
    return zuordnung


# ---------------------------------------------------- Deinstallation


def _deinstalliere_sync(
    pfad_relativ: str,
    konfiguration: Path,
    dateien: tuple[str, ...] | list[str] | None = None,
) -> None:
    """Entfernt eine Installation -- mit Dateiliste oder als Ordnerzug.

    Der Weg kommt aus dem Protokoll und wird hier noch einmal geprueft
    (:func:`zielpfade.ist_zielpfad`): die Ablage ist eine Datei, Dateien
    lassen sich von Hand veraendern, und ein veraenderter Eintrag darf
    nie dazu fuehren, dass hier etwas ausserhalb der Kategorie-Wurzeln
    wegbenannt wird.

    Befund #19: bei flachen Kategorien ist der verzeichnete Weg die
    geteilte Wurzel (``themes``, ``python_scripts``) -- die wird nie
    als Ordner entfernt. Die Deinstallation nimmt nur die verzeichneten
    Dateien mit, prueft jeden Namen wie einen Pfad und laesst
    Fremddateien und die Wurzel selbst unberuehrt. Fehlt die Liste
    (installiert vor der Heilung), gibt es Klartext statt Datenverlust.

    Der Ordnerzug (alles ausser flachen Wurzeln) bleibt wie er war:
    erst das Ziel ins Zwischenlager wegbenennen (``.weg``), dann dort
    entfernen. Scheitert das Wegbenennen, steht das Ziel noch
    unberuehrt; scheitert das Entfernen, ist das Ziel zumindest
    verschwunden und das Lager raeumt der naechste Lauf auf -- halbe
    Zustaende gibt es im Ziel nicht.
    """
    rein = (pfad_relativ or "").strip()
    if not zielpfade.ist_zielpfad(rein):
        raise InstallationsFehler(
            f"untauglicher installierter Pfad: {pfad_relativ!r} -- die "
            "Deinstallation fasst nur bekannte Kategorie-Wurzeln an"
        )
    ziel = konfiguration.joinpath(*PurePosixPath(rein).parts)

    if dateien:
        if not ziel.is_dir():
            raise InstallationsFehler(
                f"nichts installiert unter {pfad_relativ!r} -- schon entfernt?"
            )
        sauber = [zielpfade.pruefe_relativen_namen(name) for name in dateien]
        for name in sauber:
            senke = ziel / name
            senke.parent.mkdir(parents=True, exist_ok=True)
            senke.unlink(missing_ok=True)
        for name in sauber:
            _raeume_leere_eltern(ziel, ziel / name)
        return

    teile = PurePosixPath(rein).parts
    if len(teile) == 1 and teile[0] in zielpfade.FLACHE_WURZELN:
        raise InstallationsFehler(
            f"{rein} ist die geteilte Wurzel mehrerer Installationen -- ohne "
            "verzeichnete Dateiliste wird sie nicht entfernt (installiert vor "
            "der Heilung?): einmal neu installieren, dann laesst sich auch "
            "sauber entfernen"
        )
    if not ziel.is_dir():
        raise InstallationsFehler(
            f"nichts installiert unter {pfad_relativ!r} -- schon entfernt?"
        )
    zwischenlager = konfiguration / ZWISCHENLAGER_NAME
    zwischenlager.mkdir(parents=True, exist_ok=True)
    weg = zwischenlager / (ziel.name + ".weg")
    shutil.rmtree(weg, ignore_errors=True)
    try:
        os.replace(ziel, weg)
    except OSError as schaden:
        raise InstallationsFehler(
            f"das Ziel laesst sich nicht wegbewegen: {schaden}"
        ) from schaden
    shutil.rmtree(weg, ignore_errors=True)


def _beanspruche_altbestand(
    archiv: bytes, kategorie: str, zielname: str, konfiguration: Path
) -> tuple[str, ...]:
    """Die Dateiliste eines Altbestands -- inhaltsgleich zum Archiv.

    Review zu !50, Befund 2: installiert vor der Heilung, verzeichnet
    der Stand nur die Wurzel -- welche Dateien DAMALS geschrieben
    wurden, sagt allein das Archiv der installierten Version. Es wird
    derselbe Kopierplan gerechnet wie bei der Installation (ohne zu
    schreiben), und beansprucht wird nur, was INHALTSGLEICH daliegt:
    eine veraenderte oder fremde Datei bleibt unberuehrt -- Loeschen
    nach Raterei waere der Datenverlust, den Befund #19 heilt. Die
    Beschreibungen der Quelle (hacs.json, README, Lizenz) gehoeren
    nie dazu, auch wenn sie im Archiv stehen.

    Zurueck kommt die Liste als Grundlage der Deinstallation --
    leer heisst: nichts zu erkennen, der Aufrufer meldet Klartext.
    """
    plan = entpacken.plane(archiv)
    namen = [eintrag.name for eintrag in plan if not eintrag.ist_verzeichnis]
    zuordnung = _kopierplan(archiv, kategorie, zielname, namen)
    ziel = konfiguration / zielpfade.zielverzeichnis(kategorie, zielname)
    beansprucht: list[str] = []
    with zipfile.ZipFile(io.BytesIO(archiv)) as zip_datei:
        for archiv_name, name in sorted(zuordnung.items()):
            if PurePosixPath(name).name in _QUELL_BESCHREIBUNGEN:
                continue
            datei = ziel / name
            if not datei.is_file():
                continue
            if zip_datei.read(archiv_name) == datei.read_bytes():
                beansprucht.append(name)
    return tuple(beansprucht)


async def rekonstruiere_dateiliste(
    hass: HomeAssistant,
    forge: Forge,
    eintrag: Eintrag,
    version: str,
) -> tuple[str, ...]:
    """Die Dateiliste eines Altbestands aus dem Archiv der Version.

    Der Weg fuer die Deinstallation eines 0.6.3-Altbestands: das
    Archiv der INSTALLIERTEN Version beschaffen (Anhang zuerst, sonst
    Tag-Archiv -- dieselbe Wahl wie bei der Installation), dann ohne
    Schreiben beanspruchen, was inhaltsgleich daliegt. Netz im
    Ereigniskreis, Vergleiche im Vorfuehrer. Fehler kommen als
    :class:`InstallationsFehler` oder :class:`ForgeFehler` mit
    Klartext -- der Aufrufer entscheidet, was daraus wird.
    """
    pfad = eintrag.identitaet.full_name
    archiv, _herkunft = await beschaffe_archiv(forge, pfad, version)
    name = eintrag.identitaet.full_name.rsplit("/", 1)[-1]
    zielname = name or eintrag.identitaet.full_name
    konfiguration = Path(hass.config.config_dir)
    return await hass.async_add_executor_job(
        _beanspruche_altbestand, archiv, eintrag.kategorie, zielname, konfiguration
    )


# ------------------------------------------------------- Ereigniskreis


async def installiere_version(
    hass: HomeAssistant,
    forge: Forge,
    eintrag: Eintrag,
    tag: str,
    fruehere_dateien: tuple[str, ...] | list[str] | None = None,
    altbestand: bool = False,
) -> InstallationsErgebnis:
    """Bringt die Version an ihren Ort und meldet den Zielweg.

    Quelle: Anhang des Releases, sonst Archiv des Tags (Stufe M4b).
    Netz im Ereigniskreis (ueber die aiohttp-Sitzung), Schreiben im
    Vorfuehrer -- Home Assistant blockiert die Schleife fuer niemanden.
    Fehler kommen als :class:`InstallationsFehler` mit Klartext; die
    aufrufende Entity reicht ihn als HomeAssistantError weiter.

    Das InstallationsErgebnis (Zielweg plus Dateiliste bei flachen
    Kategorien) ist das Protokoll fuer die Deinstallation -- die
    aufrufende Stelle sorgt dafuer, dass es in der Ablage landet, noch
    bevor die Version als installiert gilt. ``altbestand`` (Review
    zu !50, Befund 2) ermoeglicht das Update einer 0.6.3-Installation
    ohne verzeichnete Dateiliste.
    """
    pfad = eintrag.identitaet.full_name
    archiv, _herkunft = await beschaffe_archiv(forge, pfad, tag)
    zielname = _zielname(eintrag, archiv)
    konfiguration = Path(hass.config.config_dir)
    return await hass.async_add_executor_job(
        _installiere_sync,
        archiv,
        eintrag.kategorie,
        zielname,
        konfiguration,
        tuple(fruehere_dateien or ()),
        altbestand,
    )


async def deinstalliere_version(
    hass: HomeAssistant,
    pfad_relativ: str,
    dateien: tuple[str, ...] | list[str] | None = None,
) -> None:
    """Nimmt eine installierte Version weg -- den Weg aus dem Protokoll.

    Fehler sind Klartext und werden von der aufrufenden Stelle als
    HomeAssistantError weitergereicht. Was gefehlt hat, ist kein
    Fehlerbild, das hier entschaeft werden muss: die Meldung sagt,
    dass nichts (mehr) da ist.
    """
    konfiguration = Path(hass.config.config_dir)
    await hass.async_add_executor_job(
        _deinstalliere_sync, pfad_relativ, konfiguration, tuple(dateien or ())
    )
