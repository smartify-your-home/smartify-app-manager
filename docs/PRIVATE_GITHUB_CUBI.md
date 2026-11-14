# Private GitHub → Cubi → Smartify App Manager (Testkandidat)

**Kunden benötigen keinen GitHub-Zugang und vorerst keinen PIN.** Cubi synchronisiert nur explizit erlaubte, veröffentlichte GitHub-Releases. Home Assistant holt den gefilterten Katalog alle 120 Sekunden und zeigt Update-Entitäten an. Installationen sind nur nach Bestätigung möglich.

## Read-only GitHub-Zugang auf Cubi

In GitHub einen Fine-grained Personal Access Token erstellen:
- Resource owner: smartify-your-home
- Repository access: ausschließlich die auf Cubi zu synchronisierenden Repositories
- Repository permissions: Contents (Read-only); Metadata ist automatisch verfügbar
- Token ausschließlich unter /etc/smartify/github-token speichern, Eigentümer smartify, Modus 0600
- Niemals den Token in Home Assistant, in Git-URLs, Logs, Tickets oder Chats eintragen

Die globale Paket-Policy liegt unter /etc/smartify/package-policy.json und erlaubt für jede App getrennt sync und publish. Nicht gelistete Repositories sind standardmäßig gesperrt. Die Kunden sehen ausschließlich veröffentlichte Apps aus dem Cubi-Katalog.

## Katalog und Paketformat

Der Server erzeugt den Katalog unter /srv/smartify/releases/v1/catalog.json sowie ZIP-Pakete und echte Icons unter /v1/<app-id>/. Der neue v1-Katalog wird nur aus geprüften Freigaben gebaut und als vollständiger Snapshot atomar publiziert. Der alte /sep/-Testweg bleibt separat bestehen.

**ClamAV-Pflichtprüfung:** Vor jedem neuen /v1-Veröffentlichungsversuch scannt das Cubi-Skript scan_staging.py mit clamscan alle freigegebenen heruntergeladenen GitHub-Release-Quellen und die erzeugten ZIPs/Icons. Bei fehlendem Scanner, veralteten Signaturen, Virusfund oder Scanfehler wird die Veröffentlichung abgebrochen. Der zuletzt veröffentlichte Katalog bleibt unverändert. Private Scanberichte liegen in /srv/smartify/private-state/clamav-reports.

Der Smartify App Manager prüft /v1/catalog.json alle 120 Sekunden unabhängig vom geöffneten Panel. Offizielle HA-Update-Entitäten werden pro erkannter installierter App angelegt.

## Installationsarten

- HA-Integrationen: SEP, Flow Card, Floorplan 3D, Heating und Energy Row Card. Verzeichnis vor dem Ersetzen sichern; Core-Neustart erforderlich.
- Dashboard-Karten: Weather Card, Raffstore, Tabbar. Unter /config/www/smartify/ installieren; Dashboard-Ressource in Storage-Modus ergänzen, bei YAML-Modus manuelle Ressourceneintragung erforderlich.
- Themes: YAML kann übertragen werden; Hintergrundbilder und bestehende Include-Einstellungen müssen vor produktiver Nutzung geprüft werden.
- Supervisor-Apps: Person Detection und SIP Manager brauchen einen gesondert getesteten Supervisor-App-Store-Zugriff. Sie werden vorerst **nicht** als direkt installierbar angezeigt.
- Tailnet Viewer: Windows-Programm, kein HA-Paket und daher keine HA-Installation.

## Tests vor Aktivierung auf LXC 230

Den öffentlichen Manager-Entwicklungszweig feature/private-cubi-distribution auf Cubi in ein privates Testverzeichnis auschecken und zunächst ausführen:

    python3 -m compileall -q cubi
    PYTHONPATH=cubi python3 -m unittest discover -s tests -p 'test_cubi_package_policy.py' -v
    PYTHONPATH=cubi python3 -m unittest discover -s tests -p 'test_private_cubi_distribution.py' -v

Danach die Cubi-Dateien fetch_releases.py, build_catalog.py, publish_staging.py, package_policy.py, app-recipes.json und refresh.sh außerhalb des öffentlichen Release-Verzeichnisses installieren. Die Policy in /etc/smartify/package-policy.json legt zunächst **nur SEP** frei. Ein erster manueller Bau muss /v1/catalog.json erstellen, bevor ein 2-Minuten-Timer aktiviert wird.

Bei Erfolg auf der Kunden-HA:

    curl -fsS https://smartify-packages.tail8ff129.ts.net/v1/catalog.json

Erst nach vollständigen HA-Laufzeittests die beiden systemd-Dateien aus cubi/systemd/ installieren und den Timer aktivieren. Der bestehende SEP-Synchronisierer und seine Daten bleiben unverändert.

## Sicherheitsgrenzen

- Kein PIN: Die Tailscale-Freigabe und die globale Cubi-Publish-Policy sind die aktuellen Zugangsschranken.
- Private GitHub-Repositories schützen die GitHub-Historie, nicht den im Kunden-ZIP mitgelieferten Python- oder JavaScript-Quellcode.
- SHA-256 schützt gegen unbemerkte Abweichungen zwischen ZIP und Metadaten; für belastbare Software-Herkunftssicherung ist eine getrennte digitale Signatur nötig.
- **Der Testzweig ist keine produktive Veröffentlichung.** Hiermit werden weder das laufende LXC 230 noch bestehende HA-Installationen automatisch verändert.
