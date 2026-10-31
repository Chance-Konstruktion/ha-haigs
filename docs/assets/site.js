(() => {
  "use strict";

  const WORDS = {
    de: {
      skip:"Zum Inhalt springen", nav_vision:"Warum HAIGS", nav_features:"Funktionen", nav_safety:"Sicherheit", nav_install:"Installation",
      hero_eyebrow:"OPEN SOURCE · HOME ASSISTANT INTEGRATION", hero_title_a:"Deine Forge.", hero_title_b:"Deine Regeln.",
      hero_lead:"Der Store für Home Assistant, der dort sucht, wo dein Code lebt: GitLab, Forgejo und Gitea.",
      hero_sub:"Entdecken, installieren und aktualisieren – in einer Oberfläche, nativ in Home Assistant. Und HACS bleibt genau dort, wo es ist.",
      hero_cta:"HAIGS entdecken", hero_github:"Repository ansehen", proof_native:"Native HA-Integration", proof_parallel:"Läuft neben HACS", proof_license:"MIT-Lizenz",
      preview_live:"VORSCHAU", preview_sources:"QUELLEN", preview_repos:"BEISPIELE", preview_search:"Repositories durchsuchen …", preview_project:"PROJEKT", preview_source:"QUELLE", preview_state:"STATUS",
      preview_installed:"Installiert", preview_new:"Neu", preview_connected:"3 Quellen verbunden", preview_note:"SCHEMATISCH · KEINE LIVE-DATEN",
      demo_all:"Alle", demo_integrations:"Integrationen", demo_themes:"Themes", demo_dev:"Entwicklermodus",
      float_update:"Automatische Updates", float_interval:"Dein Intervall. Dein Takt.", float_safe:"Sicher entpackt", float_archive:"Geprüft vor dem Schreiben",
      hero_bottom:"DIE QUELLEN, DIE DU SELBST BETREIBST.", signal_one:"Ein Store. Mehrere Schmieden.", signal_two:"Instanzen ohne künstliches Limit", signal_three:"HACS-Forks oder HACS-Patches", signal_four:"Open Source · MIT",
      section_vision:"DIE IDEE", vision_kicker:"DEIN CODE. DEINE INFRASTRUKTUR.", vision_title:"Home Assistant sollte nicht vorschreiben, wo du deinen Code hostest.",
      vision_copy:"Viele gute Integrationen, Plugins und Themes leben auf selbst gehosteten Git-Servern oder Codeberg. HAIGS bringt sie in einen Store, der sich in Home Assistant zu Hause fühlt – ohne eine zweite Welt neben deiner bestehenden Installation aufzubauen.",
      vision_note:"HACS bleibt installiert. HAIGS ergänzt es – nicht mehr und nicht weniger.", vision_link:"Alle Funktionen im Detail ↗", quote:"Ein Zuhause für Projekte, die nicht auf GitHub wohnen.",
      section_features:"WAS DRINSTECKT", features_kicker:"MEHR ALS EIN DOWNLOAD-KNOPF", features_title:"Ein Store mit Substanz.", features_intro:"Vom ersten Verbindungsversuch bis zur sauberen Deinstallation: HAIGS denkt den ganzen Lebenszyklus mit.",
      feature_forge_title:"Deine Forge. Ein Store.", feature_forge_copy:"GitLab, Forgejo und Gitea – öffentlich oder selbst gehostet. Beliebig viele Instanzen, jeweils mit eigenem Anbieter, Token und Prüfintervall.",
      feature_discovery_title:"Finden statt abtippen.", feature_discovery_copy:"Entdecke Projekte über das Topic hacs. Die passende hacs.json wird geprüft; die Aufnahme bleibt deine Entscheidung.",
      version_available:"UPDATE VERFÜGBAR", feature_updates_title:"Updates im richtigen Takt.", feature_updates_copy:"Eine Update-Entity pro Repository. Releases haben Vorrang, Tags sind der Rückfall – Vorabversionen bleiben optional.",
      feature_dev_title:"Direkt auf den Entwicklungszweig.", feature_dev_copy:"Der Entwicklermodus installiert auf Wunsch den neuesten Stand des Standardzweigs – ideal zum Testen eigener Arbeit, getrennt je Instanz.",
      feature_panel_title:"Fühlt sich in Home Assistant zu Hause an.", feature_panel_copy:"Native Seitenleiste, HACS-vertraute Tabellenansicht, Suche, Filter, Gruppierung, Detailseiten mit README und Releases – inklusive Statushinweisen nach der Installation.",
      mini_ready:"Aktuell", mini_update:"Update", mini_new:"Neu", catalog_source:"KATALOGQUELLE", feature_catalog_title:"HACS-Katalog optional dabei.", feature_catalog_copy:"Schalte den offiziellen HACS-Katalog als zusätzliche Quelle frei. Ein Store in der Seitenleiste reicht – HACS selbst bleibt unangetastet.",
      section_flow:"DER ABLAUF", flow_kicker:"WENIGE SCHRITTE. KLARE KONTROLLE.", flow_title:"Von der Forge bis ins Zuhause.", flow_intro:"Keine Blackbox: Du bestimmst Quelle, Kategorie und Zeitpunkt. HAIGS übernimmt die wiederkehrende Arbeit.",
      step_one_title:"Verbinden", step_one_copy:"Instanz hinzufügen. Anbieter automatisch erkennen lassen. Für private Projekte ein Read-only-Token hinterlegen.", step_one_foot:"DEIN HOST · DEIN TOKEN",
      step_two_title:"Entdecken", step_two_copy:"Nach Gruppen oder Stichworten suchen. HAIGS prüft Topic und Metadaten – du nimmst passende Projekte auf.", step_two_foot:"FINDEN · PRÜFEN · AUSWÄHLEN",
      step_three_title:"Installieren", step_three_copy:"Release-ZIP bevorzugen, sonst Tag-Archiv. Der Zielpfad wird anhand der HACS-Kategorie bestimmt.", step_three_foot:"STAGING · PRÜFEN · TAUSCHEN",
      step_four_title:"Aktuell bleiben", step_four_copy:"HAIGS prüft nach deinem Intervall. Updates, Neustart-Hinweise und Deinstallation haben ihren eigenen, nachvollziehbaren Weg.", step_four_foot:"AUTOMATISCH · NACHVOLLZIEHBAR",
      section_safety:"SICHERHEIT & VERTRAUEN", safety_kicker:"SCHUTZ VOR DEM SCHREIBEN", safety_title:"Ein Archiv darf nicht über dein System bestimmen.",
      safety_intro:"HAIGS behandelt Installationsarchive als nicht vertrauenswürdige Eingabe. Erst prüfen, dann in einem Zwischenbereich entpacken, anschließend atomar austauschen – bei einem Fehler bleibt der alte Stand erhalten.",
      safety_point_one:"Schutz gegen Pfad-Ausbrüche, absolute Pfade und Windows-Laufwerksnamen.",
      safety_point_two:"Symlinks, Gerätedateien, doppelte und verschlüsselte ZIP-Einträge werden abgewiesen.",
      safety_point_three:"Grenzen für Dateianzahl, Gesamtgröße und einzelne Dateien – geprüft vor und während des Lesens.",
      safety_point_four:"Deinstallation entfernt nur den aufgezeichneten Installationspfad bzw. die tatsächlich installierten Dateien.",
      safety_honesty:"Wichtig: Das schützt den Installationsvorgang – es ist kein Sicherheitsaudit des heruntergeladenen Codes. Installiere nur Quellen, denen du vertraust.",
      guard_title:"ARCHIV-WÄCHTER", guard_status:"AKTIV", guard_stage_one:"Unbekanntes Archiv", guard_stage_one_sub:"Noch keine Datei geschrieben", guard_stage_two:"Inhalt und Pfade geprüft", guard_stage_two_sub:"Grenzen · Typen · Zielpfade", guard_stage_three:"Atomarer Austausch", guard_stage_three_sub:"Rollback, wenn etwas schiefgeht",
      guard_metric_one:"MAX. ZIP-EINTRÄGE", guard_metric_two:"MAX. ENTPACKT", guard_metric_three:"MAX. PRO DATEI", guard_footer:"GRENZEN AUS DEM KERN · KEIN MARKETING-VERSPRECHEN",
      section_install:"LOS GEHT'S", install_kicker:"DEIN NÄCHSTER SCHRITT", install_title:"Mach deine Forge zum Teil deines Zuhauses.",
      install_intro:"Installiere HAIGS über HACS, verbinde deine erste Instanz und lass den Store den Rest erledigen.",
      install_hacs:"Über HACS öffnen", install_release:"Releases herunterladen", requirements:"Voraussetzung", requirements_token:"Token nur für private Repositories nötig",
      install_step_one:"In HACS hinzufügen", install_step_one_sub:"Repository als Integration hinzufügen und HAIGS herunterladen.",
      install_step_two:"Home Assistant neu starten", install_step_two_sub:"Danach HAIGS unter Geräte & Dienste hinzufügen.",
      install_step_three:"Forge verbinden", install_step_three_sub:"Host eingeben, Auto-Erkennung nutzen, optional Read-only-Token setzen.",
      install_step_four:"Store öffnen", install_step_four_sub:"HAIGS erscheint in der Seitenleiste. Weitere Instanzen sind jederzeit möglich.",
      owners_kicker:"FÜR PROJEKT- UND REPOSITORY-OWNER", owners_title:"Mach dein Projekt auffindbar.",
      owners_intro:"Ein Topic, eine Metadatendatei und ein Release – damit kann HAIGS dein Repository entdecken und anbieten.",
      owners_link:"Voraussetzungen für Repositorys ↗", copy_json:"JSON kopieren", code_foot:"DEFAULT BRANCH · RELEASE ODER TAG",
      section_faq:"GUTE FRAGEN", faq_kicker:"BEVOR DU LOSLEGST", faq_title:"Noch kurz gefragt?",
      faq_one_q:"Ersetzt HAIGS HACS?", faq_one_a:"Nein. HAIGS ist eine eigenständige Integration und läuft parallel zu HACS. Es verändert keinen HACS-Code.",
      faq_two_q:"Brauche ich einen Token?", faq_two_a:"Für öffentliche Repositories in der Regel nicht. Private Projekte benötigen ein Token mit Leserechten. HAIGS sendet es nur an den konfigurierten Forge-Host.",
      faq_three_q:"Unterstützt HAIGS GitHub als beliebige Forge?", faq_three_a:"Der eigene Store unterstützt GitLab, Gitea und Forgejo. Zusätzlich kann der offizielle HACS-Katalog als eigene Quelle eingebunden werden.",
      faq_four_q:"Ist der heruntergeladene Code damit sicher?", faq_four_a:"Nein. HAIGS prüft Archive und Installationspfade technisch, auditiert aber nicht den Inhalt. Die Vertrauensentscheidung für ein Repository bleibt bei dir.",
      footer_tagline:"Deine Forge. Deine Regeln.", footer_copy:"Gebaut für Freiheit – und für die Projekte, die du selbst hostest.", footer_releases:"Releases", footer_docs:"Dokumentation", footer_open:"OPEN SOURCE · BUILT WITH CARE", back_top:"Zurück nach oben ↑"
    },
    en: {
      skip:"Skip to content", nav_vision:"Why HAIGS", nav_features:"Features", nav_safety:"Security", nav_install:"Install",
      hero_eyebrow:"OPEN SOURCE · HOME ASSISTANT INTEGRATION", hero_title_a:"Your forge.", hero_title_b:"Your rules.",
      hero_lead:"The Home Assistant store that looks where your code lives: GitLab, Forgejo and Gitea.",
      hero_sub:"Discover, install and update from one native Home Assistant interface. And HACS stays exactly where it is.",
      hero_cta:"Explore HAIGS", hero_github:"View repository", proof_native:"Native HA integration", proof_parallel:"Runs alongside HACS", proof_license:"MIT license",
      preview_live:"PREVIEW", preview_sources:"SOURCES", preview_repos:"EXAMPLES", preview_search:"Search repositories …", preview_project:"PROJECT", preview_source:"SOURCE", preview_state:"STATUS",
      preview_installed:"Installed", preview_new:"New", preview_connected:"3 sources connected", preview_note:"SCHEMATIC · NO LIVE DATA",
      demo_all:"All", demo_integrations:"Integrations", demo_themes:"Themes", demo_dev:"Developer mode",
      float_update:"Automatic updates", float_interval:"Your interval. Your pace.", float_safe:"Safely extracted", float_archive:"Checked before writing",
      hero_bottom:"THE SOURCES YOU RUN YOURSELF.", signal_one:"One store. Multiple forges.", signal_two:"As many instances as you need", signal_three:"HACS forks or patches", signal_four:"Open source · MIT",
      section_vision:"THE IDEA", vision_kicker:"YOUR CODE. YOUR INFRASTRUCTURE.", vision_title:"Home Assistant shouldn't dictate where you host your code.",
      vision_copy:"Great integrations, plugins and themes live on self-hosted Git servers and Codeberg, too. HAIGS brings them into a store that feels at home in Home Assistant—without building a second world beside your existing setup.",
      vision_note:"Keep HACS installed. HAIGS complements it—nothing more, nothing less.", vision_link:"Explore all features ↗", quote:"A home for projects that don't live on GitHub.",
      section_features:"WHAT'S INSIDE", features_kicker:"MORE THAN A DOWNLOAD BUTTON", features_title:"A store with substance.", features_intro:"From the first connection attempt to clean removal, HAIGS considers the entire lifecycle.",
      feature_forge_title:"Your forge. One store.", feature_forge_copy:"GitLab, Forgejo and Gitea—public or self-hosted. Add as many instances as you need, each with its own provider, token and check interval.",
      feature_discovery_title:"Find it. Don't type it in.", feature_discovery_copy:"Discover projects through the hacs topic. HAIGS validates the matching hacs.json; adding a repository remains your choice.",
      version_available:"UPDATE AVAILABLE", feature_updates_title:"Updates on your schedule.", feature_updates_copy:"One update entity per repository. Releases first, tags as fallback—and pre-releases are optional.",
      feature_dev_title:"Track the development branch.", feature_dev_copy:"Developer mode can install the latest default-branch snapshot—useful for testing your own work, configured per instance.",
      feature_panel_title:"Feels at home in Home Assistant.", feature_panel_copy:"Native sidebar, HACS-familiar data table, search, filters, grouping and repository details with README and releases—including setup and restart guidance.",
      mini_ready:"Current", mini_update:"Update", mini_new:"New", catalog_source:"CATALOG SOURCE", feature_catalog_title:"Optional HACS catalog.", feature_catalog_copy:"Enable the official HACS catalog as an additional source. One sidebar store is enough—HACS itself remains untouched.",
      section_flow:"THE WORKFLOW", flow_kicker:"A FEW STEPS. CLEAR CONTROL.", flow_title:"From forge to your home.", flow_intro:"No black box: you choose the source, category and timing. HAIGS takes care of the recurring work.",
      step_one_title:"Connect", step_one_copy:"Add an instance. Let HAIGS detect the provider. Add a read-only token for private projects.", step_one_foot:"YOUR HOST · YOUR TOKEN",
      step_two_title:"Discover", step_two_copy:"Search by group or keyword. HAIGS checks the topic and metadata—you choose which projects to add.", step_two_foot:"FIND · VALIDATE · CHOOSE",
      step_three_title:"Install", step_three_copy:"Prefer a release ZIP, otherwise use the tag archive. The destination follows the HACS category.", step_three_foot:"STAGE · VALIDATE · SWAP",
      step_four_title:"Stay current", step_four_copy:"HAIGS checks on your schedule. Updates, restart notices and uninstall each have a clear, traceable path.", step_four_foot:"AUTOMATED · TRACEABLE",
      section_safety:"SECURITY & TRUST", safety_kicker:"PROTECTION BEFORE WRITING", safety_title:"An archive doesn't get to decide what happens to your system.",
      safety_intro:"HAIGS treats installation archives as untrusted input. It validates first, extracts into staging, then swaps atomically—if anything fails, the previous installation stays in place.",
      safety_point_one:"Protection against path traversal, absolute paths and Windows drive paths.",
      safety_point_two:"Symlinks, device files, duplicate and encrypted ZIP entries are rejected.",
      safety_point_three:"Entry-count, total-size and per-file limits—checked before and while reading.",
      safety_point_four:"Uninstall removes only the recorded installation path or the files that were actually installed.",
      safety_honesty:"Important: these protections harden the installation process; they are not a security audit of downloaded code. Install only sources you trust.",
      guard_title:"ARCHIVE GUARD", guard_status:"ACTIVE", guard_stage_one:"Untrusted archive", guard_stage_one_sub:"No files written yet", guard_stage_two:"Contents and paths validated", guard_stage_two_sub:"Limits · Types · Destinations", guard_stage_three:"Atomic replacement", guard_stage_three_sub:"Rollback if something goes wrong",
      guard_metric_one:"MAX ZIP ENTRIES", guard_metric_two:"MAX EXPANDED", guard_metric_three:"MAX PER FILE", guard_footer:"LIMITS FROM THE CORE · NOT A MARKETING CLAIM",
      section_install:"GET STARTED", install_kicker:"YOUR NEXT STEP", install_title:"Bring your forge into your home.",
      install_intro:"Install HAIGS through HACS, connect your first instance and let the store take it from there.",
      install_hacs:"Open in HACS", install_release:"Download releases", requirements:"Requirement", requirements_token:"Token only needed for private repositories",
      install_step_one:"Add in HACS", install_step_one_sub:"Add the repository as an integration and download HAIGS.",
      install_step_two:"Restart Home Assistant", install_step_two_sub:"Then add HAIGS under Devices & services.",
      install_step_three:"Connect your forge", install_step_three_sub:"Enter the host, use automatic detection and optionally add a read-only token.",
      install_step_four:"Open the store", install_step_four_sub:"HAIGS appears in the sidebar. Add more instances whenever you need.",
      owners_kicker:"FOR PROJECT AND REPOSITORY OWNERS", owners_title:"Make your project discoverable.",
      owners_intro:"One topic, one metadata file and a release—that's enough for HAIGS to discover and offer your repository.",
      owners_link:"Repository requirements ↗", copy_json:"Copy JSON", code_foot:"DEFAULT BRANCH · RELEASE OR TAG",
      section_faq:"GOOD QUESTIONS", faq_kicker:"BEFORE YOU START", faq_title:"A few quick answers.",
      faq_one_q:"Does HAIGS replace HACS?", faq_one_a:"No. HAIGS is a standalone integration that runs alongside HACS. It does not modify HACS code.",
      faq_two_q:"Do I need a token?", faq_two_a:"Usually not for public repositories. Private projects need a read-only token. HAIGS sends it only to the configured forge host.",
      faq_three_q:"Does HAIGS support GitHub as a generic forge?", faq_three_a:"The HAIGS store supports GitLab, Gitea and Forgejo. The official HACS catalog can also be enabled as a separate source.",
      faq_four_q:"Does this make downloaded code safe?", faq_four_a:"No. HAIGS validates archives and installation paths, but does not audit the code itself. You remain responsible for trusting a repository.",
      footer_tagline:"Your forge. Your rules.", footer_copy:"Built for freedom—and for the projects you host yourself.", footer_releases:"Releases", footer_docs:"Documentation", footer_open:"OPEN SOURCE · BUILT WITH CARE", back_top:"Back to top ↑"
    }
  };

  const languageButton = document.querySelector("[data-language-toggle]");
  const applyLanguage = (language) => {
    const lang = language === "en" ? "en" : "de";
    const table = WORDS[lang];
    document.documentElement.lang = lang;
    document.title = lang === "de" ? "HAIGS — Deine Forge. Deine Regeln." : "HAIGS — Your forge. Your rules.";
    const description = document.querySelector('meta[name="description"]');
    if (description) description.content = lang === "de"
      ? "HAIGS bringt GitLab, Forgejo und Gitea als eigenen Store nach Home Assistant. Mehrere Instanzen, Repository-Entdeckung und sichere Updates – ohne HACS-Fork."
      : "Bring GitLab, Forgejo and Gitea repositories into Home Assistant. Discover, install and update self-hosted projects without replacing or forking HACS.";
    document.querySelectorAll("[data-i18n]").forEach((element) => {
      const value = table[element.dataset.i18n];
      if (typeof value === "string") element.textContent = value;
    });
    if (languageButton) {
      languageButton.textContent = lang === "de" ? "EN" : "DE";
      languageButton.setAttribute("aria-label", lang === "de" ? "Switch to English" : "Zu Deutsch wechseln");
      languageButton.title = lang === "de" ? "Switch to English" : "Zu Deutsch wechseln";
    }
    try { localStorage.setItem("haigs-language", lang); } catch (_) {}
  };

  let savedLanguage = "de";
  try {
    const remembered = localStorage.getItem("haigs-language");
    if (remembered === "en" || remembered === "de") savedLanguage = remembered;
  } catch (_) {}
  applyLanguage(savedLanguage);

  languageButton?.addEventListener("click", () => {
    applyLanguage(document.documentElement.lang === "de" ? "en" : "de");
  });

  const menuButton = document.querySelector(".mobile-menu");
  const nav = document.querySelector("#primary-nav");
  const closeMenu = () => {
    menuButton?.setAttribute("aria-expanded", "false");
    nav?.classList.remove("is-open");
  };
  menuButton?.addEventListener("click", () => {
    const open = menuButton.getAttribute("aria-expanded") !== "true";
    menuButton.setAttribute("aria-expanded", String(open));
    nav?.classList.toggle("is-open", open);
  });
  nav?.querySelectorAll("a").forEach((link) => link.addEventListener("click", closeMenu));
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeMenu();
  });

  const filters = document.querySelectorAll("[data-demo-filter]");
  const rows = document.querySelectorAll(".repo-row[data-demo-kind]");
  filters.forEach((button) => {
    button.addEventListener("click", () => {
      const selected = button.dataset.demoFilter;
      filters.forEach((item) => item.classList.toggle("is-active", item === button));
      rows.forEach((row) => { row.hidden = selected !== "all" && row.dataset.demoKind !== selected; });
    });
  });

  const devToggle = document.querySelector("[data-demo-dev]");
  const demoVersion = document.querySelector("[data-demo-version]");
  devToggle?.addEventListener("change", () => {
    if (!demoVersion) return;
    const enabled = devToggle.checked;
    demoVersion.textContent = enabled ? "main · 1a2b3c4" : (document.documentElement.lang === "de" ? "Update" : "Update");
    demoVersion.classList.toggle("state-update", !enabled);
    demoVersion.classList.toggle("state-dev", enabled);
    demoVersion.setAttribute("aria-label", enabled ? "Developer branch preview" : "Update available preview");
  });

  const copyButton = document.querySelector("[data-copy-json]");
  const jsonExample = JSON.stringify({ name: "My integration", render_readme: true, homeassistant: "2025.2.0" }, null, 2);
  copyButton?.addEventListener("click", async () => {
    const label = copyButton.querySelector("[data-i18n]");
    const previous = label?.textContent || "";
    try {
      await navigator.clipboard.writeText(jsonExample);
      if (label) label.textContent = document.documentElement.lang === "de" ? "Kopiert ✓" : "Copied ✓";
      copyButton.classList.add("is-copied");
    } catch (_) {
      if (label) label.textContent = document.documentElement.lang === "de" ? "Kopieren nicht möglich" : "Copy unavailable";
    }
    window.setTimeout(() => {
      if (label) label.textContent = previous;
      copyButton.classList.remove("is-copied");
    }, 1800);
  });

  document.querySelectorAll("[data-current-year]").forEach((node) => {
    node.textContent = String(new Date().getFullYear());
  });

  const revealItems = document.querySelectorAll(".reveal");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries, instance) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          instance.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -35px 0px" });
    revealItems.forEach((item) => observer.observe(item));
  } else {
    revealItems.forEach((item) => item.classList.add("is-visible"));
  }
})();