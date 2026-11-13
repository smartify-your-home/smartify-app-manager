# Smartify App Manager – AGENTS.md

## Mandatory reading before work
1. Read `AGENTS.md`, `README.md`, `CHANGELOG.md`, `RELEASE_NOTES.md`, `docs/ARCHITECTURE.md`, and `hacs.json`.
2. Inspect `manifest.json`, integration entry point, catalog sync, frontend and related tests.
3. Preserve backwards compatibility, particularly persistent PIN hashes and module lock flags.
4. Check HA API and Marketplace compatibility before modifying setup, WebSocket or panel registration.
5. Never alter another Smartify repository without explicit instruction.

## Project and release rules
- Product: Smartify App Manager; domain `smartify_app_manager`.
- Use SemVer `MAJOR.MINOR.PATCH`; UI, manifest, docs and GitHub release/tag must agree.
- Every user-visible change updates `CHANGELOG.md` and `RELEASE_NOTES.md`, including installation/upgrade notes.
- Keep an actual root-level `hacs.json` in every Marketplace-installable version; specify minimum supported Home Assistant version.
- Use HA 2026.11-compatible `probatio` WebSocket schema markers and test command registration. The integration remains under `custom_components/smartify_app_manager`.
- All changes must preserve HA light/dark themes, mobile usability and accessible control labels.
- No new GH Actions scheduled tests that bombard users with failure emails; prefer small reliable validations.
- Do not claim a GitHub release exists until verified.
- Do not declare a production-ready release without a running Home Assistant smoke test.

## Cross-repository consistency – mandatory
- Any change to an existing Smartify module's repository name/category must be reflected in the Manager's curated catalog if the stable mapping requires it.
- Newly added public `smartify-*` repos are discovered automatically every 6 hours; the Manager must continue to auto-detect them without code changes.
- On Smartify module release publication, the Manager displays the latest published release version after its next successful sync.
- Never require every module to update at once or change its installation directory.
- Retain support for existing customer installations, migration, offline behavior and API limits.
- The Manager's own code is separate: it must be released normally when modified.
- Published GitHub release tags are different from installed HA versions. Do not label remote versions as installed.

## Security and feature boundaries
- Administrative actions require HA administrator permissions.
- Never log, transmit, or store plaintext PINs; verify hashes safely, and rate-limit attempts.
- Lock flags remain administrative *catalog labels*; they do not disable other integrations.
- Do not add license enforcement, a 30-day trial, expiry or online account requirement unless asked.
- Never execute arbitrary downloaded code: use HA Marketplace/HACS for installation and updates.
- Do not change other Smartify integrations or their release workflows for catalog purposes.

## Validation checklist (before each release)
1. `python -m compileall -q custom_components`
2. `python -m unittest discover -s tests -v`
3. `python -m json.tool hacs.json` and `python -m json.tool custom_components/smartify_app_manager/manifest.json`
4. `node --check custom_components/smartify_app_manager/frontend/panel.js`
5. Check GitHub response parsing, offline cache and rate limit against fixtures.
6. Check security, PIN, UI escaping and admin-only WebSocket permissions.
7. Test setup, sidebar, refresh, PIN, unload/reload on a running supported HA release.

## Release procedure
1. Validate and fix all failures. Never suppress tests merely to get a green workflow.
2. Update `manifest.json`, UI version, `CHANGELOG.md`, `RELEASE_NOTES.md`, README as needed.
3. Create a proper tag and published GitHub release only after validation.
4. Verify Marketplace can install and update from the intended published release.
