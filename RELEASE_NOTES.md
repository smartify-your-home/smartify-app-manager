# Release Notes

## v0.2.0 – Marketplace compatibility and automatic catalog synchronization
Date: 2026-11-13

### New
- A `hacs.json` file is now present in the repository root, allowing the HA 2026.11 Marketplace to validate the repository structure.
- The Manager now discovers public Smartify repositories automatically and checks their latest published GitHub releases every six hours.
- New repos and new release versions are shown without shipping a new App Manager version. The UI shows version tags and release-note links.
- Manual recheck is available (no more often than once every ten minutes). Last valid data is retained if GitHub is unavailable.

### Scope and safety
- **No 30-day test period.**
- The PIN controls administrative catalog lock markers only. It does not block or uninstall integrations.
- Updates, installations and removal remain in Home Assistant Marketplace; no arbitrary remote-code execution.
- Remote GitHub tags do not establish a locally installed version.
- The Manager itself still needs a new Marketplace version for its own code changes.

### Upgrade from 0.1.0
No storage migration. The existing PIN hash and module lock flags remain. The new catalog cache is populated automatically on the first successful GitHub synchronization. Home Assistant may require restart for the integration update.

### Testing
Code and file-level validations are required; running-HA installation and reload smoke tests remain necessary before declaring this production-ready.

---

## v0.1.0 – Initial source
Date: 2026-11-13

Initial Smartify administrator catalog, PIN handling, 12 module links and project documentation. No trial or license enforcement.
