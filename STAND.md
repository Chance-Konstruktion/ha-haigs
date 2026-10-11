# HAIGS — Der Stand

> Stand: 2026-09-20 (GitHub-Auftritt) — alles Wichtige auf einer Seite.

## Das Projekt in einem Satz

HACS-Erweiterung für self-hosted GitLab + Gitea/Codeberg/Forgejo: Custom-Repos
installieren, Updates erkennen — ein echtes Produkt für den Imker-Server
(`gitlab.schanz.ipv64.net`, Projekt `chance-konstruktion/haigs`, ID 107; bis 11.10.2026 `hacs-lab`).

## Was wo liegt

| Ort | Inhalt |
|---|---|
| `main` (f642366) | Amtssprache Deutsch + Härte + drei Wunden + Markenbild + Sichtbarkeit — MR !31–!35 alle gemergt |
| Version | manifest `0.3.0`, **Tag steht noch aus** (letzter Release: v0.1.1); Tag-Pipeline baut ZIP deterministisch + Paket-Registry |
| Tests | 369 Kern- (tests/) + 127 HA-Tests (tests_ha/), ruff + Struktur-Wächter in CI |
| `super-z/ha-bienentanz` | Test-Integration, jetzt **v1.3.0** mit Einrichtungsdialog (Release + Tag) |

## Was bewiesen ist

- **Generalprobe (Flug 2095/2096 WABEN): ALLES GRÜN** auf echter Bühne —
  HA 2026.2.3 Kaltstart, ZWEI echte Server (10 GitLab-Funde + 7 Codeberg-Funde),
  bienentanz v1.2.0 sauber installiert, Panel/Fußzeile/Suche/Detail bewiesen
  (Screenshots `flug2095-*.png`).
- **Die drei Wunden (MR !33, gemergt)** — README-Tabellen als Rohtext, doppelte
  Gesichter, wackelnde Installationen: alle drei geheilt und auf echter Bühne
  bewiesen (espeasy-p2p ✓ powerline ✓ vistapool ✓, Screenshots `flug2096-*.png`).
- **Die Sichtbarkeit (MR !35, Flug 2098)** — der Imker-Befund «installierte Repos
  unter Geräte & Dienste nicht zu finden» ist vollständig seziert und geheilt:
  1. **Physik:** HA scannt `custom_components` erst beim Start; die Karte unter
     Geräte & Dienste entsteht erst durch den Konfigurationseintrag; Integrationen
     ohne `config_flow` (bienentanz v1.2.0!) können dort PRINZIPIELL nie erscheinen.
  2. **Heilung:** Zustands-Chip je Karte (Neustart erforderlich → In Geräte &
     Dienste einrichten [Knopf] → Eingerichtet; dazu YAML-Weg und Rot fürs
     Nichtgeladene), dauerhafte Benachrichtigung mit derselben Anleitung,
     Lager erfährt die Installation sofort (Version + Zielweg).
  3. **Beweis:** 4 Phasen auf echter Bühne mit 2 Neustarts — v1.2.0 unfindbar
     (Chip «yaml», die Wurzel), v1.3.0 mit Dialog → Flow läuft → KARTE LEBT →
     Chip «eingerichtet» (Screenshots `flug2098-1/2/3.png`).

## Der GitHub-Auftritt (20.09.2026)

M10 sagt „Ein Fremder kann HAIGS nach der README installieren, ohne zu
fragen“ — dafür fehlten drei Stücke, die jetzt liegen:

- **[README.en.md](README.en.md)** — die englische Fassung auf heutigem Stand
  (Flug 2096/2097/2098 eingearbeitet), verlinkt von der deutschen Seite. Die
  Amtssprache bleibt Deutsch (Issue #16): Bezeichner, Commits und die
  Denk-Dokumente rühren wir nicht an.
- **Der Fehlerweg zeigt nach draußen** — `manifest.json` nennt jetzt GitHub
  als `issue_tracker` und `documentation`. Auf dem GitLab kann sich niemand
  von außen anmelden (`/users/sign_up` leitet auf den Login), ein
  Fehlerbericht wäre dort ins Leere gelaufen.
- **Der Versions-Sprung auf `0.3.0`** — das Manifest sagte `0.2.0`, der
  letzte Release war aber **v0.1.1**. HACS installiert aus Releases, nicht
  aus dem Zweig; wer uns drüben findet, hätte alten Code bekommen.
  Der Download-Weg in beiden READMEs zeigt jetzt auf die GitHub-Releases
  (die GitLab-Package-Registry steht als zweiter Weg daneben, die Bytes sind
  dieselben — der Bau ist deterministisch).

- **Der Release kommt drüben auch an** — neuer Job `github-verkuendigung`
  (`auslieferung/github_verkuenden.py`, 7 Tests). Die Spiegelung schiebt
  Commits und Tags, aber ein GitLab-Release ist ein GitLab-Objekt; drüben
  entstünde daraus nichts, und die README zeigte auf eine Release-Seite ohne
  das versprochene Archiv. Der Job legt den Eintrag an **und hängt das
  gebaute ZIP an** — das kann die Vorlage in `claude/ci-vorlagen` nicht, sie
  trägt nur ein. Ohne `GITHUB_TOKEN` sagt er das und bleibt grün.

**Erledigt am 20.09.2026 — die Kette steht:** Repo
[Chance-Konstruktion/ha-haigs](https://github.com/Chance-Konstruktion/ha-haigs)
(öffentlich), Push-Spiegel 16 (nur geschützte Zweige), `GITHUB_TOKEN` maskiert
und `GITHUB_REPO=ha-haigs` als CI-Variablen, Tag `v0.3.0` gesetzt. Die
Tag-Pipeline 10836 lief grün durch: ZIP gebaut, GitLab-Release eingetragen,
GitHub-Release angelegt **mit dem Archiv daran** (136 KB).

**Der Name drüben weicht ab, und das ist Absicht.** Das GitLab-Projekt heißt
seit 11.10.2026 `chance-konstruktion/haigs` (vorher `hacs-lab`; der alte Pfad
leitet um). Chris: HAIGS ist kein HACS-Partner mehr, sondern Konkurrenz — ein
Name überall. Auf GitHub heißt es `ha-haigs`, passend zur ha-Familie
(ha-powerline, ha-kontinuum, ha-spatial-…). `GITHUB_REPO` ist die einzige
Stelle, an der dieser Unterschied steht; ein Test hält sie fest. Den Stern
kann GitHub ohnehin nicht: erlaubt sind dort nur Buchstaben, Ziffern, `.`,
`-` und `_`.

## Nächste Schritte (Reihenfolge)

1. ~~MR !35 mergen~~ — erledigt (06.09., Pipeline 4143 grün auf `main`).
2. Integrationen, die unter Geräte & Dienste fehlen sollen: prüfen, ob ihre
   manifest.json `config_flow: true` sagt (sonst YAML-Weg — der Chip sagt es).
3. **v0.3.0-Schnitt** — Manifest steht auf `0.3.0`, der Tag fehlt noch
   (Imker-Entscheidung; Tag-Pipeline baut und veröffentlicht den Release
   selbst).
4. GitHub-Repo + Push-Spiegel, siehe oben.

## ⚠ Termine, die wehtun

- **GitLab-Token (id 44) ist am 2026-09-08 abgelaufen — die Frist ist
  verstrichen.** Was daran hing, hängt jetzt in der Luft: prüfen und einen
  neuen Token setzen. **Nicht** betroffen ist die Tag-Pipeline — `auslieferung`
  und `verkuendigung` laufen mit dem `CI_JOB_TOKEN`, der nur für den einen Lauf
  gilt. Der Release-Weg ist also frei.

## Arbeitsplatz (Biene)

- `repos/haigs` — Arbeitskopie (Zweig `flug-2098-geraete-sichtbar`, sauber)
- `repos/ha-bienentanz` — Beispiel-Integration für den Laden (**v1.3.0**, gepusht + Release)
- `repos/stock/WABEN.md` — Flugbuch des ganzen Volks (WABEN 2106)
- `e2e/` — echte HA-Testinstanz 2026.2.3 (VENV fällt Sandbox-Resets zum Opfer;
  Neubau: `uv venv --python /usr/bin/python3.13 venv && uv pip install homeassistant==2026.2.3`)
- `scripts/` — verbliebene Werkzeuge (E2E-Treiber: `e2e_geraete_sichtbar.py`
  [Phasen eins–vier], `e2e_kalt_2098.py` [Bühne kalt], HA-Start/Login)
- `repos/bienentanz` — LXM-Multi-Agent-Mesh (Flug 2101/2103, siehe eigenes README dort)

## Offene Wunden

Keine bekannten Code-Wunden offen. Die gemeldeten drei Praxistest-Wunden sind
gemergt (!33), die Sichtbarkeits-Wunde liegt in !35 ready. Nächste Erkenntnisse
kommen aus dem Praxistest nach dem Merge.
