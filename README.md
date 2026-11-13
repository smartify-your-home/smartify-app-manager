# Smartify App Manager v0.2.0

Central, administrator-only Home Assistant panel for the Smartify extension family.

## Features

- Discovers public `smartify-*` repositories owned by `smartify-your-home`, excluding the Manager itself.
- Shows all known Smartify modules, newly discovered modules and the **latest published GitHub release version** where available.
- Refreshes the catalog automatically every **6 hours**, with a manual refresh button (limited to once every 10 minutes).
- Caches the last successful catalog locally; GitHub outages do not remove the module list.
- Opens the official GitHub repository and its release notes; installs and updates themselves are handled by the Home Assistant Marketplace / HACS.
- HA administrator-only panel; PIN creation/change and PIN-protected per-module catalog lock labels.
- Respects Home Assistant themes.
- **No trial period, trial timer, commercial licensing, subscription or expiry.**

## Important limitations

- A PIN-locked module is **only marked locked in this catalog**. It is not disabled in Home Assistant or in the module itself. This is not license enforcement.
- The GitHub version is the **latest published release**, not proof of what is installed locally. The Manager does not automatically install, disable, upgrade or uninstall integrations.
- Brand-new repositories must be public, have a `smartify-` name and be owned by `smartify-your-home` to be auto-discovered. The Manager is excluded.
- GitHub availability, API rate limits and connectivity can delay remote metadata updates. Current values are cached.
- The Manager's own code must still be updated independently through the Marketplace when a new Manager release is published.

## Installation through Home Assistant 2026.11 Marketplace

1. Open **Settings → Marketplace**.
2. Add the custom GitHub repository URL `https://github.com/smartify-your-home/smartify-app-manager` as an **Integration** if it does not already appear.
3. Install the integration. The repository includes its root-level `hacs.json`.
4. Go to **Settings → Devices & Services → Add Integration → Smartify App Manager** to configure the one-time setup, if needed.
5. Open **Smartify** from the HA sidebar with an administrator account.

This version requires Home Assistant **2026.11.0 or newer**, as declared in `hacs.json`. Older Home Assistant versions are not supported by this build.

## Manual installation

Copy `custom_components/smartify_app_manager/` into the same path under your HA configuration, restart Home Assistant, and add the integration through Settings → Devices & Services.

## Developer validation

- `python -m compileall -q custom_components`
- `python -m unittest discover -s tests -v`
- `python -m json.tool hacs.json`
- `python -m json.tool custom_components/smartify_app_manager/manifest.json`
- `node --check custom_components/smartify_app_manager/frontend/panel.js`
- Test integration setup, panel loading, PIN flow, sync and unload/reload in a running HA environment.

## Files and standards

See `AGENTS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md` and `docs/ARCHITECTURE.md`. The Manager does **not** alter code in other Smartify repositories.
