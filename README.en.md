# HAIGS

**H**ome**A**ssistant-**I**mport-**G**it-**S**torage

<p align="center">
  <img src="logo.png" alt="HAIGS — the GitLab fox taking over the Home Assistant house" width="192">
</p>

> 🇬🇧 English · [🇩🇪 Deutsch](README.md)

HACS behaviour for self-hosted Git forges: add, discover, and update Home
Assistant custom components that live on **GitLab**, **Gitea**, or **Forgejo**
([Codeberg](https://codeberg.org)) — the way HACS does it for GitHub.

**Not a fork.** HAIGS is its own Home Assistant integration that runs
*alongside* HACS. We change no HACS code and copy none. There is a reason:
a fork would have to chase every HACS release, and nobody but us would ever
use it.

## The problem

HACS knows exactly one source: GitHub. A custom repository with a GitLab
address is rejected; there is no switch for it. If your integrations live on
your own — or any other — GitLab, Gitea, or Forgejo instance, you install
by hand and never learn that a new version exists.

HAIGS closes that gap. It speaks to all three families directly: it finds
repositories tagged for discovery, reads their metadata, compares versions,
downloads the version archive, and installs it safely.

## Installation

**Via HACS (recommended)**

1. HACS → ⋮ → *Custom repositories* →
   `https://github.com/Chance-Konstruktion/ha-haigs`, type *Integration*.
2. Download **HAIGS** and restart Home Assistant.
3. *Settings → Devices & services → Add integration* → **HAIGS**. Enter
   your instance's host (gitlab.com, codeberg.org, gitea.com or self-hosted)
   and optionally a read token. Leave the provider on **auto** – HAIGS
   detects whether GitLab, Forgejo or Gitea answers.
4. **HAIGS** appears in the sidebar. Add more instances the same way – as
   many as you like, in any mix.

From then on HAIGS can keep itself up to date: add this repository to
its own list and every new release shows up as an update.

**Manually:** unpack `haigs-vX.Y.Z.zip` from the
[releases page](https://github.com/Chance-Konstruktion/ha-haigs/releases)
into your configuration directory (it contains exactly
`custom_components/haigs/`), restart, continue with step 3. Every release
note carries the SHA-256; the build is deterministic.

**Requirements:** Home Assistant 2025.2 or newer (tested up to 2026.9). A read
token is only needed for private repositories (GitLab scope `read_api`, a
read-only token on Gitea/Forgejo).

> Setup and panel speak English and German.

## Using HAIGS

- **The panel – feels like HACS:** the same data table as the HACS store
  (filters, search, grouping by status, sorting, column picker), the same
  groups (*Pending update*, *Downloaded*, *New*, *Available for download*),
  the same detail page with README, chips for owner, source, stars, issues
  and version, and the *Download* button. Its own touch: GitLab orange as the
  accent and a **Source** column (forge and host) where HACS counts
  downloads. Every detail page has its own address – browser back and shared
  links work. At the bottom the tanuki signs: *“Made for freedom — no GitHub
  monopoly, because one platform is a single point of failure.”*
- **Icons like Home Assistant:** since 2026 integrations ship their icon in
  their own `brand/` folder. HAIGS shows it through Home Assistant's
  brands proxy – in the store and on updates.
- **Developer mode:** switch it on in an instance's options and HAIGS
  installs the latest state of the default branch instead of releases
  (`main@1a2b3c4`). Every push is testable right away, even without a release.
- **Unlimited servers, any mix:** every instance is one config entry —
  set up as many as you like, each with its own provider (GitLab,
  Forgejo, Gitea), token, and interval. The store shows them all as
  clickable instance chips — each labelled with its provider — with a
  dashed "+ Add instance" button that opens the setup dialog for the
  next domain. The empty store's first-run hint carries the same button.
- **Never an empty store:** the list lives in the *Lager* (the stock), a
  per-instance cache in Home Assistant's storage (`haigs.lager.<host>`).
  Opening the panel paints from that cache instantly (no network
  round-trip), then runs the fresh check in the background and re-renders
  when it lands. After a restart the cache is read while Home Assistant is
  still booting; the first background run follows shortly, and the same
  interval you set for the heartbeat keeps the cache fresh —
  `haigs_aktualisiert` events repaint the panel while it stays open.
  The refresh button still forces a run at any time.
- **Add a custom repository:** panel → ⋮ → *Custom repositories* (like
  in HACS), paste the project URL, pick a category. HAIGS reads the metadata, the version,
  and offers the install.
- **Discover:** repositories whose owner set the topic `hacs` on their
  GitLab, Gitea, or Forgejo project show up in the panel's *New* section
  — with description, stars, and the latest version. A second topic
  (`hacs-plugin`, `hacs-theme`, …) fixes the category without asking.
- **Updates:** every entry gets an update entity and a heartbeat whose
  interval you can tune per entry. A new release or tag raises the update,
  the install service swaps the files safely — staged in a temporary
  directory first, then an atomic switch, rolled back on failure.
- **Preferred source:** if a release carries exactly one ZIP attachment,
  that built artifact is installed instead of the auto-generated tag
  archive; anything ambiguous falls back to the archive. That fallback
  understands the repository layout: it finds `custom_components/<domain>/`
  at any depth and installs only that subtree — so the standard HACS
  structure installs as-is, without a built attachment (issue #15).
- **Uninstall & restart:** every entry with a recorded install also
  uninstalls — the recorded target path is checked against the known
  category roots, then removed in one move. Installing or uninstalling
  an **integration** raises a repair-center hint to restart Home
  Assistant (integrations only load at startup); the hint clears
  itself once the restart happened.
- **Where the integration ends up:** installing is not enough — Home
  Assistant scans `custom_components` only at startup, and the card under
  *Devices & Services* appears only once you add the integration there
  yourself. The store now says so in three voices: every installed
  integration carries a **state chip** on its card (restart required /
  ready to set up — a button that opens *Devices & Services* / configured /
  configured via configuration.yaml / not loaded — check the log), the
  install raises a **persistent notification** with the same advice (the
  path HACS takes), and the repair note stays as it was. Integrations
  without a setup dialog (`config_flow: false` in their manifest.json) can
  never appear under *Devices & Services* at all — the chip names the YAML
  route instead of leaving you guessing.
- **Robust stock:** a renamed project is recognised by its ID and the name
  follows silently; a reachable-but-changed repository is reported, never
  guessed; diagnostics never print your token in the clear.

## For repository owners

To make a project findable and installable by HAIGS (works the same on
GitLab, Gitea, and Forgejo/Codeberg):

1. Set the topic `hacs` under *Settings → General → Topics*.
2. Put a valid `hacs.json` on the default branch. Minimal shape:

   ```json
   {
     "name": "My integration",
     "render_readme": true,
     "homeassistant": "2025.2.0"
   }
   ```

   Repositories with a different layout set `content_in_root`,
   `zip_release`, or `filename` — the same conventions HACS established.
3. Publish versions as releases, or at least as tags. Releases win; tags
   are the fallback. No built artifact required: the auto-generated tag
   archive is enough — HAIGS recognises the `custom_components/<domain>/`
   folder inside it and installs exactly that subtree, leaving repository
   root files (README, CI config) out of the target. A release with a
   built ZIP attachment (the domain folder as its root) stays the most
   precise delivery and still wins when present. Three further shapes work
   as well, proven in the three-system test:

   - **flat ZIP attachments** — the contents of
     `custom_components/<domain>/` without any folder (the way many HACS
     repositories build them; the `manifest.json` at the root is proof
     enough),
   - **`filename` without an attachment** — when `hacs.json` names a file
     such as `powerline.zip` that belongs to a built release attachment and
     the attachment is missing, the install falls back quietly to the
     storage form of the tag archive instead of failing on a file that was
     never in the archive,
   - **version names like `github/260801`** — tags with a slash and date
     codes sort along and install along.

`hacs-development` as a second topic marks a repository as a development
state — it is only found when explicitly searched for.

## Safety

Installing code from a forge is a trust decision, not a technical one.
HAIGS takes the technical part seriously: version archives are unpacked
with path-escape, size, count, and symlink guards — four malicious test
archives (path traversal, giant file, symlink attack, zip bomb) are part of
the test suite and must be rejected *before* anything is written. The
integrity of an interrupted install never lies: staged first, switched
atomically, rolled back on failure.

## Repository layout

```
logo.png, original.png        brand artwork — the GitLab fox in the HA house
hacs.json                     repository conventions for HAIGS itself
custom_components/haigs/   the integration — thin Home Assistant layer
  manifest.json               domain, version, config flow, icon
  config_flow.py              setup dialog with connection check
  lager.py                    the store cache: persisted list + scan,
                              background interval, `haigs_aktualisiert`
  frontend/panel.js           the sidebar panel (no YAML) — GitLab-style
  frontend/iconset.js         the tanuki as sidebar icon (own icon
                              collection `haigs`, on every page)
  translations/               dialog texts
  core/                       the core — pure Python, no Home Assistant,
                              no network in tests; lives here since the
                              delivery-form decision (issue #11)
    forge.py                  the provider interface (GitLab, Forgejo, Gitea, …)
    gitlab_forge.py           GitLab REST v4
    forgejo_forge.py          Forgejo (Codeberg recordings)
    gitea_forge.py            Gitea — the Forgejo sister (topic search)
    schmiede.py               the forge factory + provider auto-detection
    http_aiohttp.py           aiohttp-backed HttpClient (session passed in)
    validierung.py            hacs.json, manifest.json
    versionen.py              version compare and update decision
    entdeckung.py             topic → candidate → validation
    entpacken.py              guarded unpacking, atomic install
auslieferung/release_bauen.py deterministic release archive builder
tests/                        core suite — pytest, no network
tests_ha/                     Home Assistant lane — offline, on a test double
```

## Development

Two lanes, one verdict: the core runs lean, the framework layer needs
Home Assistant (Python 3.13, `requirements-ha.txt`).

```bash
python -m pytest -q                       # core: no HA, no network
python -m pytest tests_ha -q -p pytest_homeassistant_custom_component
```

The hardening suites (`*_hart.py` in both lanes) run the code against
hostile input: UTF-8 BOM in `hacs.json` (Windows editors leave one),
five-segment versions where `.10` must beat `.9`, search words that look
like script injections, ten-thousand-character keywords, storage that is
not what the schema promised, captive portals answering with HTML instead
of JSON, and 500s where a GitLab was previously claimed out of thin air.
The DOM side is proven in a browser harness: hostile repository names,
descriptions, avatars (`javascript:` URLs fall back to the letter), and
search words arrive as *text*, never as live elements — no injected tag
ever executes.

On Windows set `PYTHONUTF8=1` first — otherwise healthy tests report
failures that are not there.

Releases are built deterministically by `auslieferung/release_bauen.py`:
fixed timestamps, sorted entries, reproducible bytes. A tag pipeline builds
the archive and attaches it to a release; the build refuses when the tag and
`manifest.json` disagree on the version.

**Where development happens.** This repository is developed on a self-hosted
GitLab — which is the whole point of the project — and mirrored to GitHub so
that people can find, install, and report against it. Identifiers, commit
messages and the engineering documents are German; that is a deliberate
decision, not an oversight. The reasoning lives in
[ARCHITEKTUR.md](ARCHITEKTUR.md) (the structural decisions),
[ROADMAP.md](ROADMAP.md) (milestones M0–M10 with their acceptance tests),
and [MITARBEIT.md](MITARBEIT.md) (how to contribute). The interface for a
second forge provider — and what HACS itself would have to adopt for one —
is written up in [PROPOSAL.md](PROPOSAL.md). You do not need German to use
HAIGS: this file, the setup dialog and the panel are English.

## License

[MIT](LICENSE) — Copyright (c) 2026 chance-konstruktion and the HAIGS
contributors.
