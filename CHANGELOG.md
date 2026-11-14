# Changelog

## [0.4.1] – 2026-11-14 · Cubi-Polling und zuverlässige App-Icons (Testrelease)

- Neuer Cubi-Stand wird alle zwei Minuten nur dann veröffentlicht, wenn sich Pakete, Icons oder Katalog wirklich geändert haben. So entstehen keine unnötigen Backups oder kurzzeitigen Dateiwechsel beim Abruf.
- SEP-App-Icon und andere Original-Icons: Bild-Events sind vor der Bildanforderung registriert; Ersatzicon bleibt sichtbar, bis das lokale PNG erfolgreich geladen ist.
- Bei kurzzeitiger Cubi-Unterbrechung bleibt der zuletzt erfolgreiche App-Katalog samt gecachten Original-Icons sichtbar. Installationsschaltflächen sind in diesem Fall gesperrt.
- Wenn eine neue App-Version vorübergehend kein erreichbares Icon liefert, bleibt das zuletzt lokal gespeicherte Icon derselben App sichtbar.
- Regressionstests für unveränderte Veröffentlichung und Icon-Fallbacks ergänzt.
- Neue Version ist weiterhin ein Teststand; private Cubi-Synchronisation erfordert Installation des systemd-Timers auf LXC 230.

## [0.4.0] – 2026-11-13 · Privater Cubi-Paketweg (Testrelease)

- Cubi ruft nur explizit freigegebene veröffentlichte GitHub-Releases ab; private Repositories mit einem lokal gesicherten Read-only-Token, nie vom Kunden.
- Neuer gefilterter Cubi-Katalog unter /v1/catalog.json mit Original-App-Icons und SHA-256-Paketen; atomarer Austausch des öffentlichen Paketsatzes.
- HA Manager prüft den Cubi-Katalog alle zwei Minuten und zeigt freigegebene Apps, installierte Versionen und Updates als HA-Update-Entitäten.
- Manuelle Installation/Updates nach Bestätigung, vorerst ohne PIN, mit gezielter Zielpfad-Prüfung, ZIP-Validierung, Backups und Dashboard-Ressourcenregistrierung.
- Eigenständige Supervisor-Apps, Themes mit Hintergrundbildern und Windows-Werkzeuge brauchen vor Produktivfreigabe gesonderte Tests/Installer; nicht als vollständig umgesetzt ausweisen.
- Keine automatische Installation, keine Veröffentlichung und kein produktiver LXC-Eingriff in diesem Zweig.


## Unreleased – Cubi global App allowlist (server-side preparation)

- Add `cubi/package_policy.py` with validated, fail-closed global GitHub synchronization and publication allowlists. New/unknown repositories are denied.
- Only SEP is enabled in the example configuration. Internal-only apps can be synchronized without customer publication, but require explicit approval.
- Add audit of unexpected entries in the static public Tailscale Serve release folder (including symlinks), duplicate-field/path validation and isolated offline regression tests.
- Distinguish **global sync/publication** from future per-customer app entitlements and PIN authorization.
- This prepares server-side enforcement; current LXC services, public release directory and customer runtime are unchanged.


## Unreleased – Cubi customer distribution architecture

- Document multi-app Cubi package catalogue as the intended customer-facing source of downloads and updates; native Home Assistant update entities check every 120 seconds for supported apps.
- Define a **distinct customer installation PIN** verified on Cubi; the pre-existing administrator PIN is not a package authorization system.
- Explain that existing directly served SEP ZIPs are an unauthenticated test channel. The authenticated gateway, install action and per-app entitlements are **not yet implemented**.
- Clarify temporary buttons: `App-Katalog aktualisieren` (GitHub migration source) versus `Jetzt auf Updates prüfen` (Cubi).


## Unreleased – Tailscale HTTPS test follow-up (based on 0.3.0)

- Replace multi-column app tiles with a compact, full-width single-column list; each row shows name, category, published GitHub release version, lock status and direct actions.
- Keep the row layout responsive on small/mobile screens and preserve Home Assistant light/dark themes and existing PIN lock behavior.

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
