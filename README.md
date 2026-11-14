# Smartify App Manager v0.4.1 (Testrelease)

> **Cubi package allowlist:** New Smartify GitHub repositories are never automatically synchronized or offered to customers. Cubi has a separate global sync/publication policy with **default deny**, plus future per-customer entitlements. The allowlist reference implementation and example are under [`cubi/`](cubi/README.md); it is **not yet enabled on the running Cubi services**. The existing client GitHub catalog must be replaced with the Cubi-filtered catalog before customer production.

> **Customer distribution roadmap:** Smartify Manager is the future customer-facing download/install/update interface for **all** Smartify apps, with Cubi (LXC 230) as the sole package source. For the current test phase, installations require an administrator confirmation but **no PIN**. A server-validated customer PIN is only a possible later option. The existing administrator PIN only protects legacy catalog lock labels and is not used for Cubi package installs. See [Customer Distribution](docs/CUSTOMER_DISTRIBUTION.md). The new Cubi multi-app catalog, private release sync and optional install workflow are included for controlled testing but are not yet deployed on the live Cubi service or HA-runtime-tested. Existing SEP ZIP downloads remain test-only and do not install software.


Central, administrator-only Home Assistant panel for the Smartify extension family.

## Features

- Discovers public `smartify-*` repositories owned by `smartify-your-home`, excluding the Manager itself.
- Shows all known Smartify modules, newly discovered modules and the **latest published GitHub release version** where available.
- Refreshes the catalog automatically every **6 hours**, with a manual refresh button (limited to once every 10 minutes).
- Caches the last successful catalog locally; GitHub outages do not remove the module list.
- Opens the official GitHub repository and its release notes; installs and updates themselves are handled by the Home Assistant Marketplace / HACS.
- HA administrator-only panel with a compact, single-column app list (name, status, published version and inline actions), PIN creation/change and PIN-protected per-module catalog lock labels.
- Respects Home Assistant themes.
- **No trial period, trial timer, commercial licensing, subscription or expiry.**

## Kubi SEP package source (new in 0.3.0)

- Open the Smartify panel as a Home Assistant administrator. Under **Kubi-Paketserver** enter either the LAN test server `http://192.168.2.68:8765` or the pinned Tailscale HTTPS endpoint `https://smartify-packages.tail8ff129.ts.net`, and select **Server speichern**.
- Select **Verbindung prüfen**. Home Assistant reads `/sep/latest.json` from the configured server and displays the latest approved SEP version.
- Select **Geprüftes ZIP nach Home Assistant laden**. HA fetches only the expected `smartify-energy-pro-X.Y.Z.zip` archive, validates metadata, SHA-256, ZIP structure and manifest version, and saves it under `/config/smartify-downloads/sep/`.
- The download **does not install, overwrite or update** the running SEP integration. An already downloaded version is immutable; different content is rejected.
- The address is restricted to a literal RFC1918 IPv4 HTTP URL or exactly `https://smartify-packages.tail8ff129.ts.net` (HTTPS port 443 only). Other hostnames, redirects, arbitrary paths and public IPs are rejected to reduce SSRF exposure.
- **Test deployment**: LAN HTTP is only for trusted local tests. The pinned Tailscale HTTPS endpoint requires an authorized Tailnet/device share and TLS verification, with no public port forwarding. SHA-256 protects against accidental corruption relative to metadata; it is not release signing. Before commercial production, add separately verifiable package signatures and review customer access policy. Never expose the plain HTTP port 8765 publicly.
- Kubi metadata refresh is independent of the existing six-hour **GitHub catalog** refresh. Each status check contacts Kubi directly.

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
