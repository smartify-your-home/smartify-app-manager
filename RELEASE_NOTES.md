# Release Notes

## v0.1.0 – Smartify App Manager (initial source package)
Date: 2026-11-13

**New:** A Home Assistant sidebar view for twelve Smartify projects with repository links. Admin users can set/change a PIN and maintain per-module locked/unlocked catalog labels. PINs are hashed before local persistence; changes require HA admin permissions.

**Important:** No 30-day trial. The status labels do not disable Smartify modules. Installation and updates remain delegated to HA/HACS. Existing Smartify repositories are unmodified.

**Compatibility:** Intended for contemporary HA versions with `panel_custom`, `websocket_api`, `Store` and UI config flows. Running-HA smoke test is still required. This source archive is not an official published GitHub release.

**Installation:** See README.md. Existing Smartify installations require no migration.
