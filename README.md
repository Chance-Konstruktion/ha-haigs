<div align="center">
  <img src="logo.png" alt="HAIGS fox logo" width="150">

  <h1>HAIGS</h1>
  <p><strong>Home Assistant Import · Git Storage</strong></p>
  <p><em>Your forge. Your rules.</em></p>

  <p>
    Bring GitLab, Forgejo and Gitea repositories into a native Home Assistant store.
    Discover, install and update self-hosted projects — without replacing or forking HACS.
  </p>

  <p>
    <a href="https://chance-konstruktion.github.io/ha-haigs/"><strong>Explore the HAIGS website →</strong></a>
    ·
    <a href="docs/features.md">Feature guide</a>
    ·
    <a href="https://github.com/Chance-Konstruktion/ha-haigs/releases">Releases</a>
  </p>

  <p>
    <img alt="Latest release" src="https://img.shields.io/github/v/release/Chance-Konstruktion/ha-haigs?display_name=tag&style=flat-square&color=fc6d26">
    <img alt="License" src="https://img.shields.io/github/license/Chance-Konstruktion/ha-haigs?style=flat-square">
    <img alt="Home Assistant" src="https://img.shields.io/badge/Home%20Assistant-2025.2%2B-41BDF5?style=flat-square&logo=homeassistant&logoColor=white">
    <img alt="HACS" src="https://img.shields.io/badge/HACS-compatible-18BCF2?style=flat-square">
  </p>
  <p>
    <a href="README.de.md">🇩🇪 Deutsche Dokumentation</a>
  </p>
</div>

---

**HAIGS gives Home Assistant a store for repositories that live outside GitHub.** It connects to GitLab, Forgejo and Gitea — public or self-hosted — and brings discovery, installation and updates into one familiar interface.

HAIGS is a standalone integration. It runs **alongside HACS**, does not fork it and does not modify HACS code.

## What you get

| Capability | What it does |
| --- | --- |
| **Multiple forges** | Connect any number of GitLab, Forgejo and Gitea instances. Provider detection is automatic or can be selected explicitly. |
| **Repository discovery** | Find projects by the \`hacs\` topic, group or keyword. HAIGS validates \`hacs.json\` before offering a candidate. |
| **Custom repositories** | Add a repository URL directly and choose its HACS category. |
| **Updates** | One Home Assistant update entity per repository. Releases take priority; tags are the fallback. Pre-releases are opt-in. |
| **Developer mode** | Install the latest snapshot of the default branch, configured per forge instance. |
| **Familiar store panel** | Native Home Assistant sidebar, search, filters, grouping, repository details, README and release notes. |
| **Optional HACS catalog** | Add the official HACS catalog as another source in the same store. |
| **Clean removal** | Track installed files so uninstall removes what HAIGS installed rather than wiping shared folders. |

## Installation

**Recommended: install through HACS.**

[![Open your Home Assistant instance and open this repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Chance-Konstruktion&repository=ha-haigs&category=integration)

1. In HACS, open **Custom repositories** and add  
   \`https://github.com/Chance-Konstruktion/ha-haigs\` as an **Integration**.
2. Download **HAIGS**, then restart Home Assistant.
3. Open **Settings → Devices & services → Add integration** and choose **HAIGS**.
4. Enter your forge host (for example \`gitlab.com\`, \`codeberg.org\`, \`gitea.com\` or your own server). Leave the provider on **Auto** unless you want to select it manually.
5. Add another HAIGS config entry for each additional forge instance.

[![Open your Home Assistant instance and start setting up the integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=haigs)

**Requirements:** Home Assistant 2025.2 or newer. Public repositories generally need no token. For private repositories, use a read-only token (GitLab: \`read_api\`; Gitea/Forgejo: repository read access). HAIGS scopes the authorization header to the configured forge host; release attachments on other hosts do not receive the token.

**Manual installation:** Download the archive from the [releases page](https://github.com/Chance-Konstruktion/ha-haigs/releases), extract it into \`config/custom_components/haigs\`, and restart Home Assistant.

## For repository owners

To make a project discoverable:

1. Add the topic \`hacs\` to the repository.
2. Place a valid \`hacs.json\` on its default branch. For example:

   \`\`\`json
   {
     "name": "My integration",
     "render_readme": true,
     "homeassistant": "2025.2.0"
   }
   \`\`\`

3. Publish releases or tags. The standard HACS layout \`custom_components/<domain>/\` is supported. If a release has exactly one ZIP attachment, HAIGS prefers that package; otherwise it uses the tag archive.

Category topics such as \`hacs-plugin\` and \`hacs-theme\` set the repository category. More layout details and supported metadata are in the [feature guide](docs/features.md#for-repository-owners).

## Installation safety

HAIGS treats archives as untrusted input and validates them before writing files. The core rejects path traversal and absolute paths, unsafe ZIP entry types, duplicate names and encrypted entries. It enforces limits on entry count and expanded size, stages changes before swapping them into place, and rolls back if replacement fails.

This protects the **installation process**. It does not audit, sandbox or certify the downloaded Python or JavaScript code. Only install repositories you trust.

## Development

The core can be tested without a Home Assistant installation:

\`\`\`bash
python -m pytest -q
\`\`\`

Run the Home Assistant integration tests with the custom-component test plugin installed:

\`\`\`bash
python -m pytest tests_ha -q -p pytest_homeassistant_custom_component
\`\`\`

The project also contains live-service tests for temporary Gitea and Forgejo instances. See [ARCHITEKTUR.md](ARCHITEKTUR.md), [CHANGELOG.md](CHANGELOG.md) and [MITARBEIT.md](MITARBEIT.md) for engineering decisions, release history and contribution guidance.

## Project links

- [Website](https://chance-konstruktion.github.io/ha-haigs/)
- [Feature guide](docs/features.md)
- [Changelog](CHANGELOG.md)
- [Issues and bug reports](https://github.com/Chance-Konstruktion/ha-haigs/issues)
- [Releases](https://github.com/Chance-Konstruktion/ha-haigs/releases)

## License

[MIT](LICENSE) — Copyright © 2026 Chance-Konstruktion and the HAIGS contributors.

---

<div align="center">
  <sub>Built for freedom — and for the projects you host yourself.</sub>
</div>
