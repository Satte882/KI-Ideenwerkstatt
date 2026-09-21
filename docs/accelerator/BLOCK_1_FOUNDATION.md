# Accelerator Block 1: Zielbild, Feldarchitektur und LLM-Betriebsgrenzen

**Issue:** #117  
**Übergeordneter Plan:** #116  
**Repository-Stand der Gap-Analyse:** `632d4396979426145a545a402e7a81d38b13b3f7`  
**Status:** verbindliche Foundation für #118 bis #125

## 1. Zweck und Geltungsbereich

Dieses Dokument konkretisiert Block 1 des autoritativen Accelerator-Gesamtplans. Es definiert gemeinsame Regeln für Entwurfsgrenze, Feldarchitektur, Herkunft, LLM-Betrieb und Messung. Es baut keine Capture Session, keine Extraktionsvorschau und keine Vorschlagsübernahme.

Issue #116 bleibt unverändert. Bei Widersprüchen zwischen älteren Repository-Dokumenten und der aktuellen Accelerator-Struktur sind #116, #117 und dieses Dokument maßgeblich.

## 2. Gap-Analyse gegen den aktuellen Main-Stand

### 2.1 Bestehende, wiederzuverwendende Bausteine

| Bereich | Repository-Befund | Verbindliche Folgerung |
|---|---|---|
| OpenRouter | `ki_radar/use_cases/copilot.py` besitzt bereits einen ausdrücklich ausgelösten, lesenden OpenRouter-Aufruf mit API-Key-Prüfung, HTTPS-URL-Prüfung, Timeout und gekapselter Fehlerbehandlung. | Kein zweiter Provider-Stack. Der bestehende Pfad wird gehärtet und später klein wiederverwendet. |
| Konfiguration | `config/settings/base.py` führt OpenRouter-Key, Modell, URL, Timeout, App-Name und Site-URL. | Accelerator-Grenzen erhalten ein getrenntes `ACCELERATOR_LLM_*`-Präfix. Provider-Zugangsdaten bleiben `OPENROUTER_*`. |
| Intake | `ki_radar/use_cases/intake.py` und `intake_views.py` bilden einen sechsstufigen Session-Wizard mit bestehenden Formvalidierungen und finaler Persistierung. | Kein paralleler Intake in Block 1. Block 3 prüft Wiederverwendung und persistente Erweiterung. |
| Validierung | Django-Forms prüfen bereits Pflichtfelder, Enums, deutsche Dezimalwerte, Prozentbereiche und die Konsistenz von Baseline, Ziel und Optimierungsrichtung. | Spätere Accelerator-Schreibpfade verwenden Forms oder Domain Services; Regeln werden nicht dupliziert. |
| Herkunft | `ki_radar/architecture/provenance.py`, `ProcessAnalysis.source_snapshot`, `UseCaseOrigin.source_snapshot` und Delivery-`source_manifest` speichern Quellobjekt, Quellfeld, Wert und Änderungsstand. | Dieses explizite Snapshot-Muster wird fortgeführt; keine generische Mapping-Engine. |
| Staleness | `source_differences()` und Delivery-Readiness erkennen Änderungen nach einem Snapshot. | Quellenänderungen führen zu sichtbaren Abweichungen oder Konflikten, nie zu stiller Synchronisation. |
| Historisierung | `UseCase` verwendet `django-simple-history`; fachliche Entscheidungen und Bestätigungen sind eigenständige, teils unveränderliche Datensätze. | Technische Historie ersetzt keine fachliche Bestätigung. Rote Felder bleiben außerhalb der KI-Übernahme. |
| Seiteneffekte | Änderungen an validierungsrelevanten Prozessfeldern erhöhen die Version und setzen eine vorhandene Validierung auf prüfbedürftig. Delivery-Services setzen Reviews bei relevanten Änderungen zurück. | Jede spätere Übernahme muss den regulären Schreibpfad und dessen Seiteneffekte erhalten. |
| Atomarität | Delivery-Erzeugung und Review-Aktionen verwenden `transaction.atomic`; übergebene Delivery-Versionen sind unveränderlich. | Zusammengehörige Entwurfsänderungen müssen atomar sein; übergebene Packages bleiben ausgeschlossen. |
| Logging | Standardlogging ist vorhanden; `SystemJobRun` ist auf technische Hintergrundjobs zugeschnitten. | `SystemJobRun` wird nicht für LLM-Kontingente zweckentfremdet. Block 1 führt kein LLM-Nutzungsmodell ein. |
| Dokumentation | `docs/AI_ACCELERATION_PLAN.md` beschreibt einen älteren Delivery-first-Zuschnitt. | Das Dokument wird als historischer Planungsstand gekennzeichnet; die aktuelle Neun-Block-Struktur wird nicht dort neu entworfen. |

### 2.2 Nicht bestätigte oder korrigierte Planannahmen

- Es fehlt keine vollständige Herkunftsarchitektur; mehrere konkrete Snapshot- und Staleness-Muster existieren bereits.
- Es fehlt keine LLM-Anbindung; vorhanden ist ein schmaler Review-Copilot, jedoch ohne gemeinsame Accelerator-Limits und differenzierte Fehlerklassen.
- Eine allgemeine Budgetabrechnung ist weder vorhanden noch erforderlich. Für Version 1 sind konservative Request-Grenzen maßgeblich.
- Eine belastbare nutzer- oder Capture-bezogene Quota kann vor den persistenten Objekten aus Block 3 und 4 nicht vollständig durchgesetzt werden. Block 1 definiert die Grenzen und härtet die unmittelbar anwendbaren Limits; persistente Zählung folgt mit dem konkreten Nutzungskontext.
- Der bestehende Intake ist nicht die geplante Capture Session. Er ist jedoch ein relevantes UI-, Session- und Validierungsmuster.

### 2.3 Minimale Lösung für Block 1

- ein autoritatives Foundation-Dokument,
- ein explizites Feld- und Quellenmapping,
- eine kleine validierte `ACCELERATOR_LLM_*`-Policy in `ki_radar/core/`,
- Härtung des vorhandenen OpenRouter-Copiloten,
- clientseitiger Schutz gegen versehentliche Doppelklicks,
- eine wiederverwendbare Gap-Analyse-Vorlage,
- fokussierte Tests ohne Datenbankmigration.

## 3. Ziel- und Entwurfsgrenze

### 3.1 Zielzustand

Ein fachlich bekannter neuer Fall ist innerhalb der Messgrenze fertig, wenn der vorab definierte strukturierte Entwurfszustand gespeichert, nachvollziehbar und durch einen Menschen prüfbar ist.

Ein Entwurf darf:

- beschreibende Fakten enthalten,
- strukturierte Werte als geprüfte oder noch zu bestätigende Entwurfswerte enthalten,
- Quellen, Annahmen, Lücken und Konflikte ausweisen,
- reguläre Entwurfsobjekte anlegen.

Ein Entwurf darf nicht automatisch:

- einen Value Stream oder eine Phase fokussieren,
- einen Prozess validieren,
- eine Lösungsoption bevorzugen oder auswählen,
- Governance-Ergebnisse bestätigen,
- eine Bewertung oder Freigabe setzen,
- Delivery-Sektionen bestätigen,
- eine Übergabe, einen Pilotstart oder Go-live auslösen.

### 3.2 Messstart und Messende

**Messstart:** Der Bearbeiter besitzt die vorbereiteten fachlichen Ausgangsinformationen und beginnt die Erfassung im KI-Radar.

**Messende:** Der für den jeweiligen Vergleich vorab definierte strukturierte Entwurfszustand ist gespeichert und prüfbar.

Nicht Teil der aktiven Bearbeitungszeit sind organisatorische Wartezeiten, Terminfindung und die Beschaffung noch unbekannter Fachinformationen. Providerwartezeit wird separat erfasst und nicht mit menschlicher Bearbeitungszeit vermischt.

### 3.3 Vergleichbare Durchläufe

Jeder Vergleich verwendet:

- dieselbe Szenario- und Eingabedatenversion,
- denselben vorab beschriebenen Endzustand,
- dieselben Pflichtfelder und Qualitätsregeln,
- dieselben fachlichen Gates außerhalb der Messgrenze,
- dokumentierte Erfahrung der durchführenden Person.

Für Block 9 gilt als Mindestprotokoll:

1. drei vollständige manuelle Baseline-Durchläufe,
2. drei vollständige Accelerator-Durchläufe mit denselben Szenarien,
3. primär gepaarter Vergleich durch dieselbe eingewiesene Person, um individuelle Bediengeschwindigkeit zu kontrollieren,
4. mindestens ein zusätzlicher Durchlauf durch eine zweite Person, um reine Experten- oder Lerneffekte sichtbar zu machen.

Diese Mindestzahl begründet noch keine statistisch allgemeingültige Produktbehauptung. Sie reicht für einen kontrollierten Golden-Path-Vergleich; weitergehende Aussagen benötigen mehr Fälle und Nutzer.

### 3.4 Messereignis-Format

Die folgenden Felder bilden das gemeinsame protokollierbare Format. Block 1 führt dafür kein Datenbankmodell ein.

| Feld | Bedeutung |
|---|---|
| `run_id` | eindeutige ID des Durchlaufs |
| `mode` | `manual`, `blueprint`, `accelerator` oder `delivery_mapping` |
| `scenario_id` / `scenario_version` | identische fachliche Ausgangslage |
| `target_state_version` | vorab definierter Endzustand |
| `actor_role` / `actor_experience` | Rolle und Erfahrungsniveau, keine unnötigen Personendaten |
| `started_at` / `finished_at` | Zeitrahmen des Durchlaufs |
| `active_entry_seconds` | aktive Eingabezeit |
| `navigation_seconds` | Navigation und Orientierung |
| `review_seconds` | Prüfung vorgeschlagener oder erzeugter Inhalte |
| `correction_seconds` | manuelle Korrekturzeit |
| `provider_wait_seconds` | getrennte LLM-Wartezeit |
| `questions_count` | notwendige Rückfragen |
| `errors_count` / `abort_reason` | Fehler und Abbrüche |
| `accepted_count` / `edited_count` / `rejected_count` | Vorschlagsaktionen |
| `llm_calls` / `input_tokens` / `output_tokens` / `cost` | soweit verfügbar |
| `quality_findings` | Zuordnungs-, Zahlen-, Scope-, Erfindungs- und Lückenfehler |
| `notes` | besondere Bedingungen oder Abweichungen |

## 4. Kanonische Quellen- und Snapshot-Regeln

1. Reguläre Domänenobjekte bleiben fachlich führend. Capture Sessions, Blueprints und Vorschläge sind Arbeits- und Herkunftsschichten.
2. Jede Ableitung nennt explizit Zielobjekt, Zielfeld, Quellobjekt, Quell-ID, Quellfeld und Quellwert.
3. Bei Erzeugung werden Wert und `updated_at` beziehungsweise fachliche Version als Snapshot gespeichert.
4. Spätere Quellenänderungen aktualisieren keinen Entwurf automatisch.
5. Vor jeder Übernahme werden Berechtigung, Ausgangszustand und aktueller Datenbankzustand erneut geprüft.
6. Änderungen laufen über maßgebliche Forms oder Domain Services.
7. Validierungs-, Review-, Readiness- und Historisierungsfolgen bleiben wirksam.
8. Übergebene Delivery-Versionen werden niemals verändert.
9. Fehlende Quellen bleiben Lücken; Mehrdeutigkeit wird als offene Frage oder Konflikt behandelt.
10. Systemverwaltete IDs, Versionen, Zeitstempel, Historienattribute und Erstellerfelder werden nicht vom LLM gesetzt.

## 5. Feld- und Ampelmapping für den Golden Path

### 5.1 Klassifikationsregeln

- **Grün:** beschreibender Inhalt; nach Vorschau, Berechtigung und Konfliktprüfung feldweise übernehmbar.
- **Gelb:** strukturierter, referenzieller oder fachlich abgrenzender Wert; zusätzliche Typ-, Wertebereichs-, Referenz- oder Bestätigungsprüfung erforderlich.
- **Rot:** Entscheidung, Validierung, Bestätigung, Review- oder Lifecycle-Zustand; keine direkte KI-Übernahme.
- **System:** technisch verwaltetes Feld; außerhalb der Vorschlagspipeline.

### 5.2 Value Stream und Phasen

| Ziel | Klasse | Führende oder zulässige Quelle | Maßgeblicher Schreibpfad | Änderungseffekt |
|---|---|---|---|---|
| `ValueStream.name`, `description`, `trigger`, `outcome`, `strategic_objective`, `stakeholders`, `constraints` | Grün | Capture-Antwort oder explizites Blueprint-Feld | `ValueStreamForm` | reguläre Historie/Änderungszeit |
| `ValueStream.scope_in`, `scope_out` | Gelb | getrennte, ausdrücklich zugeordnete Aussagen | `ValueStreamForm` | Scope muss getrennt sichtbar bestätigt werden |
| `ValueStream.business_unit`, `owner` | Gelb | bestehende zulässige Referenz | `ValueStreamForm` und Berechtigungsprüfung | keine freie Namensauflösung |
| `ValueStream.status` | Rot | manuelle fachliche Aktion | bestehender Workflow | keine Accelerator-Setzung |
| `ValueStreamStage.name`, `description`, `actors`, `systems`, `documents`, `pain_points` | Grün | Capture/Blueprint | `ValueStreamStageForm` | Quelle und Snapshot speichern |
| `ValueStreamStage.sequence`, `baseline_metrics` | Gelb | explizite Reihenfolge bzw. strukturierte Interpretation | `ValueStreamStageForm` plus Validierung | Reihenfolge und Metrikinterpretation prüfen |
| IDs, `demo_key`, `created_at`, `updated_at`, `created_by` | System | Anwendung | Modell/Service | nicht vorschlagbar |

### 5.3 Prozessanalyse und Lösungsoptionen

| Ziel | Klasse | Führende oder zulässige Quelle | Maßgeblicher Schreibpfad | Änderungseffekt |
|---|---|---|---|---|
| Beschreibende `ProcessAnalysis`-Felder von Scope-Start/-Ende bis Zielbildprinzipien | Grün, ausgenommen strukturierte Baseline | Capture, Phase oder Blueprint mit Feldquelle | `ProcessAnalysisForm` | relevante Änderungen erhöhen Version; Validierung kann prüfbedürftig werden |
| `ProcessAnalysis.baseline_metrics` | Gelb | Originalaussage plus geprüfte Interpretation | `ProcessAnalysisForm` | Zahlen und Einheit separat prüfen |
| `ProcessAnalysis.status`, `version` | Rot/System | bestehender Workflow | Prozessvalidierungsservice | keine KI-Bestätigung |
| `ProcessValidation.*` | Rot | zuständige Person | `ProcessValidationForm` und View | eigenständige Validierung |
| Beschreibende `SolutionOption`-Felder wie Name, Beschreibung, Nutzen, Datenanforderungen, Auswirkungen, Risiken und Architecture Fit | Grün | Prozessanalyse und ausdrücklich generative Block-7-Vorschläge | `SolutionOptionForm` | Entwurf bleibt unbewertet |
| `option_type`, `feasibility`, `integration_effort` | Gelb | whitelisted Enum-Vorschlag | `SolutionOptionForm` | Typprüfung und Bestätigung |
| `recommendation`, `evaluation_status` | Rot | manuelle Bewertung | bestehende Vergleichs- und Auswahlservices | keine Bevorzugung durch LLM |
| `SolutionSelectionDecision.*` | Rot | berechtigte Entscheidung | `solution_selection.py` | unveränderliche Entscheidung |

### 5.4 Use Case

| Ziel | Klasse | Führende oder zulässige Quelle | Maßgeblicher Schreibpfad | Änderungseffekt |
|---|---|---|---|---|
| `title`, `summary`, `problem_statement`, `affected_process`, `target_users`, `source_systems`, `data_sources`, `interface_description`, `intended_users`, `intended_purpose`, `expected_benefit`, `benefit_category`, `human_oversight`, `support_responsibility` | Grün | Capture, Discovery-Snapshot oder Blueprint | Intake-Forms bzw. `UseCaseForm` | `django-simple-history` und reguläre Validierung |
| `business_unit`, `business_owner`, `coordinator`, `technical_owner` | Gelb | bestehende berechtigte Referenz | Forms und Rollenberechtigung | keine erfundenen Personenreferenzen |
| `solution_type`, `hosting_type`, Review-required-Booleans | Gelb | whitelisted Enum/Boolean mit Originalaussage | Intake-Forms / `UseCaseForm` | Typ- und Konsistenzprüfung |
| Metrikname, Typ, Richtung, Einheit, Baseline, Ziel, Messmethode | Gelb | Originalaussage plus normalisierte Interpretation | `BenefitStepForm` / bestehende Decimal-Validierung | Wertebereich und Richtung müssen passen |
| Ist-Wert, Messdatum und Messnachweis | Gelb, außerhalb Erstentwurf | bestätigte spätere Messung | reguläre Mess-/Editierpfade | keine Vorwegnahme im Accelerator |
| `status`, `decision_status`, Review-completed-Booleans, Pilot-/Go-live-/Abschlussfelder | Rot | fachlicher Workflow | bestehende Services und Gates | keine Accelerator-Setzung |
| ID, `short_id`, Historie, Zeitstempel | System | Anwendung | Modell | nicht vorschlagbar |

### 5.5 Governance, Freigabe und Delivery

Alle Governance-Assessments und -Reviews, Decision Assessments, Approval Decisions, Zweitfreigaben, Delivery-Reviewstatus, fachliche und technische Bestätigungen, Übergabeinformationen und Lifecycle-Entscheidungen sind **Rot**.

Delivery-Freitext kann in Block 8 deterministisch oder begrenzt sprachlich vorbereitet werden. Eine vorgeschlagene Formulierung darf niemals den Sektionsstatus, eine Bestätigung, Readiness oder Übergabe setzen.

## 6. Provider- und Datenflussregeln

### 6.1 Providerpfad

- Version 1 verwendet genau den konfigurierten OpenRouter-Pfad.
- Keine dynamische Providerwahl, kein automatisches Fallback und keine Modell-Orchestrierung.
- Jeder Aufruf erfolgt nur nach ausdrücklicher Benutzeraktion.
- Deterministische Funktionen bleiben ohne API-Key und bei Provider-Ausfall nutzbar.

### 6.2 Datenminimierung

Übertragen werden nur die für den konkreten Zweck benötigten Felder. Interne IDs dürfen zur technischen Zuordnung verwendet werden, soweit erforderlich. Nicht übertragen werden pauschal gesamte Objekte, Historien, Benutzerprofile, Anhänge oder nicht benötigte Fachinhalte.

Block 4, 7 und 8 dokumentieren pro Promptversion die tatsächlich verwendeten Eingabefelder.

### 6.3 Fehler- und Atomaritätsgrenze

- fehlender API-Key, ungültige Konfiguration, zu große Eingabe, Rate Limit, Timeout, Provider-Ausfall, Providerfehler, ungültiges Format und leere Antwort werden getrennt behandelt,
- keine automatische Retry-Schleife,
- ein fehlgeschlagener Aufruf erzeugt keine fachliche Teiländerung,
- vorhandene Capture-Daten und bereits gespeicherte Vorschläge bleiben erhalten,
- Schreibvorgänge erfolgen erst nach erfolgreicher lokaler Validierung und ausdrücklicher Übernahme.

## 7. Konfiguration und Budgetgrenze

### 7.1 Namenskonvention

Providerzugang und Transport bleiben unter `OPENROUTER_*`. Gemeinsame Accelerator-Grenzen verwenden ausschließlich:

- `ACCELERATOR_LLM_TIMEOUT_SECONDS`
- `ACCELERATOR_LLM_MAX_INPUT_CHARS`
- `ACCELERATOR_LLM_MAX_OUTPUT_TOKENS`
- `ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT`
- `ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY`
- `ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY`

### 7.2 Durchsetzung in Block 1

Sofort durchgesetzt werden Timeout, Eingabegröße und Ausgabelimit. Die Request-Grenzen werden validiert und als verbindliche Konfiguration vorbereitet. Ihre persistente nutzer- und kontextbezogene Zählung folgt erst mit den konkreten Capture-/Vorschlagsobjekten in Block 4.

### 7.3 Budgetentscheidung

Version 1 verwendet konservative Request-Grenzen statt eines eigenständigen Euro-Budgets. Gründe:

- Modellpreise können sich unterscheiden,
- verlässliche Kostenmetadaten sind nicht für jeden Aufruf garantiert,
- eine Vorab-Kostenabrechnung würde ein Billing-System erfordern,
- #116 erlaubt ausdrücklich eine konservative Request-Grenze.

Token- und Kostenmetadaten werden, soweit verfügbar, als technische Metadaten erfasst und in Block 9 ausgewertet.

## 8. Logging und Retention

### 8.1 Nicht protokollieren

- API-Keys, Tokens oder Session-Cookies,
- vollständige Prompts,
- vollständige Providerantworten,
- vollständige Capture-Antworten oder vertrauliche Formularinhalte,
- unnötige personenbezogene Daten.

### 8.2 Zulässige technische Metadaten

- Aufrufzweck,
- Provider und Modell,
- interner Zielobjekttyp und interne ID,
- bereinigter Benutzerbezug, soweit für spätere Quota nötig,
- Zeitpunkt und Laufzeit,
- Eingabe- und Ausgabegröße,
- Token- und Kostenwerte, soweit verfügbar,
- Ergebnisstatus und bereinigter Fehlercode.

### 8.3 Retention

| Datenart | Regel |
|---|---|
| API-Key und Secrets | ausschließlich Secret-/Umgebungsverwaltung; nie fachlich speichern |
| vollständiger Prompt und rohe Antwort | standardmäßig nicht persistent speichern |
| aktueller Review-Copilot-Text | nur für die Antwortseite, kein eigener fachlicher Datensatz |
| spätere strukturierte Vorschläge | zusammen mit Capture-/Vorschlagskontext, bis Übernahme/Verwerfen plus definierte Ablaufphase |
| inaktive, nicht abgeschlossene Capture Session | Zielregel: Ablauf nach 30 Tagen Inaktivität; Umsetzung in Block 3 |
| Quellen-, Übernahme- und Entscheidungs-Audit | entsprechend dem zugehörigen Fachobjekt und dessen Historie |
| bereinigte technische LLM-Metadaten | Zielregel: 90 Tage, konfigurierbar; Umsetzung mit Nutzungsmodell in Block 4 |
| Messprotokolle des kontrollierten Piloten | bis Abschluss und dokumentierter Bewertung von Block 9; danach organisationsspezifische Löschentscheidung |

Block 1 führt keine allgemeine unternehmensweite Retention Policy und kein Löschframework ein.

## 9. Traceability zu den Abnahmekriterien aus #117

| Abnahmekriterium | Nachweis |
|---|---|
| Gap-Analyse dokumentiert | Abschnitt 2 und PR-Beschreibung |
| Ziel- und Messgrenze eindeutig | Abschnitte 3 und 3.4 |
| Kanonisches Feld-/Quellenmapping vorhanden | Abschnitte 4 und 5 |
| Grün/Gelb/Rot-Klassifikation nachvollziehbar | Abschnitt 5 |
| Provider-, Retention-, Logging-, Timeout- und Budget-/Rate-Limit-Regeln festgelegt | Abschnitte 6 bis 8 sowie `ki_radar/core/llm_policy.py` und Settings |
| Fehlerfälle führen nicht zu fachlichen Teiländerungen | Abschnitt 6.3, gehärteter Copilot und Tests |
| Lösung bleibt repo-spezifisch und schlank | Abschnitt 2.3 und Nicht-Ziele im Arbeitsplan |
| Bestehende Gates und Rollen bleiben unverändert | Abschnitte 3.1 und 5.5 sowie Regressionstests |

## 10. Verbindliche Übergabe an die Folgeblöcke

- #118 verwendet dieses Feldmapping als Grenze für Blueprint Version 1.
- #119 verwendet dieselben Feldbezeichner, führt Capture jedoch nicht als führende Quelle ein.
- #120 verwendet die Policy, Whitelists und Fehlergrenzen für strukturierte Extraktion.
- #121 übernimmt ausschließlich freigegebene grüne Felder und prüft Snapshots erneut.
- #122 behandelt gelbe Felder und Entwurfsobjekte über reguläre Validierung.
- #123 erzeugt Lösungsoptionen als unbewertete Kandidaten.
- #124 nutzt bestehende Delivery-Quellenmanifest- und Staleness-Mechanismen.
- #125 führt Rollen-Defaults und die kontrollierte Abschlussmessung aus.

Jeder Block beginnt erneut mit einer Gap-Analyse gegen den dann aktuellen `main`-Stand.