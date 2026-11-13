# Cubi: globale App-Freigabe vor GitHub-Synchronisierung

## Ziel

Nicht jede App aus `smartify-your-home` ist für Kunden bestimmt. **Cubi soll ausschließlich ausdrücklich freigegebene Repositories synchronisieren und publizieren.** GitHub-Releases und die bloße Existenz eines `smartify-*`-Repositories führen niemals selbst zu einer Kundenfreigabe.

Diese Freigabe wird nach Einbindung in die Cubi-Dienste die **erste** Schranke. Die **zweite** Schranke ist die spätere kundenspezifische Berechtigung samt serverseitigem Installations-PIN. Sie ist derzeit noch nicht implementiert.

## Konfiguration auf Cubi (LXC 230)

Authoritative Konfiguration (nicht in einem öffentlichen Repository speichern):

- `/etc/smartify/package-policy.json` – root-verwaltete Konfiguration.
- `/usr/local/lib/smartify/package_policy.py` – Prüfprogramm für Synchronisierung und Veröffentlichung.
- `/srv/smartify/releases/` – **öffentlich über Tailscale Serve erreichbares** Release-Verzeichnis; keine internen Pakete darin lagern.

Vorlage: `cubi/package-policy.example.json`. Darin ist **nur `smartify-energy-pro` freigegeben**. Alle nicht genannten Repositories sind gesperrt.

Eintrag pro Repository:

```json
"smartify-energy-pro": {
  "sync": true,
  "publish": true,
  "release_dir": "sep"
}
```

| sync | publish | Bedeutung |
|---|---|---|
| false | false | Auf Cubi weder von GitHub abrufen noch für Kunden publizieren |
| true | false | Nur intern nach Freigabe abrufen; nicht ins öffentliche Release-Verzeichnis |
| true | true | Von GitHub abrufen und **global** publizieren; kundenspezifische Berechtigung weiterhin erforderlich |
| false | true | Ungültig; Prüfung verweigert |

**Neue Repositories stehen nicht in der Liste und sind standardmäßig gesperrt.** Eine fehlerhafte, doppeldeutige oder fehlende Policy führt ebenfalls zu einer Sperre statt zu `sync all`.

## Prüfbefehle (nach Installation der Dateien auf Cubi)

```sh
python3 /usr/local/lib/smartify/package_policy.py validate
python3 /usr/local/lib/smartify/package_policy.py list sync
python3 /usr/local/lib/smartify/package_policy.py list publish
python3 /usr/local/lib/smartify/package_policy.py check sync smartify-energy-pro
python3 /usr/local/lib/smartify/package_policy.py check sync smartify-flow-card
python3 /usr/local/lib/smartify/package_policy.py audit-public /srv/smartify/releases
```

Der nicht freigegebene `smartify-flow-card`-Check endet absichtlich mit Exitstatus 1. Ein ungültiges oder fehlendes Policy-Dokument endet mit Status 2.

## Verpflichtende Durchsetzung

**Nur das Anlegen der JSON-Datei schützt noch nichts.** Der zukünftige generische Cubi-GitHub-Synchronisierer muss:

1. **Vor** GitHub-API, `git fetch`, `git clone` oder `git pull` die vollständige Policy einlesen und nur `list sync` berücksichtigen.
2. **Vor** Paketierung/Kopieren in `/srv/smartify/releases/` ein zweites Mal `check publish REPO` durchführen. Exakt den vorgesehenen `release_dir` verwenden.
3. Bereits publizierte, später gesperrte Apps **aus dem HTTP/Tailscale-Serve-Verzeichnis entfernen bzw. in ein nicht erreichbares Privatverzeichnis verschieben**. Ein Abschalten allein in der JSON-Datei löscht bestehende öffentliche Downloads nicht.
4. Niemals den statischen Ordner als Berechtigungssystem für einzelne Kunden betrachten. Ein Kunde mit Zugriff auf den Tailscale-Serve-Ordner kann derzeit **alle darin vorhandenen Pakete direkt herunterladen**.
5. Den Kundenkatalog nur aus `publish=true` erstellen; die zurzeit hart kodierte GitHub-Liste im Manager ist **kein** zulässiger produktiver Kundenkatalog.
6. Für spätere pro-Kunde-Freigaben einen authentifizierten HTTPS-Gateway einsetzen, der Kundenidentität, App-Freigabe und Installations-PIN **serverseitig** prüft. Kundennamen, PINs und geheime Berechtigungen gehören nicht in das GitHub-Repository.

## Hinweis zu GitHub-Sichtbarkeit

Bei einem **öffentlichen GitHub-Repository** verhindert die Cubi-Freigabeliste nicht dessen direkten Abruf über GitHub. Wirklich interne Apps gehören in **private** Repositories oder müssen anderweitig gegen öffentliche Downloads abgesichert werden.

## Aktueller Stand

Die Dateien dieses Verzeichnisses sind die **getestete Policy-Komponente**, nicht bereits eine produktive Cubi-Konfiguration. Die laufenden SEP-Dienste `smartify-sep-sync.service` und `smartify-sep-package.service` sind noch **nicht** auf die neue Policy umgestellt. Dieser Testzweig verändert keine laufenden LXC-Dienste und veröffentlicht keine internen Pakete.

Vor produktiver Aktivierung separat prüfen: Eigentümer und Rechte der Policy, Integration in beide systemd-Services, automatische Entfernung zuvor veröffentlichter aber gesperrter Pakete, fehlgeschlagene und verweigerte Synchronisierung, vorhandene Tailscale-Serve-Freigaben sowie kundenspezifische Authentifizierung.
