# Changelog

## Unreleased – Tailscale HTTPS test follow-up (based on 0.3.0)

- Allow the exact `https://smartify-packages.tail8ff129.ts.net` URL on port 443 in the Kubi package-source backend; existing RFC1918 HTTP tests remain available.
- Keep the SSRF allowlist narrow: arbitrary hostnames, ports, redirects and paths are rejected.
- Add security regression tests and update the HA panel guidance; no running SEP installation is modified.
- Development branch only; no production release or signed release metadata claimed.

## [0.3.0] - 2026-11-13 (candidate; not yet released)

### Added
- Configurable LAN Kubi SEP package endpoint in the admin-only HA panel.
- Back-end metadata check using `/sep/latest.json` and version/status display, independent of GitHub sync.
- Verified SEP ZIP download to `/config/smartify-downloads/sep/` after SHA-256 and ZIP/manifest validation.
- Source URL restrictions, immutable package retention and dedicated security regression tests.

### Unchanged
- No automatic SEP installation, runtime change, remote license enforcement or public package hosting.
- Existing Smartify GitHub catalog, module PIN labels and settings are retained.


## [0.2.0] - 2026-11-13

### Added
- Root-level minimal `hacs.json`, required for installation/update through the HA 2026.11 Marketplace.
- Automatic six-hour discovery of public Smartify repositories on GitHub.
- Newly created `smartify-*` projects join the catalog without updating the Manager source.
- Published release versions and GitHub release-note links in the module cards.
- Manual catalog refresh with a minimum ten-minute interval.
- Persistent cache of last successful GitHub data and offline fallback.
- Explicit documentation of Marketplace compatibility, API rate limits and actual scope of PIN locks.

- Compatibility adjustments for Home Assistant 2026.11 config flows and probatio WebSocket schemas.

### Unchanged
- Each Smartify module remains independently installed and updated through HA Marketplace / HACS.
- PINs are stored as salted PBKDF2 hashes and protected by HA administrator permissions.
- Module lock is a catalog label and **does not** disable integration behavior.
- No 30-day trial, license server or expiration.

## [0.1.0] - 2026-11-13

### Added
- Initial manager, 12 curated Smartify modules and repository links.
- HA sidebar, PIN management and persisted lock labels.
- Documentation and base catalog tests.
