/**
 * HAIGS Panel -- der Laden, gekleidet wie HACS.
 *
 * Geladen als ES-Modul ueber ``/haigs/panel.js``; das Frontend von
 * Home Assistant findet hier das Element ``haigs-panel`` und setzt
 * ``hass``, ``narrow`` und ``route``. Die Daten kommen ueber die
 * WebSocket-Befehle aus ``websocket_api.py`` (eintraege, erneuern,
 * detail, hinzufuegen, entfernen, deinstallieren) und den Dienst
 * ``update.install`` der update-Entities.
 *
 * Seit Flug 2100 baut das Panel auf denselben Bausteinen wie HACS
 * (Datentabelle, Markdown, Chips, Overflow-Menue) -- siehe den
 * Abschnitt «Flug 2100» weiter unten. Der Kopf der Datei haelt die
 * Texte beider Sprachen und den eigenen Markdown-Renderer, der nur
 * noch einspringt, wenn ``ha-markdown`` fehlt.
 *
 * Sicherheit: Der Markdown-Renderer flieht zuerst JEDES Zeichen und
 * baut danach erst Markup. Links und Bilder werden nur fuer
 * http(s)-Adressen gebaut, alles andere bleibt Text.
 */

const TEXTE = {
  de: {
    titel: "HAIGS",
    suche: "Suchen oder springen zu …",
    aktualisieren: "Liste aktualisieren",
    neu_knopf: "Neu hinzufügen",
    sortierung: "Sortierung",
    sort: { name: "Name", sterne: "Sterne", datum: "Datum" },
    anzahl: (n) => `${n} Repositor${n === 1 ? "y" : "ies"}`,
    abschnitte: {
      aktualisierbar: "Aktualisierbar",
      installiert: "Installiert",
      neu: "Neu",
      downloadbar: "Downloadbar",
    },
    abschnittstexte: {
      aktualisierbar: "Eine neuere Version ist erschienen",
      installiert: "Heruntergeladen und auf dem neuesten Stand",
      neu: "Was die Suche oben fand — noch nicht aufgenommen",
      downloadbar: "Beobachtet, aber noch nichts heruntergeladen",
    },
    abschnitte_leer: {
      aktualisierbar: "Nichts zu tun — alles auf dem neuesten Stand.",
      installiert: "Noch nichts heruntergeladen.",
      neu: "Noch keine Funde — oben suchen und Enter drücken.",
      downloadbar: "Nichts Beobachtetes ohne Download.",
    },
    stand: "Stand",
    suche_hinweis: "Eingrenzen beim Tippen — Enter fragt alle Instanzen",
    hinzufuegen: "Hinzufügen",
    entfernen: "Entfernen",
    deinstallieren: "Deinstallieren",
    installieren: "Installieren",
    update_install: "Aktualisieren",
    details: "Details",
    zurueck: "Zurück",
    instanzen_leer: "Keine Instanz eingerichtet — zuerst eine Instanz anlegen.",
    installiert_label: "installiert",
    neueste_label: "neueste",
    vorab: "Vorabversion",
    readme: "Beschreibung",
    readme_fehlt: "Dieses Projekt hat keine lesbare Beschreibung.",
    releases: "Releases",
    keine_releases: "Keine Releases — Tags zählen als Fallback.",
    repository: "Repository",
    tickets: "Tickets",
    releases_link: "Releases",
    sterne_ein: "Stern",
    sterne_viele: "Sterne",
    kategorie: "Kategorie",
    schon_da: "schon in der Liste",
    entfernt_hinweis: "Nur die Beobachtung — Dateien bleiben (Deinstallieren ist der eigene Knopf).",
    entfernen_frage: (name) =>
      `${name} entfernen? Installierte Dateien bleiben liegen.`,
    deinstalliert_hinweis:
      "Nimmt die installierten Dateien weg — bei Integrationen steht der nötige Neustart im Reparatur-Brett.",
    deinstallieren_frage: (name) =>
      `${name} deinstallieren? Die installierten Dateien werden entfernt.`,
    zustand: {
      neustart: "Neustart erforderlich",
      nicht_geladen: "Nicht geladen — Protokoll prüfen",
      eingerichtet: "Eingerichtet",
      hinzufuegen: "In Geräte & Dienste einrichten",
      yaml: "Einrichtung über configuration.yaml",
      ungewiss: "Weg unbekannt — neu installieren",
    },
    zustand_titel: {
      neustart:
        "Home Assistant lädt Integrationen erst beim Start — Einstellungen → System → Neu starten",
      nicht_geladen:
        "Der Ordner liegt da, aber Home Assistant hat die Integration nicht geladen — das Protokoll (Einstellungen → System → Protokolle) sagt warum",
      eingerichtet: "Die Integration ist eingerichtet — ihre Karte lebt unter Geräte & Dienste",
      hinzufuegen:
        "Öffnet Geräte & Dienste — dort «Integration hinzufügen» wählen und die Domain suchen",
      yaml: "Diese Integration hat keinen Einrichtungsdialog — „domain:” in die configuration.yaml notieren",
      ungewiss: "Installiert vor M4b — ohne verzeichneten Weg",
    },
    fehler: {
      unbekannte_instanz: "Diese Instanz ist nicht (mehr) eingerichtet.",
      nicht_gefunden: "Repository nicht gefunden — Adresse prüfen.",
      forge_fehler: "Die Instanz antwortet nicht richtig.",
      bereits_vorhanden: "Dieses Repository steht schon in der Liste.",
      kategorie_unbekannt: "Diese Kategorie gibt es nicht.",
      nicht_mehr_da: "Der Eintrag ist schon weg.",
      homeassistant_error: "Home Assistant meldet einen Fehler.",
      sonst: "Etwas ist schiefgegangen.",
    },
    scan_laeuft: "Suche läuft …",
    frisch_laeuft: "frischer Lauf …",
    fuss_zeile: "Für die Freiheit gebaut — deine Forge, deine Regeln.",
    lade_titel: "Wird geladen …",
    lade_text: "Der Bestand kommt aus dem Lager — einen Augenblick.",
    detail_lade_text: "Stammdaten, Beschreibung und Releases werden geholt.",
    instanzen_titel: "Instanzen",
    instanz_hinzufuegen: "Instanz hinzufügen",
    erste_instanz: "Erste Instanz einrichten",
    instanz_verwalten:
      "Instanz öffnen — Abstand, Custom Repositories, Entfernen",
  },
  en: {
    titel: "HAIGS",
    suche: "Search or go to …",
    aktualisieren: "Refresh list",
    neu_knopf: "Add new",
    sortierung: "Sort by",
    sort: { name: "Name", sterne: "Stars", datum: "Date" },
    anzahl: (n) => `${n} repositor${n === 1 ? "y" : "ies"}`,
    abschnitte: {
      aktualisierbar: "Updatable",
      installiert: "Installed",
      neu: "New",
      downloadbar: "Downloadable",
    },
    abschnittstexte: {
      aktualisierbar: "A newer version has been released",
      installiert: "Downloaded and up to date",
      neu: "What the search above found — not added yet",
      downloadbar: "Watched, but nothing downloaded yet",
    },
    abschnitte_leer: {
      aktualisierbar: "Nothing to do — everything is up to date.",
      installiert: "Nothing downloaded yet.",
      neu: "No findings yet — search above and press Enter.",
      downloadbar: "Nothing watched without a download.",
    },
    stand: "as of",
    suche_hinweis: "Narrow while typing — Enter asks every instance",
    hinzufuegen: "Add",
    entfernen: "Remove",
    deinstallieren: "Uninstall",
    installieren: "Install",
    update_install: "Update",
    details: "Details",
    zurueck: "Back",
    instanzen_leer: "No instance configured — set one up first.",
    installiert_label: "installed",
    neueste_label: "latest",
    vorab: "pre-release",
    readme: "Description",
    readme_fehlt: "This project has no readable description.",
    releases: "Releases",
    keine_releases: "No releases — tags count as fallback.",
    repository: "Repository",
    tickets: "Tickets",
    releases_link: "Releases",
    sterne_ein: "star",
    sterne_viele: "stars",
    kategorie: "Category",
    schon_da: "already on the list",
    entfernt_hinweis: "Only the watch — files stay in place (uninstall is its own button).",
    entfernen_frage: (name) => `Remove ${name}? Installed files stay in place.`,
    deinstalliert_hinweis:
      "Takes the installed files away — for integrations the required restart shows up in the repair center.",
    deinstallieren_frage: (name) =>
      `Uninstall ${name}? The installed files will be removed.`,
    zustand: {
      neustart: "Restart required",
      nicht_geladen: "Not loaded — check the log",
      eingerichtet: "Set up",
      hinzufuegen: "Set up in Devices & services",
      yaml: "Setup via configuration.yaml",
      ungewiss: "Unknown path — install again",
    },
    zustand_titel: {
      neustart:
        "Home Assistant loads integrations on startup only — Settings → System → Restart",
      nicht_geladen:
        "The folder is in place, but Home Assistant did not load the integration — the log (Settings → System → Logs) says why",
      eingerichtet: "The integration is set up — its card lives under Devices & services",
      hinzufuegen:
        "Opens Devices & services — choose “Add integration” there and search for the domain",
      yaml: "This integration has no setup dialog — put “domain:” into configuration.yaml",
      ungewiss: "Installed before M4b — no recorded path",
    },
    fehler: {
      unbekannte_instanz: "This instance is not configured (any more).",
      nicht_gefunden: "Repository not found — check the address.",
      forge_fehler: "The instance did not answer properly.",
      bereits_vorhanden: "This repository is already on the list.",
      kategorie_unbekannt: "Unknown category.",
      nicht_mehr_da: "Already removed.",
      homeassistant_error: "Home Assistant reported an error.",
      sonst: "Something went wrong.",
    },
    scan_laeuft: "Scanning …",
    frisch_laeuft: "fresh run …",
    fuss_zeile: "Made for freedom — your forge, your rules.",
    lade_titel: "Loading …",
    lade_text: "The stock is on its way from the store cache — one moment.",
    detail_lade_text: "Fetching metadata, description, and releases.",
    instanzen_titel: "Instances",
    instanz_hinzufuegen: "Add instance",
    erste_instanz: "Set up the first instance",
    instanz_verwalten: "Open instance — interval, custom repositories, remove",
  },
};

/** Sprache der Bedienung -- Deutsch, sonst Englisch. */
function sprache(hass) {
  const code = (hass && hass.locale && hass.locale.language) || "en";
  return String(code).toLowerCase().startsWith("de") ? "de" : "en";
}

/** Flieht jedes Zeichen, das Markup werden koennte. */
function fliehe(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** Nur absolute http(s)-Adressen duerfen Links oder Bilder werden. */
function adresse_ok(u) {
  return /^https?:\/\//i.test(String(u));
}

/** Inline-Markdown auf bereits GEFLOHENEM Text. */
function inline_markdown(s) {
  const codes = [];
  let t = String(s).replace(/`([^`]+)`/g, (m, c) => {
    codes.push(c);
    return "\x00" + (codes.length - 1) + "\x00";
  });
  t = t.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, (m, alt, u) =>
    adresse_ok(u) ? `<img src="${u}" alt="${alt}" loading="lazy">` : alt
  );
  t = t.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (m, text, u) =>
    adresse_ok(u)
      ? `<a href="${u}" target="_blank" rel="noopener noreferrer">${text}</a>`
      : text
  );
  t = t.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  t = t.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  t = t.replace(/\x00(\d+)\x00/g, (m, i) => `<code>${codes[i]}</code>`);
  return t;
}

/** Void-Tags: stehen allein, ohne Schliesser. */
const VOID_TAGS = new Set([
  "br", "hr", "img", "input", "meta", "link", "col", "area", "base",
  "embed", "source", "track", "wbr",
]);

/** Gaenzlich verbotene Tags: Skripte, Rahmen, Formen -- weg, samt Inhalt. */
const HTML_VERBOTEN = new Set([
  "script", "style", "iframe", "object", "embed", "form", "input",
  "button", "select", "textarea", "template", "noscript", "svg", "math",
  "frame", "frameset", "applet", "video", "audio", "canvas",
]);

/** Erlaubte Tags im README -- der Rest verliert seine Huelle, der Inhalt bleibt. */
const HTML_ERLAUBT = new Set([
  "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
  "colgroup", "col", "div", "span", "p", "br", "hr",
  "h1", "h2", "h3", "h4", "h5", "h6",
  "ul", "ol", "li", "dl", "dt", "dd", "blockquote", "center",
  "details", "summary", "figure", "figcaption",
  "b", "i", "u", "s", "strong", "em", "small", "sub", "sup",
  "code", "pre", "kbd", "samp", "var", "mark", "del", "ins", "abbr",
  "cite", "a", "img",
]);

/** Attribute je Tag -- nur diese reisen mit, Adressen nur http(s). */
const ATTR_PRO_TAG = {
  a: ["href", "title"],
  img: ["src", "alt", "title", "width", "height"],
  td: ["colspan", "rowspan", "align", "width"],
  th: ["colspan", "rowspan", "align", "width"],
  table: ["align", "border", "width", "summary"],
  details: ["open"],
  abbr: ["title"],
};

function html_attribute(node) {
  const tag = node.tagName.toLowerCase();
  const erlaubt = ATTR_PRO_TAG[tag];
  let raus = "";
  if (erlaubt) {
    for (const name of erlaubt) {
      const wert = node.getAttribute(name);
      if (wert === null || wert === undefined || wert === "") {
        continue;
      }
      if ((name === "href" || name === "src") && !adresse_ok(String(wert))) {
        continue;
      }
      raus += ` ${name}="${fliehe(String(wert))}"`;
    }
  }
  if (tag === "a" && adresse_ok(node.getAttribute("href") || "")) {
    raus += ' target="_blank" rel="noopener noreferrer"';
  }
  return raus;
}

function html_sauber(node) {
  if (node.nodeType === 3) {
    return inline_markdown(fliehe(node.nodeValue || ""));
  }
  if (node.nodeType !== 1) {
    return "";
  }
  const tag = node.tagName.toLowerCase();
  if (HTML_VERBOTEN.has(tag)) {
    return "";
  }
  // Ein Bild ohne taugliche Adresse ist keine Zierde, nur Muell --
  // es faellt ganz weg (javascript: und Verwandte erreichen so nie
  // den Laden).
  if (tag === "img" && !adresse_ok(node.getAttribute("src") || "")) {
    return "";
  }
  const kinder = [...node.childNodes].map(html_sauber).join("");
  if (!HTML_ERLAUBT.has(tag)) {
    return kinder;
  }
  if (VOID_TAGS.has(tag)) {
    return `<${tag}${html_attribute(node)}>`;
  }
  return `<${tag}${html_attribute(node)}>${kinder}</${tag}>`;
}

/**
 * Ein HTML-Block aus dem README, gesaeubert (Flug 2096, Wunde 1).
 *
 * Die Tabellen und der Schmuck vieler HACS-READMEs kommen als HTML --
 * bislang standen sie als Roh-Text im Laden. Der Sauberer nimmt den
 * Block auseinander (DOMParser) und setzt ihn aus der Whitelist
 * wieder zusammen: Skripte und Rahmen fallen ganz weg, unbekannte
 * Huellen verlieren nur ihre Schale, Adressen duerfen http(s) sein,
 * und Inline-Markdown laeuft ueber die Textknoten wie ueberall.
 */
function html_block(zeilen) {
  try {
    const doc = new DOMParser().parseFromString(zeilen.join("\n"), "text/html");
    return [...doc.body.childNodes].map(html_sauber).join("");
  } catch (fehler) {
    return zeilen.map(fliehe).join("\n");
  }
}

/**
 * Der Kleinstrenderer: Ueberschriften, Listen, Zitate, Code-Bloecke,
 * Trennlinien, Absaetze plus Inline-Markdown. HTML-Bloecke (Tabellen
 * und Schmuck vieler HACS-READMEs) gehen seit Flug 2096 durch den
 * Sauberer -- Whitelist, keine Skripte, nur http(s)-Adressen --;
 * alles andere kommt geflohen rein, wie immer.
 */
function markdown(text) {
  if (!text) return "";
  const rohzeilen = String(text).split(/\r?\n/);

  // Vorab-Zerlegung (Flug 2096): Codezaeune schuetzen ihren Inhalt
  // vor der HTML-Erkennung -- ein ```-Beispiel mit <table> darin bleibt
  // Code. Ein HTML-Block beginnt mit einem oeffnenden Tag und endet mit
  // dessen Schliesser; Void-Tags stehen allein. Zwischen den Zeilen
  // eines Blocks darf alles stehen (auch Leerzeilen und Fliesstext),
  // denn Textknoten kriegen ohnehin Inline-Markdown.
  const teile = []; // { art: "md", zeile } | { art: "fertig", html }
  let code = null;
  let html = null; // { zeilen: [...], tag: "table" }
  for (const roh of rohzeilen) {
    if (code !== null) {
      if (/^\s*```/.test(roh)) {
        teile.push({
          art: "fertig",
          html: `<pre><code>${fliehe(code.join("\n"))}</code></pre>`,
        });
        code = null;
      } else {
        code.push(roh);
      }
      continue;
    }
    if (/^\s*```/.test(roh)) {
      code = [];
      continue;
    }
    if (html !== null) {
      html.zeilen.push(roh);
      if (new RegExp(`</${html.tag}\\s*>`, "i").test(roh)) {
        teile.push({ art: "fertig", html: html_block(html.zeilen) });
        html = null;
      }
      continue;
    }
    const eroeffner = roh.match(/^\s*<([a-zA-Z][a-zA-Z0-9-]*)\b/);
    if (eroeffner) {
      const tag = eroeffner[1].toLowerCase();
      if (VOID_TAGS.has(tag)) {
        teile.push({ art: "fertig", html: html_block([roh]) });
        continue;
      }
      html = { zeilen: [roh], tag };
      continue;
    }
    teile.push({ art: "md", zeile: fliehe(roh) });
  }
  if (code !== null) {
    teile.push({
      art: "fertig",
      html: `<pre><code>${fliehe(code.join("\n"))}</code></pre>`,
    });
  }
  if (html !== null) {
    teile.push({ art: "fertig", html: html_block(html.zeilen) });
  }

  const stueck = [];
  let absatz = [];
  let modus = null; // null | "ul" | "ol" | "blockquote"

  const absatz_schliessen = () => {
    if (absatz.length) {
      stueck.push(`<p>${inline_markdown(absatz.join(" "))}</p>`);
      absatz = [];
    }
  };
  const liste_schliessen = () => {
    if (modus) {
      stueck.push(`</${modus === "blockquote" ? "blockquote" : modus}>`);
      modus = null;
    }
  };

  for (const teil of teile) {
    if (teil.art === "fertig") {
      absatz_schliessen();
      liste_schliessen();
      stueck.push(teil.html);
      continue;
    }
    const zeile = teil.zeile;
    const kopf = zeile.match(/^(#{1,4})\s+(.*)$/);
    if (kopf) {
      absatz_schliessen();
      liste_schliessen();
      stueck.push(
        `<h${kopf[1].length}>${inline_markdown(kopf[2].trim())}</h${kopf[1].length}>`
      );
      continue;
    }
    if (/^\s*(---+|\*\*\*+)\s*$/.test(zeile)) {
      absatz_schliessen();
      liste_schliessen();
      stueck.push("<hr>");
      continue;
    }
    const zitat = zeile.match(/^&gt;\s?(.*)$/);
    if (zitat) {
      absatz_schliessen();
      if (modus !== "blockquote") {
        liste_schliessen();
        stueck.push("<blockquote>");
        modus = "blockquote";
      }
      stueck.push(`<p>${inline_markdown(zitat[1])}</p>`);
      continue;
    }
    const unsortiert = zeile.match(/^\s*[-*+]\s+(.*)$/);
    if (unsortiert) {
      absatz_schliessen();
      if (modus !== "ul") {
        liste_schliessen();
        stueck.push("<ul>");
        modus = "ul";
      }
      stueck.push(`<li>${inline_markdown(unsortiert[1])}</li>`);
      continue;
    }
    const numeriert = zeile.match(/^\s*\d+[.)]\s+(.*)$/);
    if (numeriert) {
      absatz_schliessen();
      if (modus !== "ol") {
        liste_schliessen();
        stueck.push("<ol>");
        modus = "ol";
      }
      stueck.push(`<li>${inline_markdown(numeriert[1])}</li>`);
      continue;
    }
    liste_schliessen();
    if (!zeile.trim()) {
      absatz_schliessen();
    } else {
      absatz.push(zeile.trim());
    }
  }
  liste_schliessen();
  absatz_schliessen();
  return stueck.join("\n");
}

/** Datumskurzform, falls ISO -- sonst unverandert. */
function datum_kurz(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString();
}

/** Die Marken der drei Schmieden -- Eigennamen, nicht übersetzbar. */
const ANBIETER_NAMEN = {
  gitlab: "GitLab",
  forgejo: "Forgejo",
  gitea: "Gitea",
  // Der offizielle HACS-Katalog laeuft unter dem Anbieter "github".
  github: "HACS",
};

/** Das Ereignis, das der Server feuert, sobald ein Lager frisch liegt. */
const EREIGNIS_AKTUALISIERT = "haigs_aktualisiert";

/** Wie lange ein frischer Lauf ruht, bevor der Betritt ihn erneut erzwinge. */
const BETRETEN_RUHE_MS = 15000;

/**
 * GitLabs Pastell-Palette fuer Buchstaben-Zeichen (Flug 2085): fehlt
 * das Bild eines Projekts, bekommt sein Buchstabe eine dieser Farben
 * -- dieselbe Farbe fuer denselben Namen, wie GitLab es mit seinen
 * Initialen-Avataren haelt. Der Buchstabe bleibt dunkel (#333238,
 * GitLabs Leisten-Farbe): lesbar auf Pastell, bei Tag und bei Nacht.
 */
const ZEICHEN_FARBEN = [
  "#FFD599",
  "#D6EFFF",
  "#FCD5CE",
  "#D3FDD8",
  "#E4DFFF",
  "#FFE1BE",
  "#C4D7F6",
  "#FDE8F6",
  "#D9F2E6",
  "#F3E5C3",
];
const ZEICHEN_SCHRIFT = "#333238";

/** Dasselbe Wort -- dieselbe Farbe. Stabil, unauffaellig, ohne Speicher. */
function zeichen_farbe(name) {
  let saat = 0;
  for (const zeichen of String(name)) {
    saat = (saat * 31 + (zeichen.codePointAt(0) || 0)) % 9973;
  }
  return ZEICHEN_FARBEN[saat % ZEICHEN_FARBEN.length];
}


/** Der Fuchskopf (derselbe wie in ``iconset.js``), im Orange des Akzents. */
const FUCHS_PFAD =
  "M4.2 0.8L9 6.6L15 6.6L19.8 0.8L20.8 9.6L22.6 13L17.6 15.2L13.4 21.6L12 22.6L10.6 21.6L6.4 15.2L1.4 13L3.2 9.6ZM5.6 9L8 7.4L5 3.6ZM19 3.6L16 7.4L18.4 9ZM7.6 13L9.4 13.7L10.2 12.8L7 11.6ZM17 11.6L13.8 12.8L14.6 13.7L16.4 13Z";

/** Der Fuchs als fertiges SVG-Stueck (Groesse via CSS). */
function fuchs_svg(klassenname) {
  return (
    `<svg class="${klassenname}" viewBox="0 0 24 24" aria-hidden="true" focusable="false">` +
    `<path fill="#FC6D26" d="${FUCHS_PFAD}"/>` +
    `</svg>`
  );
}

/* ------------------------------------------------------------------ *
 * Flug 2100 -- der Laden zieht die Kleider von HACS an.
 *
 * Der Wunsch des Imkers: wer HAIGS oeffnet, soll sich fragen, ob er
 * im Original-HACS steht -- und erst am Akzent und an der Spalte
 * «Quelle» merken, dass hier mehrere Schmieden zugleich liefern.
 *
 * Darum baut das Panel nicht mehr selbst, sondern nimmt dasselbe
 * Material wie HACS: ``hass-tabs-subpage-data-table`` fuer die Liste
 * (Filter, Suche, Gruppen, Sortierung, Spalten -- alles vom Haus),
 * ``ha-markdown`` fuer die README, ``ha-assist-chip`` fuer die
 * Kennzahlen, ``ha-icon-overflow-menu`` fuer das Drei-Punkte-Menue.
 * Die Zellen sind DOM-Knoten, keine Lit-Vorlagen: Lit setzt Knoten
 * unveraendert ein, und so braucht die Datei keinen eigenen Bundler.
 *
 * Der eigene Ton: GitLabs Orange als Akzent (Knopf «Herunterladen»,
 * Kopf der ausstehenden Aktualisierungen) und die Spalte Quelle mit
 * Schmiede und Host -- dort, wo HACS die Downloads zaehlt.
 * ------------------------------------------------------------------ */

const PFADE = {
  punkte: "M12,16A2,2 0 0,1 14,18A2,2 0 0,1 12,20A2,2 0 0,1 10,18A2,2 0 0,1 12,16M12,10A2,2 0 0,1 14,12A2,2 0 0,1 12,14A2,2 0 0,1 10,12A2,2 0 0,1 12,10M12,4A2,2 0 0,1 14,6A2,2 0 0,1 12,8A2,2 0 0,1 10,6A2,2 0 0,1 12,4Z",
  zurueck: "M20,11V13H8L13.5,18.5L12.08,19.92L4.16,12L12.08,4.08L13.5,5.5L8,11H20Z",
  download: "M5,20H19V18H5M19,9H15V3H9V9H5L12,16L19,9Z",
  extern: "M14,3V5H17.59L7.76,14.83L9.17,16.24L19,6.41V10H21V3M19,19H5V5H12V3H5C3.89,3 3,3.9 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19V12H19V19Z",
  ticket: "M11,15H13V17H11V15M11,7H13V13H11V7M12,2C6.47,2 2,6.5 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M12,20A8,8 0 0,1 4,12A8,8 0 0,1 12,4A8,8 0 0,1 20,12A8,8 0 0,1 12,20Z",
  stern: "M12,17.27L18.18,21L16.54,13.97L22,9.24L14.81,8.62L12,2L9.19,8.62L2,9.24L7.45,13.97L5.82,21L12,17.27Z",
  person: "M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z",
  neuladen: "M2 12C2 16.97 6.03 21 11 21C13.39 21 15.68 20.06 17.4 18.4L15.9 16.9C14.63 18.25 12.86 19 11 19C4.76 19 1.64 11.46 6.05 7.05C10.46 2.64 18 5.77 18 12H15L19 16H19.1L23 12H20C20 7.03 15.97 3 11 3C6.03 3 2 7.03 2 12Z",
  loeschen: "M19,4H15.5L14.5,3H9.5L8.5,4H5V6H19M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19Z",
  info: "M11,9H13V7H11M12,20C7.59,20 4,16.41 4,12C4,7.59 7.59,4 12,4C16.41,4 20,7.59 20,12C20,16.41 16.41,20 12,20M12,2A10,10 0 0,0 2,12A10,10 0 0,0 12,22A10,10 0 0,0 22,12A10,10 0 0,0 12,2M11,17H13V11H11V17Z",
  plus: "M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z",
  server: "M4,1H20A1,1 0 0,1 21,2V6A1,1 0 0,1 20,7H4A1,1 0 0,1 3,6V2A1,1 0 0,1 4,1M4,9H20A1,1 0 0,1 21,10V14A1,1 0 0,1 20,15H4A1,1 0 0,1 3,14V10A1,1 0 0,1 4,9M4,17H20A1,1 0 0,1 21,18V22A1,1 0 0,1 20,23H4A1,1 0 0,1 3,22V18A1,1 0 0,1 4,17M9,5H10V3H9V5M9,13H10V11H9V13M9,21H10V19H9V21M5,3V5H7V3H5M5,11V13H7V11H5M5,19V21H7V19H5Z",
  tag: "M5.5,7A1.5,1.5 0 0,1 4,5.5A1.5,1.5 0 0,1 5.5,4A1.5,1.5 0 0,1 7,5.5A1.5,1.5 0 0,1 5.5,7M21.41,11.58L12.41,2.58C12.05,2.22 11.55,2 11,2H4C2.89,2 2,2.89 2,4V11C2,11.55 2.22,12.05 2.59,12.41L11.58,21.41C11.95,21.77 12.45,22 13,22C13.55,22 14.050,21.77 14.41,21.41L21.41,14.41C21.78,14.05 22,13.55 22,13C22,12.44 21.77,11.94 21.41,11.58Z",
  neustart: "M12,4C14.1,4 16.1,4.8 17.6,6.3C20.7,9.4 20.7,14.5 17.6,17.6C15.8,19.5 13.3,20.2 10.9,19.9L11.4,17.9C13.1,18.1 14.9,17.5 16.2,16.2C18.5,13.9 18.5,10.1 16.2,7.7C15.1,6.6 13.5,6 12,6V10.6L7,5.6L12,0.6V4M6.3,17.6C3.7,15 3.3,11 5.1,7.9L6.6,9.4C5.5,11.6 5.9,14.4 7.8,16.2C8.3,16.7 8.9,17.1 9.6,17.4L9,19.4C8,19 7.1,18.4 6.3,17.6Z",
  schliessen: "M19,6.41L17.59,5L12,10.59L6.41,5L5,6.41L10.59,12L5,17.59L6.41,19L12,13.41L17.59,19L19,17.59L13.41,12L19,6.41Z",
  repo: "M6,2H18A2,2 0 0,1 20,4V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2Z",
  zweig: "M13,14C9.64,14 8.54,15.35 8.18,16.24C9.25,16.7 10,17.76 10,19A3,3 0 0,1 7,22A3,3 0 0,1 4,19C4,17.690 4.83,16.58 6,16.17V7.83C4.83,7.42 4,6.31 4,5A3,3 0 0,1 7,2A3,3 0 0,1 10,5C10,6.31 9.17,7.42 8,7.83V13.12C8.88,12.47 10.16,12 12,12C14.67,12 15.56,10.66 15.85,9.77C14.77,9.32 14,8.25 14,7A3,3 0 0,1 17,4A3,3 0 0,1 20,7C20,8.34 19.12,9.5 17.91,9.86C17.65,11.29 16.68,14 13,14M7,18A1,1 0 0,0 6,19A1,1 0 0,0 7,20A1,1 0 0,0 8,19A1,1 0 0,0 7,18M7,4A1,1 0 0,0 6,5A1,1 0 0,0 7,6A1,1 0 0,0 8,5A1,1 0 0,0 7,4M17,6A1,1 0 0,0 16,7A1,1 0 0,0 17,8A1,1 0 0,0 18,7A1,1 0 0,0 17,6Z",
  update: "M21,10.12H14.22L16.96,7.3C14.23,4.6 9.81,4.5 7.08,7.2C4.35,9.91 4.35,14.28 7.08,17C9.81,19.7 14.23,19.7 16.96,17C18.32,15.65 19,14.080 19,12.1H21C21,14.08 20.120,16.65 18.36,18.39C14.85,21.87 9.15,21.87 5.64,18.39C2.14,14.92 2.11,9.28 5.62,5.81C9.13,2.34 14.76,2.34 18.27,5.81L21,3V10.12M12.5,8V12.25L16,14.33L15.28,15.54L11,13V8H12.5Z",
};

/** Texte der neuen Bedienung -- die Worte sind die von HACS. */
const LADEN_TEXTE = {
  de: {
    titel: "HAIGS",
    suche: "Durchsuchen",
    spalte_name: "Repository-Name",
    spalte_quelle: "Quelle",
    spalte_sterne: "Sterne",
    spalte_downloads: "Downloads",
    spalte_aktivitaet: "Aktivität",
    spalte_typ: "Typ",
    spalte_status: "Status",
    spalte_installiert: "Installierte Version",
    spalte_verfuegbar: "Verfügbare Version",
    gruppen: {
      aktualisierbar: "Ausstehende Aktualisierung",
      installiert: "Heruntergeladen",
      neu: "Neu",
      downloadbar: "Verfügbar zum Herunterladen",
    },
    typen: {
      integration: "Integration",
      plugin: "Dashboard",
      theme: "Theme",
      template: "Template",
      appdaemon: "AppDaemon",
      python_script: "Python Script",
    },
    filter_typ: "Typ",
    filter_quelle: "Quelle",
    filter_heruntergeladen: "Heruntergeladen",
    nur_heruntergeladen: "Nur heruntergeladene",
    keine_daten: "Keine Repositories gefunden",
    herunterladen: "Herunterladen",
    aktualisieren: "Aktualisieren",
    erneut: "Erneut herunterladen",
    entfernen: "Entfernen",
    deinstallieren: "Deinstallieren",
    repo_oeffnen: "Repository öffnen",
    tickets_oeffnen: "Issues öffnen",
    releases_oeffnen: "Releases öffnen",
    informationen_neu: "Informationen aktualisieren",
    liste_neu: "Liste aktualisieren",
    instanz_neu: "Quelle hinzufügen",
    instanzen: "Quellen",
    ueber: "Über HAIGS",
    benutzerdefiniert: "Benutzerdefinierte Repositories",
    repository_adresse: "Repository",
    hinzufuegen: "Hinzufügen",
    adresse_ungueltig: "Das ist keine Repository-Adresse – erwartet wird https://host/gruppe/projekt.",
    quelle_fehlt: (h) => `${h} ist noch keine Quelle – zuerst über „Quelle hinzufügen“ einrichten.`,
    abbrechen: "Abbrechen",
    version: "Version",
    dialog_download: (n) => `${n} herunterladen?`,
    dialog_download_text: (v, h) =>
      `Version ${v} wird von ${h} heruntergeladen und nach custom_components gelegt.`,
    dialog_entfernen: (n) => `${n} entfernen?`,
    dialog_entfernen_text:
      "Die Dateien werden gelöscht und das Repository verschwindet aus der Liste der Heruntergeladenen.",
    neustart_noetig: "Neustart erforderlich",
    neustart_text:
      "Home Assistant lädt neue Integrationen erst beim Start.",
    neustart_knopf: "Neu starten",
    einrichten: "Einrichten",
    readme_fehlt: "Dieses Repository hat keine README.",
    entwicklermodus: "Entwicklermodus",
    entwicklermodus_titel: "Diese Quelle lädt den neuesten Stand des Standardzweigs statt Releases",
    dialog_download_zweig: (v, h) =>
      `Entwicklermodus: Der Stand ${v} des Standardzweigs wird von ${h} heruntergeladen – ungetestet, frisch vom letzten Push.`,
    kein_release: "Noch kein Release – sobald das Repository eins veröffentlicht, lässt es sich hier herunterladen.",
    lade: "Lade …",
    erfolg_download: (n) => `${n} wurde heruntergeladen.`,
    erfolg_entfernt: (n) => `${n} wurde entfernt.`,
    keine_instanz:
      "Noch keine Quelle eingerichtet. Füge eine GitLab-, Forgejo- oder Gitea-Instanz hinzu.",
    ueber_text:
      "HAIGS bringt Integrationen, Karten und Themes aus selbst gehosteten Git-Schmieden nach Home Assistant – GitLab, Forgejo und Gitea, so viele Instanzen du willst. Kein Fork von HACS, sondern ein eigenes Zuhause daneben.",
  },
  en: {
    titel: "HAIGS",
    suche: "Search",
    spalte_name: "Repository name",
    spalte_quelle: "Source",
    spalte_sterne: "Stars",
    spalte_downloads: "Downloads",
    spalte_aktivitaet: "Activity",
    spalte_typ: "Type",
    spalte_status: "Status",
    spalte_installiert: "Installed version",
    spalte_verfuegbar: "Available version",
    gruppen: {
      aktualisierbar: "Pending update",
      installiert: "Downloaded",
      neu: "New",
      downloadbar: "Available for download",
    },
    typen: {
      integration: "Integration",
      plugin: "Dashboard",
      theme: "Theme",
      template: "Template",
      appdaemon: "AppDaemon",
      python_script: "Python Script",
    },
    filter_typ: "Type",
    filter_quelle: "Source",
    filter_heruntergeladen: "Downloaded",
    nur_heruntergeladen: "Downloaded only",
    keine_daten: "No repositories found",
    herunterladen: "Download",
    aktualisieren: "Update",
    erneut: "Redownload",
    entfernen: "Remove",
    deinstallieren: "Uninstall",
    repo_oeffnen: "Open repository",
    tickets_oeffnen: "Open issues",
    releases_oeffnen: "Open releases",
    informationen_neu: "Update information",
    liste_neu: "Refresh list",
    instanz_neu: "Add source",
    instanzen: "Sources",
    ueber: "About HAIGS",
    benutzerdefiniert: "Custom repositories",
    repository_adresse: "Repository",
    hinzufuegen: "Add",
    adresse_ungueltig: "That is not a repository address – expected https://host/group/project.",
    quelle_fehlt: (h) => `${h} is not a source yet – set it up via “Add source” first.`,
    abbrechen: "Cancel",
    version: "Version",
    dialog_download: (n) => `Download ${n}?`,
    dialog_download_text: (v, h) =>
      `Version ${v} will be downloaded from ${h} and placed in custom_components.`,
    dialog_entfernen: (n) => `Remove ${n}?`,
    dialog_entfernen_text:
      "The files are deleted and the repository leaves the list of downloads.",
    neustart_noetig: "Restart required",
    neustart_text: "Home Assistant loads new integrations on startup only.",
    neustart_knopf: "Restart",
    einrichten: "Set up",
    readme_fehlt: "This repository has no README.",
    entwicklermodus: "Developer mode",
    entwicklermodus_titel: "This source loads the latest state of the default branch instead of releases",
    dialog_download_zweig: (v, h) =>
      `Developer mode: state ${v} of the default branch will be downloaded from ${h} – untested, fresh from the last push.`,
    kein_release: "No release yet – once the repository publishes one, you can download it here.",
    lade: "Loading …",
    erfolg_download: (n) => `${n} was downloaded.`,
    erfolg_entfernt: (n) => `${n} was removed.`,
    keine_instanz:
      "No source set up yet. Add a GitLab, Forgejo or Gitea instance.",
    ueber_text:
      "HAIGS brings integrations, cards and themes from self-hosted Git forges into Home Assistant – GitLab, Forgejo and Gitea, as many instances as you like. Not a fork of HACS, but a home of its own right next to it.",
  },
};

/** Ein DOM-Knoten in einer Zeile: Tag, Eigenschaften, Kinder. */
function knoten(tag, eigenschaften, ...kinder) {
  const el = document.createElement(tag);
  for (const [schluessel, wert] of Object.entries(eigenschaften || {})) {
    if (wert === undefined || wert === null || wert === false) continue;
    if (schluessel === "class") el.className = wert;
    else if (schluessel === "style") el.setAttribute("style", wert);
    else if (schluessel.startsWith("on")) el.addEventListener(schluessel.slice(2), wert);
    else if (schluessel.startsWith(".")) el[schluessel.slice(1)] = wert;
    else el.setAttribute(schluessel, wert === true ? "" : String(wert));
  }
  for (const kind of kinder.flat()) {
    if (kind === undefined || kind === null || kind === false) continue;
    el.append(kind instanceof Node ? kind : document.createTextNode(String(kind)));
  }
  return el;
}

/** Relative Zeit wie HACS («vor 3 Tagen»), ueber Intl -- ohne Bibliothek. */
function relativ(iso, sprache_kurz) {
  if (!iso) return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return "—";
  const sek = Math.round((t - Date.now()) / 1000);
  const stufen = [
    [60, "second"],
    [60, "minute"],
    [24, "hour"],
    [7, "day"],
    [4.34524, "week"],
    [12, "month"],
    [Infinity, "year"],
  ];
  let wert = sek;
  let einheit = "second";
  for (const [teiler, name] of stufen) {
    einheit = name;
    if (Math.abs(wert) < teiler) break;
    wert = wert / teiler;
  }
  try {
    return new Intl.RelativeTimeFormat(sprache_kurz, { numeric: "auto" }).format(
      Math.round(wert),
      einheit
    );
  } catch (fehler) {
    return datum_kurz(iso);
  }
}

/** Relative Adressen der README auf die rohen Dateien der Schmiede biegen. */
function readme_adressen(text, info, anbieter) {
  text = String(text || "").replace(/^\uFEFF/, "");
  if (!info || !info.web_url) return text;
  const zweig = info.standardzweig || "main";
  const roh =
    anbieter === "github"
      ? `https://raw.githubusercontent.com/${info.web_url.replace("https://github.com/", "")}/${zweig}/`
      : anbieter === "gitlab"
      ? `${info.web_url}/-/raw/${zweig}/`
      : `${info.web_url}/raw/branch/${zweig}/`;
  const seite =
    anbieter === "github"
      ? `${info.web_url}/blob/${zweig}/`
      : anbieter === "gitlab"
      ? `${info.web_url}/-/blob/${zweig}/`
      : `${info.web_url}/src/branch/${zweig}/`;
  const absolut = (u) => /^([a-z]+:|#|\/\/)/i.test(u);
  const sauber = (u) => u.replace(/^\.\//, "").replace(/^\//, "");
  return text
    .replace(/(!\[[^\]]*\]\()([^)\s]+)/g, (m, a, u) => (absolut(u) ? m : a + roh + sauber(u)))
    .replace(/((?<!!)\[[^\]]*\]\()([^)\s]+)/g, (m, a, u) => (absolut(u) ? m : a + seite + sauber(u)))
    .replace(/(<img[^>]*\ssrc=["'])([^"']+)/gi, (m, a, u) => (absolut(u) ? m : a + roh + sauber(u)));
}

/** Die Bausteine des Hauses laden, falls noch keine Seite sie geholt hat. */
async function bausteine_laden() {
  if (customElements.get("hass-tabs-subpage-data-table")) return;
  try {
    const aufloeser = document.createElement("partial-panel-resolver");
    const routen = aufloeser._getRoutes
      ? aufloeser._getRoutes([{ component_name: "config", url_path: "a" }])
      : aufloeser.getRoutes([{ component_name: "config", url_path: "a" }]);
    await routen.routes.a.load();
    const konfig = document.createElement("ha-panel-config");
    await konfig.routerOptions.routes.integrations.load();
  } catch (fehler) {
    /* der Rueckfall unten wartet trotzdem */
  }
  await Promise.race([
    customElements.whenDefined("hass-tabs-subpage-data-table"),
    new Promise((r) => setTimeout(r, 8000)),
  ]);
}

class HaigsPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._hass = null;
    this._narrow = false;
    this._route = null;
    this._eintraege = [];
    this._funde = [];
    this._instanzen = [];
    this._anbieter = {};
    this._entwicklung = {};
    this._laedt = true;
    this._beschaeftigt = false;
    this._erneuert_am = 0;
    this._abmeldung = null;
    this._detail = null; // { zeile, daten, laedt }
    this._dialog = null;
    this._filter_typ = new Set();
    this._filter_quelle = new Set();
    this._nur_heruntergeladen = false;
    this._suchwort = "";
    this._bereit = false;
  }

  set hass(hass) {
    const erste = this._hass === null;
    this._hass = hass;
    if (this._tabelle) this._tabelle.hass = hass;
    this._kinder_hass();
    if (erste) {
      this._start();
    }
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._tabelle) this._tabelle.narrow = narrow;
  }

  set route(route) {
    this._route = route;
    if (this._tabelle) this._tabelle.route = route;
    this._folge_route();
  }

  /** Die Adresse entscheidet: /haigs/repository/<id> ist die Detailseite. */
  _folge_route() {
    if (!this._bereit || !this._route) return;
    const pfad = this._route.path || "";
    const treffer = pfad.match(/^\/repository\/(.+)$/);
    if (!treffer) {
      if (this._detail) this._schliesse_detail(true);
      return;
    }
    const id = decodeURIComponent(treffer[1]);
    if (this._detail && this._detail.zeile.id === id) return;
    const z = this._zeilen_karte && this._zeilen_karte.get(id);
    if (z) this._oeffne(z, true);
    else this._warte_auf_id = id;
  }

  set panel(panel) {
    this._panel = panel;
  }

  get _t() {
    return LADEN_TEXTE[sprache(this._hass)] || LADEN_TEXTE.en;
  }

  get _sprache_kurz() {
    return (this._hass && this._hass.locale && this._hass.locale.language) ||
      (this._hass && this._hass.language) || "en";
  }

  connectedCallback() {
    if (this._bereit) this._betrete();
  }

  disconnectedCallback() {
    if (this._abmeldung) {
      try {
        this._abmeldung();
      } catch (fehler) {
        /* schon gekuendigt */
      }
      this._abmeldung = null;
    }
  }

  async _start() {
    this.shadowRoot.innerHTML = `<style>${LADEN_STIL}</style><div class="hl-warte"><ha-spinner></ha-spinner></div>`;
    await bausteine_laden();
    await this._hole_marken_token();
    this._bereit = true;
    this._baue();
    this._folge_route();
    this._abonnieren();
    this._betrete();
  }

  /**
   * Das Token fuer HAs Marken-Proxy (``/api/brands``). Ueber ihn zeigt
   * Home Assistant die Icons aus dem ``brand/``-Ordner einer
   * Integration -- genau die, die HACS 2.0 nicht kennt, weil es nur
   * den zentralen brands-Server fragt. Fehlt der Befehl (aeltere HA),
   * bleibt es beim Projektbild.
   */
  async _hole_marken_token() {
    try {
      const antwort = await this._hass.callWS({ type: "brands/access_token" });
      this._marken_token = (antwort && antwort.token) || "";
    } catch (fehler) {
      this._marken_token = "";
    }
  }

  /** Die Adresse des Marken-Icons einer installierten Integration. */
  _marken_icon(z) {
    const domain = z.integration && z.integration.domain;
    if (!domain || !this._marken_token) return "";
    const dunkel = this._hass && this._hass.themes && this._hass.themes.darkMode;
    return `/api/brands/integration/${encodeURIComponent(domain)}/${dunkel ? "dark_" : ""}icon.png?token=${this._marken_token}`;
  }

  _kinder_hass() {
    if (!this.shadowRoot) return;
    for (const el of this.shadowRoot.querySelectorAll("[data-hass]")) {
      el.hass = this._hass;
    }
  }

  /* ---------------- Daten ---------------- */

  _abonnieren() {
    const verbindung = this._hass && this._hass.connection;
    if (!verbindung || typeof verbindung.subscribeEvents !== "function") return;
    verbindung
      .subscribeEvents(() => {
        if (!this._beschaeftigt) this._lade();
      }, EREIGNIS_AKTUALISIERT)
      .then((abmelden) => {
        this._abmeldung = abmelden;
      })
      .catch(() => {});
  }

  _betrete() {
    this._lade().finally(() => {
      if (this._erneuert_am && Date.now() - this._erneuert_am < BETRETEN_RUHE_MS) return;
      this._erneuern();
    });
  }

  _uebernehme(antwort) {
    this._eintraege = antwort.eintraege || [];
    this._funde = antwort.funde || [];
    this._instanzen = antwort.instanzen || [];
    this._anbieter = antwort.anbieter || {};
    this._entwicklung = antwort.entwicklermodus || {};
    this._laedt = false;
    this._zeichne_liste();
  }

  async _lade() {
    try {
      this._uebernehme(await this._hass.callWS({ type: "haigs/eintraege" }));
    } catch (fehler) {
      this._melde(this._fehlertext(fehler));
    }
  }

  async _erneuern() {
    if (this._beschaeftigt) return;
    this._beschaeftigt = true;
    try {
      const antwort = await this._hass.callWS({ type: "haigs/erneuern" });
      this._uebernehme(antwort);
      const gescheitert = Object.entries(antwort.gescheitert || {});
      if (gescheitert.length) {
        this._melde(gescheitert.map(([h, g]) => `${h}: ${g}`).join(" · "));
      }
    } catch (fehler) {
      this._melde(this._fehlertext(fehler));
    }
    this._erneuert_am = Date.now();
    this._beschaeftigt = false;
  }

  _fehlertext(fehler) {
    const alt = TEXTE[sprache(this._hass)] || TEXTE.en;
    const code = fehler && fehler.code;
    if (code && alt.fehler[code] !== undefined) return alt.fehler[code];
    if (fehler && fehler.message) return alt.fehler.sonst + " (" + fehler.message + ")";
    return alt.fehler.sonst;
  }

  /** Eine Nachricht unten am Rand, wie HA sie zeigt. */
  _melde(text) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", {
        detail: { message: text },
        bubbles: true,
        composed: true,
      })
    );
  }

  _gehe(ziel) {
    try {
      window.history.pushState(null, "", ziel);
      window.dispatchEvent(new Event("location-changed"));
    } catch (fehler) {
      window.location.assign(ziel);
    }
  }

  /* ---------------- Zeilen ---------------- */

  _status(e) {
    if (e._fund) return e.gesehen ? "downloadbar" : "neu";
    if (e.installiert && e.neueste && e.installiert !== e.neueste) return "aktualisierbar";
    if (e.installiert) return "installiert";
    return "downloadbar";
  }

  _zeilen() {
    const zeilen = [];
    const t = this._t;
    for (const e of this._eintraege) {
      const status = this._status(e);
      zeilen.push({
        ...e,
        id: e.storage_key,
        anzeige: this._kurzname(e.name),
        status,
        status_text: t.gruppen[status],
        typ_text: t.typen[e.kategorie] || e.kategorie,
        quelle: this._quelle_text(e.host),
        sterne: e.sterne || 0,
        downloads: e.downloads || 0,
        aktivitaet: e.veroeffentlicht_am || e.hinzugefuegt_am || "",
      });
    }
    for (const f of this._funde) {
      if (f.vorhanden || f.gueltig === false) continue;
      zeilen.push({
        ...f,
        _fund: true,
        id: "fund|" + f.host + "|" + f.full_name,
        pfad: f.full_name,
        anzeige: this._kurzname(f.name),
        status: this._status({ _fund: true, gesehen: f.gesehen }),
        status_text: t.gruppen[this._status({ _fund: true, gesehen: f.gesehen })],
        typ_text: t.typen[f.kategorie] || f.kategorie,
        quelle: this._quelle_text(f.host),
        sterne: f.sterne || 0,
        downloads: f.downloads || 0,
        neueste: f.letzte_version,
        aktivitaet: f.zuletzt_aktiv || "",
      });
    }
    return zeilen.filter((z) => {
      if (this._filter_typ.size && !this._filter_typ.has(z.kategorie)) return false;
      if (this._filter_quelle.size && !this._filter_quelle.has(z.host)) return false;
      if (this._nur_heruntergeladen && !z.installiert) return false;
      return true;
    });
  }

  _kurzname(name) {
    return String(name || "").split("/").pop();
  }

  _quelle_text(host) {
    const a = this._anbieter[host];
    return (ANBIETER_NAMEN[a] || a || "Git") + " · " + host;
  }

  /**
   * Das Zeichen einer Zeile: erst das Marken-Icon der Integration (ihr
   * ``brand/``-Ordner, ueber HAs Proxy), dann das Projektbild der
   * Schmiede, zuletzt ein Buchstabe -- nie ein kaputtes Bild.
   */
  _zeichen(z, gross) {
    const groesse = gross ? 40 : 32;
    const quellen = [this._marken_icon(z), z.avatar_url].filter(Boolean);
    if (!quellen.length) return this._buchstabe(z, groesse);
    const bild = knoten("img", {
      class: "hl-zeichen",
      src: quellen.shift(),
      alt: "",
      style: `width:${groesse}px;height:${groesse}px`,
    });
    bild.addEventListener("error", () => {
      const naechste = quellen.shift();
      if (naechste) bild.src = naechste;
      else bild.replaceWith(this._buchstabe(z, groesse));
    });
    return bild;
  }

  _buchstabe(z, groesse) {
    const name = (z.anzeige || z.name || "?").split("/").pop();
    return knoten(
      "div",
      {
        class: "hl-zeichen hl-buchstabe",
        style: `width:${groesse}px;height:${groesse}px;background:${zeichen_farbe(name)};color:${ZEICHEN_SCHRIFT}`,
      },
      name.charAt(0).toUpperCase()
    );
  }

  _spalten() {
    const t = this._t;
    const schmal = this._narrow;
    return {
      icon: {
        title: "",
        label: "Icon",
        type: "icon",
        moveable: false,
        showNarrow: true,
        template: (z) => this._zeichen(z, false),
      },
      anzeige: {
        title: t.spalte_name,
        main: true,
        sortable: true,
        filterable: true,
        direction: "asc",
        flex: 3,
        showNarrow: true,
        template: (z) =>
          knoten(
            "div",
            { class: "hl-zelle-name" },
            knoten("div", { class: "hl-name" }, z.anzeige),
            knoten("div", { class: "hl-beschr" }, z.beschreibung || "")
          ),
      },
      beschreibung: { title: "", hidden: true, filterable: true },
      quelle: {
        title: t.spalte_quelle,
        sortable: true,
        groupable: true,
        filterable: true,
        hidden: schmal,
        flex: 1.2,
        template: (z) =>
          knoten(
            "div",
            { class: "hl-zelle-name" },
            knoten("div", { class: "hl-name" }, ANBIETER_NAMEN[this._anbieter[z.host]] || this._anbieter[z.host] || "Git"),
            knoten("div", { class: "hl-beschr" }, z.host)
          ),
      },
      sterne: {
        title: t.spalte_sterne,
        sortable: true,
        type: "numeric",
        hidden: schmal,
        width: "80px",
        template: (z) => String(z.sterne),
      },
      downloads: {
        title: t.spalte_downloads,
        sortable: true,
        type: "numeric",
        hidden: schmal,
        width: "100px",
        template: (z) => (z.downloads ? z.downloads.toLocaleString() : "—"),
      },
      aktivitaet: {
        title: t.spalte_aktivitaet,
        sortable: true,
        hidden: schmal,
        width: "130px",
        template: (z) => relativ(z.aktivitaet, this._sprache_kurz),
      },
      installiert: {
        title: t.spalte_installiert,
        sortable: true,
        hidden: true,
        defaultHidden: true,
        width: "140px",
        template: (z) => z.installiert || "—",
      },
      neueste: {
        title: t.spalte_verfuegbar,
        sortable: true,
        hidden: true,
        defaultHidden: true,
        width: "140px",
        template: (z) => z.neueste || "—",
      },
      status_text: {
        title: t.spalte_status,
        groupable: true,
        sortable: true,
        hidden: true,
        defaultHidden: true,
      },
      typ_text: {
        title: t.spalte_typ,
        sortable: true,
        groupable: true,
        filterable: true,
        hidden: schmal,
        width: "110px",
      },
      aktionen: {
        title: "",
        label: "Aktionen",
        type: "overflow-menu",
        showNarrow: true,
        moveable: false,
        hideable: false,
        template: (z) =>
          knoten("ha-icon-overflow-menu", {
            ".hass": this._hass,
            ".narrow": true,
            ".items": this._menue(z),
            "data-hass": true,
            onclick: (ev) => ev.stopPropagation(),
          }),
      },
    };
  }

  _menue(z) {
    const t = this._t;
    const punkte = [
      { path: PFADE.info, label: t.informationen_neu, action: () => this._oeffne(z) },
      z.web_url && { path: PFADE.extern, label: t.repo_oeffnen, action: () => window.open(z.web_url, "_blank", "noreferrer") },
      z.tickets_url && { path: PFADE.ticket, label: t.tickets_oeffnen, action: () => window.open(z.tickets_url, "_blank", "noreferrer") },
    ];
    if (z.installiert) {
      punkte.push({ path: PFADE.neuladen, label: t.erneut, action: () => this._frage_download(z) });
      punkte.push({ divider: true });
      punkte.push({ path: PFADE.loeschen, label: t.entfernen, warning: true, action: () => this._frage_entfernen(z) });
    } else {
      if (z.neueste) {
        punkte.push({ path: PFADE.download, label: t.herunterladen, action: () => this._frage_download(z) });
      }
      if (!z._fund) {
        punkte.push({ divider: true });
        punkte.push({ path: PFADE.loeschen, label: t.entfernen, warning: true, action: () => this._entferne_eintrag(z) });
      }
    }
    return punkte.filter(Boolean);
  }

  /* ---------------- Bau ---------------- */

  _baue() {
    const t = this._t;
    const wurzel = this.shadowRoot;
    wurzel.innerHTML = `<style>${LADEN_STIL}</style>`;

    const tabelle = document.createElement("hass-tabs-subpage-data-table");
    tabelle.hass = this._hass;
    tabelle.narrow = this._narrow;
    tabelle.route = this._route || { prefix: "/haigs", path: "" };
    tabelle.tabs = [{ name: t.titel, path: "/haigs" }];
    tabelle.mainPage = true;
    tabelle.clickable = true;
    tabelle.hasFilters = true;
    tabelle.id = "id";
    tabelle.searchLabel = t.suche;
    tabelle.noDataText = t.keine_daten;
    tabelle.initialGroupColumn = "status_text";
    tabelle.groupOrder = ["aktualisierbar", "installiert", "neu", "downloadbar"].map(
      (g) => t.gruppen[g]
    );
    tabelle.initialSorting = { column: "sterne", direction: "desc" };
    tabelle.columns = this._spalten();
    tabelle.data = [];
    tabelle.addEventListener("row-click", (ev) => {
      const z = this._zeilen_karte && this._zeilen_karte.get(ev.detail.id);
      if (z) this._oeffne(z);
    });
    tabelle.addEventListener("clear-filter", () => {
      this._filter_typ.clear();
      this._filter_quelle.clear();
      this._nur_heruntergeladen = false;
      this._zeichne_liste();
    });

    const werkzeug = knoten("ha-icon-overflow-menu", {
      slot: "toolbar-icon",
      ".hass": this._hass,
      ".narrow": true,
      "data-hass": true,
      ".items": [
        { path: PFADE.neuladen, label: t.liste_neu, action: () => { this._erneuert_am = 0; this._erneuern(); } },
        { path: PFADE.repo, label: t.benutzerdefiniert, action: () => this._benutzerdefiniert() },
        { path: PFADE.plus, label: t.instanz_neu, action: () => this._gehe("/config/integrations/integration/haigs") },
        { divider: true },
        { path: PFADE.info, label: t.ueber, action: () => this._ueber() },
      ],
    });
    tabelle.append(werkzeug);

    this._filterflaeche = knoten("div", { slot: "filter-pane", class: "hl-filter" });
    tabelle.append(this._filterflaeche);

    this._tabelle = tabelle;
    this._listenseite = knoten("div", { class: "hl-seite" }, tabelle);
    this._detailseite = knoten("div", { class: "hl-seite hl-detail", hidden: true });
    this._dialogplatz = knoten("div", {});
    wurzel.append(this._listenseite, this._detailseite, this._dialogplatz);
    this._zeichne_liste();
  }

  _zeichne_liste() {
    if (!this._tabelle) return;
    const zeilen = this._zeilen();
    this._zeilen_karte = new Map(zeilen.map((z) => [z.id, z]));
    this._tabelle.columns = this._spalten();
    this._tabelle.data = zeilen;
    this._tabelle.filters =
      this._filter_typ.size + this._filter_quelle.size + (this._nur_heruntergeladen ? 1 : 0);
    if (!this._laedt && !this._instanzen.length) {
      this._tabelle.noDataText = this._t.keine_instanz;
    }
    this._zeichne_filter();
    if (this._warte_auf_id && this._zeilen_karte.has(this._warte_auf_id)) {
      const id = this._warte_auf_id;
      this._warte_auf_id = null;
      this._oeffne(this._zeilen_karte.get(id), true);
    }
    if (this._detail) {
      const frisch = this._zeilen_karte.get(this._detail.zeile.id);
      if (frisch) {
        this._detail.zeile = frisch;
        this._zeichne_detail();
      }
    }
  }

  _zeichne_filter() {
    const t = this._t;
    const flaeche = this._filterflaeche;
    flaeche.replaceChildren();
    const typen = [...new Set([...this._eintraege, ...this._funde].map((e) => e.kategorie))].filter(Boolean);
    const haken = (text, an, wechsel) =>
      knoten(
        "label",
        { class: "hl-haken" },
        knoten("input", { type: "checkbox", ".checked": an, onchange: (ev) => wechsel(ev.target.checked) }),
        knoten("span", {}, text)
      );
    const gruppe = (titel, inhalt) =>
      knoten("ha-expansion-panel", { outlined: false, expanded: true, header: titel }, knoten("div", { class: "hl-filter-inhalt" }, inhalt));
    flaeche.append(
      gruppe(t.filter_typ, typen.map((k) =>
        haken(t.typen[k] || k, this._filter_typ.has(k), (an) => {
          an ? this._filter_typ.add(k) : this._filter_typ.delete(k);
          this._zeichne_liste();
        })
      )),
      gruppe(t.filter_quelle, this._instanzen.map((h) =>
        haken(this._quelle_text(h), this._filter_quelle.has(h), (an) => {
          an ? this._filter_quelle.add(h) : this._filter_quelle.delete(h);
          this._zeichne_liste();
        })
      )),
      gruppe(t.filter_heruntergeladen, [
        haken(t.nur_heruntergeladen, this._nur_heruntergeladen, (an) => {
          this._nur_heruntergeladen = an;
          this._zeichne_liste();
        }),
      ])
    );
  }

  /* ---------------- Detail ---------------- */

  async _oeffne(z, von_route) {
    if (!von_route) {
      this._gehe("/haigs/repository/" + encodeURIComponent(z.id));
      return;
    }
    this._fund_gesehen(z);
    this._detail = { zeile: z, daten: null, laedt: true };
    this._listenseite.hidden = true;
    this._detailseite.hidden = false;
    this._zeichne_detail();
    try {
      const daten = await this._hass.callWS({ type: "haigs/detail", host: z.host, pfad: z.pfad || z.full_name });
      if (this._detail && this._detail.zeile.id === z.id) {
        this._detail.daten = daten;
        this._detail.laedt = false;
        this._zeichne_detail();
      }
    } catch (fehler) {
      if (this._detail) {
        this._detail.laedt = false;
        this._detail.fehler = this._fehlertext(fehler);
        this._zeichne_detail();
      }
    }
  }

  // Wie HACS: Wer einen neuen Fund oeffnet, nimmt ihm das "neu". Lokal sofort,
  // serverseitig dauerhaft; die Zeile bleibt ein Fund (Herunterladen geht weiter ueber _fund).
  _fund_gesehen(z) {
    if (!z._fund || z.gesehen) return;
    z.gesehen = true;
    const f = this._funde.find((x) => x.host === z.host && x.full_name === z.full_name);
    if (f) f.gesehen = true;
    this._hass
      .callWS({ type: "haigs/gesehen", host: z.host, pfad: z.full_name })
      .catch(() => {});
    this._zeichne_liste();
  }

  _schliesse_detail(von_route) {
    if (!von_route) {
      this._gehe("/haigs");
      return;
    }
    this._detail = null;
    this._detailseite.hidden = true;
    this._detailseite.replaceChildren();
    this._listenseite.hidden = false;
  }

  _zeichne_detail() {
    const t = this._t;
    const d = this._detail;
    if (!d) return;
    const z = d.zeile;
    const info = (d.daten && d.daten.info) || {};
    const besitzer = (z.pfad || z.full_name || "").split("/").slice(0, -1).join("/");

    const kopf = knoten(
      "div",
      { class: "hl-kopf" },
      knoten("ha-icon-button", {
        ".path": PFADE.zurueck,
        ".label": "Zurück",
        onclick: () => this._schliesse_detail(),
      }),
      knoten("div", { class: "hl-kopf-titel" }, z.anzeige),
      knoten("ha-icon-overflow-menu", {
        ".hass": this._hass,
        ".narrow": true,
        ".items": this._menue(z),
        "data-hass": true,
      })
    );

    const chip = (pfad, text, titel, link) => {
      const c = knoten("ha-assist-chip", { ".label": String(text), title: titel || "", ".filled": false });
      c.append(knoten("ha-svg-icon", { slot: "icon", ".path": pfad }));
      if (link) {
        c.addEventListener("click", () => window.open(link, "_blank", "noreferrer"));
        c.classList.add("hl-klickbar");
      }
      return c;
    };
    const sterne = info.sterne !== undefined ? info.sterne : z.sterne;
    const tickets = info.offene_tickets !== undefined ? info.offene_tickets : z.offene_tickets;
    const chips = knoten(
      "div",
      { class: "hl-chips" },
      besitzer && chip(PFADE.person, besitzer, "", null),
      chip(PFADE.server, this._quelle_text(z.host), t.spalte_quelle, info.web_url || z.web_url),
      chip(PFADE.stern, sterne || 0, t.spalte_sterne, info.web_url || z.web_url),
      z.downloads > 0 && chip(PFADE.download, z.downloads.toLocaleString(), t.spalte_downloads, null),
      tickets !== undefined && chip(PFADE.ticket, tickets, "Issues", info.tickets_url || z.tickets_url),
      z.neueste && chip(PFADE.tag, z.neueste, t.version, info.releases_url || z.releases_url),
      this._entwicklung[z.host] && chip(PFADE.zweig, t.entwicklermodus, t.entwicklermodus_titel, null)
    );

    const karte = knoten("ha-card", { class: "hl-detail-karte" }, chips);

    const zustand = this._zustand_hinweis(z);
    if (zustand) karte.append(zustand);
    if (!z.neueste && !z.installiert && !d.laedt) {
      karte.append(knoten("div", { class: "hl-zustand-platz" }, knoten("ha-alert", { "alert-type": "info" }, t.kein_release)));
    }

    if (d.laedt) {
      karte.append(knoten("div", { class: "hl-warte-klein" }, knoten("ha-spinner", { size: "small" })));
    } else if (d.fehler) {
      karte.append(knoten("ha-alert", { "alert-type": "error" }, d.fehler));
    } else {
      const text = d.daten && d.daten.readme;
      if (text) {
        const md = knoten("ha-markdown", {
          class: "hl-readme",
          ".breaks": false,
          ".lazyImages": true,
          ".content": readme_adressen(text, info, this._anbieter[z.host]),
        });
        if (!customElements.get("ha-markdown")) {
          const ersatz = knoten("div", { class: "hl-readme" });
          ersatz.innerHTML = markdown(text);
          karte.append(ersatz);
        } else {
          karte.append(md);
        }
      } else {
        karte.append(knoten("div", { class: "hl-leer" }, info.beschreibung || z.beschreibung || t.readme_fehlt));
      }
    }

    const update_da = z.installiert && z.neueste && z.installiert !== z.neueste;
    const fab_text = !z.neueste
      ? null
      : update_da
        ? t.aktualisieren
        : z.installiert
          ? null
          : t.herunterladen;
    const fab =
      fab_text &&
      knoten(
        "button",
        { class: "hl-fab", onclick: () => this._frage_download(z) },
        knoten("ha-svg-icon", { ".path": update_da ? PFADE.update : PFADE.download }),
        knoten("span", {}, fab_text)
      );

    this._detailseite.replaceChildren(
      kopf,
      knoten("div", { class: "hl-detail-inhalt" }, karte, this._fusszeile()),
      fab || ""
    );
  }

  /**
   * Die Fusszeile (Flug 2092, zurueck seit Flug 2100): Fuchs und
   * Geluebde unter der Detailkarte. Der Fuchs tanzt, wenn man ihn
   * streichelt (hover) -- sonst steht er still und wartet.
   */
  _fusszeile() {
    const alt = TEXTE[sprache(this._hass)] || TEXTE.en;
    const fuss = knoten("footer", { class: "hl-fuss", role: "contentinfo" });
    fuss.innerHTML = fuchs_svg("hl-fuss-fuchs");
    fuss.append(knoten("span", { class: "hl-fuss-wort" }, alt.fuss_zeile));
    return fuss;
  }

  _zustand_hinweis(z) {
    const i = z.integration;
    if (!i || !i.zustand || i.zustand === "eingerichtet") return null;
    const alt = TEXTE[sprache(this._hass)] || TEXTE.en;
    const typ = i.zustand === "nicht_geladen" ? "error" : i.zustand === "neustart" ? "warning" : "info";
    const hinweis = knoten("ha-alert", { "alert-type": typ, title: alt.zustand[i.zustand] || "" }, alt.zustand_titel[i.zustand] || "");
    if (i.zustand === "neustart") {
      hinweis.append(
        knoten("ha-button", { slot: "action", onclick: () => this._hass.callService("homeassistant", "restart") }, this._t.neustart_knopf)
      );
    } else if (i.zustand === "hinzufuegen") {
      hinweis.append(
        knoten("ha-button", { slot: "action", onclick: () => this._gehe("/config/integrations/dashboard") }, this._t.einrichten)
      );
    }
    return knoten("div", { class: "hl-zustand-platz" }, hinweis);
  }

  /* ---------------- Dialoge ---------------- */

  _dialog_zeigen(titel, text, knopf_text, aktion, warnung) {
    const t = this._t;
    const zu = () => this._dialogplatz.replaceChildren();
    const knopf = knoten(
      "button",
      { class: "hl-dlg-knopf" + (warnung ? " hl-warnung" : " hl-primaer") },
      knopf_text
    );
    knopf.addEventListener("click", async () => {
      knopf.disabled = true;
      knopf.replaceChildren(knoten("ha-spinner", { size: "tiny" }));
      try {
        await aktion();
      } finally {
        zu();
      }
    });
    const dlg = knoten(
      "div",
      { class: "hl-dlg-grund", onclick: (ev) => ev.target === ev.currentTarget && zu() },
      knoten(
        "div",
        { class: "hl-dlg", role: "dialog", "aria-modal": "true" },
        knoten("div", { class: "hl-dlg-titel" }, titel),
        knoten("div", { class: "hl-dlg-text" }, text),
        knoten(
          "div",
          { class: "hl-dlg-knoepfe" },
          knoten("button", { class: "hl-dlg-knopf", onclick: zu }, t.abbrechen),
          knopf
        )
      )
    );
    this._dialogplatz.replaceChildren(dlg);
  }

  _frage_download(z) {
    const t = this._t;
    const name = (z.anzeige || "").split("/").pop();
    this._dialog_zeigen(
      t.dialog_download(name),
      this._entwicklung[z.host]
        ? t.dialog_download_zweig(z.neueste || "—", z.host)
        : t.dialog_download_text(z.neueste || "—", z.host),
      z.installiert && z.installiert !== z.neueste ? t.aktualisieren : t.herunterladen,
      () => this._herunterladen(z)
    );
  }

  _frage_entfernen(z) {
    const t = this._t;
    const name = (z.anzeige || "").split("/").pop();
    this._dialog_zeigen(t.dialog_entfernen(name), t.dialog_entfernen_text, t.entfernen, () => this._deinstalliere(z), true);
  }

  /**
   * «Benutzerdefinierte Repositories» -- derselbe Dialog wie in HACS:
   * Adresse und Typ eintragen, Hinzufuegen; darunter die Liste mit
   * dem Muelleimer. Die Adresse nennt den Host, der Host waehlt die
   * Quelle -- eine fremde Instanz muss erst als Quelle eingerichtet sein.
   */
  _benutzerdefiniert(fehler_text) {
    const t = this._t;
    const zu = () => this._dialogplatz.replaceChildren();
    const feld = knoten("input", {
      class: "hl-feld",
      type: "url",
      placeholder: "https://gitlab.example.com/gruppe/projekt",
      "aria-label": t.repository_adresse,
    });
    const typ = knoten(
      "select",
      { class: "hl-feld", "aria-label": t.spalte_typ },
      Object.keys(t.typen).map((k) => knoten("option", { value: k }, t.typen[k]))
    );
    const meldung = knoten("div", { class: "hl-dlg-fehler" }, fehler_text || "");
    const knopf = knoten("button", { class: "hl-dlg-knopf hl-primaer" }, t.hinzufuegen);
    const absenden = async () => {
      const ziel = this._zerlege_adresse(feld.value);
      if (!ziel) {
        meldung.textContent = t.adresse_ungueltig;
        return;
      }
      if (!this._instanzen.includes(ziel.host)) {
        meldung.textContent = t.quelle_fehlt(ziel.host);
        return;
      }
      knopf.disabled = true;
      knopf.replaceChildren(knoten("ha-spinner", { size: "tiny" }));
      try {
        await this._hass.callWS({ type: "haigs/hinzufuegen", host: ziel.host, pfad: ziel.pfad, kategorie: typ.value });
        await this._lade();
        this._benutzerdefiniert();
      } catch (fehler) {
        this._benutzerdefiniert(this._fehlertext(fehler));
      }
    };
    knopf.addEventListener("click", absenden);
    feld.addEventListener("keydown", (ev) => ev.key === "Enter" && absenden());

    const liste = knoten(
      "div",
      { class: "hl-dlg-liste" },
      this._eintraege.map((e) =>
        knoten(
          "div",
          { class: "hl-dlg-zeile" },
          this._zeichen({ ...e, anzeige: this._kurzname(e.name) }, false),
          knoten(
            "div",
            { class: "hl-zelle-name" },
            knoten("div", { class: "hl-name" }, e.pfad || e.name),
            knoten("div", { class: "hl-beschr" }, (t.typen[e.kategorie] || e.kategorie) + " · " + e.host)
          ),
          knoten("ha-icon-button", {
            ".path": PFADE.loeschen,
            ".label": t.entfernen,
            onclick: async () => {
              try {
                await this._hass.callWS({ type: "haigs/entfernen", storage_key: e.storage_key });
              } catch (fehler) {
                this._melde(this._fehlertext(fehler));
              }
              await this._lade();
              this._benutzerdefiniert();
            },
          })
        )
      )
    );

    const dlg = knoten(
      "div",
      { class: "hl-dlg-grund", onclick: (ev) => ev.target === ev.currentTarget && zu() },
      knoten(
        "div",
        { class: "hl-dlg hl-dlg-breit", role: "dialog", "aria-modal": "true" },
        knoten(
          "div",
          { class: "hl-dlg-kopf" },
          knoten("div", { class: "hl-dlg-titel" }, t.benutzerdefiniert),
          knoten("ha-icon-button", { ".path": PFADE.schliessen, ".label": t.abbrechen, onclick: zu })
        ),
        liste,
        knoten("div", { class: "hl-dlg-form" }, feld, typ),
        meldung,
        knoten("div", { class: "hl-dlg-knoepfe" }, knopf)
      )
    );
    this._dialogplatz.replaceChildren(dlg);
    feld.focus();
  }

  /** Eine Repository-Adresse in Host und Pfad zerlegen (https, mit oder ohne .git). */
  _zerlege_adresse(text) {
    let roh = String(text || "").trim();
    if (!roh) return null;
    if (!/^[a-z]+:\/\//i.test(roh)) roh = "https://" + roh;
    try {
      const u = new URL(roh);
      const pfad = u.pathname
        .replace(/\/-\/.*$/, "")
        .replace(/\/(src|tree|blob|releases|issues)\/.*$/, "")
        .replace(/\.git$/, "")
        .replace(/^\/+|\/+$/g, "");
      if (!u.host || pfad.split("/").length < 2) return null;
      return { host: u.host, pfad };
    } catch (fehler) {
      return null;
    }
  }

  _ueber() {
    const t = this._t;
    const alt = TEXTE[sprache(this._hass)] || TEXTE.en;
    this._dialog_zeigen(t.ueber, t.ueber_text + " " + alt.fuss_zeile, "OK", async () => {});
  }

  async _herunterladen(z) {
    const t = this._t;
    this._beschaeftigt = true;
    try {
      let eintrag = z;
      if (z._fund) {
        await this._hass.callWS({ type: "haigs/hinzufuegen", host: z.host, pfad: z.full_name, kategorie: z.kategorie });
        // Die update-Entity entsteht im Hintergrund -- kurz warten, bis die Liste sie nennt.
        for (let i = 0; i < 20; i++) {
          const antwort = await this._hass.callWS({ type: "haigs/eintraege" });
          eintrag = (antwort.eintraege || []).find((e) => e.host === z.host && e.pfad === z.full_name);
          if (eintrag && eintrag.entity_id) break;
          await new Promise((r) => setTimeout(r, 750));
        }
      }
      if (!eintrag || !eintrag.entity_id) throw new Error("update-Entity fehlt");
      await this._hass.callService("update", "install", { entity_id: eintrag.entity_id });
      this._melde(t.erfolg_download((z.anzeige || "").split("/").pop()));
    } catch (fehler) {
      this._melde(this._fehlertext(fehler));
    }
    this._beschaeftigt = false;
    this._erneuert_am = 0;
    await this._erneuern();
  }

  async _deinstalliere(z) {
    const t = this._t;
    try {
      await this._hass.callWS({ type: "haigs/deinstallieren", storage_key: z.storage_key });
      this._melde(t.erfolg_entfernt((z.anzeige || "").split("/").pop()));
    } catch (fehler) {
      this._melde(this._fehlertext(fehler));
    }
    await this._lade();
  }

  async _entferne_eintrag(z) {
    try {
      await this._hass.callWS({ type: "haigs/entfernen", storage_key: z.storage_key });
    } catch (fehler) {
      this._melde(this._fehlertext(fehler));
    }
    if (this._detail) this._schliesse_detail();
    await this._lade();
  }
}

customElements.define("haigs-panel", HaigsPanel);

const LADEN_STIL = `
  :host {
    display: block;
    height: 100%;
    --hl-akzent: #fc6d26;
    --hl-akzent-text: #ffffff;
  }
  .hl-seite { height: 100%; }
  .hl-seite[hidden] { display: none; }
  hass-tabs-subpage-data-table { height: 100%; }
  .hl-warte, .hl-warte-klein {
    display: flex; align-items: center; justify-content: center;
  }
  .hl-warte { height: 100vh; }
  .hl-warte-klein { padding: 48px 0; }
  .hl-zeichen {
    border-radius: 6px; object-fit: contain; display: block;
  }
  .hl-buchstabe {
    display: flex; align-items: center; justify-content: center;
    font-weight: 500; font-size: 16px;
  }
  .hl-zelle-name { overflow: hidden; min-width: 0; }
  .hl-name {
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .hl-beschr {
    color: var(--secondary-text-color);
    font-size: 12px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .hl-quelle {
    color: var(--secondary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .hl-filter { padding: 0; }
  .hl-filter ha-expansion-panel {
    --expansion-panel-content-padding: 0 16px;
    border-bottom: 1px solid var(--divider-color);
  }
  .hl-filter-inhalt { display: flex; flex-direction: column; padding: 4px 0 12px; }
  .hl-haken {
    display: flex; align-items: center; gap: 12px;
    padding: 6px 0; cursor: pointer; color: var(--primary-text-color);
  }
  .hl-haken input { accent-color: var(--primary-color); width: 18px; height: 18px; }

  .hl-detail {
    background: var(--primary-background-color);
    min-height: 100%;
    position: relative;
  }
  .hl-kopf {
    position: sticky; top: 0; z-index: 4;
    display: flex; align-items: center; gap: 8px;
    height: var(--header-height, 56px);
    padding: 0 4px 0 calc(4px + env(safe-area-inset-left));
    background: var(--app-header-background-color, var(--primary-background-color));
    color: var(--app-header-text-color, var(--primary-text-color));
    border-bottom: var(--app-header-border-bottom, 1px solid var(--divider-color));
    box-sizing: border-box;
  }
  .hl-kopf-titel {
    flex: 1; font-size: 20px; font-weight: 400;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .hl-detail-inhalt {
    max-width: 1100px; margin: 0 auto; padding: 8px 8px 96px; box-sizing: border-box;
  }
  .hl-detail-karte { display: block; padding: 16px; }
  .hl-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
  .hl-chips ha-assist-chip.hl-klickbar { cursor: pointer; }
  .hl-zustand-platz { margin: 0 0 12px; }
  .hl-readme { display: block; overflow-wrap: anywhere; }
  .hl-readme img { max-width: 100%; }
  .hl-leer { color: var(--secondary-text-color); padding: 16px 0; }

  .hl-fuss {
    display: flex; align-items: center; justify-content: center; gap: 8px;
    padding: 20px 16px 8px; color: var(--secondary-text-color);
    font-size: 12px; text-align: center; transition: color .2s;
  }
  .hl-fuss-fuchs { height: 18px; width: auto; flex: 0 0 auto; }
  .hl-fuss:hover { color: var(--primary-text-color); }
  .hl-fuss:hover .hl-fuss-fuchs { animation: hl-fuchs-tanz .6s ease; }
  @keyframes hl-fuchs-tanz {
    25% { transform: rotate(-9deg); }
    60% { transform: rotate(7deg); }
    100% { transform: rotate(0); }
  }

  .hl-fab {
    position: fixed;
    right: calc(16px + env(safe-area-inset-right));
    bottom: calc(16px + env(safe-area-inset-bottom));
    z-index: 5;
    display: inline-flex; align-items: center; gap: 12px;
    height: 56px; padding: 0 20px 0 16px;
    border: none; border-radius: 16px; cursor: pointer;
    background: var(--hl-akzent); color: var(--hl-akzent-text);
    font: inherit; font-weight: 500; font-size: 14px;
    letter-spacing: 0.9px; text-transform: uppercase;
    box-shadow: 0 3px 5px -1px rgba(0,0,0,.2), 0 6px 10px 0 rgba(0,0,0,.14), 0 1px 18px 0 rgba(0,0,0,.12);
    transition: box-shadow 0.2s, filter 0.2s;
  }
  .hl-fab:hover { filter: brightness(1.08); box-shadow: 0 5px 5px -3px rgba(0,0,0,.2), 0 8px 10px 1px rgba(0,0,0,.14), 0 3px 14px 2px rgba(0,0,0,.12); }

  .hl-dlg-grund {
    position: fixed; inset: 0; z-index: 10;
    background: rgba(0,0,0,0.5);
    display: flex; align-items: center; justify-content: center; padding: 16px;
  }
  .hl-dlg {
    background: var(--ha-dialog-surface-background, var(--card-background-color));
    color: var(--primary-text-color);
    border-radius: var(--ha-dialog-border-radius, 24px);
    padding: 24px; width: 100%; max-width: 480px; box-sizing: border-box;
    box-shadow: 0 11px 15px -7px rgba(0,0,0,.2), 0 24px 38px 3px rgba(0,0,0,.14);
  }
  .hl-dlg-titel { font-size: 22px; line-height: 28px; margin-bottom: 16px; }
  .hl-dlg-breit { max-width: 560px; }
  .hl-dlg-kopf { display: flex; align-items: flex-start; justify-content: space-between; }
  .hl-dlg-liste { max-height: 40vh; overflow-y: auto; margin: 0 -8px 16px; }
  .hl-dlg-zeile { display: flex; align-items: center; gap: 12px; padding: 4px 8px; }
  .hl-dlg-zeile .hl-zelle-name { flex: 1; }
  .hl-dlg-form { display: flex; gap: 8px; flex-wrap: wrap; }
  .hl-feld {
    flex: 1 1 200px; height: 48px; padding: 0 12px; box-sizing: border-box;
    border-radius: 8px; border: 1px solid var(--outline-color, var(--divider-color));
    background: var(--input-fill-color, transparent); color: var(--primary-text-color); font: inherit;
  }
  select.hl-feld { flex: 0 1 160px; }
  .hl-feld:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
  .hl-dlg-fehler { color: var(--error-color); min-height: 20px; margin-top: 8px; font-size: 14px; }
  .hl-dlg-text { color: var(--secondary-text-color); line-height: 20px; }
  .hl-dlg-knoepfe { display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px; }
  .hl-dlg-knopf {
    min-width: 64px; height: 40px; padding: 0 16px;
    border-radius: 20px; border: none; cursor: pointer;
    background: transparent; color: var(--primary-color);
    font: inherit; font-weight: 500;
  }
  .hl-dlg-knopf:hover { background: rgba(var(--rgb-primary-color, 3,169,244), 0.08); }
  .hl-dlg-knopf.hl-primaer { background: var(--hl-akzent); color: var(--hl-akzent-text); }
  .hl-dlg-knopf.hl-warnung { background: var(--error-color); color: #fff; }
`;
