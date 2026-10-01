# AP4 Human-Time Runbook

Issue: #107  
Planbasis: `main@2b9a2f87699cbf1f1014463d3061e3d05b77a86c`  
Messvertrag: `docs/planning/AP4_MEASUREMENT_CONTRACT.md`

## Aktueller Status — 2026-10-01

Dieses Runbook beschreibt den eingefrorenen Ablauf der ersten, inzwischen gestoppten Kampagne. AP4-01 bis AP4-03 waren technische Fehlversuche, AP4-04 wurde vom Menschen wegen UX-Findings gestoppt, AP4-05 bis AP4-08 wurden nicht gestartet. Die vier historischen JSON-Records bleiben unverändert; es gibt keinen belastbaren Human-Time-Median und keine belastbare Human-Rework-Quote.

Für den aktuellen technischen Abschlussweg sind beide Zeitmetriken transparent nicht nachgewiesen (Validation Gap); Blind Human Review ist bewusst ausgeschlossen und nicht bestanden. Keine zweite Kampagne wird gestartet. Die folgenden Durchführungsschritte und das historische Gate in §10 sind keine aktuell offene operative Beauftragung. Maßgeblich ist der dokumentierte Abschlussweg in `AP4_ACCEPTANCE_RESULTS.md`; Arbeitsplan und Messvertrag bleiben unverändert.

## Zweck

Dieses Runbook operationalisiert ausschließlich die bereits eingefrorenen AP4-Messgrößen:

- aktive Human Work;
- menschliche Nacharbeit.

Es ändert weder den Arbeitsplan noch den Messvertrag und führt keine neue fachliche Metrik ein.

## 1. Messpopulation

### Aktive Human Work

Gemessen werden **alle acht eingefrorenen AP4-Fälle AP4-01 bis AP4-08** genau einmal mit echter menschlicher Teilnahme auf dem aktuellen Post-Hardening-Produktstand.

Grund:
- der Arbeitsplan verlangt die Messung für die eingefrorene Population;
- Non-AI und WAITING_HUMAN sind ausdrücklich valide positive Ergebnisse;
- ein früher valider Human-Gate-/Non-AI-Endzustand darf nicht künstlich bis Delivery weitergeführt werden.

### Menschliche Nacharbeit

Für die primäre Nacharbeitsmetrik werden ausschließlich die vier bereits eingefrorenen direkten Baseline-Paare verwendet:

- AP4-01
- AP4-02
- AP4-03
- AP4-04

Das entspricht dem bestehenden Measurement Contract. Für AP4-05 bis AP4-08 existiert keine frische manuelle E2E-Referenz und es wird keine neue nachträgliche Vergleichsbasis erfunden.

## 2. Rollen

### Mensch

Nur der Mensch zählt für Human-Time.

Der Mensch:
- liest Problem und bereitgestellte Quellen;
- gibt echte fachliche Eingaben ein;
- navigiert selbst durch die relevanten UI-Schritte;
- trifft erforderliche Authority Decisions;
- prüft den ersten reviewfähigen autonomen Entwurf;
- nimmt fachlich notwendige Korrekturen selbst vor.

### Lokaler Coding-Agent

Der Agent darf:
- Anwendung/Services starten;
- den festgelegten Fall technisch vorbereiten;
- Source Pack und Startzustand verifizieren;
- Messwerte protokollieren;
- Systemwartezeit separat erfassen;
- Browser-/Domain-State nach dem menschlichen Durchlauf sichern;
- Evidence-Dateien vorbereiten.

Der Agent darf **nicht**:
- fachliche Entscheidungen stellvertretend treffen;
- UI-Schritte übernehmen, deren Zeit als Human Work gezählt werden soll;
- menschliche Review-/Korrekturzeit schätzen;
- einen fehlgeschlagenen Messlauf durch einen besseren Lauf ersetzen.

## 3. Zeitdefinitionen

Die vorhandenen Felder des Measurement Contract bleiben unverändert.

### `active_input_seconds`

Aktive menschliche Zeit für:
- Problem-/Quellenaufnahme, soweit sie für eine Eingabe erforderlich ist;
- Eingabe oder fachliche Änderung kanonischer Werte;
- Formulieren echter fachlicher Antworten.

### `navigation_seconds`

Aktive menschliche Bedienzeit:
- relevante Seiten öffnen;
- zwischen erforderlichen fachlichen Schritten wechseln;
- Buttons/Navigation bedienen.

Nicht enthalten:
- Warten auf Provider, Server oder Hintergrundverarbeitung.

### `authority_decision_seconds`

Aktive menschliche Zeit für eine echte bindende Entscheidung, z. B.:
- Scope;
- Solution Selection;
- Zuständigkeit;
- Risiko-/Review-Entscheidung;
- Approval.

Authority-Zeit zählt zur Active Human Work, aber nicht als vermeidbare Rückfrage oder vermeidbare Nacharbeit.

### `post_draft_review_seconds`

Aktive menschliche Zeit ab dem ersten reviewfähigen autonomen Entwurf für dessen fachliche Prüfung.

### `post_draft_correction_seconds`

Aktive menschliche Zeit für fachliche Korrekturen nach dem ersten reviewfähigen autonomen Entwurf.

### `system_wait_seconds`

Provider-/Server-/Agentenwartezeit.

Sie wird real protokolliert, zählt aber **nicht** zur Active Human Work.

## 4. Start und Stopp der Human-Time

Die Human-Time startet mit der ersten echten menschlichen Aktivität am eingefrorenen Ausgangsproblem.

Sie läuft nur während tatsächlicher menschlicher Arbeit und wird während Systemwartezeit pausiert.

### Regulärer AI-/Delivery-Pfad

Ende für die Messung der Active Human Work:

> erster reviewfähiger Decision Package bzw. der erste fachlich reviewfähige autonome Entwurf des korrekten aktuellen Pfads.

### Valider Non-AI- oder WAITING_HUMAN-Pfad

Falls der fachlich korrekte Fall vor einem Decision Package endet, endet die Active-Human-Work-Messung am **ersten reviewfähigen korrekten Human-Gate-/Non-AI-Endzustand**.

Dieser Zustand wird ausdrücklich als solcher dokumentiert und nicht als erzeugtes Decision Package ausgegeben.

Damit werden die laut Plan validen Non-AI-/WAITING_HUMAN-Fälle nicht künstlich in einen fachlich falschen Delivery-Pfad gezwungen.

## 5. Messdurchführung pro Fall

Für AP4-01 bis AP4-08 gilt:

1. eingefrorenes Problem und identisches Source Pack verwenden;
2. neutralen reproduzierbaren Startzustand herstellen;
3. `human_time_measured=true` nur für tatsächlich gemessene menschliche Teilnahme;
4. menschliche Aktivzeit segmentweise erfassen;
5. Systemwartezeit separat erfassen;
6. nur reale menschliche Eingaben/Feldänderungen zählen;
7. echten Endzustand akzeptieren – einschließlich Non-AI und WAITING_HUMAN;
8. keine Wiederholung für ein „besseres“ Zeitergebnis;
9. technischen Abbruch/Providerfehler als solchen dokumentieren, nicht durch Schätzung ersetzen.

## 6. Messreihenfolge

Reihenfolge:

1. AP4-01 – organisatorisch / Non-AI
2. AP4-02 – Rule Automation / Non-AI
3. AP4-03 – Controlled LLM
4. AP4-04 – Workflow / Hybrid
5. AP4-05 – Missing Decision-Critical Evidence
6. AP4-06 – Conflicting Evidence
7. AP4-07 – Governance Relevant
8. AP4-08 – Data / CSV

Die Reihenfolge verhindert eine nachträgliche Auswahl besonders günstiger Fälle.

## 7. Primäre Berechnung

### Active Human Work pro Fall

```text
active_input_seconds
+ navigation_seconds
+ authority_decision_seconds
+ post_draft_review_seconds
+ post_draft_correction_seconds
```

AP4-Ziel:

```text
Median über die acht gemessenen AP4-Fälle ≤ 1.200 Sekunden
```

Der Bericht kann zusätzlich den strengeren 15-Minuten-Wert sichtbar machen, aber der eingefrorene technische Grenzwert bleibt 1.200 Sekunden.

### Menschliche Nacharbeit

Nur AP4-01 bis AP4-04:

```text
Summe post_draft_review_seconds
+ Summe post_draft_correction_seconds
------------------------------------------------
Summe aktive menschliche Arbeitszeit
der vier frischen manuellen E2E-Baselines
```

Ziel:

```text
≤ 20 %
```

Authority Decisions werden nicht als vermeidbare Nacharbeit interpretiert.

## 8. Keine Schätzungen / keine Retrospektive

Nicht zulässig:

- alte scripted Operator-Zeit nachträglich zu Human-Time erklären;
- Browser-/CLI-Laufzeit als menschliche Arbeitszeit übernehmen;
- fehlende Zeitwerte schätzen;
- bestehende scored/post-fix Records überschreiben;
- einen ungünstigen Messlauf durch einen späteren besseren ersetzen.

Die Human-Time-Messung erzeugt eine eigene nachvollziehbare Messdokumentation. Die technische Integration in das finale AP4-Aggregat erfolgt erst nach abgeschlossener Messung, ohne die historische scored Evidence umzuschreiben.

## 9. Pro Fall zu protokollieren

Mindestens:

```text
case_id
measurement_started_at
measurement_finished_at
active_input_seconds
navigation_seconds
authority_decision_seconds
post_draft_review_seconds
post_draft_correction_seconds
system_wait_seconds
human_time_measured = true
manual_fields_changed
post_draft_fields_changed
avoidable_questions
authority_questions
reached_reviewable_state
reviewable_state_type
notes
```

Zusätzlich:
- finaler Browser-State;
- relevanter Domain-State;
- bei Authority Decision die tatsächlich getroffene menschliche Entscheidung;
- technische Abbrüche/Providerfehler, falls vorhanden.

## 10. Gate nach der Messung

Die Human-Time-Runde ist abgeschlossen, wenn:

- alle acht Fälle einmal mit echter menschlicher Teilnahme gemessen wurden oder ein technischer Abbruch transparent als Failure vorliegt;
- keine Zeit geschätzt wurde;
- Active-Human-Work-Median berechnet werden kann;
- für AP4-01 bis AP4-04 die Nacharbeitsquote berechnet werden kann;
- ursprüngliche scored/post-fix Evidence unverändert erhalten bleibt.

Erst danach werden:
1. Human-Time und Nacharbeit in den finalen AP4-Bericht integriert;
2. die entsprechenden Issue-#107-Checkboxen bewertet;
3. Blind Human Review / finaler #1-Gesamtnachweis abgearbeitet.
