# Reproduktion des Audits

Pruefstand: Satte882/KI-Ideenwerkstatt, main, Commit abbfb302747510106a4eac0db807b50bc254deb2.

Dieses Paket veraendert keinen Produktcode. Die zusaetzlichen Gegenproben pruefen beobachtetes Verhalten; PASSED bedeutet bei einer Defektprobe, dass der Defekt reproduziert wurde.

## Umgebung

- Windows, Python 3.13.5, Django 5.2.17, pytest 9.1.1.
- PostgreSQL 17.5-bookworm, frischer Container ohne bestehendes Volume.
- Vorhandene Repository-Umgebung .venv; alle Datenbankzustaende sind Test-Fixtures.
- Externe Netzwerkverbindungen der Testprozesse sind gesperrt. Modellantworten werden aus den bestehenden deterministischen Tests ersetzt. Keine Produktionsdatenbank verwenden.
- run_audit.py ist fuer den angegebenen lokalen Repositorypfad eingerichtet; bei Wiederholung an einem anderen Ort nur ROOT anpassen.

## Ausfuehrung in PowerShell

Paket in ein separates Arbeitsverzeichnis entpacken. Im Repository:

```powershell
docker run --detach --rm --name ki-outcome-audit-20261025 -e POSTGRES_USER=audit -e POSTGRES_PASSWORD=audit_local_only -e POSTGRES_DB=outcome_audit -p 127.0.0.1:55439:5432 --tmpfs /var/lib/postgresql/data postgres:17.5-bookworm
docker exec ki-outcome-audit-20261025 pg_isready -U audit -d outcome_audit
docker exec ki-outcome-audit-20261025 createdb -U audit outcome_audit_probes
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONIOENCODING='utf-8'
$env:AUDIT_RUN='full'
& .venv/Scripts/python.exe '<entpackter-Pfad>/run_audit.py'
$env:AUDIT_RUN='probes'
& .venv/Scripts/python.exe '<entpackter-Pfad>/run_audit.py' '<entpackter-Pfad>/test_audit_probes.py' -vv
docker stop ki-outcome-audit-20261025
```

Vor Start auf pg_isready mit Ergebnis 'accepting connections' warten. Ein belegter Port/Containername ist kein Grund, einen bestehenden Container zu loeschen: fuer die Wiederholung einen eigenen Namen/Port waehlen und run_audit.py entsprechend anpassen. --rm entfernt ausschliesslich den eigens gestarteten Container beim Stop; die tmpfs-Testdaten verbleiben nicht.

Der Runner setzt die PostgreSQL-Verbindung auf 127.0.0.1:55439, verwendet Django-Testdatenbanken, verlagert pytest-Cache, temporaere Dateien und Anonymisierungsledger neben die Auditdateien und deaktiviert Coverage-Ausgaben. Alle Gegenproben importieren bestehende Fixtures aus dem unveraenderten Repository.

## Enthaltene Ergebnisse

- full-suite.log / full-results.xml: 2592 passed, 2 skipped, 0 failed; 872.48 Sekunden.
- probes.log / probes-results.xml: 8 passed; 46.68 Sekunden.
- probe-evidence.jsonl: 10 Beobachtungsdatensaetze aus den 8 Gegenproben, einschliesslich zweier ehrlicher Go-live-Blockaden bei unbekannter Messung.
- repository-state.json: Commit, Remote-main, unveraenderter versionierter Stand, Versionsangaben.

Die beiden uebersprungenen Bestandstests betreffen auf Windows fehlende Symlink-Rechte. Die Warnungen stammen vom kuenftigen Django-6-Standardschema fuer URL-Felder. Es wurden weder echte Modellqualitaet noch realer wirtschaftlicher Nutzen getestet.

## Grenzen der Geschaeftsszenarien

A prueft die neue Outcome-Kohorte ab bestehender Prozess-/Optionsfixture bis Pilot und ungeklärtem Abschluss. Die Fixture ist kein fachlicher Beweis fuer wirtschaftliche KI-Ueberlegenheit und kein durchgehender neuer Discovery-bis-Outcome-Fall. B nutzt die echte strategische Materialisierung bis zur reproduzierten Screeningblockade; nachgelagerte Schritte wurden nicht durch erfundene Ratings erzwungen. C prueft den direkten Fall bis zum begruendet unbekannten Ergebnis und Ende. Alle Detailaussagen stehen in der Entscheidungsvorlage.
