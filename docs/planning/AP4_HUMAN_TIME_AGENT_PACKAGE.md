# AP4 Human-Time – Agent Execution Package

Repository lokal:

`C:\Users\user\Documents\GitHub\KI-Ideenwerkstatt`

Branch:

`feature/issue-107-ap4-evidence`

Verbindliche Grundlage:

- `docs/planning/AP4_HUMAN_TIME_RUNBOOK.md`
- `docs/planning/AP4_MEASUREMENT_CONTRACT.md`
- `tests/fixtures/ap4_case_manifest_v1.json`
- Issue #107

## Rolle des lokalen Coding-Agenten

Du bist **technischer Recorder und Messassistent**, nicht menschliche Fach-Authority.

Du darfst:
- Repository/Branch synchronisieren;
- Anwendung und erforderliche lokale Services starten;
- den jeweils festgelegten AP4-Fall technisch vorbereiten;
- eingefrorenes Source Pack und neutralen Startzustand prüfen;
- Timer/Stopwatch für die einzelnen Zeitsegmente führen;
- Systemwartezeit separat protokollieren;
- nach dem menschlichen Durchlauf Browser-/Domain-State sichern;
- Messdaten in das standardisierte Human-Time-Record-Format übertragen;
- nach Abschluss aller Messfälle eine technische Konsistenzprüfung der Records durchführen.

Du darfst **nicht**:
- fachliche Antworten für den Menschen formulieren oder auswählen;
- Authority Decisions treffen;
- UI-Schritte selbst übernehmen, deren Dauer als Human Work gemessen werden soll;
- alte scripted Operator-Zeit als Human-Time wiederverwenden;
- fehlende Zeitwerte schätzen;
- einen ungünstigen/fehlgeschlagenen Messlauf durch einen besseren Wiederholungslauf ersetzen;
- scored/post-fix Evidence überschreiben;
- Produktcode oder Messvertrag ändern, sofern nicht ein reproduzierbarer Defekt die Messung technisch unmöglich macht.

## Vor Beginn

1. Auf Branch `feature/issue-107-ap4-evidence` wechseln und aktuellen Stand holen.
2. Sicherstellen, dass `docs/planning/AP4_HUMAN_TIME_RUNBOOK.md` unverändert vorliegt.
3. Anwendung/DB starten.
4. Human-Time-Verzeichnis verwenden:

   `artifacts/ap4/human_time/`

5. Pro Fall genau **eine** Record-Datei anlegen:

   `AP4-01-human-time.json` bis `AP4-08-human-time.json`

6. Keine Human-Time-Messung starten, bevor der Mensch ausdrücklich sagt, dass er bereit ist.

## Messreihenfolge

Die Reihenfolge ist fest:

1. AP4-01
2. AP4-02
3. AP4-03
4. AP4-04
5. AP4-05
6. AP4-06
7. AP4-07
8. AP4-08

Kein Überspringen zugunsten eines vermeintlich günstigeren Falls.

## Ablauf je Fall

### Phase 1 – technische Vorbereitung

Der Agent:
- lädt den Fall aus `tests/fixtures/ap4_case_manifest_v1.json`;
- prüft Problemstellung, Source Pack und Dateien;
- stellt einen neutralen reproduzierbaren Startzustand her;
- dokumentiert den technischen Startzustand;
- öffnet/nennt dem Menschen den Startpunkt.

Diese Agentenzeit zählt **nicht** als Human-Time.

### Phase 2 – menschlicher Durchlauf

Ab jetzt bedient ausschließlich der Mensch die fachlich relevanten UI-Schritte.

Der Agent führt nur die Zeitsegmente:

- `active_input_seconds`
- `navigation_seconds`
- `authority_decision_seconds`
- `post_draft_review_seconds`
- `post_draft_correction_seconds`
- `system_wait_seconds`

Regeln:

- Nur tatsächlich aktive menschliche Arbeit zählt in die ersten fünf Felder.
- Während Provider-/Server-/Agentenwartezeit Human-Timer pausieren und `system_wait_seconds` laufen lassen.
- Kurze reine Denkzeit des Menschen innerhalb eines fachlichen Schrittes zählt zur jeweiligen aktiven Human-Zeit.
- Unterbrechungen ohne Bezug zum Fall zählen nicht.
- Wenn der Mensch eine Authority Decision trifft, Zeit separat unter `authority_decision_seconds` erfassen.
- Keine Zeit rückwirkend schätzen.

### Phase 3 – reviewfähiger Zustand

Der Messpunkt für Active Human Work endet beim ersten fachlich korrekten reviewfähigen Zustand:

- regulärer AI-/Delivery-Pfad: erster reviewfähiger autonomer Entwurf / Decision Package;
- valider Non-AI-Pfad: erster reviewfähiger korrekter Non-AI-Endzustand;
- valider WAITING_HUMAN-Pfad: erstes korrektes präzises Human Gate.

Nicht künstlich weiterlaufen lassen, nur um Delivery zu erreichen.

### Phase 4 – Nacharbeit

Nur für AP4-01 bis AP4-04:

- echte menschliche Review-Zeit nach dem ersten reviewfähigen autonomen Entwurf unter `post_draft_review_seconds`;
- echte fachliche Korrekturzeit unter `post_draft_correction_seconds`;
- tatsächlich fachlich geänderte Felder unter `post_draft_fields_changed`.

Für AP4-05 bis AP4-08 wird keine künstliche Nacharbeits-Baseline erzeugt.

### Phase 5 – technische Sicherung

Nach Ende des menschlichen Durchlaufs:

- finalen Browser-State dokumentieren;
- relevanten Domain-State sichern;
- erreichten reviewfähigen Zustand benennen;
- ggf. menschliche Authority Decision wortgetreu in der Record-Datei festhalten;
- technische Fehler/Providerfehler dokumentieren;
- Record gegen das Template prüfen.

## Technischer Abbruch

Bei Provider-/Systemfehler:

- Lauf nicht wiederholen;
- technische Ursache dokumentieren;
- bis dahin gemessene Human-Time real beibehalten;
- `measurement_status = "technical_failure"`;
- keine Schätzung für fehlende Segmente;
- keine Produktänderung ohne reproduzierbaren Produktdefekt.

## Record-Format

Template:

`artifacts/ap4/human_time/TEMPLATE.json`

Jeder Fall erhält daraus eine eigene Datei.

Pflichtwerte nach erfolgreicher Messung:

- `case_id`
- `measurement_status`
- `measurement_started_at`
- `measurement_finished_at`
- alle sechs Zeitfelder
- `human_time_measured = true`
- `manual_fields_changed`
- `post_draft_fields_changed`
- `avoidable_questions`
- `authority_questions`
- `reached_reviewable_state`
- `reviewable_state_type`
- `browser_evidence`
- `domain_evidence`
- `notes`

## Nach jedem Fall

Dem Menschen nur kompakt melden:

- Fall-ID
- erreichter Zustand
- Active Human Work gesamt
- Systemwartezeit
- Authority-Zeit
- Review-/Korrekturzeit
- technischer Status

Noch **keine Gesamtbewertung** nach einzelnen Fällen.

## Nach allen acht Fällen

1. Records auf Vollständigkeit prüfen.
2. Active Human Work je Fall berechnen:

```text
active_input
+ navigation
+ authority_decision
+ post_draft_review
+ post_draft_correction
```

3. Median über AP4-01 bis AP4-08 berechnen.
4. Ziel prüfen: Median ≤ 1.200 s.
5. Nacharbeitsquote nur für AP4-01 bis AP4-04 gegen die bestehenden frischen manuellen Baselines berechnen.
6. Ziel prüfen: ≤ 20 %.
7. Keine bestehenden scored/post-fix Records verändern.
8. `docs/planning/AP4_ACCEPTANCE_RESULTS.md` erst nach abgeschlossener Messung aktualisieren.
9. Issue #107 mit den realen Human-Time-Ergebnissen ergänzen.
10. PR #108 nicht mergen und Issue #107 nicht schließen.

## Abschlussbericht des lokalen Agenten

Nur:

- Active Human Work: 8 Einzelwerte + Median + PASS/FAIL
- Human Rework: AP4-01–04 + Quote + PASS/FAIL
- technische Abbrüche, falls vorhanden
- Authority Decisions: Anzahl
- Evidence-Dateien
- geänderte Dateien/Commit
- verbleibende offene Punkte

Kein zusätzlicher Review, keine neue Hardening-Runde und kein Merge.
