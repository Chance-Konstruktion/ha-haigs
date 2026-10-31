<div align="center">
  <img src="logo.png" alt="HAIGS-Fuchslogo" width="150">

  <h1>HAIGS</h1>
  <p><strong>Home Assistant Import · Git Storage</strong></p>
  <p><em>Deine Forge. Deine Regeln.</em></p>

  <p>
    GitLab-, Forgejo- und Gitea-Repositories als nativer Home-Assistant-Store.
    Selbst gehostete Projekte entdecken, installieren und aktualisieren – ohne HACS zu ersetzen oder zu forken.
  </p>

  <p>
    <a href="https://chance-konstruktion.github.io/ha-haigs/"><strong>Die HAIGS-Website ansehen →</strong></a>
    ·
    <a href="docs/features.md">Funktionsübersicht</a>
    ·
    <a href="https://github.com/Chance-Konstruktion/ha-haigs/releases">Veröffentlichungen</a>
  </p>

  <p>
    <img alt="Neueste Veröffentlichung" src="https://img.shields.io/github/v/release/Chance-Konstruktion/ha-haigs?display_name=tag&style=flat-square&color=fc6d26">
    <img alt="Lizenz" src="https://img.shields.io/github/license/Chance-Konstruktion/ha-haigs?style=flat-square">
    <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2025.2%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white">
    <img alt="HACS" src="https://img.shields.io/badge/HACS-kompatibel-18BCF2?style=flat-square">
  </p>
  <p>
    <a href="README.md">🇬🇧 English documentation</a>
  </p>
</div>

---

**HAIGS bringt einen Store für Home Assistant zu Repositories, die außerhalb von GitHub leben.** Die Integration verbindet GitLab, Forgejo und Gitea – öffentlich oder selbst gehostet – und bündelt Entdeckung, Installation und Updates in einer vertrauten Oberfläche.

HAIGS ist eine eigenständige Integration. Sie läuft **parallel zu HACS**, ist kein Fork und verändert keinen HACS-Code.

## Was HAIGS mitbringt

| Funktion | Was sie macht |
| --- | --- |
| **Mehrere Git-Schmieden** | Beliebig viele GitLab-, Forgejo- und Gitea-Instanzen verbinden. Der Anbieter wird automatisch erkannt oder explizit gewählt. |
| **Repository-Entdeckung** | Projekte über das Topic \`hacs\`, Gruppen oder Stichwörter finden. Vor dem Angebot prüft HAIGS die \`hacs.json\`. |
| **Eigene Repositories** | Repository-URL direkt eintragen und HACS-Kategorie festlegen. |
| **Updates** | Eine Home-Assistant-Update-Entity je Repository. Releases haben Vorrang, Tags dienen als Rückfall. Vorabversionen sind optional. |
| **Entwicklermodus** | Auf Wunsch den neuesten Stand des Standardzweigs installieren – je Forge-Instanz einstellbar. |
| **Vertrauter Store** | Native Home-Assistant-Seitenleiste, Suche, Filter, Gruppierung, Repository-Details, README und Release-Notizen. |
| **Optionaler HACS-Katalog** | Den offiziellen HACS-Katalog als zusätzliche Quelle im selben Store einbinden. |
| **Saubere Deinstallation** | Installierte Dateien werden nachverfolgt. Beim Entfernen löscht HAIGS gezielt die eigenen Dateien statt gemeinsamer Ordner. |

## Installation

**Empfohlen: Installation über HACS.**

[![Home Assistant öffnen und dieses Repository in HACS hinzufügen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chance-Konstruktion&repository=ha-haigs&category=integration)

1. In HACS **Benutzerdefinierte Repositories** öffnen und  
   \`https://github.com/Chance-Konstruktion/ha-haigs\` als **Integration** hinzufügen.
2. **HAIGS** herunterladen und Home Assistant neu starten.
3. **Einstellungen → Geräte & Dienste → Integration hinzufügen** öffnen und **HAIGS** auswählen.
4. Forge-Host eintragen (zum Beispiel \`gitlab.com\`, \`codeberg.org\`, \`gitea.com\` oder einen eigenen Server). Den Anbieter auf **Auto** lassen, sofern du ihn nicht manuell wählen möchtest.
5. Für jede weitere Forge-Instanz einen eigenen HAIGS-Konfigurationseintrag anlegen.

[![Home Assistant öffnen und die HAIGS-Einrichtung starten.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=haigs)

**Voraussetzungen:** Home Assistant 2025.2 oder neuer. Für öffentliche Repositories ist normalerweise kein Token nötig. Private Repositories benötigen ein Token mit Leserechten (GitLab: \`read_api\`; Gitea/Forgejo: Lesezugriff auf das Repository). HAIGS begrenzt den Authorization-Header auf den konfigurierten Forge-Host; Release-Anhänge anderer Hosts erhalten das Token nicht.

**Manuelle Installation:** Archiv von der [Releases-Seite](https://github.com/Chance-Konstruktion/ha-haigs/releases) herunterladen, nach \`config/custom_components/haigs\` entpacken und Home Assistant neu starten.

## Für Repository-Betreiber

Damit ein Projekt entdeckt werden kann:

1. Das Topic \`hacs\` zum Repository hinzufügen.
2. Eine gültige \`hacs.json\` im Standardzweig ablegen. Beispiel:

   \`\`\`json
   {
     "name": "My integration",
     "render_readme": true,
     "homeassistant": "2025.2.0"
   }
   \`\`\`

3. Releases oder Tags veröffentlichen. Das übliche HACS-Verzeichnislayout \`custom_components/<domain>/\` wird unterstützt. Hat ein Release genau einen ZIP-Anhang, bevorzugt HAIGS dieses Paket; andernfalls wird das Tag-Archiv verwendet.

Kategorie-Topics wie \`hacs-plugin\` und \`hacs-theme\` legen die Repository-Kategorie fest. Weitere Layouts und Metadaten stehen in der [Funktionsübersicht](docs/features.md#for-repository-owners).

## Sicherheit bei der Installation

HAIGS behandelt Archive als nicht vertrauenswürdige Eingabe und prüft sie, bevor Dateien geschrieben werden. Der Kern weist Pfad-Ausbrüche und absolute Pfade, unsichere ZIP-Eintragstypen, doppelte Namen und verschlüsselte Einträge zurück. Er begrenzt Dateianzahl und entpackte Gesamtgröße, bereitet Änderungen in einem Zwischenbereich vor und rollt bei einem Fehler den Austausch zurück.

Das schützt den **Installationsvorgang**. Der heruntergeladene Python- oder JavaScript-Code wird dadurch weder auditiert noch isoliert oder zertifiziert. Installiere nur Repositories, denen du vertraust.

## Entwicklung

Der Kern lässt sich ohne Home-Assistant-Installation testen:

\`\`\`bash
python -m pytest -q
\`\`\`

Die Home-Assistant-Integrationstests laufen mit installiertem Custom-Component-Test-Plugin:

\`\`\`bash
python -m pytest tests_ha -q -p pytest_homeassistant_custom_component
\`\`\`

Zusätzlich enthält das Projekt Live-Tests mit temporären Gitea- und Forgejo-Instanzen. [ARCHITEKTUR.md](ARCHITEKTUR.md), [CHANGELOG.md](CHANGELOG.md) und [MITARBEIT.md](MITARBEIT.md) dokumentieren Architekturentscheidungen, Änderungshistorie und Mitarbeit.

## Projektlinks

- [Website](https://chance-konstruktion.github.io/ha-haigs/)
- [Funktionsübersicht](docs/features.md)
- [Änderungshistorie](CHANGELOG.md)
- [Fehler melden und Fragen stellen](https://github.com/Chance-Konstruktion/ha-haigs/issues)
- [Veröffentlichungen](https://github.com/Chance-Konstruktion/ha-haigs/releases)

## Lizenz

[MIT](LICENSE) — Copyright © 2026 Chance-Konstruktion und die HAIGS-Mitwirkenden.

---

<div align="center">
  <sub>Gebaut für Freiheit – und für die Projekte, die du selbst hostest.</sub>
</div>
