# Architektur

Fünf Entscheidungen, die alles Weitere bestimmen. Wer eine davon
umwerfen will: gern, aber im Ticket und mit Begruendung -- nicht
nebenbei im Code.

## 1. Kein Fork

HAIGS steht **neben** HACS, nicht darin. Kein kopierter HACS-Code,
keine gepatchte Kopie, keine Abhaengigkeit auf HACS-Interna.

*Warum:* Ein Fork muss jeder HACS-Version hinterherlaufen und bleibt
trotzdem etwas, das nur wir benutzen. Wir bauen die Faehigkeit lieber
so, dass HACS sie spaeter uebernehmen **koennte** (siehe M10).

## 2. Identitaet ist nicht der Name

```python
RepositoryIdentity(
    provider="gitlab",
    host="gitlab.example.net",
    provider_id="789012",
    full_name="foo/bar",
)
```

Daraus abgeleitet:

| Feld | Wert | wofuer |
|---|---|---|
| `uid` | `gitlab:789012` | Schluessel innerhalb einer Instanz |
| `storage_key` | `gitlab@gitlab.example.net:789012` | Schluessel in der Ablage |
| `display_full_name` | `foo/bar*lab` | alles, was ein Mensch sieht |

Drei Folgen, die genau so gewollt sind:

* Ein umbenanntes Projekt bleibt derselbe Eintrag -- die ID traegt.
  Seit M8 wird der Name auch wirklich nachgezogen: der Lauf fragt die
  Stammdaten ueber die ID (billig ueber den ETag-Zwischenspeicher),
  prueft unter dem aktuellen Namen und ersetzt den gespeicherten still.
  Entities und Staende bleiben, wo sie sind -- ihr Schluessel ist die
  Identitaet, nicht der Name.
* Dieselbe Projekt-ID auf zwei GitLab-Instanzen sind zwei Eintraege --
  darum steckt der Host in `storage_key` und nicht in `uid`.
* Ein GitHub-Repo namens `foo/bar-lab` wird nie mit einem
  GitLab-Eintrag verwechselt, weil der Anbieter ein Feld ist und kein
  Namensbestandteil.

`strip_suffix()` gibt es, damit ein Anzeigename nie versehentlich in
eine Abfrage geraet: `foo/bar*lab` existiert im GitLab nicht.

## 3. Eine Schnittstelle je Anbieter, kein Sonderpfad

`core/forge.py` beschreibt, was HAIGS braucht: Stammdaten,
Releases, eine Datei, eine Archiv-Adresse, eine Topic-Suche -- und seit
M8 die Stammdatenfrage über die ID, denn der Name eines Projekts ist
die Adresse des Menschen und damit vergänglich: Projekte werden
umbenannt, Pfade wiederverwendet. Mehr nicht. `gitlab_forge.py` ist die
erste Umsetzung, `forgejo_forge.py`
(M9, Codeberg als Referenzinstanz) die zweite -- ohne dass der Ablauf,
der Speicher oder die Oberfläche dazwischen etwas vom Anbieter wissen.

Ein `if provider == "gitlab":` ausserhalb der Anbieterklassen gilt als
Fehler. M9 hat die Probe bestanden: der dritte Anbieter ist eine
weitere Klasse und sonst nichts.

Der HTTP-Zugang wird hineingereicht (`HttpClient`), nicht importiert.
Deshalb laeuft der ganze Kern in Tests ohne Netz, und Home Assistant
gibt spaeter einfach seine aiohttp-Sitzung hinein.

## 4. Topic ist Absicht, nicht Aufnahme

```
kein Topic          -> gar nicht erst ansehen
hacs                -> Kandidat, jetzt pruefen
hacs + development  -> Kandidat, aber nur auf Wunsch
```

Danach erst: `hacs.json` lesen, Kategorie bestimmen, validieren. Ein
falsch gesetztes Topic soll nichts kaputtmachen koennen, und "baut
etwas fuer Home Assistant" ist nicht dasselbe wie "gehoert in HACS".

Die Zusatz-Topics `hacs-integration`, `hacs-plugin`, `hacs-theme`,
`hacs-template`, `hacs-appdaemon`, `hacs-python_script` bestimmen die
Kategorie. Ohne Zusatz-Topic gilt `integration`.

## 5. Der Kern wohnt in der Integration

```
custom_components/haigs/      die Integration -- importiert Home Assistant
  core/                           der Kern -- pures Python, kein HA-Import
    forge.py                      Schnittstelle (Anbieter, Fehlerarten, …)
    gitlab_forge.py, forgejo_forge.py
    http_aiohttp.py               aiohttp-Umsetzung des HttpClient
```

Bis M0.5 lag der Kern als eigenstaendiges ``haigs`` neben
``custom_components`` -- verbunden durch einen Suchpfad-Fallback. Das
brach in der echten Handinstallation (Issue #11, Befund a): der
Fallback zeigte ins Konfigurationsverzeichnis, dorthin kopiert
niemand etwas, also ImportError. Die drei Kandidaten:

1. **Kern in die Integration ziehen** (gewaehlt): eine Adresse, ein
   Verzeichnis, relative Importe (``from .core.forge import ...``).
   Der Suchpfad bleibt unberuehrt -- das ist keine Kleinigkeit, denn
   jeder Griff auf ``sys.path`` in einer echten Installation (
   ``/config``) beschattet frueher oder spaeter die Standardbibliothek
   oder Home Assistant. Handinstallation heisst jetzt: einen Ordner
   kopieren. Der Release-ZIP enthaelt einen Ordner. Kein Werkzeug, kein
   Paketindex, nichts zu installieren, bevor der erste Versuch startet.
2. **Kern als Wheel ueber ``requirements``**: sauber verpackt, aber ein
   Paketindex mehr im Spiel -- und jeder HACS-Nutzer bekaeme eine
   Abhaengigkeit, die nicht aus diesem Repository kommt. Fuer eine
   Integration, die gerade bei privaten Instanzen ihr Publikum hat,
   ist das der schlechtere Handel.
3. **Release-Archiv mit zwei Ordnern**: loest die Handinstallation
   nicht -- wer von Hand kopiert, kopiert beim besten Willen nicht
   zwei Verzeichnisse an zwei verschiedene Stellen.

Der Preis von (1) heisst ehrlich: der Kern liegt in einem
Home-Assistant-Verzeichnis, obwohl er nichts mit Home Assistant zu tun
hat. Der Preis wird beglichen, nicht verheimlicht: die Regel ``kein
HA-Import im Kern`` bleibt maschinell pruefbar (CI grept ``core/`` auf
Home-Assistant-Importe), der Form-Waechter ``auslieferungsform`` in der
Pipeline verhindert das Zurueckrutschen in die Wurzel-Form, und die
Kern-Tests melden den Kern per ``tests/kern_laden.py`` an -- registriert
in ``sys.modules``, niemals auf den Suchpfad gestellt. Die
Home-Assistant-Bahn (``tests_ha/``) importiert denselben Code unter
seinem echten Namen; keine Bahn teilt Objekte mit der anderen.

## Was der Kern nicht darf

* Home Assistant importieren
* eine HTTP-Bibliothek importieren
* Dateien schreiben (das macht ab M4 die HA-Schicht)
* auf der Forge schreiben -- HAIGS liest, immer
