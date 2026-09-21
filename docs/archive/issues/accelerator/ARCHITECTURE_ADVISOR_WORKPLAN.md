# Architecture Advisor – verbindlicher Workplan

Issue: #211  
Parent: #210  
Stand: 2026-08-09  
Startbasis `main`: `9cdcddf47edd29cd6814d9d31747d904c5947a89`

## Ziel und Grenze

Vorhandene `SolutionOption`-Objekte erhalten ein kleines, expert-informed Architecture Assessment mit exakt vier menschlich beantworteten Fragen. Der Architecture Mode und seine Begründungen werden ausschließlich deterministisch abgeleitet.

Die Umsetzung erweitert weder den bestehenden Lösungsvergleich noch Auswahl-, Governance-, Delivery- oder Lifecycle-Gates. Es entsteht keine generische Rules Engine, kein LLM-Klassifikator, kein Score und keine automatische Multi-Agent-Empfehlung.

## Erneute Gap-Analyse zum tatsächlichen Start

Die Gap-Analyse wurde gegen den oben genannten aktuellen `main`-Commit erneut verifiziert.

### Bestehende Domain-Struktur

- `SolutionOption` liegt in der bestehenden App `ki_radar.architecture`.
- Bereits vorhanden und unverändert zu lassen sind insbesondere `feasibility`, `integration_effort`, `integration_impact`, `technology_constraints`, `risks`, `architecture_fit`, `evaluation_status` und `recommendation`.
- `architecture_fit` ist Bestandteil der bestehenden fachlichen Solution-Option-Bewertung und wird nicht zum Speicherort des neuen Architecture Modes umgedeutet.
- `comparison_complete` und der bestehende Solution-Selection-Pfad bleiben vom Advisor unabhängig.
- `SolutionSelectionDecision` ist ein eigener auditierbarer und unveränderlicher Entscheidungsweg; der Advisor setzt oder verändert ihn nicht.
- `UseCaseOrigin`, Governance-, Delivery- und Lifecycle-Pfade bleiben unverändert.

### Bestehende Berechtigungen

Der Advisor verwendet die bestehende Berechtigung zum Bearbeiten der zugehörigen SolutionOption bzw. des Value Streams. Es wird keine neue Advisor-Rolle und keine parallele Berechtigungsmatrix eingeführt.

### Bestehende Audit-Patterns

Die vorhandene Architecture-Audit-Hilfe schützt speziell unveränderliche Lösungsentscheidungen und ist keine generische History-Plattform. Für V1 wird deshalb keine neue Audit-Engine gebaut. Das Assessment speichert Bearbeiter, Zeitstempel, Assessment-Version und Ruleset-Version.

### Roadmap- und Architekturkontext

#210/#211 dokumentieren die ausdrückliche Produktentscheidung für diesen begrenzten Architecture-Advisor-Pfad nach Abschluss des Accelerator-Gesamtpfads. Die Umsetzung bleibt innerhalb des modularen Django-Monolithen und der bestehenden serverseitigen UI.

## Fachlicher Konsistenzvertrag

### Vier Antworten

Jede Frage besitzt genau die Werte `Ja`, `Nein`, `Unklar`:

1. Einfachere Lösung ausreichend?
2. Semantisches Reasoning erforderlich?
3. Mehrere bekannte KI-Schritte erforderlich?
4. Dynamische Orchestrierung erforderlich?

### Kanonische vollständige Fälle

Für vollständig mit Ja/Nein beantwortete Assessments gelten als minimale positive Muster:

- `Ja / Nein / Nein / Nein` → `No LLM required`
- `Nein / Ja / Nein / Nein` → `Controlled LLM`
- `Nein / Ja / Ja / Nein` → `LLM Workflow`
- `Nein / Ja / Nein / Ja` → `Bounded Agent`

Folgende vollständige Muster sind bewusst offen:

- Eine einfachere Lösung wird als ausreichend bestätigt und gleichzeitig wird ein LLM-, KI-Mehrschritt- oder dynamischer Orchestrierungsbedarf behauptet → `Assessment open` / `contradictory_answers`.
- Mehrere fest vorgegebene KI-Schritte und dynamische Orchestrierung werden gleichzeitig als erforderlich bestätigt → `Assessment open` / `contradictory_answers`.
- Eine einfachere Lösung reicht nicht, semantisches Reasoning ist aber ebenfalls nicht erforderlich → `Assessment open` / `architecture_boundary_unclear`. Das Vier-Fragen-Modell deckt andere mögliche technische Klassen wie klassische Optimierung, nicht-generative ML-Verfahren oder andere Nicht-LLM-Architekturen nicht ab.

`No LLM required` darf niemals vergeben werden, wenn Frage 2 mit `Ja` beantwortet ist.

### Symmetrische Behandlung von `Unklar`

`Unklar` führt nicht allein aufgrund seines Vorhandenseins automatisch zu `Assessment open`.

Für jede unbekannte Antwort werden die möglichen vollständigen Ja/Nein-Vervollständigungen betrachtet. Ein `Unklar` ist outcome-irrelevant und darf für die Mode-Entscheidung ignoriert werden, wenn alle zulässigen Vervollständigungen zum selben Architecture Mode führen. Sobald mindestens zwei mögliche Vervollständigungen unterschiedliche Modes ergeben, lautet das Ergebnis `Assessment open` mit `insufficient_information`.

Diese Regel gilt symmetrisch für alle vier Fragen; es gibt keine Sonderbehandlung nur für Frage 1.

Für offene Ergebnisse können mehrere Reason Codes gleichzeitig gelten. Die maschinenlesbare Reihenfolge ist fest:

1. `contradictory_answers`
2. `insufficient_information`
3. `architecture_boundary_unclear`

Diese Reihenfolge ist ausschließlich eine stabile Diagnose-/Darstellungsreihenfolge und keine versteckte Mode-Präzedenz. Widersprüche stehen zuerst, weil explizit unvereinbare Aussagen vor fehlenden Angaben geklärt werden müssen. Fehlende Information folgt als zweites, weil sie eine eindeutige Klassifikation verhindern kann. Die V1-Architekturgrenze steht danach, weil sie einen intern konsistenten, aber von der Taxonomie nicht abgedeckten Fall beschreibt.

### Positive Reason Codes

Auch erfolgreiche Klassifikationen erhalten einen maschinenlesbaren primären Reason Code:

- `simpler_solution_sufficient`
- `controlled_llm_sufficient`
- `fixed_llm_workflow_sufficient`
- `dynamic_orchestration_required`

`Warum dieses Muster?`, `Warum kein Agent?` und offene Punkte werden ausschließlich aus diesen fixierten Codes und Antwortmustern erzeugt.

## Regelmatrix und Drift-Schutz

Die 81 Kombinationen der vier dreistufigen Antworten werden nicht manuell gepflegt.

AP2 implementiert einen kleinen, ausschließlich für den fachlichen Contract verwendeten Generator, der aus den fixierten Präzedenz- und Unklar-Regeln eine reviewbare JSON-Fixture mit allen 81 Kombinationen erzeugt. Die Fixture wird committed und später von den Classifier-Tests als unabhängige Erwartungsbasis verwendet. Der produktive Classifier darf weder den Fixture-Generator noch die Fixture zur Laufzeit importieren.

Ein Drift-Test erzeugt die Matrix erneut und verlangt byte-/strukturidentische Ausgabe zur committed Fixture. Fachliche Regeländerungen müssen dadurch bewusst sowohl Contract als auch Fixture-Version ändern.

## Ruleset-Versionierung

V1 startet mit einer expliziten Ruleset-Version.

Bereits gespeicherte Assessments werden bei einer späteren Ruleset-Änderung niemals automatisch neu klassifiziert oder migriert. Ihr gespeicherter Mode, ihre Reason Codes und ihre Ruleset-Version bleiben unverändert, bis ein Nutzer das Assessment ausdrücklich erneut bearbeitet und speichert.

Das Assessment-Version-Feld dient der fachlichen Nachvollziehbarkeit von Änderungen, nicht als Concurrency-Token.

## Optimistic Locking

Optimistic Locking/CAS ist für #211 V1 ausdrücklich kein Ziel. Gleichzeitige Bearbeitung erhält keine neue Sperr- oder Merge-Logik. Der bestehende serverseitige Schreib- und Berechtigungspfad bleibt maßgeblich; die Assessment-Version wird nicht als Optimistic-Lock-Guard verwendet.

## Persistenzziel

Bevorzugt wird genau ein kleines 1:1-Assessment-Objekt zur `SolutionOption` mit:

- vier menschlichen Antworten;
- abgeleitetem Architecture Mode;
- maschinenlesbaren Reason Codes;
- Ruleset-Version;
- Assessment-Version;
- Bearbeiter;
- Zeitstempeln.

Mode und Reason Codes sind serverseitig abgeleitete Felder und dürfen nicht frei vom Client übernommen werden.

## UI-Ziel

Die vier Fragen und das Ergebnis werden in die bestehende SolutionOption-Oberfläche integriert. Es entsteht keine neue Hauptnavigation und kein großer Wizard.

Sichtbar sind:

- vier Fragen;
- Architecture Mode;
- Warum dieses Muster?;
- Warum kein Agent? bei `Controlled LLM` und `LLM Workflow`;
- offene Punkte bei `Assessment open`.

Die bestehende Vergleichsansicht erhält ausschließlich eine kompakte Architektur-Zeile pro Option. Das Assessment wird nicht Bestandteil von `comparison_complete` und erzeugt kein neues Auswahl-Gate.

Ein separates kurzes UI-Playbook wird in AP2 angelegt. Es enthält ausschließlich Klick- und Prüfschritte für die manuelle UI-Abnahme und keinerlei CI-Anweisungen.

## Arbeitspakete

### AP1 – Gap-Analyse und verbindlicher Workplan

- aktuellen `main`-Stand erneut verifizieren;
- bestehende SolutionOption-, Bewertungs-, Berechtigungs- und Audit-Patterns bestätigen;
- fachliche Leitplanken, Ruleset-Verhalten, Nicht-Ziele und Arbeitsweise festschreiben;
- dieses Dokument als ersten eigenständigen PR mergen.

### AP2 – Konsistenzvertrag, Regelmatrix und UI-Playbook

- vollständige Präzedenz-/Konfliktregeln als ausführbaren Contract festlegen;
- symmetrische `Unklar`-Semantik über Outcome-Invarianz umsetzen;
- 81 Kombinationen programmgesteuert als versionierte JSON-Fixture erzeugen;
- Generator-vs-Fixture-Drift-Test ergänzen;
- Reason-Code-Reihenfolge und positive Reason Codes fixieren;
- separates `ARCHITECTURE_ADVISOR_UI_PLAYBOOK.md` anlegen.

### AP3 – Deterministischer Classifier und Explainability

- reinen, datenbankunabhängigen Classifier implementieren;
- gegen die 81er-Fixture testen;
- `No LLM required`-Invariante für Q2=`Ja` testen;
- deterministische Explainability aus Reason Codes ableiten;
- Golden-/Snapshot-Tests für sichtbare Warum-Texte ergänzen;
- nach Merge: erster Zwischenstatus mit UI-Playbook. Da noch keine UI-Integration existiert, dokumentiert der Status transparent, welche UI-Schritte erst ab AP6 ausführbar sind und welche Ergebnisfälle im Playbook bereits feststehen.

### AP4 – Assessment-Persistenz und Ruleset-Versionierung

- genau ein kleines 1:1-Assessment-Modell ergänzen;
- vier Antworten, abgeleiteten Mode/Reason Codes, Ruleset-Version, Assessment-Version, Bearbeiter und Zeitstempel persistieren;
- Migration ergänzen;
- automatische Re-Klassifikation bestehender Assessments ausschließen;
- keine Optimistic-Locking-Logik einführen.

### AP5 – Serverseitiger Schreibpfad und Berechtigungen

- Create/Update des Assessments serverseitig integrieren;
- vorhandene SolutionOption-/Value-Stream-Berechtigungen wiederverwenden;
- Mode und Reason Codes ausschließlich serverseitig berechnen;
- Manipulations-, Permission- und Versionierungs-Tests ergänzen;
- keine Änderung an Bewertung, Auswahl oder Governance.

### AP6 – Integration in die SolutionOption-Oberfläche

- vor UI-Änderungen `DESIGN.md` vollständig gegen den aktuellen `main` lesen;
- vier Fragen kompakt in die bestehende SolutionOption-Oberfläche integrieren;
- Mode, Warum, Warum kein Agent und offene Punkte sichtbar machen;
- keine neue Hauptnavigation und keinen großen Wizard schaffen;
- UI-Tests für kanonische und offene Fälle ergänzen;
- nach Merge: zweiter Zwischenstatus mit ausführbarem UI-Playbook.

### AP7 – Vergleichsansicht und Gate-/Side-Effect-Invarianz

- kompakte Architecture-Zeile pro Option in der bestehenden Vergleichsansicht ergänzen;
- nachweisen, dass Advisor keine bestehenden SolutionOption-Bewertungsfelder, `comparison_complete`, Empfehlung, Auswahlentscheidung, Process Validation oder Use-Case-Erzeugung verändert;
- direkt angrenzende Governance-/Delivery-/Lifecycle-Side-Effects als Negativregression absichern, ohne #213 vorwegzunehmen.

### AP8 – Matrix-Drift-Schutz, UI-Regression und Abschluss

- vollständige Unit-/UI-/Regression-Suite für #211 konsolidieren;
- 81er-Matrix, Golden-Texte und Ruleset-Version als Drift-Vertrag prüfen;
- bekannte methodische Grenzen dokumentieren;
- vollständige Repository-CI grün nachweisen;
- #211-Checkliste vollständig abhaken und Issue abschließen.

Die breitere Real-DEMO-/adversariale End-to-End-Abnahme von #211 und #212 bleibt Aufgabe von #213.

## Arbeitsweise

- Jedes AP wird einzeln und sequenziell umgesetzt.
- Jedes AP erhält genau einen eigenen Entwicklungs-Commit/PR; kein Sammel-PR am Ende.
- Das nächste AP beginnt erst nach Merge des vorherigen APs und vollständig abgeschlossener Repository-CI.
- Die AP-Titel in #211 müssen exakt den Überschriften dieses Dokuments entsprechen und werden erst nach erfolgreichem Merge und grüner CI abgehakt.
- #210 wird nicht verändert.

### Verbindliche CI-Regel für den Entwicklungsworkflow

Bei einem fehlgeschlagenen CI-Lauf wird nicht unmittelbar ein Fix gepusht. Zuerst wird der komplette Lauf einschließlich aller gestarteten Jobs bis zum Endzustand abgewartet. Danach werden die Fehler aller Jobs ausschließlich anhand der CI-Logs gesammelt. Erst dann werden die bestätigten Ursachen gemeinsam in einem Fix-Commit behoben und ein neuer vollständiger Lauf gestartet.

Ausnahme: Ein Fehler blockiert nachweislich alle Folge-Jobs so, dass deren eigene Fehler nicht sichtbar werden können. Nur dann darf vorher korrigiert werden.

Diese CI-Regel gilt ausschließlich für den Entwicklungs-/Commit-/PR-Workflow. Sie gehört nicht in das UI-Playbook.

## Zwischenstatus und UI-Playbook

Es gibt genau zwei geplante Zwischenstatus:

1. nach AP3: Classifier isoliert vollständig testbar;
2. nach AP6: Integration in die SolutionOption-Oberfläche vollständig nutzbar.

Das separate UI-Playbook enthält nur die manuellen Klick-/Prüfschritte für:

- die vier Fragen;
- Architecture Mode;
- Warum dieses Muster?;
- Warum kein Agent?;
- offene Punkte.

Es enthält keinen CI-Bezug.

## Nicht-Ziele von #211

- Änderung von #210;
- LLM für die Klassifikation;
- Score oder automatische Lösungsauswahl;
- GO/NO-GO;
- Multi-Agent-Empfehlung;
- generische Rules Engine;
- neue Governance-Gates;
- Optimistic Locking/CAS;
- neue allgemeine Audit-/History-Plattform;
- automatische Re-Klassifikation bei Ruleset-Änderungen;
- Vorwegnahme des Critic-/Repair-Workflows aus #212 oder der Real-DEMO-Abnahme aus #213.
