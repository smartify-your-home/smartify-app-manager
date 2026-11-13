# Smartify App Manager v0.1.0

Home Assistant custom integration that provides an **administrator-only Smartify catalog** with a sidebar panel and optional PIN-protected module status flags.

## Included in v0.1.0
- App catalog for 12 Smartify repositories; direct repository/installation links.
- Separate repositories remain independently versioned, installed and updated through Home Assistant / HACS.
- Home Assistant administrator-only panel and WebSocket API.
- Set/change administrator PIN (PBKDF2-HMAC-SHA256 with per-installation random salt).
- PIN-protected module status flag (`locked`/`unlocked`) persisted in HA storage.
- Five incorrect PIN attempts trigger a five-minute cooldown (in-memory, reset on HA restart).
- Responsive interface using HA theme variables.
- **No 30-day trial or license expiry.**

## Scope limitations
**Status flags are only administrative catalog labels.** They DO NOT disable a running integration, its automations, entities or cards. True enforcement would require explicit opt-in cooperation inside each Smartify module. This version does not provide silent installation, removal, or update execution. No claim of copyright/code protection is made.

## Manual installation
1. Copy `custom_components/smartify_app_manager/` into `<config>/custom_components/smartify_app_manager/`.
2. Restart Home Assistant.
3. Go to **Settings → Devices & Services → Add Integration**, search for `Smartify App Manager` and finish the empty setup flow.
4. Open **Smartify** in the sidebar (Home Assistant administrator account).
5. Open a repository link to add/install that integration via your chosen HA/HACS workflow.

## Installation via HACS
Publish this repository separately with `custom_components/smartify_app_manager` at its root; add it as a custom integration repository in HACS if not listed.

## Development & tests
Run `python -m compileall -q custom_components`, `python -m unittest discover -s tests -v`, and `node --check .../panel.js`. Final HA smoke test is necessary before production use.

## Release documentation
See `AGENTS.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `docs/ARCHITECTURE.md`.
