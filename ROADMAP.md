# Fahrplan HAIGS

Ohne Zeitangaben. Die Reihenfolge ist die Abhaengigkeit, nicht der
Kalender. Jede Stufe hat ein Ziel, einen Umfang und eine **Abnahme** --
solange die Abnahme nicht erfuellt ist, gilt die Stufe als offen.

Grundregeln, die fuer jede Stufe gelten:

* **Kein Fork von HACS.** HAIGS ist eine eigene Integration neben
  HACS. Nichts in diesem Repo ist eine geaenderte Kopie von HACS-Code.
* **Kein `if provider == "gitlab":` im Ablauf.** Anbieterwissen steckt
  hinter `custom_components/haigs/core/forge.py`, sonst nirgends.
* **Der Kern bleibt frei von Home Assistant.** Alles unter
  `custom_components/haigs/core/` laeuft ohne HA und ist ohne Netz
  testbar (Form-Entscheidung zu #11).
* **Jede Stufe endet gruen.** Neue Funktion ohne Test ist keine
  fertige Stufe.

---

## M0 -- Fundament (erledigt)

**Ziel:** Die Begriffe stehen, bevor Code darauf gebaut wird.

* `identity.py` -- `RepositoryIdentity`, `uid`, `storage_key`,
  `display_full_name` mit `*lab`
* `forge.py` -- Schnittstelle, `RepositoryInfo`, `Release`, Fehlerarten
* `gitlab_forge.py` -- GitLab REST v4: Projekt, Releases, Tags, Datei,
  Archiv-Adresse, Topic-Suche
* `validierung.py` -- `hacs.json` und `manifest.json`
* `versionen.py` -- Vergleich, Vorabversionen, Update-Entscheidung
* `entdeckung.py` -- Topic -> Kandidat -> Pruefung -> Fund
* CI mit ruff und pytest

**Abnahme:** 41 Tests gruen, Pipeline gruen.

---

## M1 -- Echter HTTP-Zugang (erledigt)

**Ziel:** Der Kern spricht mit einer echten GitLab-Instanz.

* `haigs/http_aiohttp.py`: Umsetzung von `HttpClient` auf der
  aiohttp-Sitzung von Home Assistant
* Uebersetzung der Statuscodes in `NichtGefunden` / `ForgeFehler`
  (404 -> `NichtGefunden`, 401/403 -> eigene Meldung mit Klartext
  "Token fehlt oder reicht nicht", 429 -> Wartezeit beachten)
* Token optional: oeffentliche Projekte gehen ohne, private brauchen
  einen Lesetoken (`read_api`)
* Seitenweises Abholen (`X-Next-Page`), damit eine Instanz mit vielen
  Projekten nicht nach 100 Treffern abbricht
* Zwischenspeicher: `ETag` / `If-None-Match`, damit ein Update-Lauf
  ueber viele Repos nicht jedes Mal alles neu holt

**Abnahme:** Tests gegen eine Aufzeichnung echter Antworten (keine
Netzanfrage in der CI). Zusaetzlich ein Handlauf gegen
`gitlab.schanz.ipv64.net` mit protokolliertem Ergebnis im MR.

---

## M2 -- Home-Assistant-Geruest (erledigt)

**Ziel:** Die Integration laesst sich installieren und einrichten.

* `custom_components/haigs/`: `manifest.json`, `__init__.py`,
  `const.py`, `config_flow.py`, `strings.json` + `translations/de.json`
* Einrichtungsdialog: Host, optionaler Token, Pruefverbindung
  (schlaegt fehl mit verstaendlicher Meldung, nicht mit Stacktrace)
* Mehrere Instanzen nebeneinander (gitlab.com **und** die eigene) --
  darum steckt der Host in `storage_key`
* Ablage ueber `homeassistant.helpers.storage.Store`, Version 1,
  Migrationsfunktion von Anfang an vorgesehen
* `DataUpdateCoordinator` mit einstellbarem Abstand

**Abnahme:** Integration laesst sich in einer HA-Testinstanz
hinzufuegen und wieder entfernen; `config_flow`-Tests mit
`pytest-homeassistant-custom-component`.

---

## M3 -- Custom Repository hinzufuegen (erledigt)

**Ziel:** Das, was HACS mit GitHub kann, mit einer GitLab-Adresse.

* Eingabe der vollen Adresse (`https://host/gruppe/projekt`), daraus
  Host + Pfad, daraus ueber die API die Identitaet
* Kategorie waehlen (Vorbelegung aus `hacs-<kategorie>`-Topic)
* Validierung vor dem Anlegen; bei Fehlern zeigen, **was** fehlt
* Eintrag speichern; doppelte `storage_key` werden abgewiesen
* Entfernen eines Eintrags (mit und ohne Deinstallation der Dateien)

**Abnahme:** Ein Repository aus der eigenen Instanz erscheint als
`gruppe/projekt*lab` in der Liste, ueberlebt einen HA-Neustart, und
ein gleichnamiges GitHub-Repo verdraengt es nicht.

---

## M4 -- Installation und Deinstallation (erledigt)

**Stand:** M4a (Entpacken und Zielpfade, MR !3, Issue #12) ist
erledigt. M0.5 -- die Auslieferungsform -- ist entschieden und umgesetzt
(Issue #11): der Kern wohnt in der Integration, relative Importe, kein
Suchpfad-Griff. M4b (Issue #4) ist geliefert: Release-Anhang als
bevorzugte Quelle (eindeutig, sonst Tag-Archiv), verzeichneter Zielweg
in der Ablage, Deinstallation genau diesen Weg entlang, Neustart-Hinweis
bei Integrationen aufs Reparatur-Brett -- Dogfood-Beweis mit dem eigenen
Release-ZIP in der HA-Bahn.

**Ziel:** Dateien landen an der richtigen Stelle.

* Quelle: Release-Anhang, sonst Archiv des Tags
* Zielpfade je Kategorie (`custom_components/<domain>/`,
  `www/community/<name>/`, `themes/`, `python_scripts/` ...)
* `hacs.json`-Felder beachten: `content_in_root`, `filename`,
  `zip_release`
* Entpacken **sicher**: keine Pfade ausserhalb des Ziels, Groessen- und
  Anzahlgrenze, keine Symlinks
* Erst in ein Zwischenverzeichnis, dann tauschen -- ein Abbruch darf
  keine halbe Installation hinterlassen
* Deinstallation raeumt genau das weg, was installiert wurde
* Neustart-Hinweis fuer Kategorien, die einen brauchen

**Abnahme:** Tests mit gebauten Zip-Dateien, darunter mindestens drei
boesartige (Pfadausbruch, Riesendatei, Symlink). Eine echte
Integration aus dem eigenen GitLab laeuft nach der Installation in HA.

---

## M5 -- Update-Erkennung (erledigt)

**Ziel:** Der eigentliche Zweck: neue Releases fallen auf.

* Periodischer Lauf ueber alle Eintraege, Abstand einstellbar
* Je Eintrag eine `update`-Entity: installierte Version, neueste
  Version, Release-Notizen, `install`-Dienst
* Schalter je Eintrag: Vorabversionen mitnehmen
* Rueckfallebene Tags, wenn ein Projekt keine Releases pflegt
* Fehler eines Repos darf den Lauf der anderen nicht abbrechen

**Abnahme:** Ein neues Release im GitLab erscheint ohne Zutun in HA;
`versionen.py` bleibt die einzige Stelle, die vergleicht.

---

## M6 -- Entdeckung ueber Topics (erledigt)

**Ziel:** Nicht nur einzeln hinzufuegen, sondern finden.

* Quelle eintragen: ganze Instanz oder Gruppe (mit Untergruppen)
* Scan nach Topic `hacs`, danach die Pruefung aus M0
* Ergebnisliste mit Beschreibung, Sternen, offenen Tickets, letzter
  Version
* `hacs-development` bleibt aussen vor, ausser man will es
* Der Scan schreibt nichts -- Aufnahme bleibt eine Entscheidung des
  Benutzers

**Abnahme:** Eine Gruppe mit gemischten Projekten (mit Topic, ohne
Topic, mit Topic aber ohne `hacs.json`) liefert genau die richtigen
Treffer.

---

## M7 -- Oberflaeche (erledigt)

**Ziel:** Bedienung wie im HACS-Store, nur eben mit `*lab`.

* Eigenes Panel: installierte Eintraege, verfuegbare Eintraege, Suche,
  Sortierung nach Sternen und Datum
* Detailansicht: README gerendert, Verweise auf Repository, Tickets,
  Releases
* Die `*lab`-Kennzeichnung ueberall dort, wo ein Name steht
* Deutsche und englische Uebersetzung

**Abnahme:** Ein Durchgang ohne YAML: hinzufuegen, installieren,
aktualisieren, entfernen -- alles ueber die Oberflaeche.

---

## M8 -- Bestand und Robustheit (erledigt)

**Ziel:** Es haelt auch, wenn etwas schiefgeht.

* Diagnose-Ausgabe (`diagnostics`) ohne Token im Klartext
* `repairs`-Meldungen: Token abgelaufen, Repository verschwunden,
  Kategorie passt nicht mehr
* Speicher-Migration, falls sich das Format aendert
* Verhalten bei umbenannten Projekten: die `provider_id` traegt, der
  Name wird nachgezogen
* Verhalten bei nicht erreichbarer Instanz: alte Daten behalten,
  Fehler melden, nicht loeschen

**Abnahme:** Tests fuer jeden dieser Faelle; kein Token in Logs oder
Diagnose.

---

## M9 -- Dritter Anbieter (erledigt)

**Ziel:** Der Beweis, dass die Schnittstelle traegt.

* `forgejo_forge.py` (Codeberg) als dritte Umsetzung
* Kein Eingriff in Ablauf, Speicher oder Oberflaeche noetig -- wenn
  doch, ist die Schnittstelle falsch geschnitten und wird korrigiert
* Anzeige-Suffix je Anbieter erweitern

**Abnahme:** Codeberg-Repository laeuft durch denselben Ablauf;
Aenderungen ausserhalb des neuen Anbieters bleiben klein und benannt.

**Nachtrag Flug 2088:** der vierte Anbieter (`gitea_forge.py`, Tochter
der Forgejo-Umsetzung) und die Schmiede (`schmiede.py`, Formung und
Auto-Erkennung im Einrichtungsdialog) wiederholten den Beweis: Gitea
brachte zwei Stueck Eigenes mit (Name und Such-Parameter), der Ablauf
blieb unberuehrt. Der Eintrag fehlt absichtlich oben: er ist kein
Meilenstein, sondern die Wiederholung eines bestandenen.

---

## M10 -- Nach draussen (erledigt)

**Ziel:** Nicht nur bei uns nuetzlich.

* Eigenes `hacs.json` und Release-Prozess fuer HAIGS selbst
* README auf Englisch, Installationsweg von Hand beschrieben
  (HACS selbst kann uns nicht ausliefern -- es kennt nur GitHub)
* Die Forge-Schnittstelle als Vorschlag aufbereiten: was HACS
  uebernehmen muesste, damit ein zweiter Anbieter moeglich wird
* Entscheidung dann: Vorschlag einreichen oder eigenstaendig bleiben

**Abnahme:** Ein Fremder kann HAIGS nach der README installieren und
ein GitLab-Repository hinzufuegen, ohne zu fragen.

---

## Was ausdruecklich nicht geplant ist

* **Kein Nachbau des HACS-Katalogs.** Der Standardkatalog liegt selbst
  auf GitHub. HAIGS arbeitet mit Custom Repositories und
  Topic-Entdeckung, nicht mit einer kuratierten Liste.
* **Kein Umbenennen im GitLab.** `*lab` entsteht in der Erweiterung.
* **Keine Schreibzugriffe auf die Forge.** HAIGS liest.
