# Block 2: Gap-Analyse zum deterministischen Scenario-Blueprint

**Block / Issue:** Block 2 / #118  
**Geprüfter Branch:** `main`  
**Geprüfter Commit:** `6680257cd57940e6a80f4f189bab49eaaadf9dc9`  
**Prüfdatum:** 2026-08-05  
**Workplan:** `docs/accelerator/BLOCK_2_WORKPLAN.md`

## 1. Ziel und Scope

Nach Block 2 kann ein bekanntes Szenario ohne LLM als konsistenter Entwurfsgraph geprüft und erzeugt werden. Der Graph umfasst minimal:

- einen Value Stream,
- dessen Phasen,
- eine Prozessanalyse,
- mehrere Lösungsoptionen,
- einen Use Case mit Stammdaten und primärer Metrik,
- Rollen- und Organisationseinheitsreferenzen,
- die Herkunftsbeziehung zwischen Discovery und Use Case.

Nicht erzeugt werden Fokusentscheidungen, Prozessvalidierungen, bevorzugte Optionen, Bewertungen, Governance-Entscheidungen, Freigaben, Delivery Packages, Übergaben, Pilot- oder Go-live-Zustände.

## 2. Repository-Evidenz

| Prüfbereich | Geprüfte Dateien und Objekte | Bestätigter Befund |
|---|---|---|
| Zentrale Demo-Ausführung | `ki_radar/core/management/commands/seed_demo_data.py` | Orchestriert Demo-Identitäten, Use Cases, Metriken, Architektur, Golden Path und nachgelagerte Statusänderungen. Nur mit `DEBUG=True` zulässig. |
| Allgemeine Demo-Daten | `ki_radar/core/demo_data.py`, `ki_radar/core/demo_decision_data.py` | Erzeugen und ergänzen Demo-Use-Cases einschließlich fortgeschrittener Status-, Review- und Entscheidungsdaten. Nicht als Blueprint-Vorlage geeignet. |
| Architektur-Demo | `ki_radar/core/demo_architecture_data.py` | Erzeugt Value Streams, Phasen, Prozessanalysen, Lösungsoptionen, Herkunft, Bewertungen, Entscheidungen und Delivery-Daten. Setzt unter anderem `ACTIVE`, `TARGET_DEFINED`, `PREFERRED`, Governance-Vorprüfung und finalisierte Entscheidungen direkt. |
| Supplier Golden Path | `ki_radar/core/golden_path_demo.py` | Ist atomar und nutzt stabile `demo_key`-Werte, setzt aber `REVIEW`, `APPROVED`, `SELECTED`, `PREFERRED`, GovernanceAssessment, ApprovalDecision und DeliveryPackage. Darf deshalb nicht kopiert oder direkt wiederverwendet werden. |
| Real-DEMO-Korrektur | `ki_radar/architecture/management/commands/correct_real_demo_scope.py`, Issue #106 | Liefert bewährte Muster für vollständige Vorabprüfung, Dry Run, Konfliktschutz, `transaction.atomic()`, Vorher-/Nachher-Diff und Audit. Der fachliche Korrekturstand wurde am 2026-08-04 lokal angewendet. |
| Value-Stream-Modell | `ki_radar/architecture/models.py` | `ValueStream.demo_key` ist eindeutig; `status` hat den sicheren Default `DRAFT`. Phasen sind innerhalb eines Value Streams über `sequence` eindeutig. |
| Prozessanalyse | `ki_radar/architecture/models.py`, `ki_radar/architecture/forms.py` | Sicherer Default ist `DRAFT`. `ProcessAnalysisForm` blockiert eine neue direkte Setzung von `VALIDATED`. |
| Lösungsoptionen | `ki_radar/architecture/models.py`, `ki_radar/architecture/forms.py` | Sichere Defaults sind `recommendation=CANDIDATE` und `evaluation_status=DRAFT`. `PREFERRED` wird nicht über das normale Erfassungsformular gesetzt. |
| Use Case | `ki_radar/use_cases/models.py`, `ki_radar/use_cases/forms.py` | `UseCase.demo_key` ist eindeutig; sichere Defaults sind `status=IDEA` und `decision_status=CLARIFICATION`. Das Formular validiert Rollen, Pflichtfelder, Metrikwerte und Metrikrichtung. |
| Klassifikation | `ki_radar/use_cases/classification.py` | `UseCaseForm.save()` transportiert einen Klassifikations-Payload; ein `post_save`-Signal persistiert `UseCaseClassification`. |
| Value-Stream-Fokus | `ki_radar/architecture/focus.py`, `ki_radar/architecture/forms.py` | `ValueStreamForm.save()` transportiert einen Fokus-Payload. Für Block 2 muss der Status zwingend `NOT_SCREENED` bleiben. |
| Herkunft | `ki_radar/architecture/models.py`, `ki_radar/architecture/provenance.py` | `UseCaseOrigin` verbindet Use Case, Phase, Prozessanalyse und optional Lösungsoption; `source_snapshot` kann die bestätigte Herkunftsversion aufnehmen. |
| Technisches Laufprotokoll | `ki_radar/core/models.py` | `SystemJobRun` kann Laufstatus, Zeitpunkte, Details und bereinigte Fehler speichern. Ein neues Auditmodell ist nicht erforderlich. |
| Tests | `tests/test_demo_data.py`, `tests/test_demo_architecture_data.py`, `tests/test_issue_106_real_demo_scope.py`, Architektur-, Intake- und Gate-Tests | Bestehende Tests schützen Demo-Reproduzierbarkeit, Issue-#106-Korrektur, Formularregeln und Gate-Trennung. Block 2 benötigt zusätzliche isolierte Blueprint-Regressionen. |

## 3. Bereits vorhandene Bausteine

Unverändert wiederverwendbar:

- `ValueStreamForm`
- `ValueStreamStageForm`
- `ProcessAnalysisForm`
- `SolutionOptionForm`
- `UseCaseForm`
- `UseCaseOrigin`
- `SystemJobRun`
- `transaction.atomic()`
- eindeutige `demo_key`-Felder von `ValueStream` und `UseCase`
- eindeutige Phasenreihenfolge je Value Stream
- Klassifikations- und Fokus-Signale
- die Konflikt- und Auditmuster aus `correct_real_demo_scope`

Bestehende fachliche Seiteneffekte, die erhalten bleiben müssen:

- Klassifikation wird beim Speichern eines Use Cases über den Form-Payload persistiert.
- Ein Value Stream erhält einen Fokusdatensatz; dessen Status bleibt für Blueprint-Erzeugung `NOT_SCREENED`.
- `UseCase.save()` erzeugt eine neue `short_id`.
- `UseCaseOrigin` kann die Klassifikation aus dem Discovery-Kontext aktualisieren. Da Block 2 keine Fokusentscheidung setzt, muss der explizite Use-Case-Klassifikations-Payload maßgeblich bleiben.

## 4. Direkt gesetzte fortgeschrittene Zustände in vorhandenen Seeds

Die vorhandenen Demo-Seeds setzen unter anderem direkt:

- `ValueStream.Status.ACTIVE`
- `ValueStreamFocus.Status.SELECTED`
- `ProcessAnalysis.Status.TARGET_DEFINED`
- `SolutionOption.Recommendation.PREFERRED`
- `SolutionOption.EvaluationStatus.ASSESSED` in fortgeschrittenen Szenarien
- `UseCase.Status.REVIEW`, `PILOT` oder weitere Lifecycle-Stände
- `UseCase.DecisionStatus.APPROVED` oder andere verbindliche Entscheidungen
- `GovernanceAssessment`
- `DecisionAssessment`
- `ApprovalDecision`
- `DeliveryPackage` einschließlich Ready-/Handover-Zuständen

Diese Bestandteile sind bewusste Test- und Demonstrationsdaten für spätere Workflowstufen. Block 2 darf davon nur fachliche Text- und Strukturwerte als geprüfte Quelle nutzen, niemals die fortgeschrittenen Zustände oder nachgelagerten Objekte.

## 5. Abgleich mit Issue #106

Bestätigter Stand:

- Der einzige vorhandene lokale `[Real-DEMO]`-Value-Stream heißt `[Real-DEMO] Beschaffungsbedarf bis Bestellung`.
- Die Datenkorrektur wurde am 2026-08-04 erfolgreich auf Datensatz `2a0be3c0-6dc3-49af-ae1f-cfd5f09a9565` angewendet.
- `scope_in` und `scope_out` sind danach getrennt gespeichert.
- Der private Audit besitzt SHA-256 `784156d3734c6c8f33474176a7f38114c8db3ff7138871efff6f14f76ad9c794`.
- Es existiert nach dem Abschlussnachweis kein weiterer `[Real-DEMO]`-Value-Stream.

Verbindliche Konsequenz für den Referenz-Blueprint:

- `scope_in` darf keinen eingebetteten Abschnitt „Nicht im Scope“ enthalten.
- `scope_out` muss als eigenes Feld befüllt werden.
- Es wird keine String-Heuristik und keine automatische Textzerlegung eingeführt.
- Der Regressionstest prüft diese Trennung ausdrücklich.

Nicht im Repository verfügbar:

- Die fachlichen Rohwerte des privaten Issue-#106-Audits.
- Ein vollständiger Export des lokalen `[Real-DEMO]`-Graphen.

Deshalb wird Version 1 nicht als unkontrollierter Datenbankexport behandelt. Sie bildet ausschließlich einen explizit im Repository geprüften, minimalen Referenzgraphen ab. Nicht belegte lokale Zusatzfelder werden nicht übernommen.

## 6. Minimale repo-spezifische Lösung

### Unterstützte Objektmenge

Genau:

- 1 Value Stream,
- mindestens 1 Phase,
- genau 1 Prozessanalyse für den Referenzfall,
- mindestens 2 Lösungsoptionen,
- genau 1 Use Case,
- genau 1 Herkunftsbeziehung.

Das Format darf diese Mengen technisch als Listen darstellen, bleibt aber auf den Golden Path und die vorhandenen Modelle begrenzt.

### Stabile Schlüssel

- Blueprint: `scenario_key`
- Value Stream: bestehendes `demo_key`
- Use Case: bestehendes `demo_key`
- Phasen: lokaler Blueprint-Schlüssel plus eindeutige `sequence`
- Prozessanalyse und Lösungsoptionen: lokale Blueprint-Schlüssel innerhalb des Szenarios
- Benutzer: exakter `username`
- Organisationseinheit: exakter, eindeutig geprüfter `name`

### Verhalten für bestehende Daten

- `CREATE`: Kein Objekt des Szenarios vorhanden; gesamter Graph kann erzeugt werden.
- `NO_CHANGE`: Vollständiger Graph vorhanden und alle unterstützten Werte stimmen überein; kein Schreibzugriff.
- `CONFLICT`: Teilgraph, abweichender Wert, unerwartete Beziehung oder mehrdeutige Referenz; gesamter Apply wird abgebrochen.

Es gibt kein Update, Merge, Replace oder partielles Apply.

### Referenzvoraussetzungen

Der Blueprint erzeugt keine Benutzer, Rollen, Gruppen oder Organisationseinheiten. Vor Apply müssen vorhanden sein:

- eine aktive, nicht anonymisierte ausführende Person,
- alle referenzierten aktiven Benutzer,
- die referenzierte aktive Organisationseinheit,
- für rollenbeschränkte Felder die bereits vorhandenen Gruppenmitgliedschaften.

Für Demo-Umgebungen werden diese Voraussetzungen über den bestehenden Demo-Identitäts-/Seed-Pfad hergestellt. Eine fachlich leere Datenbank ohne Referenzobjekte liefert einen verständlichen Validierungsfehler; sie wird nicht stillschweigend ergänzt.

### Atomaritätsgrenze

Die gesamte Szenarioerzeugung liegt in einer einzigen Datenbanktransaktion. Jeder Schema-, Referenz-, Form-, Diff- oder Persistenzfehler verhindert den vollständigen Graphen.

## 7. Nicht bestätigte oder korrigierte Planannahmen

| Annahme | Repository-Befund | Konsequenz |
|---|---|---|
| Der vorhandene Golden-Path-Seed könne direkt wiederverwendet werden. | Er setzt zahlreiche rote Zustände und nachgelagerte Objekte. | Nur Struktur- und Textquellen prüfen; neuer kleiner Entwurfspfad über Forms. |
| Eine vollständig leere Datenbank könne das Szenario allein aus dem Blueprint erzeugen. | Benutzer, Gruppen und Organisationseinheiten liegen außerhalb des Block-2-Schemas und werden von Forms vorausgesetzt. | Reproduzierbarkeit gilt nach Herstellung dokumentierter Referenzvoraussetzungen. |
| Der vollständige aktuelle `[Real-DEMO]`-Graph sei versioniert verfügbar. | Nur Name, Korrekturpfad und Abschlussnachweis aus #106 sind versioniert; Rohwerte liegen privat/lokal. | Version 1 enthält nur explizit belegte und geprüfte Referenzwerte. |
| Ein neues generisches Schlüssel- oder Auditmodell sei nötig. | `demo_key`, lokale Schlüssel, `source_snapshot` und `SystemJobRun` reichen für den Golden Path. | Keine Migration und kein generisches Import-/Audit-Framework. |
| Ein Objektkonflikt könne isoliert übersprungen werden. | Issue #118 fordert Atomarität; Teilgraphen sind unzulässig. | Ein einzelner Konflikt macht den gesamten Apply nicht ausführbar. |

## 8. Risiken und Schutzmaßnahmen

| Risiko | Schutzmaßnahme |
|---|---|
| Fortgeschrittene Seed-Zustände werden versehentlich übernommen. | Positive Feldlisten und technische Verbotsprüfung für rote Zustände. |
| Triviale JSON-Formatierung ändert die Prüfsumme. | Kanonische Serialisierung vor SHA-256. |
| Lokale Änderungen werden überschrieben. | `CONFLICT` statt Update oder Merge. |
| Teilgraph verbleibt nach Fehler. | Vollständige Vorabvalidierung plus eine `transaction.atomic()`-Grenze. |
| Referenzobjekte fehlen oder sind unzulässig. | Vollständige Auflösung und Prüfung vor Apply. |
| Issue-#106-Fehler wird erneut eingefroren. | Expliziter Test für getrennte `scope_in`-/`scope_out`-Werte ohne String-Heuristik. |
| Referenz-Prüfsumme wird still angepasst. | Änderung nur mit Versionswechsel oder fachlich bestätigter Korrektur in eigenem begründetem PR. |
| Blueprint-Datei driftet unbemerkt. | Test der Datei selbst gegen die festgelegte erwartete kanonische Prüfsumme. |

## 9. Abnahmemapping

| Abnahmekriterium aus #118 | Geplante Umsetzung |
|---|---|
| Gap-Analyse dokumentiert | Dieses Dokument / AP 1 |
| Versioniertes Blueprint-Schema | AP 2 und AP 3 |
| Dry Run und verständlicher Diff | AP 5 und AP 9 |
| Atomare und reproduzierbare Erzeugung | AP 4 bis AP 6, AP 10 |
| Definiertes Wiederholungsverhalten | `CREATE`, `NO_CHANGE`, graphweiter `CONFLICT` in AP 5 und AP 6 |
| Keine roten Zustände | Positive Feldlisten, Form-Defaults und Negativtests in AP 2, AP 4, AP 6 und AP 10 |
| `[Real-DEMO]` als Referenz | AP 8 und AP 10 unter Erhalt des #106-Korrekturstands |
| Kleine repo-spezifische Lösung | Keine Migration, DSL, Plugins, Merge-Engine oder Endnutzeroberfläche |

## 10. Entscheidung vor Coding

**Empfohlener Zuschnitt:** Ein kleiner JSON-Blueprint-Interpreter im bestehenden `core`-Bereich, der Forms zur fachlichen Validierung verwendet, einen stabilen Dry Run erzeugt und den vollständigen Graphen atomar anlegt.

**Begründung:** Die vorhandenen Forms, Defaults, Schlüssel, Signale, Herkunftsbeziehungen und das Job-Protokoll decken die notwendigen fachlichen Grenzen bereits ab. Neu benötigt werden nur Formatvertrag, kanonische Prüfsumme, Orchestrierung, Diff und Tests.

**Nicht umgesetzte Alternativen:**

- Kopie oder Refactoring des vollständigen Demo-Seeds,
- allgemeine Importplattform,
- universelle Workflow-DSL,
- generisches Mapping- oder Plugin-System,
- automatische Aktualisierung oder Merge vorhandener Graphen,
- neues Blueprint-, Audit- oder Provenienz-Datenmodell.

**Offene fachliche Entscheidung, die Coding blockiert:** keine.
