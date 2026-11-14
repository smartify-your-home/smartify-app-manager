#!/usr/bin/env bash
# Private Cubi multi-app pipeline; install only after a successful staging test.
set -euo pipefail
umask 077
LOCK=/srv/smartify/private-state/catalog-sync.lock
mkdir -p /srv/smartify/private-state /srv/smartify/private-checkouts /srv/smartify/staging
exec 9>"$LOCK"
flock -n 9 || exit 0
STAGE="$(mktemp -d /srv/smartify/staging/cubi-v1-XXXXXXXX)"
cleanup() { if [[ -d "$STAGE" ]]; then rm -rf -- "$STAGE"; fi; }
trap cleanup EXIT

/usr/bin/python3 /usr/local/lib/smartify/cubi/fetch_releases.py \
  --policy /etc/smartify/package-policy.json \
  --token /etc/smartify/github-token \
  --checkouts /srv/smartify/private-checkouts

/usr/bin/python3 /usr/local/lib/smartify/cubi/build_catalog.py \
  --policy /etc/smartify/package-policy.json \
  --recipes /usr/local/lib/smartify/cubi/app-recipes.json \
  --checkouts /srv/smartify/private-checkouts \
  --output "$STAGE/v1"

# Fail closed: never expose a new candidate until ClamAV approves BOTH
# the downloaded source trees and built ZIPs/icons. On any nonzero exit
# the trap removes only this private staging folder; /v1 is untouched.
/usr/bin/python3 /usr/local/lib/smartify/cubi/scan_staging.py \
  --policy /etc/smartify/package-policy.json \
  --recipes /usr/local/lib/smartify/cubi/app-recipes.json \
  --checkouts /srv/smartify/private-checkouts \
  --stage "$STAGE/v1" \
  --report-dir /srv/smartify/private-state/clamav-reports

/usr/bin/python3 /usr/local/lib/smartify/cubi/publish_staging.py \
  --policy /etc/smartify/package-policy.json \
  --recipes /usr/local/lib/smartify/cubi/app-recipes.json \
  --stage "$STAGE/v1" \
  --serve-root /srv/smartify/releases \
  --private-backups /srv/smartify/private-backups
