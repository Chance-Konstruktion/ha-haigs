# HAIGS

**H**ome**A**ssistant-**I**mport-**G**it-**S**torage

<p align="center">
  <img src="logo.png" alt="HAIGS-Logo" width="192">
</p>

> [🇬🇧 English](README.md) · 🇩🇪 Deutsch

Ein Store für Home-Assistant-Custom-Components, die auf **GitLab**, **Gitea**
oder **Forgejo** ([Codeberg](https://codeberg.org)) liegen statt auf GitHub —
hinzufügen, entdecken, aktuell halten, selbst gehostet oder öffentlich.

HACS kennt nur GitHub. HAIGS ist eine eigene Integration, die *neben* HACS
läuft; kein Fork, kein geänderter HACS-Code.

## Funktionen

- **Vertrauter Store** — Tabelle, Gruppen, Suche, Filter und Detailseite wie
  im HACS-Store, dazu eine Spalte *Quelle* mit Forge und Host.
- **Beliebig viele Instanzen** — GitLab, Gitea und Forgejo gemischt, jede mit
  eigenem Token und Prüfintervall; der Anbieter wird selbst erkannt.
- **Entdecken** — Projekte mit dem Topic `hacs` erscheinen unter *Neu*; ein
  zweites Topic (`hacs-plugin`, `hacs-theme`, …) legt die Kategorie fest.
- **Benutzerdefinierte Repositories** — Projekt-URL einfügen, Kategorie
  wählen, installieren.
- **Updates** — je installiertem Repository eine Update-Entität; Releases
  zuerst, Tags als Rückfall.
- **Sichere Installation** — Archive werden auf Pfadausbruch, Größe,
  Dateianzahl und Symlinks geprüft; Aufbau im Zwischenordner, atomarer
  Wechsel, Rückrollen bei Fehlern; die Deinstallation entfernt genau das
  Installierte.
- **Entwicklermodus** — je Instanz den neuesten Stand des Standardzweigs
  statt eines Releases installieren.
- **Offizieller HACS-Katalog, zuschaltbar** — die rund 4000 HACS-Repositories
  im selben Store.
- **Icons** aus dem `brand/`-Ordner der Repositories.
- **Klare nächste Schritte** nach der Installation: Neustart-Hinweis,
  Einrichten-Knopf oder Hinweis auf YAML-Einrichtung.

Ausführlich (englisch): [docs/features.md](docs/features.md).

## Installation

[![Öffne deine Home-Assistant-Instanz und dieses Repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chance-Konstruktion&repository=ha-haigs&category=integration)

Oder von Hand:

1. HACS → ⋮ → *Benutzerdefinierte Repositories* →
   `https://github.com/Chance-Konstruktion/ha-haigs`, Typ *Integration*.
2. **HAIGS** herunterladen, Home Assistant neu starten.
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen* → **HAIGS**.
   Host eintragen (gitlab.com, codeberg.org, gitea.com oder der eigene
   Server), für private Repositories ein Lese-Token. Anbieter auf **auto**
   lassen.
4. **HAIGS** erscheint in der Seitenleiste. Weitere Instanzen genauso.

**Voraussetzungen:** Home Assistant 2025.2 oder neuer. Ein Token braucht es
nur für private Repositories (`read_api` bei GitLab, Lese-Token bei
Gitea/Forgejo).

## Lizenz

[MIT](LICENSE) — Copyright (c) 2026 chance-konstruktion und die
HAIGS-Mitwirkenden.
