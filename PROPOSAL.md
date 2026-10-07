# Ein zweiter Anbieter für HACS — ein Vorschlag

> Dieses Dokument ist die nach außen gerichtete Ausarbeitung der Forge-Naht,
> auf der HAIGS läuft. Es wendet sich an die Leute, die
> [HACS](https://github.com/hacs/integration) betreuen. Die Entscheidung, ob
> er wirklich upstream eingereicht wird, gehört dem Besitzer des Repositories —
> dieses Dokument ist das Material für diese Entscheidung, nicht die
> Entscheidung selbst.
>
> Alles hier Beschriebene ist in diesem Repository umgesetzt und getestet,
> gegen GitLab und Forgejo (Referenz-Instanz: codeberg.org), mit
> aufgezeichneten, byte-genauen Antwort-Fixtures in `tests/`.

## Die Fassung in einem Satz

HACS spricht genau eine Forge an. Wir schlagen vor, daraus eine *Naht* zu
machen — eine kleine Schnittstelle mit einer GitHub-Implementierung —, damit
ein zweiter Anbieter (GitLab, Forgejo) eine Implementierung wird, kein Fork.

## Warum es das gibt

Jeder Home-Assistant-Nutzer, der heute Custom Components auf einer GitLab- oder
Forgejo-Instanz hält, installiert von Hand und hört nie von Updates. Es gibt in
HACS keinen Schalter für eine Nicht-GitHub-Quelle; die Quelle ist in die
Maschinerie eingewoben. Das Ergebnis ist ein Ökosystem-Merkmal, das nur eine
Forge liefern kann — und eine lange Geschichte von Forks, die HACS-Releases
hinterherjagen und sterben.

HAIGS existiert, weil wir das Merkmal *jetzt* brauchten, ohne Fork. Es läuft
als eigene Integration neben HACS. Beim Bauen wurde die Form der Naht klar —
und genau diese Form ist es, die dieser Vorschlag zurückgibt.

## Die Naht

Acht Methoden. Das ist die ganze Anbieter-Fläche, hinter der alles
Forge-Wissen wohnt:

| Methode | Was sie beantwortet | GitHub-Entsprechung |
|---|---|---|
| `repository(path)` | Stammdaten für `owner/name` | `GET /repos/{owner}/{repo}` |
| `repository_by_id(id)` | Stammdaten über die stabile Anbieter-ID | `GET /repositories/{id}` |
| `releases(path)` | veröffentlichte Versionen, neueste zuerst | `GET /repos/…/releases` |
| `tags(path)` | Tags als Rückfall, wenn es keine Releases gibt | `GET /repos/…/tags` |
| `file(path, name, ref)` | den Inhalt einer Datei an einem Ref | `GET /repos/…/contents/…` |
| `archive(path, ref)` | das Quell-Archiv einer Version | codeload-ZIP |
| `archive_url(path, ref)` | die Adresse des Archivs (für Menschen, Browser) | — |
| `search_by_topic(topic, group, subgroups)` | alles, was die Besitzer getaggt haben | Suche + `topic:`-Filter |

Zwei Datenklassen überqueren die Naht: `RepositoryInfo` (Identität,
Beschreibung, Topics, Sterne, Archiv-Flag, Web/Ticket/Release-URLs) und
`Release` (Tag, Name, Notizen, Datum, Prerelease-Flag, Assets). Eine
`NotFound`-Ausnahme heißt „weg oder Rechte fehlen“; alles andere ist ein
schlichter Forge-Fehler. Der Kern von HAIGS kennt keine Status-Codes, keine
HTTP-Bibliothek und kein `if provider == "gitlab"` — ein Wächter-Job in der CI
kippt den Bau bei jedem Anbieter-Sonderfall außerhalb der Anbieterklasse.

## Die Identitäts-Regel, die es haltbar macht

Ein Repository ist **nicht** sein Name. Es ist Anbieter + Host + Anbieter-ID.
Der Name ist Anzeige. Projekte werden umbenannt; Pfade werden wiederverwendet;
ein an `owner/name` aufgehängter Eintrag bricht still, genau wenn der Nutzer
nicht hinschaut. Auf die ID aufgehängt, ist eine Umbenennung ein Ereignis,
kein Verlust: Der nächste Herzschlag fragt `repository_by_id`, bekommt den
neuen Namen und folgt ihm — Entities und Installations-Zustand bleiben, wo
sie sind. (Das ist umgesetzt und getestet; es ist das Wertvollste, was wir
gelernt haben.)

Der Anzeige-Name trägt den Anbieter als Nachsilbe — `foo/bar*lab` für GitLab —,
nur von HAIGS erzeugt, nie zur Forge zurückgeschrieben. Zwei Repositories
mit demselben Namen auf verschiedenen Forges koexistieren, ohne sich zu
stoßen, und ein GitHub-Repository, das zufällig auf `-lab` endet, wird nie mit
einem verwechselt: Die Quelle ist ein Feld im Datensatz, kein Teil der
Zeichenkette.

## Validierung ist Inhalt, nicht Absicht

Ein Topic ist eine Ansage; Metadaten sind eine Behauptung. HAIGS behandelt
beides als Eingaben, nicht als Urteile: Jeder Kandidat aus der Entdeckung geht
durch Inhalts-Validierung — `hacs.json` muss parsen und ein Objekt sein,
verbotene Schlüssel werden abgelehnt, `manifest.json` muss strukturell gesund
sein (Domain, Name, Version, Codeowners), die Version muss existieren, bevor
ein Update angeboten wird. Die Abnahme-Idee überträgt sich direkt: Ein
upstream-HACS, das einen zweiten Anbieter wachsen lässt, wird dieselbe
Validierung vor jeder Installation wollen — weil eine Forge, die er nicht
kontrolliert, irgendwann Mühl liefert.

## Was HACS ändern müsste

1. **Jeden Repository-Zugriff durch die Naht leiten.** Die acht Methoden
   oben, eine `GitHubForge`-Implementierung. Das heutige Verhalten bleibt
   byte-identisch; die Änderung ist mechanisch, und der Wächter gegen
   Sonderfälle ist ein CI-Grep.
2. **Den Laden auf Anbieter + Host + ID aufhängen, den Namen anzeigen.** Eine
   Migration des bestehenden Ladens ist ein einmaliger ID-Abruf je Eintrag.
3. **Bei Custom Repositories einen optionalen Anbieter/eine Instanz
   akzeptieren.** Die UI-Frage — „URL einfügen, wir erkennen die Forge“ — ist
   genau das, was der Einrichtungs-Dialog von HAIGS schon tut (ein
   eingefügter Projekt-Link wird auf seinen Host gekürzt).
4. **Entdeckung je Forge belassen.** GitHub-Topics sind der bestehende
   Mechanismus; GitLab hat Topics, Forgejo hat Topics. `search_by_topic` ist
   die Naht, und jede Forge beantwortet sie ehrlich.

Was HACS *nicht* ändern müsste: Kategorie-Behandlung, die Download-Konventionen
(`content_in_root`, `zip_release`, `filename`), die Update-Maschinerie, das
Laden-Format der Einträge jenseits des Identitäts-Schlüssels.

## Was wir bewusst weggelassen haben

- **Kein Schreib-Zugriff auf irgendeine Forge.** Die Schnittstelle ist
  nur lesend. Sterne, Issues, Releases: nie geschrieben.
- **Kein kuratierter Katalog.** Der Standard-Katalog von HACS lebt auf GitHub
  als kuratierter Inhalt; der Katalog eines zweiten Anbieters ist eine
  Frage der Ordnungspolitik, keine Frage der Naht. Wir arbeiten mit Custom
  Repositories und Topic-Entdeckung.
- **Keine Rate-Limit-Gleichschaltung.** Jede Forge hat eigene Limits und
  eigenes ETag-Verhalten. Die Naht hält Anbieter-Wissen in der
  Anbieterklasse; Kontingente gleichzuschalten steht außerhalb.
- **Keine Auslieferung von HACS selbst.** HAIGS ist keine
  HACS-Distribution und will keine werden.

## Kosten und Risiken, ehrlich

- **Pflege.** Ein zweiter Anbieter ist für immer ein zweiter Satz
  aufgezeichneter Fixtures, API-Eigenheiten und Bruchberichte. Die Naht hält
  den Wirkungskreis klein (eine Datei je Anbieter), aber die Fläche ist für
  immer nicht null.
- **Auseinanderlaufen.** GitLabs Archiv-Endpunkte, Topic-Suche und
  Release-Assets weichen im Detail von GitHubs ab. Wir glätten an der Naht
  (GitLab-Tag-Archive hüllen den Inhalt in einen Wurzelordner — die
  Archiv-Verbraucher der Naht beherrschen je Anbieter genau so eine
  Konvention).
- **Sicherheits-Fläche.** Aus einer Forge zu installieren, die man nicht
  kontrolliert, erhöht die Anforderungen ans Entpacken. Wir behandeln das
  als unverhandelbar: Wächter gegen Pfad-Flucht, Größe, Anzahl und Symlinks
  mit vier böswilligen Test-Archiven in der Suite, Installationen erst
  aufgebaut, dann atomar gewechselt, bei Scheitern zurückgerollt. Eine
  upstream-Übernahme sollte nicht weniger verlangen.
- **Identität ist der harte Teil, nicht die Verrohrung.** Die API-Aufrufe
  sind leicht. Die Laden-Migration und die Semantik „Umbenennung ist ein
  Ereignis“ sind dort, wo die Entwurfs-Arbeit hinging — und wo der Wert liegt.

## Zwei Wege, wie es laufen kann

**Upstream eingereicht.** Die Naht-Beschreibung oben, die Identitäts-Regel und
die Validierungs-Haltung sind die Teile, die sich zu übernehmen lohnen. Der
Code ist kein Einsetzen (andre Lizenz-Herkünfte, andre innere Strukturen) —
aber der Entwurf ist ein arbeitender, getesteter Existenz-Beweis aus zwei
lebenden Anbietern.

**Eigenständig, dauerhaft.** HAIGS bleibt eine schlanke
Begleit-Integration neben HACS. Das ist der kleinere Ökosystem-Beitrag, aber
einer ohne jede Abstimmung: Er funktioniert heute, gegen echte GitLab- und
Codeberg-Instanzen, und nichts an ihm wartet auf die Fahrkarte von upstream.

Der Besitzer des Repositories entscheidet. Beide Zukünfte sind ehrlich.

---

*Dieses Dokument gehört zum HAIGS-Meilenstein M10 („Nach draußen“). Die
Entwicklungs-Dokumentation — [ARCHITEKTUR.md](ARCHITEKTUR.md) für die fünf
Struktur-Entscheidungen, [ROADMAP.md](ROADMAP.md) für Meilensteine und
Abnahmen — trägt das ganze Denken hinter allem, was hier behauptet wird. Die
englische Fassung dieses Vorschlags gehört zum späteren GitHub-Auftritt und
liegt bis dahin in der Git-Geschichte verwahrt.*
