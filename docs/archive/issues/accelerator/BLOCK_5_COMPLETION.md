# Accelerator Block 5 – Abschlussnachweis

## 1. Ergebnis

Block 5 liefert den ersten nutzbaren Accelerator-MVP für eine sichere, feldweise Übernahme von LLM-Vorschlägen in bestehende Value Streams und Use Cases.

Der Nutzer kann ausdrücklich freigegebene grüne Textfelder einzeln prüfen, direkt übernehmen, vor der Übernahme bearbeiten oder verwerfen. Jede Übernahme prüft serverseitig Berechtigung, Zielbindung, Kandidatenzustand, Quellversion und den kanonischen Hash des konkreten Zielfelds. Zwischenzeitliche Feldänderungen werden nicht überschrieben, sondern als verständlicher Drei-Werte-Konflikt dargestellt.

## 2. Sequenzielle Umsetzung

| Paket | Pull Request | Ergebnis |
|---|---:|---|
| Arbeitsplan | #165 | Verbindliche AP- und Abnahmefolge |
| AP 1 | #166 | Gap-Analyse, Feldfreigabe und Schreibpfade |
| AP 2 | #167 | Zielbindung, Feature-Flag und MVP-Grenzen |
| AP 3 | #168 | Kanonisierung, Snapshot und Kandidaten-Gültigkeit |
| AP 4 | #169 | Kandidatenstatus, Supersede und Idempotenz |
| AP 5 | #170 | Explizite Feldregistry und reguläre Form-Adapter |
| AP 6 | #171 | Atomare Übernahme, Berechtigung und Konfliktschutz |
| AP 7 | #172 | Datensparsames Audit, LLM-Kostenbezug und Retention |
| AP 8 | #173 | Review-UI, Unsicherheitsregeln und Konfliktaktionen |
| AP 9 | #174 | Nebenläufigkeits-, Sicherheits- und Regressionstests |
| AP 10 | #175 | Real-DEMO, Messung, UI-Verifikation und Blockabschluss |

Jedes Arbeitspaket wurde beziehungsweise wird als eigener Branch, ein eigener Commit und ein eigener Pull Request umgesetzt. Issue #116 wurde nicht verändert.

## 3. Fachlicher Umfang

### Freigegebene Zieltypen

- `ValueStream`
- `UseCase`

### Schreibgrenze

- ausschließlich statisch freigegebene `CharField`- und `TextField`-Felder,
- keine Reflection-basierte generische Schreibfunktion,
- vollständige Validierung über die bestehenden regulären ModelForms,
- Speicherung ausschließlich des konkret freigegebenen Felds,
- bestehende Use-Case-History und fachliche Seiteneffekte bleiben erhalten.

### Unsicherheits-Policy

| Unsicherheit | Direkte Übernahme | Bearbeitet übernehmen | Verwerfen |
|---|---:|---:|---:|
| `low` | ja | ja | ja |
| `medium` | nein | ja | ja |
| `high` | nein | nein | ja |

Die Policy liegt als kleine zentrale Matrix neben `AdoptionTargetSpec`. Unsicherheit ist eine Eigenschaft des Kandidaten und gilt zieltypübergreifend; eine Wiederholung derselben Regeln in jedem Registry-Eintrag würde redundante Pflege erzeugen. UI und direkte POST-Requests verwenden dieselbe fail-closed Policy.

## 4. Konflikt- und Nebenläufigkeitsschutz

- atomare Reservierung `open -> processing` per Compare-and-swap,
- Sperre des Kandidaten und anschließend des gebundenen Zielobjekts,
- erneute Berechtigungs- und Integritätsprüfung innerhalb derselben Transaktion,
- Feldhash statt globalem `updated_at` als ausschlaggebender Konfliktmaßstab,
- keine stille Überschreibung bei zwischenzeitlicher Änderung,
- idempotente Wiederholung bereits terminaler Kandidaten,
- genau ein Audit-Eintrag pro verarbeiteter Kandidatenentscheidung,
- kein falscher Konflikt bei unterschiedlichen Feldern desselben Zielobjekts.

Die UI zeigt im Konfliktfall ausschließlich:

- damaligen Ausgangswert,
- aktuellen Datenbankwert,
- vorgeschlagenen Wert,
- „Neu analysieren“,
- regulär manuell bearbeiten,
- „Verwerfen“.

Eine Force-Overwrite- oder Drei-Wege-Merge-Funktion existiert nicht.

## 5. Audit, Kosten und Retention

`FieldAdoptionAudit` hält einen unveränderlichen minimalen Nachweis mit:

- stabilen Snapshot-IDs für Session, Analyse, Vorschlag und Kandidat,
- Zieltyp, Ziel-ID und Zielfeld,
- Ausgangs-, Vorschlags-, bearbeitetem und finalem Wert,
- Aktion, Ergebnis, Fehlercode, Benutzer und Zeitpunkt,
- Provider, Modell, Vertragsversionen, Token und Kosten,
- Quellfrage und Hash des Quellausschnitts.

Nicht dauerhaft dupliziert werden Capture-Rohantworten, vollständige Prompts, Providerantworten oder Quellausschnitte.

Kandidaten folgen der bestehenden Capture-Retention und werden mit dem Capture-Rohdatenbaum gelöscht. Audit-Fremdschlüssel werden dabei per `SET_NULL` gelöst; die unveränderlichen Snapshot-IDs und der minimale Änderungsnachweis bleiben erhalten. Offene Kandidaten überleben die Löschung ihrer Capture Session nicht.

## 6. Migrationen

Block 5 umfasst folgende Accelerator-Migrationen:

- `0003_capture_target_binding`
- `0004_field_adoption_candidate`
- `0005_field_adoption_candidate_state`
- `0006_field_adoption_audit`

Die Repository-CI prüft `makemigrations --check --dry-run` und wendet sämtliche Migrationen auf PostgreSQL an.

## 7. Sicherheits- und Regressionstestmatrix

Nachgewiesen sind mindestens:

- POST-only und CSRF-Schutz,
- Ownership-Scope der Analyse und des Kandidaten,
- unveränderte fachliche Berechtigungen für Value Stream und Use Case,
- Manipulationsschutz für Ziel-ID, Zieltyp und Zielfeld,
- fehlendes, archiviertes und zwischenzeitlich geändertes Ziel,
- Validierungsfehler ohne Domänenmutation,
- Erhalt von Use-Case-History und Workflow-Gates,
- paralleler Doppelklick auf denselben Kandidaten: eine Mutation und ein Audit,
- zwei Benutzer auf unterschiedlichen Feldern desselben Ziels: kein Deadlock und kein falscher Feldkonflikt,
- vollständige Block-3-, Block-4- und Repository-Regressionen.

## 8. Reproduzierbarer `[Real-DEMO]`

Der Management-Command `run_block5_real_demo` erzeugt reproduzierbar einen Value Stream und einen Use Case, bindet je eine abgeschlossene Capture Session, legt erfolgreiche Analyse-Läufe mit eindeutigen Analyse-IDs an und führt die Feldentscheidungen über dieselben Produktionsservices aus.

Erwartete Ergebnisverteilung:

| Ergebnis | Anzahl |
|---|---:|
| direkt übernommen | 1 |
| bearbeitet übernommen | 1 |
| verworfen | 2 |
| konfliktbehaftet | 1 |
| ersetzt | 1 |
| offen | 0 |

Kosten- und Laufbezug:

- drei eindeutige Analyse-Läufe,
- zwei Analyse-Läufe mit tatsächlich übernommenen Feldern,
- zwei tatsächlich verwendete Felder,
- Gesamtkostenwert aller Läufe: `0.006000`,
- Kostenwert der verwendeten Läufe: `0.005000`,
- Kostenwert je verwendetem Feld: `0.002500`,
- Providerwartezeit: `3200 ms`,
- Review- und Korrekturzeit werden separat durch den real ausgeführten Servicepfad gemessen.

Der CI-Nachweis verwendet deterministische erfolgreiche Analyse-Datensätze und ruft keinen externen Provider auf. Dadurch bleiben Ergebnisverteilung, Kostenaggregation und Sicherheitsverhalten reproduzierbar; die Anwendung verarbeitet dabei reale Datenbankobjekte und die vollständigen Produktionsservices.

## 9. UI-Verifikation

Der Workflow `Block 5 completion verification` prüft mit Playwright auf Desktop (`1440 × 1000`) und Mobile (`390 × 844`):

- Low-, Medium- und High-Unsicherheitskarten,
- erlaubte und verbotene Aktionen je Policy,
- Drei-Werte-Konfliktkarte,
- ausschließlich erlaubte Konfliktaktionen,
- fehlenden horizontalen Überlauf,
- keine außerhalb des Viewports liegenden Interaktionen.

Er erzeugt ein JSON-Manifest, Server- und Verifikationslogs sowie vier vollständige Screenshots als 30 Tage aufbewahrtes Workflow-Artefakt. Die endgültigen Workflow- und Artefakt-IDs werden nach dem grünen AP-10-Lauf in diesem Nachweis ergänzt.

## 10. CI- und Abnahmenachweis

- AP 7: PR #172, vollständige unveränderte Repository-CI grün.
- AP 8: PR #173, vollständige unveränderte Repository-CI grün.
- AP 9: PR #174, CI-Lauf `31086843900` (`KI-Radar CI`, Run 1033) grün.
- AP 10: vollständige Repository-CI und eigener Block-5-Abschlussworkflow müssen vor Merge grün sein.

Die Haupt-CI bleibt unverändert und prüft weiterhin repository-weit:

- Ruff lint,
- `ruff format --check .`,
- Django-Systemcheck,
- Migrationskonsistenz und Migration,
- vollständige Testsuite,
- Bandit,
- Dependency Audit,
- lokale, Staging- und Produktions-Compose-Konfiguration,
- Produktions- und Entwicklungs-Image-Build.

## 11. Bestätigte Nicht-Ziele

Nicht umgesetzt wurden:

- gelbe Metrik-, Enum-, Boolean-, Datums-, Referenz- oder Rollenfelder,
- rote Entscheidungs-, Validierungs- oder Bestätigungsfelder,
- automatische Phasen-, Prozessanalyse- oder Lösungsoptionsanlage,
- Sammelübernahme,
- automatische Freigabe, Governance- oder Lifecycle-Entscheidung,
- Änderungen an übergebenen Delivery Packages,
- Force-Overwrite oder Drei-Wege-Merge,
- Echtzeit-Kollaboration oder WebSockets,
- generische Audit-, Retention-, Feature-Flag- oder Schreibplattform.

## 12. Abnahme gegen Issue #121

| Abnahmekriterium | Nachweis |
|---|---|
| Gap-Analyse dokumentiert | AP 1 |
| nur explizit freigegebene grüne Felder | AP 1 und AP 5 |
| Berechtigung, Ausgangswert und aktueller Zustand | AP 3 und AP 6 |
| keine stille Überschreibung | AP 4 und AP 6 |
| verständliche Konfliktdarstellung | AP 8 und UI-Verifikation |
| reguläre Forms oder Domain Services | AP 5 und AP 6 |
| Übernahme, Bearbeitung und Verwerfen auditierbar | AP 7 |
| Erfolg, Berechtigung, Konkurrenz, Validierung und unzulässige Felder getestet | AP 9 |
| Lösung explizit und klein | AP 2, AP 5 und bestätigte Nicht-Ziele |
| erster real nutzbarer MVP | AP 8 bis AP 10 |

Issue #121 wird erst nach grünem AP-10-PR, visueller Prüfung der Artefakte, vollständiger Checkliste und Merge geschlossen.
