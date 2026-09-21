# Backup und Restore

## Backup

```bash
docker compose -f compose.prod.yml --profile jobs run --rm backup
```

Das Skript:

- erzeugt `pg_dump -Fc`,
- validiert die Datei mit `pg_restore --list`,
- bewahrt 14 tägliche und ungefähr drei monatliche Generationen auf,
- dokumentiert Erfolg oder Fehler als `SystemJobRun`,
- kann optional über `RCLONE_REMOTE` eine Offsite-Kopie übertragen.

## Restore-Test

Ein Restore darf nie ungeprüft in die Produktionsdatenbank erfolgen.

```bash
export RESTORE_DATABASE=ki_radar_restore_test
docker compose -f compose.prod.yml --profile jobs run --rm \
  -e RESTORE_DATABASE=ki_radar_restore_test \
  backup /bin/sh /app/scripts/restore.sh /backups/daily/<datei>.dump
```

Danach Anwendung testweise gegen `ki_radar_restore_test` starten und prüfen:

- Anmeldung,
- Benutzer und Rollen,
- Use Cases,
- Reviews,
- Governance-Assessments,
- Änderungshistorie,
- Nachweislinks,
- Anonymisierungsstatus.

## Datenschutz nach Restore

Das externe Anonymisierungs-Ledger muss außerhalb der Datenbank erhalten bleiben. Nach Wiederherstellung eines älteren Backups sind zwischenzeitlich durchgeführte Anonymisierungen erneut anzuwenden.

## RPO/RTO

- RPO: höchstens 24 Stunden
- RTO: Zielwert vier Stunden
