# HAIGS

**H**ome**A**ssistant-**I**mport-**G**it-**S**torage

<p align="center">
  <img src="logo.png" alt="HAIGS — der GitLab-Fuchs übernimmt das Home-Assistant-Haus" width="192">
</p>

> 🇩🇪 Deutsch · [🇬🇧 English](README.en.md)

HACS-Verhalten für selbst gehostete Git-Forges: Home-Assistant-Custom-Components,
die auf **GitLab**, **Gitea** oder **Forgejo** ([Codeberg](https://codeberg.org))
leben, hinzufügen, entdecken und aktuell halten — so, wie HACS es für GitHub tut.

**Kein Fork.** HAIGS ist eine eigene Home-Assistant-Integration, die *neben*
HACS läuft. Wir ändern keinen HACS-Code und kopieren keinen. Das hat einen
Grund: Ein Fork müsste jedem HACS-Release hinterherjagen, und niemand außer uns
würde ihn je benutzen.

## Das Problem

HACS kennt genau eine Quelle: GitHub. Ein Custom Repository mit GitLab-Adresse
wird abgelehnt; es gibt dafür keinen Schalter. Wohnen deine Integrationen auf
einer eigenen — oder irgendeiner anderen — GitLab-, Gitea- oder
Forgejo-Instanz, installierst du von Hand und erfährst nie, dass es eine neue
Version gibt.

HAIGS schließt diese Lücke. Es spricht alle drei Familien direkt an: Es
findet Repositories mit dem Entdeckungs-Topic, liest ihre Metadaten, vergleicht
Versionen, lädt das Versions-Archiv herunter und installiert es sicher.

## Installation

**Über HACS (empfohlen)**

1. HACS → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/Chance-Konstruktion/ha-haigs`, Typ *Integration*.
2. **HAIGS** herunterladen und Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen* → **HAIGS**.
   Host deiner Instanz eintragen (gitlab.com, codeberg.org, gitea.com oder
   selbst gehostet), optional ein Lese-Token. Der Anbieter bleibt auf **auto** –
   HAIGS erkennt selbst, ob GitLab, Forgejo oder Gitea antwortet.
4. In der Seitenleiste erscheint **HAIGS**. Weitere Instanzen richtest du
   genauso ein – so viele du willst, in beliebiger Mischung.

Danach hält sich HAIGS auch selbst aktuell: Nimm dieses Repository in die
eigene Liste auf, und jedes neue Release erscheint als Update.

**Von Hand:** `haigs-vX.Y.Z.zip` von der
[Release-Seite](https://github.com/Chance-Konstruktion/ha-haigs/releases)
ins Konfigurationsverzeichnis entpacken (es enthält genau
`custom_components/haigs/`), neu starten, weiter bei Schritt 3. Die SHA-256
steht in jeder Release-Beschreibung; der Bau ist deterministisch.

**Voraussetzungen:** Home Assistant 2025.2 oder neuer (getestet bis 2026.9).
Ein Lese-Token brauchst du nur für private Repositories (GitLab-Scope
`read_api`, bei Gitea/Forgejo ein Token mit Leserecht).

> Einrichtung und Panel sprechen Deutsch und Englisch.

## HAIGS benutzen

> **Handbuch:** das
> [Projekt-Wiki](https://gitlab.schanz.ipv64.net/chance-konstruktion/hacs-lab/-/wikis/Home)
> erklärt alles in der Tiefe — Installation, Provider anbinden (so viele
> Server, wie du magst, GitLab/Gitea/Forgejo in beliebiger Mischung),
> Einstellungen, den Laden, die Anleitung für Repository-Besitzer und eine
> Seite Fehlerbehebung.

- **Das Panel – fühlt sich an wie HACS:** dieselbe Datentabelle wie der
  HACS-Store (Filter, Suche, Gruppen nach Status, Sortierung, Spaltenwahl),
  dieselben Gruppen (*Ausstehende Aktualisierung*, *Heruntergeladen*, *Neu*,
  *Verfügbar zum Herunterladen*), dieselbe Detailseite mit README, Chips für
  Besitzer, Quelle, Sterne, Issues und Version und dem Knopf
  *Herunterladen*. Der eigene Ton: GitLab-Orange als Akzent und die Spalte
  **Quelle** (Schmiede und Host), wo HACS die Downloads zählt. Jede
  Detailseite hat ihre eigene Adresse – Zurück im Browser und geteilte Links
  funktionieren. Unten unterschreibt der Tanuki: *„Für die Freiheit gebaut —
  kein GitHub-Monopol-Scheiß.“*
- **Icons wie in Home Assistant:** Integrationen bringen ihr Icon seit 2026 im
  eigenen `brand/`-Ordner mit. HAIGS zeigt es über den Marken-Proxy von
  Home Assistant – im Laden und bei den Updates.
- **Entwicklermodus:** In den Optionen einer Instanz einschalten, und statt
  Releases lädt HAIGS den neuesten Stand des Standardzweigs
  (`main@1a2b3c4`). Jeder Push ist sofort testbar, auch ohne Release.
- **Grenzenlos Server, beliebige Mischung:** jede Instanz ist ein
  Konfigurationseintrag — richte so viele ein, wie du magst, jede mit eigenem
  Anbieter (GitLab, Forgejo, Gitea), Token und Takt. Der Laden zeigt sie alle
  als klickbare Instanz-Chips — jeder mit seinem Anbieter beschriftet — mit
  einem gestrichelten „+ Instanz hinzufügen“-Knopf, der den Einrichtungs-Dialog
  für die nächste Domain öffnet. Derselbe Knopf sitzt im Erstlings-Hinweis des
  leeren Ladens.
- **Nie ein leerer Laden:** die Liste lebt im *Lager*, einem Zwischenspeicher
  je Instanz im Home-Assistant-Speicher (`haigs.lager.<host>`). Das Panel
  zu öffnen malt sofort aus dem Lager (kein Netz-Umlauf), dann läuft die
  frische Prüfung im Hintergrund und zeichnet neu, sobald sie landet. Nach
  einem Neustart wird das Lager gelesen, während Home Assistant noch
  hochfährt; der erste Hintergrundlauf folgt kurz darauf, und derselbe Takt,
  den du für den Herzschlag eingestellt hast, hält das Lager frisch —
  `haigs_aktualisiert`-Ereignisse streichen das Panel neu, solange es
  offen bleibt. Der Auffrischen-Knopf erzwingt einen Lauf jederzeit.
- **Custom Repository hinzufügen:** Panel → ⋮ → *Benutzerdefinierte
  Repositories* (wie in HACS), die Projekt-URL einfügen, eine Kategorie wählen. HAIGS liest Metadaten und
  Version und bietet die Installation an.
- **Entdecken:** Repositories, deren Besitzer auf ihrem GitLab-, Gitea- oder
  Forgejo-Projekt das Topic `hacs` gesetzt haben, erscheinen im Bereich *Neu*
  des Panels — mit Beschreibung, Sternen und neuester Version. Ein zweites
  Topic (`hacs-plugin`, `hacs-theme`, …) legt die Kategorie fest, ohne zu
  fragen.
- **Offizielle HACS-Repos:** Einstellungen → Geräte & Dienste → HAIGS →
  *Konfigurieren* → *Offizielle HACS-Repos anzeigen*. Das legt eine eigene
  Quelle „HACS" an (Katalog von `data-v2.hacs.xyz`, kein Token nötig): rund
  4000 Integrationen, Plugins und Themes erscheinen im Bereich *Neu*, samt
  Downloads. So genügt ein einziger Store in der Seitenleiste. Derselbe
  Schalter entfernt die Quelle wieder; den Entwicklermodus gibt es für sie
  nicht.
- **Updates:** jeder Eintrag bekommt eine Update-Entity und einen Herzschlag,
  dessen Takt du je Eintrag einstellen kannst. Ein neues Release oder Tag
  hebt das Update, der Installations-Dienst tauscht die Dateien sicher — erst
  im temporären Verzeichnis aufgebaut, dann ein atomarer Wechsel, bei
  Scheitern zurückgerollt.
- **Bevorzugte Quelle:** trägt ein Release genau ein ZIP-Attachment, wird
  dieses gebaute Artefakt installiert statt des automatisch erzeugten
  Tag-Archivs; alles Mehrdeutige fällt auf das Archiv zurück. Dieser Rückfall
  versteht das Repository-Layout: Er findet `custom_components/<domain>/` auf
  jeder Tiefe und installiert genau diesen Teilbaum — die normale
  HACS-Struktur installiert sich also, wie sie ist, ohne gebautes Attachment
  (Issue #15).
- **Deinstallation & Neustart:** jeder Eintrag mit aufgezeichneter
  Installation deinstalliert auch — der aufgezeichnete Zielpfad wird gegen die
  bekannten Kategorie-Wurzeln geprüft und dann in einem Zug entfernt. Das
  Installieren oder Deinstallieren einer **Integration** hebt einen
  Reparatur-Zettel, Home Assistant neu zu starten (Integrationen laden nur
  beim Start); der Zettel verschwindet von selbst, sobald der Neustart
  passiert ist.
- **Wo die Integration bleibt (Flug 2098):** Installieren reicht nicht —
  Home Assistant scannt `custom_components` erst beim Start, und die Karte
  unter *Geräte & Dienste* entsteht erst, wenn du die Integration danach
  selbst hinzufügst. Der Laden sagt das jetzt in drei Stimmen: jede
  installierte Integration trägt einen **Zustands-Chip** auf ihrer Karte
  (Neustart erforderlich / bereit zum Einrichten — ein Knopf, der *Geräte &
  Dienste* öffnet / eingerichtet / Einrichtung über configuration.yaml /
  nicht geladen — Protokoll prüfen), die Installation legt eine
  **dauerhafte Benachrichtigung** mit demselben Rat (denselben Weg, den
  HACS geht), und der Reparatur-Zettel bleibt, wie er war. Integrationen
  ohne Einrichtungsdialog (`config_flow: false` in ihrer manifest.json)
  können unter *Geräte & Dienste* prinzipiell nie erscheinen — der Chip
  nennt dann den YAML-Weg, statt dich raten zu lassen.
- **Robuster Bestand:** ein umbenanntes Projekt wird an seiner ID erkannt, und
  der Name folgt still; ein erreichbares, aber verändertes Repository wird
  gemeldet, nie geraten; Diagnosen drucken dein Token nie im Klartext.

## Für Repository-Besitzer

Damit HAIGS ein Projekt findet und installieren kann (auf GitLab, Gitea
und Forgejo/Codeberg gleichermaßen):

1. Setze das Topic `hacs` unter *Einstellungen → Allgemein → Topics*.
2. Lege ein gültiges `hacs.json` auf den Standard-Zweig. Kleinstform:

   ```json
   {
     "name": "Meine Integration",
     "render_readme": true,
     "homeassistant": "2025.2.0"
   }
   ```

   Repositories mit anderem Layout setzen `content_in_root`, `zip_release`
   oder `filename` — dieselben Konventionen, die HACS etabliert hat.
3. Veröffentliche Versionen als Releases oder zumindest als Tags. Releases
   gewinnen; Tags sind der Rückfall. Kein gebautes Artefekt nötig: das
   automatisch erzeugte Tag-Archiv genügt — HAIGS erkennt den Ordner
   `custom_components/<domain>/` darin und installiert genau diesen
   Teilbaum; Dateien der Repository-Wurzel (README, CI-Konfiguration) bleiben
   außen vor. Ein Release mit gebautem ZIP-Attachment (der Domain-Ordner als
   Wurzel) bleibt die genaueste Lieferform und gewinnt weiterhin, wenn
   vorhanden. Und drei Formen, die seit dem 3-System-Test ebenfalls gehen:

   - **flache ZIP-Attachments** — der Inhalt von
     `custom_components/<domain>/` ohne jeden Ordner (so bauen es viele
     HACS-Repos; die `manifest.json` an der Wurzel genügt als Ausweis),
   - **`filename` ohne Attachment** — nennt die `hacs.json` eine Datei wie
     `powerline.zip`, die zum gebauten Release-Anhang gehört, und fehlt der
     Anhang, fällt die Installation still auf die Lagerform des Tag-Archivs
     zurück, statt an einer Datei zu scheitern, die nie im Archiv lag,
   - **Versions-Namen wie `github/260801`** — Tags mit Schrägstrich und
     Datumscodes sortieren mit und installieren mit.

`hacs-development` als zweites Topic markiert ein Repository als
Entwicklungs-Zustand — es wird nur gefunden, wenn ausdrücklich danach gesucht
wird.

## Sicherheit

Code von einer Forge zu installieren ist eine Vertrauensentscheidung, keine
technische. HAIGS nimmt den technischen Teil ernst: Versions-Archive
werden mit Wächtern gegen Pfad-Flucht, Größe, Anzahl und Symlinks entpackt —
vier böswillige Test-Archive (Pfad-Traversal, Riesen-Datei, Symlink-Angriff,
Zip-Bombe) gehören zur Testsuite und müssen abgelehnt werden, *bevor*
irgendetwas geschrieben wird. Die Unversehrtheit einer abgebrochenen
Installation lügt nie: erst aufgebaut, dann atomar gewechselt, bei Scheitern
zurückgerollt.

## Repository-Aufbau

```
logo.png, original.png        das eine Markenbild — Quelle (original.png) und
                              512er-Form (logo.png): Panel, Avatar, exe
hacs.json                     Repository-Konventionen für HAIGS selbst
custom_components/haigs/   die Integration — dünne Home-Assistant-Schicht
  manifest.json               Domain, Version, Config-Flow, Icon
  config_flow.py              Einrichtungs-Dialog mit Verbindungsprüfung
  lager.py                    der Laden-Cache: gehaltene Liste + Bestandslauf,
                              Hintergrund-Takt, `haigs_aktualisiert`
  frontend/panel.js           das Seitenleisten-Panel (ohne YAML) — GitLab-Stil
  frontend/iconset.js         der Tanuki als Seitenleisten-Icon (eigene
                              Icon-Sammlung `haigs`, auf jeder Seite)
  translations/               Dialog-Texte
  core/                       der Kern — reines Python, ohne Home Assistant,
                              ohne Netz in den Tests; liegt hier seit der
                              Entscheidung zur Lieferform (Issue #11)
    forge.py                  die Anbieter-Schnittstelle (GitLab, Forgejo, Gitea, …)
    gitlab_forge.py           GitLab REST v4
    forgejo_forge.py          Forgejo (Codeberg-Aufzeichnungen)
    gitea_forge.py            Gitea — die Forgejo-Schwester (Topic-Suche)
    schmiede.py               die Schmiede-Fabrik + Anbieter-Auto-Erkennung
    http_aiohttp.py           HttpClient auf aiohttp (Sitzung kommt von außen)
    validierung.py            hacs.json, manifest.json
    versionen.py              Versions-Vergleich und Update-Entscheidung
    entdeckung.py             Topic → Kandidat → Validierung
    entpacken.py              bewachtes Entpacken, atomare Installation
auslieferung/release_bauen.py deterministischer Release-Archiv-Bau
tests/                        Kern-Suite — pytest, ohne Netz
tests_ha/                     Home-Assistant-Bahn — offline, am Prüf-Doppel
```

## Entwicklung

Zwei Bahnen, ein Urteil: der Kern läuft schlank, die Framework-Schicht braucht
Home Assistant (Python 3.13, `requirements-ha.txt`).

```bash
python -m pytest -q                       # Kern: kein HA, kein Netz
python -m pytest tests_ha -q -p pytest_homeassistant_custom_component
```

Die Härtungs-Suiten (`*_hart.py` in beiden Bahnen) fahren den Code gegen
feindliche Eingaben: UTF-8-BOM in `hacs.json` (Windows-Editoren lassen eines
da), fünfteilige Versionen, wo `.10` gegen `.9` gewinnen muss, Suchwörter, die
wie Skript-Einschleusungen aussehen, zehntausend Zeichen lange Schlüsselwörter,
Speicher, der nicht hält, was das Schema versprach, Captive Portals, die mit
HTML statt JSON antworten, und 500er, wo vorher ein GitLab aus dem Nichts
behauptet wurde. Die DOM-Seite ist im Browser-Harness bewiesen
(`scripts/schaufenster2093/`): feindliche Repository-Namen, Beschreibungen,
Avatare (`javascript:`-URLs fallen auf den Buchstaben zurück) und Suchwörter
kommen als *Text* an, nie als lebende Elemente — nie führt ein
eingeschleustes Tag etwas aus.

Unter Windows zuerst `PYTHONUTF8=1` setzen — sonst melden gesunde Tests
Fehler, die keine sind.

Releases baut `auslieferung/release_bauen.py` deterministisch: feste
Zeitstempel, sortierte Einträge, reproduzierbare Bytes. Eine Tag-Pipeline baut
das Archiv und heftet es an ein GitLab-Release; der Bau verweigert, wenn Tag
und `manifest.json` verschiedene Versionen nennen.

Die Dokumentation hier ist durchgehend deutsch — auf der Forge ist Deutsch
Amtssprache (Issue #16). Das Denken wohnt in
[ARCHITEKTUR.md](ARCHITEKTUR.md) (die fünf Struktur-Entscheidungen),
[ROADMAP.md](ROADMAP.md) (Meilensteine M0–M10 mit ihren Abnahmen) und
[MITARBEIT.md](MITARBEIT.md) (wie man mitarbeitet). Die Schnittstelle für
einen zweiten Forge-Anbieter — und was HACS selbst dafür übernehmen müsste —
steht ausgearbeitet in [PROPOSAL.md](PROPOSAL.md).

**Wo gearbeitet wird.** Entwickelt wird auf dem selbst gehosteten GitLab —
das ist der Sinn des Projekts — und nach
[GitHub](https://github.com/Chance-Konstruktion/ha-haigs) gespiegelt, damit
Fremde das Projekt finden, installieren und Fehler melden können. Auf dem
GitLab kann sich niemand von außen anmelden, deshalb ist
**[GitHub der Ort für Fehlerberichte](https://github.com/Chance-Konstruktion/ha-haigs/issues)**.
Die englische Fassung dieser Seite liegt als [README.en.md](README.en.md)
daneben.

## Lizenz

[MIT](LICENSE) — Copyright (c) 2026 chance-konstruktion und die
HAIGS-Beitragenden.
