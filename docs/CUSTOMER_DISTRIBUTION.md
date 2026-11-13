# Smartify App Manager – Kunden-Paketverwaltung über Cubi

Status: verbindliche Zielarchitektur, noch **nicht vollständig implementiert**. Der laufende SEP-Testweg lädt nur ZIPs; er installiert nicht und schützt den Download noch nicht mit einem PIN.

## Freigabe vor jedem GitHub-Abruf (Default Deny)

**Nicht jedes Smartify-Repository ist eine Kunden-App.** Cubi führt eine globale, root-verwaltete Freigabeliste unter `/etc/smartify/package-policy.json` (Format und Prüfprogramm unter [cubi/README.md](../cubi/README.md)). Die Abfrage eines GitHub-Releases allein autorisiert keine Synchronisierung.

- `sync=false`: Cubi darf das Repository nicht von GitHub abrufen.
- `sync=true, publish=false`: Cubi darf die App nur intern synchronisieren; sie darf nie im öffentlich erreichbaren Release-Verzeichnis oder Kundenkatalog landen.
- `sync=true, publish=true`: App ist **global** für Kunden vorgesehen, aber noch nicht jedem Kunden individuell freigegeben.
- Nicht aufgeführte Repositories, fehlende oder fehlerhafte Freigabelisten = **sperren**.
- Eine bereits publizierte, nachträglich gesperrte App muss sofort aus dem erreichbaren Veröffentlichungsverzeichnis entfernt werden; das bloße Abschalten der Synchronisierung reicht nicht.
- Der spätere **kundenbezogene** Berechtigungsfilter ist unabhängig davon: Kunde A kann App X freigeschaltet bekommen, Kunde B nicht. Die PIN-Prüfung erfolgt serverseitig auf Cubi.
- Der Manager darf seinen **produktiven Kundenkatalog nicht direkt aus allen öffentlichen GitHub-Repositories** erzeugen. Er erhält ausschließlich von Cubi freigegebene, nach Kundenrechten gefilterte Einträge.

Die neue Policy-Prüfbibliothek liegt derzeit **nur im Entwicklungszweig**; die laufenden Cubi-Dienste werden dadurch nicht geändert.

## Ziel und Zuständigkeiten
- **GitHub:** interne Entwicklung, validierte veröffentlichte Releases; kein direkter Kunden-Installationsweg.
- **Cubi (LXC 230):** zentrale Quelle aller freigegebenen Smartify-App-Pakete, Katalog, Kunden-/App-Berechtigungen, serverseitige PIN-Prüfung, signierte Pakete und Audit ohne PINs im Log.
- **Smartify App Manager auf Kunden-HA:** alle 120 Sekunden Cubi auf neue Versionen prüfen; pro installierter/verfügbarer App die installierte und die angebotene Version anzeigen; offizielle Home-Assistant-`update`-Entitäten; Freischalten, Herunterladen und nach expliziter Zustimmung installieren. Keine direkte Installation über GitHub/HACS als Kunden-Workflow.
- **Der aktuelle sechs-Stunden-GitHub-Katalog ist nur Entwicklungs-/Übergangsfunktion**, keine Kunden-Updatequelle. Ein späterer Cubi-Katalog löst diese Anzeige ab.

## Vorgesehener Kundenablauf
1. Cubi bietet einen **einzigen, versionierten App-Katalog**, z. B. `GET /v1/catalog`. Eintrag: stabile App-ID, Titel, Original-Icon, Typ (HA-Integration, Lovelace-Ressource, Themes usw.), veröffentlichte Version, unterstützte HA-Version, Release-Hinweise, signierter Artefaktverweis und ggf. Freischaltungsstatus.
2. Der Manager vergleicht diesen Katalog alle 120 Sekunden mit den **tatsächlich installierten lokalen Versionen**. Keine Updates aus GitHub-Commitständen oder ZIP-Dateinamen erraten. Unbekannte installierte Version -> keine automatische Update-Freigabe.
3. Pro unterstützter installierter App gibt es eine **native HA-Update-Entität** mit `installed_version` und `latest_version`; bei noch nicht installierten Apps zeigt der Manager eine Installationsoption. Der Manager meldet Updates, führt sie nicht automatisch aus.
4. Beim Klick auf **Installieren** wird der **Kunden-Installations-PIN** abgefragt. Dieser PIN ist **nicht** der bisherige Administrator-PIN, der nur Katalog-Sperrkennzeichen schützt. Cubi validiert PIN + Kundenidentität + App-Berechtigung serverseitig; eine rein lokale UI-PIN-Abfrage ist ausdrücklich unzulässig.
5. Cubi stellt erst nach erfolgreicher Prüfung ein **kurzlebiges, app-/versions-/kundenbezogenes Downloadrecht** aus. Übertragungsweg ist Tailscale Serve HTTPS. Manager verifiziert zusätzlich die kryptografische Paket-Signatur und das erwartete Manifest.
6. Der Kunde bestätigt die Installation. Je nach App-Typ wird die korrekte HA-Installationsstrategie gewählt; Backup/Rollback und ggf. notwendiger HA-Neustart werden deutlich angekündigt. Niemals stillschweigend laufende Integrationen überschreiben.
7. Für Updates dieselben Versions-/Integritäts-/Kompatibilitätsprüfungen. Ob ein PIN bei **jedem** Update oder nur bei der ersten Freischaltung erforderlich ist, wird als explizite Produktregel umgesetzt und dokumentiert; bis dahin keine implizite Berechtigung.

## Sicherheit und technische Sperren
- Der derzeitige statische `tailscale serve --https ... /srv/smartify/releases` bietet **keine PIN-Grenze**. Solange die ZIPs direkt über eine freigegebene URL heruntergeladen werden können, darf die Oberfläche **keinen PIN-geschützten Download behaupten**.
- Für den Kundenbetrieb **authentifizierten Paket-Gateway auf Cubi** bauen. Nur dieses Gateway darf Archive ausliefern; das Rohverzeichnis und HTTP-Port 8765 dürfen nicht über eine zweite erreichbare Route umgangen werden. Tailscale-ACLs auf TCP 443 begrenzen zusätzlich den Netzzugang.
- PINs mit langsamem Passwort-Hash (beispielsweise Argon2id), individueller Salt, Rate-Limit, Fehlversuchssperre, TLS, serverseitig geprüfter Kundenidentität und möglichst kurzfristigem Auth-Token absichern. Keine Klartext-PINs in Logs, Home-Assistant-Storage oder Browser-URL.
- Der bestehende SHA-256-Abgleich gegen `latest.json` allein ist keine Signatur. Cubi muss Releases aus einer getrennt vertrauenswürdigen Quelle signieren oder verifizierbare vertrauenswürdige Signaturen mitliefern; ein kompromittierter Paketserver darf die Vertrauenswurzel nicht einfach austauschen.
- Alle API-Pfade und App-IDs strikt allowlisten; keine beliebigen externen Download-URLs oder Dateipfade aus dem Katalog ausführen.
- Offline: Letzten Katalog als Cache anzeigen, aber **keine** ungeprüften Installationen durchführen. Fehlgeschlagene Checks deaktivieren Update-Meldungen nicht dauerhaft und führen zu keinem Endlos-Neustart.
- Tailscale-Verbindung für den Manager ist Voraussetzung. Öffentliche Web-/Routerfreigabe ist nicht erforderlich.

## Migrationsregel / aktueller Stand
- Bereits funktionierende SEP-HTTPS-Metadaten und geprüfte ZIP-Downloads bleiben unangetastet, bis das geschützte Gateway steht.
- Die bisherige `kubi_url`-Storage-Einstellung sowie WebSocket-Typen werden während der Migration kompatibel gelesen. Sichtbar ausschließlich **Cubi** mit C.
- Das generische Cubi-Katalogformat und serverseitige PIN-API sind **noch nicht live**. Der gegenwärtige native Update-Entwurf gilt zunächst nur für SEP; niemals behaupten, alle Apps seien bereits angebunden.
- Eigenständiger Server-/Kunden-End-to-End-Test vor Freigabe: 2-Minuten-Änderungserkennung, PIN richtig/falsch, Kunde ohne Berechtigung, URL-Bypass, SHA/Signatur falsch, Installation/Rollback, HA Neustart, Tailscale-Ausfall.
