# Architecture and security boundary

- `const.py`: curated catalog of Smartify GitHub repositories.
- `config_flow.py`: one instance per HA installation.
- `__init__.py`: persistent HA Store, WebSocket catalog + PIN modification + module status flag, and admin-only custom panel.
- `frontend/panel.js`: custom-element view using the Home Assistant `hass.callWS` connection; HA CSS variables for theming.

## Trust boundary
A customer with filesystem/administrator access to their Home Assistant instance controls all locally installed code. The PIN is a safeguard for administrator workflows, not commercial tamper resistance. The locked flag is **not enforced** in other Smartify integrations. A future opt-in enforcement interface must be designed with explicit compatibility contracts, idempotent disable/re-enable semantics, restore-state safeguards, customer data preservation and safety-critical local operation.

## Data
`hass.helpers.storage.Store` stores `pin_hash`, random `pin_salt`, and module `locks` under `.storage/smartify_app_manager.settings` (not a file users should edit). Plaintext PIN is never saved. A wrong-PIN attempt counter is held in memory and triggers a temporary lockout.

## Future phases (not implemented)
- Inspect actual HACS/HA installation versions and expose update status.
- Optional per-module enable/disable API in cooperating modules.
- Release information and changelog aggregation.
- Optional signed licensing (only when explicitly commissioned).
