# Release Notes

## Unreleased architecture preparation – Cubi multi-app updates and installation PIN

- The long-term Smartify Manager customer path is **Cubi only** for package downloads and updates, independent of the GitHub developer release workflow.
- Every supported installed Smartify app will get its own native HA update entity, checked against a shared Cubi package catalog every two minutes. SEP is the first candidate, not proof that all apps are already supported.
- New app installations must prompt for a **customer installation PIN** and be authorized server-side by Cubi. The existing administrator PIN is unrelated and must not be presented as authorization.
- The authenticated Cubi gateway, PIN activation endpoint and installation action are **not yet operational**; current SEP HTTPS ZIP download remains a manual test flow.
- Full architecture and bypass-prevention requirements documented under `docs/CUSTOMER_DISTRIBUTION.md`.

---


## Unreleased development fixes – Tailscale HTTPS and compact app list

- Replace the app tile grid with compact list rows. On wide screens actions stay on the same row; on mobile screens they move beneath the app details.
- Keep repository/release links and PIN-protected catalog lock actions unchanged; no effect on the installed SEP integration.

- The 0.3.0 development build rejected all HTTPS URLs. The package-source validation now permits the exact private Tailscale Serve address `https://smartify-packages.tail8ff129.ts.net`, with the canonical HTTPS port 443.
- LAN HTTP access via a literal RFC1918 IPv4 URL continues to work; arbitrary HTTPS hosts, extra paths and alternative ports remain blocked.
- TLS hostname/certificate verification remains enabled, redirects stay disabled, existing download integrity and no-auto-install safeguards remain unchanged.
- Still requires a live HA smoke test. No new published release and no automatic deployment to customers.

---

## v0.3.0 – Kubi SEP package source (development candidate)
Date: 2026-11-13

### Added
- New **Kubi-Paketserver** section in the Smartify administrator panel: enter LAN URL, save, test connection, inspect SEP release and download a verified ZIP.
- Home Assistant downloads from Kubi, not the user's browser; no CORS dependency.
- Verifies published-release metadata, SHA-256, ZIP paths and embedded integration version before saving to `/config/smartify-downloads/sep/`.
- Private-LAN URL restriction and no redirects; reuse of existing PIN/lock settings without migration.

### Not included
- No automatic installation, Marketplace update, public distribution, customer authentication, license enforcement, or HTTPS server deployment. Existing SEP installation remains unchanged.
- Temporary unauthenticated HTTP server is strictly for local testing; SHA-256 is not a package signature.

### Smoke test required before publishing
Install on a compatible running HA, save `http://192.168.2.122:8765`, verify status, download ZIP, confirm SHA, restart HA and verify the app panel. A real HA smoke test is not yet complete; **do not tag as production release**.

---


## v0.2.0 – Marketplace compatibility and automatic catalog synchronization
Date: 2026-11-13

### New
- A minimal `hacs.json` file is now present in the repository root, allowing the HA 2026.11 Marketplace to validate the repository structure.
- The Manager now discovers public Smartify repositories automatically and checks their latest published GitHub releases every six hours.
- New repos and new release versions are shown without shipping a new App Manager version. The UI shows version tags and release-note links.
- Manual recheck is available (no more often than once every ten minutes). Last valid data is retained if GitHub is unavailable.

- Updated the config flow and PIN WebSocket validation to match Home Assistant 2026.11's current API.

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
