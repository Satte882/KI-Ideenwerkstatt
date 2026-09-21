# Umsetzungsauftrag: KI-Radar

> **Status:** Dieses Dokument beschreibt die ursprüngliche Basisspezifikation des ersten Umsetzungsschritts. Der aktuelle Produktstand umfasst zusätzlich geführten Intake, evidenzbasierte Freigaben, Portfolio-Matrix, optionale Value-Stream- und Prozessanalyse, explizite Lösungsoptionen sowie versionierte Delivery Packages. Maßgeblich für den aktuellen Funktionsumfang sind [README.md](README.md) und [docs/DISCOVERY_ARCHITECTURE.md](docs/DISCOVERY_ARCHITECTURE.md).

## 1. Zweck

KI-Radar ist eine branchenneutrale, interne und codebasierte Webanwendung zur Erfassung und Steuerung von KI-Use-Cases in kleinen und mittleren Unternehmen. Das System verwaltet Ideen, Prüfungen, Piloten, produktive Anwendungen und beendete Vorhaben. Es ersetzt weder Projektmanagement noch rechtliche, datenschutzrechtliche oder sicherheitstechnische Fachprüfungen.

Zielgröße:

- 10–30 registrierte Ideen
- 3–8 parallele Piloten oder produktive Use Cases
- 5–15 regelmäßige Benutzer
- ein Unternehmen und ein Mandant

## 2. Architektur

- Python 3.13
- Django 5.2 LTS
- PostgreSQL
- Gunicorn hinter Nginx
- serverseitige Django Templates und Bootstrap
- Docker Compose
- getrennte Stacks für lokal, Staging und Produktion
- `django-simple-history`
- pytest, pytest-django und Ruff
- GitHub Actions

Die Anwendung ist ein modularer Monolith mit den Modulen Accounts, Use Cases, Governance, Reviews, Notifications, Reporting und Core. Komplexe Geschäftslogik liegt in Services, nicht in Templates oder Signals.

Nicht Bestandteil der ersten Version sind FastAPI, React, Power Platform, Celery, Redis, LLM-Funktionen, automatische AI-Act-Klassifizierung, Multi-Tenancy und frei konfigurierbare Workflow-Engines.

## 3. Rollen

- **Technischer Administrator:** Betrieb, Benutzer und Stammdaten
- **KI-Koordinator:** alle Use Cases pflegen, Governance-Screenings und Reviews durchführen
- **Business Owner:** eigene Use Cases pflegen
- **Leser:** nicht archivierte Use Cases lesen

Lifecycle-Änderungen auf Betrieb oder Beendet sind KI-Koordinatoren beziehungsweise Administratoren vorbehalten. Berechtigungen werden serverseitig geprüft.

## 4. Lifecycle

1. Idee
2. Prüfung
3. Pilot
4. Betrieb
5. Beendet

Statuswechsel erfolgen über Reviews. Rücksprünge sind möglich, müssen aber begründet werden. Für Zielstatus gelten Pflichtinformationen:

- Prüfung: Problem, Bereich/Prozess, Owner, Nutzen
- Pilot: Baseline, Erfolgskriterium, Zielwert, Datenquellen, Governance-Screening, Pilotende, Review-Termin
- Betrieb: Pilotergebnis, technischer Owner, Kosten, Support, menschliche Kontrolle, erforderliche Fachprüfungen, Review-Termin
- Beendet: Grund, Datum und Umgang mit Daten und Zugängen

## 5. Fachliches Datenmodell

### User und Organisationseinheit

Eigenes Django-User-Modell mit Organisationseinheit, Funktion, externer ID, Aktiv- und Anonymisierungsstatus. Organisationseinheiten sind frei konfigurierbare Stammdaten.

### UseCase

Enthält Identifikation, fachlichen Kontext, Owner, Lifecycle, Lösungsart, Anbieter, Modell, Systeme, Datenquellen, Nutzen, Erfolgsmessung, Kosten, vier qualitative Bewertungen, Governance-Prüfflags, Betriebsverantwortung und Abschlussinformationen.

Es wird kein gewichteter Gesamtscore berechnet. Der angezeigte Hinweis ist nicht bindend.

### GovernanceAssessment

Erfasst personenbezogene Daten, Beschäftigtendaten, Bewertung natürlicher Personen, biometrische Daten, Sicherheitsbezug, regulierte Produkte, externe Anbieter, externe generierte Inhalte, menschliche Kontrolle und erforderliche Fachprüfungen. Das System erteilt keine rechtliche Klassifizierung oder Freigabe.

### Review

Dokumentiert Entscheidung, Begründung, bisherigen und neuen Status, Maßnahmen, Verantwortlichen, Fälligkeit und nächsten Review.

### EvidenceLink

Speichert Links auf freigegebene externe Dokumentenablagen. Dateien selbst werden nicht hochgeladen.

### NotificationLog

Ist als Erweiterungspunkt für spätere Benachrichtigungen vorhanden. Der SMTP-Versand ist im ersten Schritt ausdrücklich ausgenommen.

### SystemJobRun

Dokumentiert operative Jobs wie Datenbank-Backup und Review-Scan.

## 6. Datenschutz und Löschung

Fachliche Kerndaten werden archiviert. Benutzerkonten werden bei Ausscheiden zunächst deaktiviert. Bei bestätigtem berechtigtem Löschbedarf wird der Benutzer anonymisiert:

- Name, reale E-Mail, externe ID, Funktion und Organisationseinheit werden entfernt
- Benutzername wird neutral ersetzt
- Konto und Sessions werden deaktiviert
- Rechte werden entfernt
- historische relationale Referenzen bleiben über die interne ID bestehen
- keine rückführbare Klarnamenzuordnung wird geführt

Ein externes, minimales Anonymisierungs-Ledger ermöglicht die Wiederanwendung nach Restore eines älteren Backups. Freitexte und externe Systeme sind zusätzlich zu prüfen.

## 7. Benutzeroberfläche

- Dashboard mit Status, Piloten, Betrieb, überfälligen und anstehenden Reviews, fehlender Governance und veralteten Einträgen
- Use-Case-Liste mit Suche, Filter und CSV-Export
- Detailseite für Kontext, Nutzen, Technik, Governance, Reviews, Nachweise und Historie
- Bearbeitungsformular
- Governance-Screening
- Review- und Statusentscheidung
- Monatsreview-Ansicht

## 8. Automatisierung

Ein täglicher `scan_due_reviews` ermittelt überfällige, in 30 Tagen fällige und terminlose Use Cases und dokumentiert den erfolgreichen Lauf. Er versendet aktuell keine E-Mail. Dashboard und Monatsreview fragen die Fälligkeiten direkt ab.

## 9. Security

- HTTPS, HSTS, sichere Cookies, CSRF, CSP und Clickjacking-Schutz
- Argon2-Passwort-Hashing
- Login-Rate-Limit und Lockout
- keine Secrets im Repository
- Docker Secrets in Produktion
- Datenbank nicht öffentlich erreichbar
- serverseitige Berechtigungen
- sensible Inhalte nicht in Logs oder Fehlertracking
- ohne SSO/MFA nur internes Netz oder VPN

## 10. Backup und Restore

- tägliches `pg_dump -Fc`
- Prüfung des Dumps mit `pg_restore --list`
- 14 tägliche und drei monatliche Generationen
- verschlüsselte Offsite-Kopie vor echtem Produktivbetrieb zu konfigurieren
- RPO 24 Stunden, RTO vier Stunden
- quartalsweiser Restore-Test
- erneute Anwendung zwischenzeitlicher Anonymisierungen nach Restore

## 11. Monitoring

- `/health/live`
- `/health/ready`
- geschützter `/health/operations`
- optionale Sentry-Integration ohne Standard-PII
- Überwachung von Erreichbarkeit, Datenbank, Backup, Review-Scan, Speicher und TLS
- externe Alarmierung ist infrastrukturspezifisch zu konfigurieren

## 12. Staging

Staging läuft im Einzelbetrieb auf demselben Server, aber mit separatem Compose-Projekt, Datenbank, Benutzer, Volumes, Netzwerk, Secrets und Port. Staging greift nie auf die Produktionsdatenbank zu und versendet keine realen Benachrichtigungen.

## 13. CI/CD und Qualität

Bei Pull Requests und Pushes laufen:

- Ruff
- Django System Check
- Migration Check
- Unit- und Integrationstests mit PostgreSQL
- Bandit
- pip-audit
- Docker-Build

Kritische Berechtigungs-, Lifecycle-, Governance-, Review-, Anonymisierungs- und Joblogik wird automatisiert getestet.

## 14. Betriebsmodell

Benötigte Verantwortlichkeiten sind Sponsor, KI-Koordinator, Business Owner und technischer Betreiber. Für den aktuellen Einzelbetrieb gelten dokumentierte Mindestanforderungen: Remote-Repository, Passwortmanager/Recovery-Codes, ADRs, Backups, Restore-Tests, Monitoring und Notfallhandbuch. Die vollständige personelle Redundanz bleibt bis zur Einarbeitung einer zweiten Person offen.

## 15. Abnahme

Die Solo-Betriebsfreigabe setzt funktionierende Rollen, Lifecycle, Governance, Historie, Reviews, Dashboard, Review-Scan, Anonymisierung, Security, CI, Backup, Restore, Monitoring-Grundlagen und Dokumentation voraus. Eine vollständige betriebliche Abnahme erfordert zusätzlich eine zweite Person, die Deployment, Restore und Fehleranalyse praktisch durchführen kann.

## 16. Abweichung im ersten Umsetzungsschritt

Der E-Mail-basierte SMTP-Reminder wird nicht umgesetzt. Alle anderen fachlichen und technischen Bereiche werden implementiert oder – soweit sie externe Infrastruktur oder Zugangsdaten erfordern – vollständig vorbereitet und in `OPEN_QUESTIONS.md` als konkrete Produktivkonfiguration dokumentiert.
