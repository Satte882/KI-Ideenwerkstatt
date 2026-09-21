# Betriebshandbuch

## Betriebsbestandteile

- Django/Gunicorn-Anwendung
- PostgreSQL
- Nginx
- täglicher Review-Scan
- tägliches Datenbank-Backup
- Sentry-kompatibles Fehlertracking, sofern konfiguriert
- externer Uptime-Monitor

## Datenhaltung und Verantwortlichkeit

PostgreSQL ist das führende Speichersystem für die in der Weboberfläche erfassten fachlichen Anwendungsdaten. Dazu gehören unter anderem Use Cases, Architecture- und Discovery-Artefakte, Bewertungen, Freigaben, Governance-Screenings, Lifecycle-Reviews, Delivery Packages und technische Änderungshistorien.

Git und GitHub enthalten Code, Migrationen und Dokumentation, aber nicht automatisch die über die Oberfläche erfassten Produktionsdaten.

Der Produktionsstack verwendet getrennte persistente Volumes:

```text
prod_db      → PostgreSQL-Daten
prod_var     → variable Anwendungsdaten und Anonymisierungs-Ledger
prod_backups → Datenbank-Backups
prod_static  → gesammelte statische Dateien
```

Das Anonymisierungs-Ledger liegt bewusst außerhalb der Datenbank und muss neben Datenbank-Backups gesichert und nach einem Restore erneut angewendet werden.

Der technische Administrator beziehungsweise der festgelegte Betreiber ist verantwortlich für:

- Verfügbarkeit und Schutz der Datenbank,
- tägliche Backups und deren Überwachung,
- regelmäßige Restore-Tests,
- Sicherung des Anonymisierungs-Ledgers,
- Offsite-Sicherung, sofern für den Betrieb erforderlich,
- Speicherkapazität und Aufbewahrungsfristen,
- dokumentierte Lösch-, Auskunfts- und Wiederherstellungsprozesse.

Persistente Docker-Volumes sind kein Ersatz für ein Backup. Ein Löschen der produktiven Volumes darf nur im Rahmen eines kontrollierten Betriebs- oder Wiederanlaufverfahrens erfolgen.

Die vollständige Datenfluss- und Speicherübersicht steht in [`DATA_STORAGE.md`](DATA_STORAGE.md). Backup- und Restore-Details stehen in [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md).

## Regelbetrieb

Täglich automatisch:

- Datenbank-Backup
- Review-Scan
- Uptime- und Readiness-Prüfung

Monatlich manuell:

- Dependency- und Security-Updates prüfen
- fehlgeschlagene Jobs und Fehlerereignisse prüfen
- Speicherauslastung und Zertifikatsrestlaufzeit prüfen
- Staging- und Produktionsdeployment gemäß Releaseprozess

Quartalsweise:

- Restore-Test
- Testalarm für Anwendungsausfall
- Testalarm für fehlgeschlagene Jobs
- Prüfung des Notfallhandbuchs

## Status und Logs

```bash
docker compose -f compose.prod.yml ps
docker compose -f compose.prod.yml logs --tail=200 app
docker compose -f compose.prod.yml logs --tail=200 db
```

## Deployment

```bash
docker build -t ki-radar:<version> .
KI_RADAR_IMAGE=ki-radar:<version> docker compose -f compose.staging.yml up -d
# Smoke-Tests durchführen
KI_RADAR_IMAGE=ki-radar:<version> docker compose -f compose.prod.yml up -d
```

Vor Produktion immer Backup und Staging-Test durchführen.

Ein Deployment oder Git-Update ersetzt weder Datenbank-Backups noch Datenmigrationen. Django-Migrationen verändern die Datenbankstruktur kontrolliert; die fachlichen Daten verbleiben in PostgreSQL.

## Review-Scan

```bash
docker compose -f compose.prod.yml exec -T app python manage.py scan_due_reviews
```

Der Job versendet aktuell keine E-Mails. Er aktualisiert den operativen Jobstatus und liefert Zähler für überfällige, anstehende und terminlose Reviews.

## Anonymisierung

1. Datenschutzentscheidung im Admin als `PrivacyRequest` mit Status `Genehmigt` dokumentieren.
2. Benutzer-ID und Vorgangsreferenz ermitteln.
3. Als technischer Administrator ausführen:

```bash
python manage.py anonymize_user <USER_ID> <REQUEST_REFERENCE> --actor-id <ADMIN_ID>
```

Nach Restore:

```bash
python manage.py reapply_anonymizations --ledger /app/var/anonymization-ledger.jsonl --dry-run
python manage.py reapply_anonymizations --ledger /app/var/anonymization-ledger.jsonl
```

## Notfall-Wiederanlauf

1. neuen Host mit Docker bereitstellen,
2. Repository klonen,
3. Secrets aus gesichertem Speicher wiederherstellen,
4. produktives Image bauen oder abrufen,
5. PostgreSQL starten,
6. Backup in getrennte Datenbank wiederherstellen und prüfen,
7. produktive Datenbank gezielt bereitstellen,
8. Anonymisierungs-Ledger erneut anwenden,
9. Anwendung und Nginx starten,
10. Health-Checks und Smoke-Tests durchführen,
11. Monitoring und Alarmierung prüfen.