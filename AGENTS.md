# Smartify App Manager – AGENTS.md

## Mandatory reading before any code change
1. Read this `AGENTS.md`, `README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `docs/ARCHITECTURE.md`.
2. Inspect `manifest.json`, integration entry point, frontend and relevant tests.
3. Preserve backwards compatibility with existing customer configurations.
4. Check Home Assistant API compatibility before changing custom panel or WebSocket APIs.
5. Do not modify other Smartify repositories without explicit request.

## Project conventions
- Product: Smartify App Manager; domain `smartify_app_manager`.
- Version format: semantic versions (`MAJOR.MINOR.PATCH`), shown in UI, not commit SHAs.
- Every user-visible change updates `CHANGELOG.md` and `RELEASE_NOTES.md`, and aligns `manifest.json` + frontend label.
- Every release includes installation/update instructions and a note about compatibility or migration.
- Use Home Assistant theme variables; light/dark themes must work.
- Any lock/PIN action must require a Home Assistant administrator; PINs must never be stored in plaintext or logged.
- The module lock in v0.1.0 is *catalog metadata only*, NOT a hard security/license lock; never describe it as enforcing third-party integrations.
- No trial period, trial timer, license server, license expiry, or subscription management until requested.
- No installer that downloads/executes arbitrary remote code. Prefer HA Marketplace/HACS-managed installation.
- GitHub repository list is curated and explicit. Each Smartify module remains separate.
- No GitHub Actions job that repeatedly emails on a known failing workflow. Validate locally before publishing.

## Validation checklist (required before release)
- `python -m compileall -q custom_components`
- `python -m unittest discover -s tests -v`
- `python -m json.tool custom_components/smartify_app_manager/manifest.json`
- `node --check custom_components/smartify_app_manager/frontend/panel.js` (if Node available)
- Review permission checks, PIN hash persistence, PIN brute-force limit, and safe frontend escaping.
- Verify HA setup/config flow and panel behaviour in a running supported HA version before marking release production-ready.

## Release procedure
1. Validate above checks, resolve failures (do not suppress tests).
2. Update manifest and frontend versions together.
3. Update CHANGELOG and RELEASE_NOTES with meaningful user-facing changes.
4. Tag `vX.Y.Z` and publish GitHub release after HA smoke test.
5. Do not claim a GitHub release exists unless actually created and verified.
