# Issue #331 – Gap-Analyse

**Issue:** #331 – Fokuswahl & Lösungsentscheidung: Evidenzstatus, Time-to-Value und No-AI-Ausgang  
**Baseline:** `main` @ `9576cb925abd610ad40bbf1d00bcaec9c75f8263`  
**Datum:** 22.08.2026  
**Status:** historischer Analyse-Nachweis; umgesetzt über PR #334

## Ziel der Analyse

Vor der Implementierung wurde geprüft, welche bestehenden Mechanismen wiederverwendet werden können und wo tatsächlich eine Restlücke besteht. #331 durfte weder eine zweite Evidence-/Validation-Engine noch einen neuen Portfolio-Scorer oder einen parallelen No-AI-Workflow erzeugen.

## Gap-Matrix

| Capability | Bestehender Mechanismus | Nachgewiesene Restlücke | Entscheidung |
|---|---|---|---|
| Fokusphase | `StageFocusDecision`, `StageFocusForm`, `criteria_snapshot`, Rationale, Kurzpfad | Stage-Vergleich kannte Impact, Problemintensität, Datenzugang und Veränderungsaufwand, aber kein Verbesserungspotenzial, kein Time-to-Value und keine explizite Evidenzbasis | **EXTEND** bestehende Snapshot-Semantik; kein neues Focus-Modell |
| Value-Stream-Fokus | `ValueStreamFocus` | vorgelagerte Screening-/Auswahlentscheidung bereits vorhanden | **REUSE**, keine parallele Fokuslogik |
| Provenance | `build_process_source_snapshot()` / `source_differences()` | Herkunft und Drift vorhanden, aber keine eigene Belastbarkeitsklassifikation | **REUSE** |
| ProcessValidation | `ProcessValidation`, `process_version`, `VALIDATED/REVIEW_REQUIRED` | Validierung processweit; bestehende `cause_hypotheses` und `confirmed_causes` liefern bereits persistente semantische Trennung | **REUSE + Projektion**, keine zweite Evidence-Engine |
| Findings | `process_findings.py` | belastbare Zustände sollten aus persistenten Feldern und Validation eindeutig dargestellt werden | **EXTEND** Darstellung/Projektion, keine neue Finding-Persistenz |
| Lösungsoption | `SolutionOption` mit organisatorischen, regelbasierten, Standardsoftware-, Custom-, Analytics/ML-, GenAI-, Assistant-, No-Tech- und Other-Typen | kein TTV; kein expliziter Hybridtyp; Custom/Other wurden im KI-Pfad zu breit klassifiziert | **EXTEND/FIX** bestehendes Modell |
| Lösungsentscheidung | immutable `SolutionSelectionDecision` mit Vergleichs-, Prozess- und Diagnose-Snapshot | neue TTV-/Evidenz-/AI-Komponenten-Dimensionen fehlten | **EXTEND Snapshot**, kein neues Decision-Modell |
| No-AI | bestehende View-/Journey-Branches | AI-Klassifikation zu breit; bevorzugte Non-AI-Lösung musste als erfolgreicher Abschluss statt implizite Use-Case-Next-Action erscheinen | **FIX/EXTEND**, kein neuer No-AI-Datensatz |
| Neubewertung | immutable Decision-History, `PROTECT`, bestehende Lifecycle-/Retirement-Logik | kein Nachweis für neuen Lifecycle-Mechanismus | **REUSE + Regressionstest**, keine automatischen Deletes/Resets |
| Architecture Advisor | vorhandene Architecture-Assessments | keine #331-spezifische Architekturlücke | **REUSE** |
| Delivery/Handover | bestehende Evidence-/Mapping-/Export-Mechanismen | liegt downstream eines tatsächlich angelegten Use Cases | **REGRESSION ONLY**, kein #331-Handover-Ausbau |
| Navigation | Journey, `analysis_navigation.py`, Templates | Non-AI-Entscheidung musste als gültiger Abschluss sichtbar werden | **EXTEND** |
| Tests | bestehende Fokus-, Validation-, Solution-, Journey-, Retirement- und Delivery-Tests | kein integrierter Vertrag für TTV, Evidenz, Hybrid und No-AI | **NEW fokussierte #331-Tests** plus minimale Vertragsanpassungen |

## Kleinste belastbare Lösung

1. **Fokus:** `improvement_potential`, `time_to_value` und Evidenzbasis im bereits persistierten `criteria_snapshot` ergänzen; `change_effort` bleibt separat bestehen.
2. **Evidenz:** bestehende strukturierte Felder, `ProcessValidation`, Provenance sowie Version/Stale-Logik als kanonische Quellen verwenden; keine neue allgemeine Evidence-Persistenz.
3. **Lösungsoption:** `SolutionOption` minimal um TTV, Evidenzbasis, Hybridtyp und explizite KI-Komponenten-Semantik ergänzen. Legacy-Werte nicht erfinden.
4. **Entscheidung:** vorhandene immutable History weiterverwenden und die neuen Vergleichsdimensionen in den Snapshot aufnehmen.
5. **No-AI:** aus bevorzugter Lösung und KI-Komponente ableiten. Eine Preferred Non-AI-Lösung beendet Discovery erfolgreich und zeigt keine verpflichtende Use-Case-Anlage.
6. **Neubewertung:** ein neuer Entscheidungsstand ergänzt die History; vorhandene Use Cases oder Delivery-Artefakte werden nicht automatisch verändert.

## Verworfene Alternativen

- neues allgemeines `EvidenceStatus`-Domainmodell beziehungsweise zweite Evidence Engine → **verworfen**, weil `ProcessValidation` und Provenance bereits kanonische Mechanismen besitzen;
- eigener `NoAIOutcome`-Datensatz → **verworfen**, weil der Zustand aus auditierter Preferred Solution und KI-Komponente reproduzierbar ist;
- gewichtete TTV-/Portfolio-Score-Engine → **verworfen**, weil TTV ein sichtbarer Trade-off und keine automatische Rangfolge sein soll;
- starre Kaskade `Standardisierung → Automation → KI` → **verworfen**, weil die Lösung technologieoffen und kombinierbar bleiben muss;
- Ausbau von Retirement oder Delivery → **verworfen**, weil #331 dort nur bestehende Invarianten regressionsseitig schützen sollte.

## Schemaentscheidung

Eine kleine Schemaänderung an `SolutionOption` war erforderlich, weil TTV, Evidenzbasis und die explizite KI-Komponenten-Semantik dort nicht belastbar aus bestehenden Feldern ableitbar waren. Für Fokus und Prozess-Evidenz wurde keine neue Tabelle beziehungsweise Engine eingeführt.

## Ergebnis

Die Gap-Analyse wurde vor dem ersten Implementierungscommit dokumentiert. Die daraus abgeleitete reuse-first Lösung wurde anschließend in PR #334 umgesetzt.
