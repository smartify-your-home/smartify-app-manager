# Smartify App Manager 0.4.0 – Cubi-Testrelease
Stand: 13. November 2026

## Neu
- Einspaltige, mobilefreundliche App-Liste mit Original-Icons für verfügbare Smartify-Apps.
- Zweiminütliche Abfrage des Cubi-Katalogs unter `/v1/catalog.json` – auch wenn der Smartify-Sidebarbereich geschlossen ist.
- Für installierte, unterstützte Apps native Home-Assistant-Update-Entitäten.
- Installieren und Aktualisieren freigegebener HA-Integrationen und Dashboard-Dateien nach ausdrücklicher Bestätigung **ohne PIN**, mit SHA-256-Prüfung, Pfadprüfung und Sicherung vorhandener Dateien.
- Vorbereitung für private GitHub-Repositories: Nur Cubi liest freigegebene veröffentlichte Releases mit einem eingeschränkten lokalen Lese-Token; Kunden haben keinen GitHub-Zugang.
- Bisherige HTTPS-Verbindung `https://smartify-packages.tail8ff129.ts.net`, SEP-Metadaten und manueller ZIP-Download bleiben vorhanden.
- PIN-geschützte Alt-Katalogkennzeichen sind von neuen Cubi-Installationen getrennt.

## Einschränkungen dieser Testversion
- Die neue `/v1`-Paketquelle auf Cubi muss **separat installiert und getestet** werden. Bis dahin wird der noch fehlende Katalog als Hinweis angezeigt; der bestehende `/sep`-Downloadweg bleibt erreichbar.
- Die offizielle Update-Entität meldet nur, wenn sie tatsächlich installierte Versionen mit einem freigegebenen Cubi-Release vergleichen kann.
- Supervisor-Apps (Person Detection, SIP Manager) werden noch nicht direkt installiert; für diese ist die Supervisor-App-Store-Integration erforderlich.
- Themes, Hintergrundbilder und bereits durch HACS verwaltete Dashboard-Ressourcen brauchen einen separaten Migrationstest.
- Automatisches Übernehmen von Updates ist absichtlich ausgeschaltet.
- GitHub-Repositories bleiben öffentlich/privat gemäß ihrem bisherigen Zustand. Ein privater Quellcode ist nach Installation eines Python-/JS-Pakets für den Empfänger grundsätzlich lesbar.
- Unterstützt laut `hacs.json` Home Assistant **2026.11.0 oder neuer**. Vor einer Aktualisierung Versionsstand und Backup deiner HA-Konfiguration prüfen.

## Installation zum Test
Home Assistant → Einstellungen → Marketplace → Benutzerdefinierte Repositories:
`https://github.com/smartify-your-home/smartify-app-manager` (Integration).

Oder die ZIP-Anlage der GitHub-Version manuell in eine **Test-HA** entpacken, sodass `custom_components/smartify_app_manager` unter `/config/` liegt. Danach Home Assistant neu starten. Die bisherige Manager-Konfiguration bleibt bestehen.

**Wichtig:** Dieses Release aktualisiert weder den Cubi LXC noch deine laufende SEP-Integration automatisch.
