# Datenspeicherung und Datenfluss

Diese Dokumentation beantwortet die Frage, was mit Daten geschieht, die Benutzer in der KI-Radar-Oberfläche eingeben.

## Kurzfassung

Fachliche Eingaben aus der Oberfläche werden nach erfolgreicher serverseitiger Validierung in einer PostgreSQL-Datenbank gespeichert.

```text
Browser
  → Django-Anwendung
  → Berechtigungs- und Fachvalidierung
  → PostgreSQL
  → persistenter Speicher des jeweiligen Betriebsstacks
```

Git und GitHub enthalten den Programmcode, Datenbankmigrationen und Dokumentation. Sie enthalten nicht automatisch die in der Oberfläche erfassten Anwendungsdaten.

## Gespeicherte Datenarten

PostgreSQL ist das führende Speichersystem für unter anderem:

- Benutzer, Rollen und Organisationseinheiten,
- Fachdomänen, Capabilities, Value Streams und Fokusentscheidungen,
- Prozessanalysen und Lösungsoptionen,
- Use Cases und deren aktuelle Lifecycle-Daten,
- Bewertungen, Freigaben und Lifecycle-Reviews,
- Governance-Screenings und Prüfstatus,
- versionierte Delivery Packages,
- Nachweislinks,
- technische Änderungshistorien,
- Job-, Monitoring- und Benachrichtigungsprotokolle.

Delivery Packages werden in der Datenbank gespeichert. Ein Markdown-Export ist nur eine abgeleitete Darstellung und nicht die führende Datenquelle.

## Nachweise und Dokumente

KI-Radar speichert bei Nachweisen derzeit Metadaten und URLs, beispielsweise Bezeichnung, Dokumenttyp, Version, Kommentar und Ersteller. Das verlinkte Dokument selbst verbleibt im jeweiligen externen Dokumenten- oder Delivery-System, etwa SharePoint, Confluence, Jira, Azure DevOps oder GitHub.

Es findet über diese Funktion kein allgemeiner Datei-Upload in die KI-Radar-Datenbank statt.

## Änderungshistorie und Attribution

Zentrale Objekte verwenden `django-simple-history`. Dadurch können neben dem aktuellen Datensatz frühere Zustände gespeichert werden. Bei Änderungen über die Webanwendung wird nach Möglichkeit auch der angemeldete Benutzer als Verursacher der Änderung erfasst.

Fachliche Entscheidungen wie Freigaben und Lifecycle-Reviews werden zusätzlich als eigene Datensätze dokumentiert. Technische Historie und fachliche Entscheidungshistorie erfüllen unterschiedliche Zwecke und dürfen nicht miteinander verwechselt werden.

Historisierte oder fachlich dokumentierte Werte können auch dann noch in historischen Datensätzen vorhanden sein, wenn der aktuelle Wert später geändert wurde.

## Lokale Entwicklung

Der lokale Docker-Compose-Stack heißt `ki-radar-local`. PostgreSQL verwendet das benannte Volume:

```text
local_db → /var/lib/postgresql/data
```

Docker Compose erzeugt daraus normalerweise einen durch Docker verwalteten Volumenamen wie:

```text
ki-radar-local_local_db
```

Der tatsächliche physische Ablageort wird von Docker Desktop beziehungsweise Docker Engine verwaltet und liegt nicht im Git-Repository.

Folgende Vorgänge lassen das Datenbank-Volume normalerweise bestehen:

```powershell
docker compose -f compose.local.yml stop
docker compose -f compose.local.yml down
docker compose -f compose.local.yml up --build
```

Auch ein Branchwechsel, `git pull` oder ein Merge überträgt oder löscht die fachlichen Daten nicht. Git und PostgreSQL sind getrennte Systeme.

Dieser Befehl löscht dagegen die lokale Datenbank und die lokalen Volumes vollständig:

```powershell
docker compose -f compose.local.yml down -v
```

Vor seiner Ausführung müssen benötigte lokale Daten exportiert oder gesichert sein.

Das lokale Entwicklungssetup besitzt keine automatisch zugesicherte Offsite-Sicherung. Persistenz im Docker-Volume ist kein Backup.

## Staging

Der Staging-Stack heißt `ki-radar-staging` und verwendet getrennte persistente Volumes:

```text
staging_db     → PostgreSQL-Daten
staging_var    → variable Anwendungsdaten, insbesondere das Anonymisierungs-Ledger
staging_static → gesammelte statische Dateien
```

Staging-Daten sind von lokalen und produktiven Daten getrennt. Staging darf nicht als alleinige Sicherung der Produktion betrachtet werden.

## Produktion

Der Produktionsstack heißt `ki-radar-prod` und verwendet:

```text
prod_db      → PostgreSQL-Daten
prod_var     → variable Anwendungsdaten und Anonymisierungs-Ledger
prod_backups → erzeugte Datenbank-Backups
prod_static  → gesammelte statische Dateien
```

Die Datenbank ist die führende Quelle für die fachlichen Anwendungsdaten. Das externe Anonymisierungs-Ledger liegt bewusst außerhalb der Datenbank und muss bei Backup, Restore und Hostwechsel zusätzlich erhalten bleiben.

Details zu Backup, Restore, Aufbewahrung und Wiederanlauf stehen in:

- [`BACKUP_RESTORE.md`](BACKUP_RESTORE.md)
- [`OPERATIONS.md`](OPERATIONS.md)

## Backup und Löschung

Die dokumentierte produktive Backup-Funktion erzeugt einen PostgreSQL-Dump, validiert ihn und bewahrt mehrere Generationen auf. Optional kann über `RCLONE_REMOTE` eine Offsite-Kopie übertragen werden.

Ein Backup ist erst belastbar, wenn Restore-Tests erfolgreich durchgeführt werden. Der produktive Zielwert beträgt laut Betriebsdokumentation:

- RPO: höchstens 24 Stunden,
- RTO: vier Stunden.

Lösch- und Aufbewahrungsregeln müssen vor einem realen Produktivbetrieb organisationsspezifisch festgelegt und dokumentiert werden. Das Repository definiert noch keine vollständige unternehmensweite Retention Policy für alle fachlichen Daten.

Für Accelerator-Capture-Sessions, strukturierte LLM-Vorschläge und bereinigte LLM-Betriebsmetadaten gelten zusätzlich die verbindlichen Zielregeln aus [`accelerator/BLOCK_1_FOUNDATION.md`](accelerator/BLOCK_1_FOUNDATION.md). Die automatische technische Umsetzung erfolgt erst in den Blocks, die diese persistenten Objekte einführen.

## Optionale externe Übertragungen

### OpenRouter

Ohne konfigurierten `OPENROUTER_API_KEY` werden keine Use-Case-Daten an OpenRouter gesendet.

Wird der optionale Review-Copilot ausdrücklich gestartet, sendet die Anwendung ausgewählte Use-Case-Daten an die konfigurierte OpenRouter-API, darunter insbesondere:

- ID, Titel und Lifecycle-Status,
- Problemstellung und erwarteter Nutzen,
- Erfolgsmetrik, Baseline, Ziel und gegebenenfalls Ist-Wert,
- Kostenangaben,
- Ergebnis der deterministischen Entscheidungsprüfung.

Die Copilot-Ausgabe ist nur ein semantischer Hinweis und keine Freigabeinstanz. Nach aktuellem Stand wird die Antwort für die aufgerufene Seite dargestellt und nicht als eigener fachlicher Entscheidungsdatensatz gespeichert.

Für Accelerator-LLM-Aufrufe gelten gemeinsame Eingabe-, Ausgabe- und Timeoutgrenzen mit dem Präfix `ACCELERATOR_LLM_*`. Vollständige Prompts, Capture-Antworten und rohe Providerantworten werden nicht in Standardlogs geschrieben. Zulässig sind ausschließlich bereinigte technische Metadaten wie Zweck, Provider, Modell, interner Zielobjektbezug, Laufzeit, Größen, Ergebnisstatus sowie Token- und Kostenwerte, soweit verfügbar.

Die vollständigen Provider-, Datenfluss-, Logging- und Retention-Regeln stehen in [`accelerator/BLOCK_1_FOUNDATION.md`](accelerator/BLOCK_1_FOUNDATION.md).

### Sentry

Sentry ist optional. Bei konfiguriertem `SENTRY_DSN` können technische Fehler- und Diagnosedaten an die konfigurierte Sentry-Instanz übertragen werden. Die Konfiguration deaktiviert das Mitsenden personenbezogener Standarddaten und vollständiger Request-Bodies; die konkrete datenschutzrechtliche Bewertung bleibt dennoch Teil des jeweiligen Betriebsmodells.

### Externe Nachweis- und Delivery-Systeme

Nachweislinks und Delivery-URLs verweisen auf externe Systeme. Welche Daten dort gespeichert, übertragen oder aufbewahrt werden, richtet sich nach dem jeweiligen Zielsystem und liegt außerhalb der KI-Radar-Datenbank.

## Verantwortungsgrenzen

Vor einem realen Produktivbetrieb müssen mindestens festgelegt und dokumentiert werden:

- verantwortlicher Betreiber der PostgreSQL-Datenbank,
- Backup- und Restore-Verantwortung,
- Speicherort und Schutz der Offsite-Backups,
- Aufbewahrungs- und Löschfristen,
- Berechtigungs- und Zugriffskonzept,
- Verschlüsselung und Schlüsselverwaltung,
- Behandlung von Staging- und Testdaten,
- zulässige externe Übertragungen,
- Verfahren für Auskunft, Berichtigung, Anonymisierung und Löschung.

## Praktische Prüfung

Lokale Volumes anzeigen:

```powershell
docker volume ls --filter name=ki-radar-local
```

Details des lokalen Datenbank-Volumes anzeigen:

```powershell
docker volume inspect ki-radar-local_local_db
```

Der tatsächliche Name kann abweichen, wenn der Compose-Projektname beim Start überschrieben wurde.

Datenbankverbindung innerhalb des lokalen Stacks prüfen:

```powershell
docker compose -f compose.local.yml exec db `
  psql -U ki_radar -d ki_radar -c "SELECT current_database(), current_user;"
```

Diese Befehle zeigen den technischen Speicher. Fachliche Inhalte sollten regulär über die Anwendung oder kontrollierte Administrations- und Backup-Prozesse verwaltet werden.
