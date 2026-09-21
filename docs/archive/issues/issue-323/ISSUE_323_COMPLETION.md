# Issue #323 – Completion

**Issue:** #323 – ProcessAnalysis: SIPOC als sichtbare Leitfrage für Inputs, Quellen und Empfänger ergänzen  
**PR:** #339 – `feat: SIPOC-Leitfrage in ProcessAnalysis sichtbar machen (#323)`  
**Merge-Commit:** `3030ef042a5be8d2fe0a6c5fa2fd1f934c23698a`  
**Abgeschlossen:** 22.08.2026

## Ergebnis

#323 schließt die in #315 nachgewiesenen reinen Methodik-/Help-Text-Lücken der bestehenden `ProcessAnalysis`, ohne ein neues SIPOC-Artefakt oder zusätzliche Persistenz einzuführen.

Umgesetzt wurden:

- ein kompakter sichtbarer SIPOC-Hinweis `Supplier → Input → Process → Output → Customer` innerhalb der bestehenden ProcessAnalysis-Formularkarte;
- die klare Abgrenzung, dass SIPOC nur als Denk- und Scopingrahmen dient und kein separates Artefakt entsteht;
- feldnahe Leitfragen für fachliche Inputs unter **Datenobjekte und Dokumente**;
- feldnahe Leitfrage für den fachlichen Output unter **Ergebnis**;
- Supplier-/Customer-Kontext bei **Übergaben und Schnittstellen**, damit Quelle relevanter Inputs und Empfänger des Ergebnisses ohne Doppelpflege konkretisiert werden können;
- die explizite methodische Abgrenzung, dass `source_snapshot` Provenance übernommener Radar-Inhalte dokumentiert und nicht mit einem fachlichen SIPOC-Supplier gleichzusetzen ist;
- fokussierte Regressionstests für Sichtbarkeit, Leitfragen und die Wiederverwendung bestehender ProcessAnalysis-Felder;
- Synchronisierung von `VALUE_STREAM_METHODOLOGY.md`, `ROADMAP.md` und `planning/EXECUTION_PLAN.md` auf den abgeschlossenen Stand.

## Bewusst nicht gebaut

- kein SIPOC-Modul oder SIPOC-Canvas;
- keine Supplier-/Customer-Entitäten;
- keine neuen Input-/Output-Objektmodelle;
- keine zusätzlichen SIPOC-Pflichtfelder;
- keine Migration;
- keine neue Persistenz;
- keine neue ProcessAnalysis-Journey oder Pflichtstufe;
- keine Änderung an Models, Views oder Provenance-Logik;
- keine Änderung an `ProcessValidation`, Version-/Stale-Mechanismen oder Diagnose-Readiness aus #318;
- keine Änderung an Evidenz-, Time-to-Value-, Hybrid-, No-AI- oder Solution-Selection-Semantik aus #331;
- keine Änderung an `UseCaseOrigin` und Process→Use-Case-Traceability aus #322;
- kein neues CSS- oder UI-Pattern.

## Review des Perplexity-Feedbacks

Das externe Review wurde als Input bewertet und nicht ungeprüft übernommen.

Übernommen wurden die relevanten Punkte:

- Supplier/Customer wird primär bei `handoffs` beziehungsweise **Übergaben und Schnittstellen** verankert;
- der SIPOC-Hinweis bleibt ein kleiner Methodikblock innerhalb der bestehenden ProcessAnalysis-Karte statt einer zweiten Kontext-Karte;
- die bestehende Feld- und Datenstruktur bleibt führend;
- der bestehende Methodik-Testvertrag wurde bei der Versionsanhebung auf 1.2 erhalten.

Nicht wörtlich übernommen wurde der Vorschlag, technische Feldnamen im UI als primäre Nutzerführung auszugeben. Die Oberfläche verwendet stattdessen die vorhandenen fachlichen Feldbezeichnungen.

## CI-Verlauf und Fehlerbehandlung

Die vereinbarte CI-Regel wurde eingehalten: Bei roten Läufen wurde nicht auf Verdacht weitergeändert, sondern der jeweils vollständige verfügbare Laufstatus und der konkrete Log ausgewertet.

- CI #1568 scheiterte früh an einem einzelnen Ruff-RUF001 im neuen Test. Da dieser Fehler alle Folgeprüfungen blockierte, wurde ausschließlich die belegte Assertion korrigiert.
- CI #1569 erreichte die vollständige Testsuite. Dort war genau ein Fehler belegt: `tests/test_issue_308_methodology.py` erwartete Methodik-Version 1.1, während das Dokument bewusst auf 1.2 angehoben worden war.
- Der Diff zeigte zusätzlich eine unbeabsichtigte Verkürzung dieser bestehenden Testdatei. Sie wurde vollständig auf den `main`-Testvertrag zurückgeführt; einzig die notwendige Versions-Assertion `1.1 → 1.2` blieb als Änderung bestehen.
- Der finale PR-Head `2c5c520c808fee2b17991040f7d8ec52b85008a9` bestand CI #1571 vollständig.

## Tests und CI

CI #1571 war vollständig grün. Erfolgreich waren unter anderem:

- Lockfile-Prüfung und Dependency-Installation;
- Ruff lint und format;
- Django System Check;
- Migrationsprüfung (`No changes detected`) und Migrationen;
- Architecture Real-DEMO E2E;
- vollständige Test-Suite mit **1309 Tests**;
- Bandit;
- Dependency Audit;
- Local-, Production- und Staging-Compose-Validierung;
- Production- und Development-Image-Build.

Die #323-spezifischen Regressionstests belegen insbesondere:

- SIPOC ist namentlich sichtbar;
- `Supplier → Input → Process → Output → Customer` wird angezeigt;
- die Leitfragen für Input, Supplier/Quelle, Output und Customer/Empfänger sind sichtbar;
- `data_objects` und `outcome` bleiben bestehende Pflichtfelder;
- `handoffs` bleibt optional;
- es existieren keine neuen Formfelder `supplier`, `input`, `output` oder `customer`.

## Folgepflege

Mit dem Merge ist #323 abgeschlossen und der Execution Plan weist #310 als nächsten aktiven Schritt aus. Die Architektur- und Discovery-Dokumentation musste nicht um eine neue Struktur erweitert werden, da #323 weder Datenmodell noch Journey verändert.
