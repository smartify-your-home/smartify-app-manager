# Smartify App Manager architecture

> **Global Cubi package source restrictions:** Server-side package synchronization is controlled by an explicit allowlist (see [`cubi/README.md`](../cubi/README.md)). Default is deny; `sync=true` and `publish=true` are separate. Customer-specific authorization follows after global publication. The current development-time public GitHub catalog is not suitable as the customer catalog and must be replaced by Cubi's permission-filtered response.


> Target for customer deployment: [Cubi multi-app package distribution and PIN-gated installations](CUSTOMER_DISTRIBUTION.md). The current GitHub-synced catalog is a temporary development feed. The current Cubi ZIP endpoint is unauthenticated and **does not** enable PIN-secured installs. Every installed supported Smartify app should eventually have a native HA update entity, checked at two-minute intervals using Cubi's unified catalog.


## Components
- `const.py`: curated, stable module IDs, descriptions and GitHub repository names.
- `catalog_sync.py`: async GitHub discovery via HA's shared aiohttp session, latest published release lookup, rate limiting, persisted cache, input filtering and fallback.
- `__init__.py`: HA integration lifecycle, administrative PIN/PBKDF2 storage, WebSocket API and six-hour background scheduling.
- `config_flow.py`: one instance per HA installation, using HA 2026.11's empty config-flow form.
- WebSocket commands use `probatio` schemas (not deprecated `voluptuous` marker declarations).
- `frontend/panel.js`: theme-aware sidebar app catalog, version display, release links and PIN controls.

## Keeping other Smartify modules up to date
1. Home Assistant fetches the public GitHub user repo listing every six hours; only `smartify-*` repositories with owner `smartify-your-home` are eligible.
2. The Manager excludes itself and merges new modules with a curated list; curated IDs remain stable, preserving PIN labels.
3. For each module, GitHub's latest **published** release is fetched. A tag without a published release is not shown as a release version.
4. The data is cached in Home Assistant `.storage`. On loss of Internet, the last known catalog remains visible.
5. Module installations, updates and their actual installed versions are still managed by the official HA Marketplace. The Manager cannot infer that a module is installed from a release tag.
6. New module discovery does not require a Manager commit. **Manager code changes still require a normal Manager release.**
7. GitHub API access is unauthenticated and rate-limited. Normal sync runs every six hours; manual sync is throttled to a ten-minute minimum.

No GitHub Actions schedules or external customer tokens are needed.

## Security boundary
- Only HA administrators access the panel/WebSocket commands.
- Administrative PINs are protected using PBKDF2-HMAC-SHA256 with a fresh random salt.
- PINs are never stored in plaintext or included in remote requests; repeated failures incur a temporary cooldown.
- The PIN lock is *metadata only*, not a commercial license or protection from filesystem administrators.
- No trial counter, license server, expiring license or automatic runtime disable.
- Only validated GitHub repository names under the pinned owner become links. GitHub results are treated as untrusted data.
- Safety-critical automations and local controls are not modified.

## Upgrade and storage
Settings and remote catalog are persisted in `.storage/smartify_app_manager.settings` through HA Store. Existing v0.1.0 PIN and lock flags are retained. The Catalog survives temporary GitHub outages.

## Kubi SEP source (0.3.0 candidate)
- `kubi_source.py` implements a constrained HTTP-to-RFC1918-IPv4 or pinned Smartify Tailscale HTTPS package retrieval path; the Home Assistant backend fetches the metadata, not the browser.
- The admin-only WebSocket commands set and persist the URL in the existing Store, report validated release metadata, and download ZIPs after SHA-256 and archive manifest verification.
- ZIPs are kept separately in `/config/smartify-downloads/sep/`; the running integration is never modified. Existing per-version files are not overwritten with different bytes.
- Kubi access is not related to the six-hour public GitHub catalog synchronization and has no timer; the panel explicitly refreshes it.
- The Python `http.server` used on Kubi is a temporary test-only LAN server, not a secure customer download service. Its metadata and checksum have no cryptographic origin authentication. Tailscale Serve provides a restricted HTTPS transport for shared customers, without port forwarding. For production complete release signing, scoped access controls and customer entitlements.
