# Changelog

## [0.2.0] - 2026-11-13

### Added
- Root-level `hacs.json`, required for installation/update through the HA 2026.11 Marketplace.
- Automatic six-hour discovery of public Smartify repositories on GitHub.
- Newly created `smartify-*` projects join the catalog without updating the Manager source.
- Published release versions and GitHub release-note links in the module cards.
- Manual catalog refresh with a minimum ten-minute interval.
- Persistent cache of last successful GitHub data and offline fallback.
- Explicit documentation of Marketplace compatibility, API rate limits and actual scope of PIN locks.

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
