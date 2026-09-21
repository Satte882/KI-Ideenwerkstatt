# KI-Radar

[![KI-Radar CI](https://github.com/Satte882/KI-UseCase-Radar/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Satte882/KI-UseCase-Radar/actions/workflows/ci.yml)

> AI Business Architecture, Portfolio- und Decision-Governance-Cockpit für kleine und mittlere Unternehmen

KI-Radar verbindet Business Architecture, Prozessdiagnose, lösungsoffene KI-Auswahl, Governance, Delivery Readiness und Lifecycle-Steuerung in einem nachvollziehbaren Arbeitsmodell.

Das System beantwortet nicht nur, **welche KI-Ideen existieren**, sondern vor allem:

- Aus welchem Geschäftsproblem entsteht ein Vorhaben?
- Welcher End-to-End-Bereich rechtfertigt einen Deep Dive?
- Welche Ursache beziehungsweise welcher Engpass soll tatsächlich adressiert werden?
- Reicht eine organisatorische, regelbasierte oder klassische technische Lösung aus?
- Falls KI sinnvoll ist: Welche technische Autonomie ist wirklich erforderlich?
- Sind Nutzen, Datenlage, Evidenz und technische Machbarkeit ausreichend belastbar?
- Welche Governance- und Fachprüfungen fehlen?
- Ist das Vorhaben entscheidungs- und umsetzungsreif?
- Welche Systeme, Datenflüsse, Anforderungen und Architekturartefakte benötigt Delivery?
- Was wurde im Pilot tatsächlich gemessen und welche Lifecycle-Entscheidung folgt daraus?

---

## End-to-End-Arbeitsmodell

```text
Business Architecture & Discovery
→ Fokus & Prozessdiagnose
→ Lösungsraum
→ Use Case
→ Bewertung & Governance
→ Freigabe
→ Delivery Readiness & Übergabe
→ Pilot
→ Wirkung validieren
→ Scale Readiness & Ergebnisentscheidung
→ Betrieb oder Abschluss
```

Der systematische Pfad beginnt bei Geschäftsarchitektur und Problemverständnis. KI ist darin **eine Lösungsoption unter mehreren**, nicht der Ausgangspunkt der Analyse.

Bereits bekannte Vorhaben können weiterhin direkt über den Use-Case-Intake erfasst werden. Systematisch abgeleitete Vorhaben erhalten zusätzlich eine nachvollziehbare Herkunftskette vom Value Stream über Fokus, Prozessanalyse und Lösungsoption bis zum Use Case.

Die operative Umsetzung verbleibt in Jira, Azure DevOps, GitHub oder einem anderen Delivery-System. KI-Radar hält den entscheidungsrelevanten Kontext, die Governance, die Übergabereife und die späteren Review-Snapshots.

Die Gesamtstrecke wird in der Oberfläche kontextbezogen dargestellt. Auf konkreten Arbeitsobjekten zeigt eine kompakte Lifecycle-Orientierung den tatsächlichen Zustand und die nächste relevante Entscheidung; Querschnitts- und Listensichten wie Portfolio verzichten bewusst auf eine pseudo-lineare Journey.

---

## Acht zentrale Produktfähigkeiten

### 1. Business Architecture, Discovery und Fokus

KI-Radar unterstützt die strukturierte Analyse eines Geschäftsbereichs durch:

- kontrollierte Fachdomänen und Business Capabilities;
- End-to-End-Value-Streams;
- Trigger, Outcome, Stakeholder, Scope-In und Scope-Out;
- geordnete Wertschöpfungsphasen mit erkennbarem Wertfortschritt;
- Fokus-Screening nach strategischem Impact, wirtschaftlichem Potenzial, Problemintensität, Datenzugänglichkeit und Veränderungsaufwand;
- dokumentierte Auswahl für einen Deep Dive;
- kontextsensitive Methodik-Hilfe und verständliche Skalenanker.

Value Stream, Capability und Process bleiben fachlich getrennte Konzepte. Der Discovery-Pfad ist optional und belastet bekannte Einzelvorhaben nicht mit unnötigen Architekturartefakten.

Details: [Discovery & Architecture](docs/DISCOVERY_ARCHITECTURE.md) · [Value-Stream-Methodik](docs/VALUE_STREAM_METHODOLOGY.md)

### 2. Prozessdiagnose und lösungsoffene Auswahl

Die Prozessanalyse erfasst unter anderem:

- Ist-Ablauf;
- Rollen, Systeme und Datenobjekte;
- Geschäftsregeln;
- Handoffs und Ausnahmen;
- Baseline-Kennzahlen;
- beobachtete Probleme;
- Ursachenhypothesen und bestätigte Ursachen;
- optional einen tatsächlich systembestimmenden Constraint.

Frühe Exploration bleibt möglich. Eine verbindliche bevorzugte Lösung wird jedoch erst auf ausreichend belastbarer Diagnosebasis festgelegt.

Organisatorische Änderungen, Standardsoftware, regelbasierte Automatisierung, klassische technische Lösungen und KI bleiben echte Alternativen. KI wird nicht automatisch bevorzugt.

### 3. AI Accelerator

Der Accelerator beschleunigt die Erstbefüllung, ohne die fachlichen Gates zu umgehen:

- persistente, wiederaufnehmbare geführte Erfassung;
- strukturierte LLM-Extraktionsvorschläge;
- sichtbare Quellen, Unsicherheit, offene Fragen und Konflikte;
- serverseitig kontrollierte Feld- und Typvalidierung;
- konfliktgeschützte feldweise Übernahme;
- strukturierte Entwürfe für Metriken, Value-Stream-Phasen und Prozessanalysen;
- generative Entwürfe mehrerer Lösungsoptionen;
- deterministisches Evidence-to-Delivery-Mapping;
- nachvollziehbare Rollen-Defaults.

LLM-Funktionen erzeugen Vorschläge und Entwürfe. Sie setzen keine Fokusentscheidung, bevorzugte Lösung, Freigabe, Governance-Entscheidung, Delivery-Bestätigung oder Lifecycle-Entscheidung.

Vertiefende Nachweise liegen unter [`docs/accelerator/`](docs/accelerator/).

### 4. Architecture Advisor und Solution Quality Control

Für vorhandene Lösungsoptionen kann KI-Radar die minimal hinreichende Architekturklasse deterministisch einordnen:

- `No LLM required`;
- `Controlled LLM`;
- `LLM Workflow`;
- `Bounded Agent`;
- `Assessment open`.

Die Einordnung basiert auf vier fachlichen Fragen und liefert reproduzierbare Reason Codes sowie sichtbare Begründungen wie **„Warum dieses Muster?“** und **„Warum kein Agent?“**.

Für generierte Lösungsentwürfe existiert zusätzlich ein kontrollierter Quality-Control-Pfad:

```text
Generate
→ deterministic Validate
→ Critic
→ optional exactly one Repair
→ deterministic Validate
→ final Critic
→ Human Review
```

Der Critic prüft semantische Qualität, aber keine fachliche Rangfolge. Repair ist auf genau einen gezielten Versuch begrenzt. Human Review bleibt der Endpunkt.

### 5. Decision Governance und Portfolio

Jeder Use Case wird anhand einer nachvollziehbaren Evidenzbasis bewertet.

Berücksichtigt werden unter anderem:

- wirtschaftlicher Nutzen;
- strategischer Beitrag;
- technische Machbarkeit;
- Datenreife;
- Risiko und Komplexität;
- Qualität und Aktualität der Evidenz;
- Confidence und offene Annahmen;
- Governance-, Datenschutz-, Security- und Rechtsprüfungen;
- unabhängige Bestätigungen und Rollentrennung.

Bewertung und verbindliche Freigabe sind getrennte Arbeitsschritte. Serverseitige Hard Gates schützen die maßgeblichen Entscheidungen.

Die Portfolio-Sicht verbindet Managementübersicht und Handlungsfähigkeit:

- Fachdomänen- und Capability-Zuordnung;
- kategorische Matrix aus Nutzen und technischer Machbarkeit;
- Entscheidungsstatus und Confidence;
- Filter nach Organisationseinheit, Lifecycle, Lösungstyp und Status;
- konkrete Blocker und direkte Navigation zur notwendigen Aktion.

Es gibt bewusst keinen künstlichen Gesamtscore und kein automatisches Ranking.

Details: [Entscheidungsmethodik](docs/DECISION_METHOD.md)

### 6. Delivery Readiness, Provenance und Übergabe

Aus einer final positiven Freigabe kann ein versioniertes Delivery Package erzeugt werden.

Es bündelt unter anderem:

- Problem- und Geschäftskontext;
- Zielbild und Scope;
- Nutzer und Nutzungsszenarien;
- System-, Daten- und Integrationskontext;
- Ist-/Ziel-Systemlandschaft;
- Daten- und Informationsflüsse;
- Architekturartefakte und technische Verantwortlichkeiten;
- funktionale und nichtfunktionale Anforderungen;
- Security-, Datenschutz- und Rechtsanforderungen;
- Human Oversight, Logging, Betrieb und Support;
- MVP-Scope;
- Akzeptanzkriterien, Tests und Erfolgsmessung;
- Risiken, Annahmen und Abhängigkeiten;
- Architekturentscheidungen und initialen Umsetzungsrahmen.

Delivery Readiness gliedert das Package in sieben prüfbare Sektionen. Übernommene Inhalte bleiben mit Herkunft sichtbar. Strukturierte Findings benennen konkrete Regel, Ursache, Zuständigkeit und nächste Handlung.

Source-Snapshots und kontrollierte Source Decisions verhindern, dass spätere Änderungen an Upstream-Objekten stillschweigend bestehende Packages verändern. Übergebene Package-Versionen bleiben unveränderlich.

Die vollständige methodische Grundlage ist im [Vorgehensmodell für produktionsreife KI-Systeme](docs/DELIVERY_METHODOLOGY.md) hinterlegt.

### 7. Lifecycle, Wirkung und Betrieb

Die Journey endet nicht mit dem Handover.

KI-Radar führt den Lifecycle:

```text
Idee → Prüfung → Pilot → Betrieb → Beendet
```

`Scale Readiness` ist dabei bewusst kein zusätzlicher Status, sondern die verbindliche Ergebnisentscheidung vor dem Statuswechsel von `Pilot` nach `Betrieb`.

Dazu gehören:

- expliziter Pilotstart erst nach verbindlicher Übergabe;
- Baseline, Zielwert, aktueller Ist-Wert und Messmethode;
- Messzeitraum, Messdatum und Nachweis;
- geplantes Pilotende und nächster Review;
- Scale Readiness als explizites Gate zwischen validierter Pilotwirkung und Betrieb;
- sechs Prüfdimensionen mit Pilot-, Governance-, Delivery-, ML-Test-Score- und Betriebsinformationen;
- nachvollziehbare Vorschläge `GO`, `CONDITIONAL GO` oder `NO-GO`, Hard Blocker und eine konkrete nächste Aktion;
- Conditional Go nur mit Maßnahme, Owner und Frist;
- historischer Scale-Readiness-Snapshot im bestehenden Lifecycle-Review;
- dokumentierte Ausnahme für eine vorzeitige Produktivsetzung;
- Betriebsreviews und Hinweis auf veraltete Nutzenmessungen;
- Abschluss mit Beendigungsgrund, Daten-/Zugangsbehandlung und Lessons Learned.

Der Workspace **„Wirkung & Betrieb“** verdichtet diese Informationen für Review- und Managemententscheidungen. Scale Readiness liegt dort unter **„Ergebnisentscheidung“** unmittelbar vor dem Betrieb; ein erfolgreicher Pilot allein kann den Go-live nicht auslösen. Eine historische Messreihe mehrerer eigenständiger Wirkungsmessungen ist bewusst noch kein Kernbestandteil.

Details: [Outcome Workspace](docs/OUTCOME_WORKSPACE.md) und [Scale Readiness](docs/SCALE_READINESS.md)

### 8. Business & Decision Control Room

Die Oberfläche folgt einem gemeinsamen Business- und Decision-Control-Room-Muster.

- Portfolio- und Listensichten sind Querschnittsansichten ohne künstliche lineare Journey;
- konkrete Arbeitsobjekte zeigen einen kontextuellen Lifecycle;
- pro Zustand gibt es genau eine dominante Next Action;
- Arbeitsstatus, Prüfstatus und Readiness werden getrennt dargestellt;
- große Arbeitsobjekte verwenden wiederverwendbare Workspace- und Formularmuster;
- Desktop, Tablet und Mobile sind Teil des gemeinsamen UI-Vertrags;
- sichtbarer Tastaturfokus, semantische Statusbezeichnungen und zugängliche Interaktionen sind systemweit berücksichtigt.

Der Control Room verändert keine fachlichen Gates, sondern macht deren Bedeutung und nächste Handlung verständlicher.

---

## Beispiel: Automatische Eingangsrechnungsprüfung

Der mitgelieferte Demo-Datensatz zeigt einen reproduzierbaren End-to-End-Fall:

1. Der Value Stream **„Beschaffung bis Zahlung“** wird einer Fachdomäne und Capability zugeordnet.
2. Das Fokus-Screening dokumentiert, warum ein bestimmter Bereich vertieft wird.
3. Die Prozessanalyse macht Ablauf, Systeme, Daten, Bottlenecks und Baseline sichtbar.
4. Organisatorische, regelbasierte und KI-gestützte Lösungsoptionen werden lösungsoffen verglichen.
5. Eine bevorzugte Lösungsrichtung wird nachvollziehbar ausgewählt.
6. Der daraus abgeleitete Use Case wird hinsichtlich Nutzen, Datenreife, Machbarkeit, Risiko und Governance bewertet.
7. Nach der finalen Freigabe entsteht ein versioniertes Delivery Package mit Systemlandschaft, Datenflüssen, MVP-Scope, Anforderungen und Akzeptanzkriterien.
8. Nach verbindlicher Übergabe wird der Pilot explizit gestartet und seine Wirkung gemessen.
9. Scale Readiness bündelt die vorhandenen Nachweise; erst die gespeicherte Ergebnisentscheidung erlaubt den Übergang in Betrieb oder Abschluss.

Damit wird nicht nur ein KI-Use-Case dokumentiert, sondern seine fachliche Herkunft, Diagnose, Lösungswahl, Entscheidungsgrundlage, Umsetzungsreife und spätere Wirkung nachvollziehbar gemacht.

---

## TOGAF-light

KI-Radar nutzt TOGAF ADM als pragmatischen Ordnungsrahmen. Es ist kein vollständiges Enterprise-Architecture-Repository und bildet kein umfassendes TOGAF-Metamodell ab.

| Bereich | Umsetzung in KI-Radar |
| --- | --- |
| Architecture Vision | Scope, Ziel, Stakeholder und Leitplanken |
| Business Architecture | Fachdomäne, Capability, Value Streams, Prozesse, Rollen und Diagnose |
| Information Systems | Anwendungen, Datenobjekte, Datenflüsse und Integrationen |
| Technology Architecture | Technologie-, Hosting- und Plattformbedingungen |
| Opportunities & Solutions | Fokusentscheidung, Lösungsalternativen und Architecture Advisor |
| Migration Planning | Systemlandschaft, MVP, Akzeptanz, Risiken, Backlog und Delivery Package |
| Governance und Change | Bewertungen, Entscheidungen, Versionen, Reviews und Lifecycle |

Der TOGAF-Bezug wird nur dort verwendet, wo tatsächlich entsprechende Architekturartefakte entstehen.

---

## Architekturübersicht

```text
Browser
   │
   ▼
Django Modular Monolith
   ├── Architecture
   ├── Accelerator
   ├── Use Cases
   ├── Governance
   ├── Reviews
   ├── Reporting
   ├── Delivery
   └── Accounts
   │
   ▼
PostgreSQL
```

Optionale externe Systeme:

```text
OpenRouter · Sentry · Jira · Azure DevOps · GitHub · Confluence
```

Grundsätze:

- Analyse und verbindliche Entscheidung verbleiben in KI-Radar.
- Operative Delivery-Steuerung verbleibt in spezialisierten Werkzeugen.
- Verbindliche Prüfungen werden serverseitig ausgeführt.
- LLM-Funktionen sind optional und nicht entscheidungsbefugt.
- KI-Autonomie wird nur dort vorgesehen, wo eine einfachere Architektur nicht ausreicht.
- Das Delivery Package ist eine umsetzungsbezogene Architektur- und Übergabesicht, kein vollständiger Enterprise-Architecture-Katalog.

---

## Datenspeicherung und externe KI-Dienste

Fachliche Eingaben aus der Weboberfläche werden nach erfolgreicher Validierung in PostgreSQL gespeichert. Git und GitHub enthalten Code, Migrationen und Dokumentation, aber nicht automatisch die erfassten Anwendungsdaten.

Ohne konfigurierten API-Key funktionieren die deterministischen Kernfunktionen vollständig. Daten werden nur durch ausdrücklich gestartete LLM-Funktionen an den konfigurierten Provider übertragen, beispielsweise für strukturierte Capture-Analyse, Lösungsentwürfe, Critic oder gezielten Repair. Die fachlichen Schreib- und Entscheidungspfade bleiben auch dann serverseitig kontrolliert.

Details: [Datenspeicherung und Datenfluss](docs/DATA_STORAGE.md)

---

## Zentrale Architekturentscheidungen

Architekturrelevante Entscheidungen werden als Architecture Decision Records dokumentiert. ADRs halten Kontext, Entscheidung und Konsequenzen fest; sie dienen nicht als allgemeines Capability- oder Änderungsinventar.

| ADR | Entscheidung |
| --- | --- |
| [0001](docs/adr/0001-django-monolith.md) | Modularer Django-Monolith |
| [0002](docs/adr/0002-history.md) | Technische Historie und fachliche Entscheidungen getrennt dokumentieren |
| [0003](docs/adr/0003-staging-same-host.md) | Staging als separater Stack auf demselben Host |
| [0004](docs/adr/0004-no-email-reminders.md) | Noch kein produktiver E-Mail-Versand |
| [0005](docs/adr/0005-anonymization-ledger.md) | Restore-feste Anonymisierung über externes Ledger |
| [0006](docs/adr/0006-process-mining-out-of-scope.md) | Process Mining bleibt außerhalb der Produktgrenze |
| [0007](docs/adr/0007-golden-path-review-reuse.md) | Bestehendes Lifecycle-Review für Go-live und Abschluss wiederverwenden |

---

## Rollen

| Rolle | Verantwortung |
| --- | --- |
| Technischer Administrator | Betrieb, Benutzer und Stammdaten |
| KI-Koordinator | Fokus, Analyse, Bewertung, Governance, Freigaben und Delivery-Handover |
| Business Owner | fachliche Verantwortung für Value Streams, Prozesse, Use Cases und Packages |
| Leser | lesender Zugriff auf nicht archivierte Inhalte |

Berechtigungen, Rollentrennung und fachliche Gates werden serverseitig geprüft.

---

## Bewusste Nicht-Ziele

KI-Radar ist kein:

- Projektmanagement- oder Ressourcenplanungssystem;
- BPMN- oder Process-Mining-Werkzeug;
- vollständiges Enterprise-Architecture-Repository;
- automatisches Priorisierungs- oder Budgetoptimierungssystem;
- automatisches AI-Act-Klassifizierungssystem;
- Ersatz für Datenschutz-, Rechts- oder Sicherheitsprüfungen;
- autonomes LLM-Entscheidungssystem;
- Multi-Agent-System als Selbstzweck;
- Multi-Tenant-SaaS.

Der Schwerpunkt liegt auf **fachlich begründeter Auswahl, kontrollierter KI-Unterstützung, belastbarer Entscheidung und strukturierter Übergabe von KI-Vorhaben**.

---

## Technischer Aufbau

- Python 3.13;
- Django 5.2 LTS;
- PostgreSQL;
- serverseitige Django-Templates und Bootstrap;
- modularer Monolith;
- Gunicorn und Nginx;
- Docker Compose für lokale Entwicklung, Staging und Produktion;
- `django-simple-history`;
- optional OpenRouter;
- optional Sentry.

---

## Qualitätssicherung

Die CI prüft unter anderem:

- Lockfile-Konsistenz;
- Ruff Lint und Format;
- Django System Check;
- fehlende Migrationen;
- Unit- und Integrationstests mit PostgreSQL;
- Berechtigungen und serverseitige Hard Gates;
- Security-Prüfung mit Bandit;
- Dependency Audit;
- Docker- und Deployment-Konfigurationen.

Die Regression deckt unter anderem Business Architecture, Prozessanalyse, Accelerator, Architecture Advisor, Critic/Repair, Use-Case-Governance, Portfolio, Delivery Readiness, Lifecycle und Rollen-/Berechtigungsregeln ab.

---

## Reifegrad und Einsatzgrenzen

KI-Radar ist eine funktionsfähige Single-Tenant-Referenzimplementierung für den internen Einsatz in einer Organisation.

Vor einer extern erreichbaren Produktivinstallation müssen abhängig vom konkreten Unternehmen insbesondere SSO/MFA, Domain/TLS, Monitoring, Offsite-Backups, Datenschutz, Aufbewahrung sowie Betriebs- und Lizenzmodell geklärt werden.

---

## Dokumentation

Die Dokumente sind nach ihrem **primären Zweck** getrennt; technische Umsetzungshistorie bleibt in Issues, Pull Requests und Completion-Nachweisen.

### Produkt und Einordnung

- [Produkt-Roadmap](docs/ROADMAP.md)
- [Discovery & Architecture](docs/DISCOVERY_ARCHITECTURE.md)
- [Outcome Workspace](docs/OUTCOME_WORKSPACE.md)

### Methodik und fachliche Referenz

- [Value-Stream-Methodik](docs/VALUE_STREAM_METHODOLOGY.md)
- [Entscheidungsmethodik](docs/DECISION_METHOD.md)
- [Delivery-Methodik](docs/DELIVERY_METHODOLOGY.md)
- [Accelerator-Nachweise](docs/accelerator/)

### Einrichtung und Betrieb

- [Lokales Setup](SETUP.md)
- [Betrieb](docs/OPERATIONS.md)
- [Backup und Restore](docs/BACKUP_RESTORE.md)
- [Monitoring](docs/MONITORING.md)
- [Security](docs/SECURITY.md)

### Technische Referenz und Entscheidungen

- [Basisspezifikation](SPECIFICATION.md)
- [Datenspeicherung und Datenfluss](docs/DATA_STORAGE.md)
- [Architecture Decision Records](docs/adr/)
- [Offene Betriebs- und Konfigurationsentscheidungen](OPEN_QUESTIONS.md)

---

## Schnellstart

Die vollständige lokale Installation, Demo-Daten und der fachliche Testablauf stehen in [SETUP.md](SETUP.md).

---

## Grundprinzip

> KI-Radar bewertet nicht, ob eine Idee modern klingt.  
> Es macht sichtbar, ob ein Vorhaben aus einem relevanten Geschäftsproblem entsteht, diagnostisch verstanden, lösungsoffen bewertet, messbar, technisch angemessen, ausreichend belegt, verantwortbar entscheidbar und für Delivery konkret genug ist.
