# HAIGS in detail

## Using HAIGS

- **The panel – instantly familiar:** the same data table as the HACS store
  (filters, search, grouping by status, sorting, column picker), the same
  groups (*Pending update*, *Downloaded*, *New*, *Available for download*),
  the same detail page with README, chips for owner, source, stars, issues
  and version, and the *Download* button. Its own touch: GitLab orange as the
  accent and a **Source** column (forge and host) where HACS counts
  downloads. Every detail page has its own address – browser back and shared
  links work.
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
- **Never an empty store:** the list lives in a
  per-instance cache in Home Assistant's storage (`haigs.lager.<host>`).
  Opening the panel paints from that cache instantly (no network
  round-trip), then runs the fresh check in the background and re-renders
  when it lands. After a restart the cache is read while Home Assistant is
  still booting; the first background run follows shortly, and the same
  check interval keeps the cache fresh —
  `haigs_aktualisiert` events repaint the panel while it stays open.
  The refresh button still forces a run at any time.
- **Add a custom repository:** panel → ⋮ → *Custom repositories* (like
  in HACS), paste the project URL, pick a category. HAIGS reads the metadata, the version,
  and offers the install.
- **Discover:** repositories whose owner set the topic `hacs` on their
  GitLab, Gitea, or Forgejo project show up in the panel's *New* section
  — with description, stars, and the latest version. A second topic
  (`hacs-plugin`, `hacs-theme`, …) fixes the category without asking.
- **Official HACS repositories:** Settings → Devices & services → HAIGS →
  *Configure* → *Show official HACS repositories*. This adds a separate
  "HACS" source (the catalog from `data-v2.hacs.xyz`, no token needed):
  about 4000 integrations, plugins, and themes appear in the *New* section,
  with download counts, so one store in the sidebar is enough. The same
  switch removes the source again; developer mode does not apply to it.
- **Updates:** every entry gets an update entity and a check interval
  you can tune per entry. A new release or tag raises the update,
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
  yourself. The store says so in three places: every installed
  integration carries a **state chip** on its card (restart required /
  ready to set up — a button that opens *Devices & Services* / configured /
  configured via configuration.yaml / not loaded — check the log), the
  install raises a **persistent notification** with the same advice (the
  path HACS takes), and the repair note stays as it was. Integrations
  without a setup dialog (`config_flow: false` in their manifest.json) can
  never appear under *Devices & Services* at all — the chip names the YAML
  route instead of leaving you guessing.
- **Robust inventory:** a renamed project is recognised by its ID and the name
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
   as well, covered by the test suite:

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

## Troubleshooting

- **The connection test fails:** Leave *Provider* set to `auto` first. If
  detection cannot identify the server, choose GitLab, Gitea, or Forgejo
  explicitly. Public repositories usually need no token; private repositories
  need a read token (`read_api` on GitLab, or a token with read permission on
  Gitea/Forgejo).
- **A server uses a self-signed certificate:** Keep TLS verification enabled
  for normal HTTPS connections. Disable it only for a certificate you trust.
  Use an explicit `http://` address only on a trusted network — a token sent
  over HTTP is unencrypted.
- **A repository is missing from *New*:** Automatic discovery requires the
  `hacs` topic and a valid `hacs.json` on the default branch. A repository
  added explicitly through *Custom repositories* does not need the topic.
- **An update does not appear immediately:** Each instance is checked on its
  configured check interval; the default is 720 minutes (12 hours). Use
  the panel's refresh action for an immediate check. If a forge is unreachable,
  the cached list may remain visible until a later check succeeds.
- **An installed integration is not available:** Restart Home Assistant after
  installation, then add the integration under *Settings → Devices & services*
  if it exposes a config flow. Integrations with `config_flow: false` require
  their documented YAML setup and do not appear in the add-integration dialog.
- **Know what is being installed:** HAIGS supports GitLab, Gitea, and
  Forgejo/Codeberg, plus the separate official HACS catalog source. Archive
  checks protect installation paths; they do not audit the downloaded code or
  make an unfamiliar repository trustworthy.
