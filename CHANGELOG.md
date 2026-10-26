# Änderungen

Alle nennenswerten Änderungen an HAIGS. Die Versionen folgen
[SemVer](https://semver.org/lang/de/); installiert wird aus den
[GitHub-Releases](https://github.com/Chance-Konstruktion/ha-haigs/releases).

## 0.6.8 — 2026-10-26

### Behoben
- Der HACS-Katalog packt Quellarchive und Einzeldatei-Releases nicht mehr auf
  der Ereignisschleife von Home Assistant um, sondern in einem Thread. Große
  Archive ließen HA sonst kurz hängen. Hinweis aus dem Review von @frenck
  (acs/default#11671](https://github.com/hacs/default/pull/11671)).
- Das Token reist nur zum Host der eingestellten Forge, nie zu fremden
  Release-Links ([#20](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/20),
  ebenfalls aus diesem Review).
- Die Entdeckung bleibt bei einer kaputten Kategorie-Quelle nicht stehen:
  eine Quelle je Kategorie, ein Fehler je Kandidat
  ([#22](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/22)).
- Robustheit in sieben Punkten: Sperre, kein Hartfehler, Aufräumen,
  Takthalter, Deckel, Vorführer, Obergrenze
  ([#23](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/23)).
- Kaputte ZIPs werden ehrlich abgewiesen statt still Verwirrung zu stiften
  (+57 Tests dafür).
- Übersetzungen: `options.errors` in `options.error` (hassfest).
- Optionsdialog: die Checkbox hält ihr Versprechen
  ([#24](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/24),
  Punkt 3).
- Forge-Nachheilung: das `v`-Präfix (gaming-assistant taggt `v261011`,
  HAIGS streicht es) und der leere Tag-Fall (spatial-matter ohne Tags).

### Neu
- TLS-Schalter: Zertifikat prüfen kann aus — selbstsignierte Instanzen
  ([#26](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/26)).
  Die Dialogbeschreibung nennt den Schalter in allen drei Sprachen.

### Intern
- FORGEN-TEST DRIFT-ROBUST: gegen den NEUESTEN Tag zur Laufzeit gewogen —
  dieselbe Laufzeit-Messung, ohne Datum-Falle (roter Build in !61).
- FORMAT-HEILUNG: ruff format zahlt die CI-Wahrheit (Refs #24).
- `requirements-dev` gepinnt, Token-Eingabe versteckt (#24 Kleinkram).

## 0.6.7.1 — 2026-10-15

### Behoben
- Versionsnachträge werden zerlegt statt als Text verglichen
  ([#21](https://gitlab.schanz.ipv64.net/chance-konstruktion/haigs/-/work_items/21)).
  `1.0.0-rc10` gilt jetzt als neuer als `1.0.0-rc2`, `beta.11` als neuer als
  `beta.2`, und `1.2.3-10` als neuer als `1.2.3-9`. Vorher wurden solche
  Updates still übersehen. Ein rein numerischer Nachtrag wie `1.2.3-10`
  bleibt eine fertige Fassung, keine Vorabversion.

### Intern
- Fahrplan, Stand und Vorschlag sind im Changelog aufgegangen;
  `ROADMAP.md`, `STAND.md`, `PROPOSAL.md` und `original.png` sind raus.

## 0.6.7 — 2026-10-11

### Neu
- Tags als Rückfall auch beim Entdecken und in der Versionsliste
  ([ha-haigs#1](https://github.com/Chance-Konstruktion/ha-haigs/issues/1)):
  Repositories ohne Releases erscheinen mit ihren Tags.

## 0.6.6 — 2026-10-11

### Behoben
- Gitea wurde als Forgejo erkannt. Forgejo erkennt HAIGS jetzt am
  `+gitea-` in der Versionsangabe, alles andere fragt die Startseite.
- Gitea und Forgejo ohne Token: Die Abfrage nach Projekt-Nummer endet dort
  anonym mit 401 (auch auf codeberg.org und gitea.com). HAIGS holt die
  Stammdaten dann über den bekannten Pfad und prüft die Nummer.

### Intern
- Neue CI-Bahn `tests-forgen`: HAIGS läuft gegen echte Gitea- und
  Forgejo-Server, befüllt mit eigenen Repositories, über `http://`.

## 0.6.5 — 2026-10-11

### Neu
- `http://` für Instanzen ohne TLS, etwa ein Forgejo im Heimnetz
  ([#1](https://github.com/Chance-Konstruktion/ha-haigs/issues/1)).
  Ohne Angabe bleibt es bei `https://`. Ein Token über `http://` erzeugt
  eine Warnung im Log.

### Geändert
- Der Name heißt überall HAIGS. Der Projektpfad im GitLab ist jetzt
  `chance-konstruktion/haigs`.
- HAIGS tritt als eigener Store auf, nicht als Begleiter von HACS.

## 0.6.4 — 2026-10-10

### Behoben
- Flache Kategorien (Themes, Python-Skripte) schreiben dateiweise in den
  gemeinsamen Ordner. Kollisionen werden vorher geprüft, die
  Deinstallation entfernt genau die eigenen Dateien.
- Zielnamen aus der `hacs.json` werden geprüft; kein Schreiben außerhalb
  des Ziels.
- Ältere Installationen ohne Dateiliste lassen sich weiter aktualisieren
  und entfernen.
- Klartext-Meldung, wenn die `hacs.json` im Archiv kein Objekt ist.

## 0.6.3 — 2026-10-08

### Geändert
- Logo und Seitenleisten-Icon ohne fremde Markenzeichen: der Fuchskopf.
- Lizenzhinweise in `NOTICE.md`, eigener User-Agent.
- README mit Ein-Klick-Knöpfen für die Einrichtung.

## 0.6.2 — 2026-10-08

### Geändert
- Angesehene Neuheiten wandern zu „Herunterladen“, wie bei HACS.

## 0.6.1 — 2026-10-08

### Geändert
- Neue Fußzeile: „your forge, your rules“.

## 0.6.0 — 2026-10-08

### Neu
- Der offizielle HACS-Katalog als zuschaltbare Quelle, mit Download-Zahlen
  im Panel.

### Behoben
- Plugins kommen aus dem Release-ZIP; Symlinks aus Quellarchiven werden
  entfernt.

## 0.5.1 — 2026-10-07

### Geändert
- Reparatur-Meldungen zeigen das Icon des betroffenen Repositorys.

## 0.5.0 — 2026-10-07

### Geändert
- Umbenennung: HACS*lab heißt jetzt HAIGS. Die Domain ist `haigs`.

## 0.4.1 — 2026-10-07

### Behoben
- `manifest.json` nennt die Abhängigkeiten so, wie hassfest es verlangt.

## 0.4.0 — 2026-10-07

### Neu
- Benutzerdefinierte Repositories direkt im Laden hinzufügen.
- Entwicklermodus: installiert den Kopf eines Zweigs statt eines Releases.
- Icons aus dem `brand`-Ordner der Repositories, auch in den Updates.

### Geändert
- Der Laden sieht aus wie in Home Assistant gewohnt.

## 0.3.0 — 2026-09-20

### Neu
- Gitea als vierter Anbieter; der Einrichtungsdialog erkennt den Anbieter
  selbst.
- Laden mit Suche, Sortierung, Detailansicht und gerenderter README;
  seitenweises Nachladen bei großen Instanzen.
- Zustand je installierter Integration: Neustart nötig, einrichten,
  eingerichtet. Dazu eine Benachrichtigung mit Anleitung.
- Englische README, Fehlerberichte über GitHub.

### Behoben
- README-Tabellen werden als Tabellen gezeigt.
- Doppelte Einträge desselben Repositorys.
- Repositories mit `custom_components/<domain>/` in tieferen Ordnern und
  mit `filename` ohne Release-Anhang.
- Härtung gegen feindliche Eingaben: BOM in `hacs.json`, lange Versionen,
  HTML statt JSON, eingeschleuste Namen in der Oberfläche.

## 0.1.1 — 2026-09-04

### Geändert
- Icon im Einrichtungsdialog.

## 0.1.0 — 2026-09-04

Erste Ausgabe.

- Anbieter GitLab und Forgejo (Codeberg) hinter einer gemeinsamen
  Schnittstelle; der Kern läuft ohne Home Assistant.
- Einrichtungsdialog mit Verbindungsprüfung, mehrere Instanzen
  nebeneinander, Token optional.
- Custom Repositories hinzufügen, Entdeckung über das Topic `hacs`.
- Installation aus Release-Anhang oder Tag-Archiv, bewachtes Entpacken
  (Pfadausbruch, Größe, Symlinks), atomarer Tausch, saubere Deinstallation.
- `update`-Entitäten mit Release-Notizen, Vorabversionen je Eintrag
  schaltbar, Rückfall auf Tags.
- Panel ohne YAML, Diagnose ohne Token, Reparatur-Meldungen.
