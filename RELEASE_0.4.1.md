# Smartify App Manager 0.4.1 – Cubi-Abgleich und zuverlässige Icons

**Testrelease vom 14. November 2026**

## Fehlerkorrekturen
- Der Zwei-Minuten-Abgleich auf Cubi publiziert unveränderte Pakete nicht mehr neu. Keine wachsenden Backup-Verzeichnisse bei unveränderten Releases, kein unnötiger Austausch der Dateien.
- Das SEP-Icon und weitere Original-App-Icons verwenden einen stabilen lokalen HA-Cache. Ein sichtbares HA-Ersatzicon bleibt bestehen, bis das PNG erfolgreich geladen ist.
- Bildfehler werden korrekt erkannt, selbst wenn der Browser das Ergebnis sofort aus dem Cache liefert.
- Bei vorübergehenden Cubi-Verbindungsfehlern bleibt der zuletzt gültige Katalog mit den bereits geladenen Icons sichtbar. Installationsaktionen werden bis zur Wiederverbindung ausgeblendet.
- Beim Versionswechsel darf das letzte gecachte App-Icon vorläufig angezeigt werden, falls das neue Icon nicht abrufbar ist.

## Test und Einrichtung
- Home-Assistant-Integration und Cubi-Skripte haben unterschiedliche Installationsorte. Das neue GitHub-Release aktualisiert **nur den Smartify App Manager**, nicht den LXC.
- Die automatische Cubi-Synchronisation wird durch den separaten systemd-Timer `smartify-cubi-catalog-refresh.timer` in LXC 230 aktiviert.
- Vor dem Aktivieren `cubi/publish_staging.py` im LXC aktualisieren.
- Der bisherige SEP-Paketweg `/sep/` und die bestehende SEP-Installation bleiben unverändert.
- Es gibt keine automatische Installation und keinen PIN in dieser Testphase.

## Installation
Die ZIP-Anlage `smartify-app-manager-0.4.1.zip` enthält die Home-Assistant-Integration unter `custom_components/smartify_app_manager/`. Sie kann im Test-HA über die Dateien oder nach Aktualisierung des GitHub-Standardzweigs über HACS/Marketplace installiert werden.

Der neue Cubi-Katalog ist unter `/v1/catalog.json` bereitgestellt; die HTTPS-Erreichbarkeit von der Kunden-HA muss separat geprüft werden.
