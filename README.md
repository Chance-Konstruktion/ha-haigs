# HAIGS

**H**ome**A**ssistant-**I**mport-**G**it-**S**torage

<p align="center">
  <img src="logo.png" alt="HAIGS logo" width="192">
</p>

> 🇬🇧 English · [🇩🇪 Deutsch](README.de.md)

A store for Home Assistant custom components that live on **GitLab**,
**Gitea** or **Forgejo** ([Codeberg](https://codeberg.org)) instead of
GitHub — add, discover and keep them up to date, self-hosted or public.

HACS only knows GitHub. HAIGS is a separate integration that runs *alongside*
HACS; it is not a fork and changes no HACS code.

## Features

- **Familiar store panel** — same table, groups, search, filters and detail
  page as the HACS store, with a *Source* column for the forge and host.
- **Any number of instances** — GitLab, Gitea and Forgejo in any mix, each
  with its own token and check interval; the provider is detected
  automatically.
- **Discovery** — projects with the topic `hacs` show up under *New*; a
  second topic (`hacs-plugin`, `hacs-theme`, …) sets the category.
- **Custom repositories** — paste any project URL, pick a category, install.
- **Updates** — one update entity per installed repository; releases first,
  tags as fallback.
- **Safe installs** — archives are checked for path escapes, size, file count
  and symlinks; files are staged and switched atomically, rolled back on
  failure; uninstall removes exactly what was installed.
- **Developer mode** — per instance, install the latest commit of the default
  branch instead of a release.
- **Optional official HACS catalog** — show the ~4000 HACS repositories in the
  same store, so one sidebar entry is enough.
- **Integration icons** from the repository's `brand/` folder, via Home
  Assistant's brands proxy.
- **Clear next steps** after installing an integration: restart hint, setup
  button, or a note when it needs YAML configuration.

Details: [docs/features.md](docs/features.md).

## Installation

**Via HACS (recommended)**

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chance-Konstruktion&repository=ha-haigs&category=integration)

Or by hand:

1. HACS → ⋮ → *Custom repositories* →
   `https://github.com/Chance-Konstruktion/ha-haigs`, type *Integration*.
2. Download **HAIGS** and restart Home Assistant.
3. *Settings → Devices & services → Add integration* → **HAIGS**. Enter the
   host (gitlab.com, codeberg.org, gitea.com or your own server) and, for
   private repositories, a read token. Leave the provider on **auto**.

   [![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=haigs)
4. **HAIGS** appears in the sidebar. Add more instances the same way.

**Manually:** unpack `haigs-vX.Y.Z.zip` from the
[releases page](https://github.com/Chance-Konstruktion/ha-haigs/releases) into
your configuration directory, restart, continue with step 3.

**Requirements:** Home Assistant 2025.2 or newer. A token is only needed for
private repositories (`read_api` on GitLab, a read-only token on
Gitea/Forgejo).

## For repository owners

1. Set the topic `hacs` on your project.
2. Put a valid `hacs.json` on the default branch:

   ```json
   {
     "name": "My integration",
     "render_readme": true,
     "homeassistant": "2025.2.0"
   }
   ```

3. Publish releases or tags. The standard HACS layout
   (`custom_components/<domain>/`) works without a built archive; a release
   with exactly one ZIP attachment is preferred when present.

More layouts and options: [docs/features.md](docs/features.md#for-repository-owners).

## Troubleshooting

See [docs/features.md](docs/features.md#troubleshooting) — connection test,
self-signed certificates, missing repositories, delayed updates.

## Development

```bash
python -m pytest -q                                              # core, no HA
python -m pytest tests_ha -q -p pytest_homeassistant_custom_component
```

On Windows set `PYTHONUTF8=1` first. Developed on a self-hosted GitLab and
mirrored to GitHub; code identifiers and engineering notes are German. See
[ARCHITEKTUR.md](ARCHITEKTUR.md), [CHANGELOG.md](CHANGELOG.md) and
[MITARBEIT.md](MITARBEIT.md).

## License

[MIT](LICENSE) — Copyright (c) 2026 chance-konstruktion and the HAIGS
contributors.
