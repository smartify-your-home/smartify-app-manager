# ClamAV-Patch für Cubi LXC 230

Der neue Pflichtscan schützt ausschließlich den neuen /v1-App-Katalog. Der bestehende SEP-Dienst unter /sep wird nicht umgestellt.
Die derzeit freigegebenen Apps (SEP, Raffstore) bleiben in der bestehenden Policy. Weder diese Policy noch der GitHub-Lesetoken werden überschrieben.

## Voraussetzungen

- /usr/bin/clamscan ist im LXC 230 installiert.
- Die ClamAV-Signaturdatenbank wird mit clamav-freshclam aktualisiert.
- /usr/local/lib/smartify/cubi/refresh.sh wird als systemd-Service gestartet.

## Installation und Test auf dem Proxmox-Host root@cubi

```bash
pct exec 230 -- bash -s <<'CUBI'
set -euo pipefail

# ClamAV installieren (ClamAV-Daemon ist für clamscan NICHT nötig).
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y clamav clamav-freshclam
systemctl enable --now clamav-freshclam
command -v clamscan
clamscan --version

# Der erstmalige Signatur-Download muss abgeschlossen sein.
if ! find /var/lib/clamav -maxdepth 1 -type f \\( -name 'daily.cvd' -o -name 'daily.cld' \\) | grep -q .; then
  echo 'ClamAV hat noch keine daily-Signaturen. Erst freshclam-Journal prüfen.' >&2
  journalctl -u clamav-freshclam -n 30 --no-pager
  exit 1
fi

SRC=/tmp/smartify-clamav-patch
if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 --branch feature/cubi-clamav-release-gate \
    https://github.com/smartify-your-home/smartify-app-manager.git "$SRC"
else
  git -C "$SRC" fetch --depth 1 origin feature/cubi-clamav-release-gate
  git -C "$SRC" checkout -B feature/cubi-clamav-release-gate FETCH_HEAD
fi

cd "$SRC"
python3 -m compileall -q cubi tests
PYTHONPATH=cubi python3 -m unittest discover -s tests -p 'test_cubi_clamav.py' -v

install -o root -g root -m 0644 cubi/scan_staging.py \
  /usr/local/lib/smartify/cubi/scan_staging.py
install -o root -g root -m 0755 cubi/refresh.sh \
  /usr/local/lib/smartify/cubi/refresh.sh
install -o root -g root -m 0644 cubi/systemd/smartify-cubi-catalog-refresh.service \
  /etc/systemd/system/smartify-cubi-catalog-refresh.service

systemctl daemon-reload
systemctl start smartify-cubi-catalog-refresh.service
systemctl enable --now smartify-cubi-catalog-refresh.timer

echo '=== ClamAV und Cubi-Status ==='
systemctl show -p ActiveState -p Result smartify-cubi-catalog-refresh.service
systemctl list-timers --all smartify-cubi-catalog-refresh.timer
journalctl -u smartify-cubi-catalog-refresh.service -n 30 --no-pager
CUBI
```

## Erfolgskriterium

Im Journal muss eine Meldung wie 'Cubi ClamAV CLEAN: apps=2 ...' erscheinen.
Danach meldet publish_staging.py 'changed: false', sofern der Katalog unverändert geblieben ist. Bei unveränderten Quellen, Signaturen und einem erfolgreichen Scan innerhalb von 12 Stunden erscheint stattdessen 'Cubi ClamAV CACHED_CLEAN': das Ergebnis wird sicher wiederverwendet, ohne das Signaturpaket alle zwei Minuten neu zu laden.
Private Berichte über echte Scanläufe liegen unter /srv/smartify/private-state/clamav-reports; die Prüfcache-Datei unter /srv/smartify/private-state/clamav-last-clean.json. Sie darf niemals in den öffentlichen /v1-Verzeichnisbaum verschoben werden.

## Bei BLOCKED

Kein neuer Release wird veröffentlicht. Der zuletzt gültige /v1-Katalog bleibt bestehen.
Im JSON-Bericht stehen ClamAV-Ausgabe und Grund der Blockierung.
Erst den Fehler prüfen (Signaturstand, Scannerfehler, Speicher/Timeout, Fund), danach erneut versuchen.
**Keine Scan-Umgehung einrichten.**

Der GitHub-Release des Smartify App Managers muss dafür nicht neu installiert werden.

## Warum ein Scan nicht jede Gefahr erkennt

ClamAV kann bekannte Malware und verdächtige Archive finden; es validiert nicht die gesamte Python- oder JavaScript-Logik. Ein fehlerfreier Virenscan beweist keine Abwesenheit von Backdoors oder Bugs. Zusätzlich sind Code-Reviews und automatisierte Integrations-/Funktionstests sinnvoll.
