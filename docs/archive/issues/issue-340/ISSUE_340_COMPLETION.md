# Issue #340 – Completion

**Issue:** #340 – Guided Intake: unbekannte Baseline/Zielwerte bis zur Bewertung zulassen  
**PR:** #341 – `fix: unbekannte Intake-Metriken bis zur Bewertung zulassen (#340)`  
**Merge-Commit:** `d75b9a46899b5ba32fe00e2e5111784b36da955a`  
**Abgeschlossen:** 22.08.2026

## Ergebnis

#340 schließt die beim neutralisierten #310-Runbook nachgewiesene Inkonsistenz zwischen hypothesenfähiger früher Discovery und dem bisherigen Zwang zu numerischen Baseline-/Zielwerten im Guided Intake.

Umgesetzt wurden:

- `metric_baseline` und `metric_target` sind im Guided Intake optional;
- unbekannte Werte werden als `NULL` persistiert, nicht als künstliche Platzhalterzahl;
- Erfolgsmetrik, Typ, Richtung, Einheit und Messmethode bleiben weiterhin Intake-Pflicht;
- vorhandene Prozentwerte werden auch dann validiert, wenn der jeweils andere Messwert noch unbekannt ist;
- ein Use Case ohne Baseline/Zielwert kann regulär bis zur strukturierten Bewertung aufgenommen werden;
- positive Freigaben bleiben ohne Baseline/Zielwert serverseitig blockiert;
- negative finale Entscheidungen bleiben bei ansonsten vollständiger Aufnahme möglich;
- bestehende Pilot- und Go-live-Metrikgates bleiben unverändert.

## Bewusst nicht geändert

- keine Änderung an Diagnose-Readiness oder `confirmed_causes` aus #318;
- keine neue Metric-Maturity- oder Evidence-Engine;
- keine Datenmigration;
- keine automatische Baseline-/Zielwert-Ermittlung;
- keine Demo-Sonderlogik;
- keine Lockerung der Messanforderungen für positive Freigabe, Pilot oder Go-live.

## Bezug zu #310

Der Reiseveranstalter-Demo-Case kann damit ohne erfundene Messwerte bis zur Bewertung geführt werden. Baseline und Zielwert bleiben im Demo-Intake leer und werden erst dann ergänzt, wenn belastbare Werte vorliegen.

Der separate Diagnose-Readiness-Widerspruch wurde nicht durch einen Produkt-Bypass gelöst. #310 definiert stattdessen einen ausdrücklich synthetischen Szenariofakt als bestätigte Ursache innerhalb des fiktiven Demo-Kontexts; `ProcessValidation` und reale Evidenz werden weiterhin nicht fingiert.

## Tests und CI

Der PR-Head `4b16ef202692bde729d202fda0289752417de871` bestand CI #1574 vollständig.

Grün waren:

- Lockfile-Prüfung und Dependency-Installation;
- Ruff lint und format;
- Django System Check;
- Migrationsprüfung und Migrationen;
- Architecture Real-DEMO E2E;
- vollständige Testsuite;
- Bandit;
- Dependency Audit;
- Local-, Production- und Staging-Compose-Validierung;
- Production- und Development-Image-Build.

Die #340-Regressionstests decken insbesondere ab:

- Intake mit unbekannter Baseline und unbekanntem Zielwert;
- Persistenz als `NULL`;
- weiterhin aktive Prozentvalidierung vorhandener Einzelwerte;
- positive Freigabe-Blocker für fehlende Baseline/Zielwert;
- negative Entscheidung ohne künstlichen Metrikblocker;
- unveränderte Pilot-Metrik-Hard-Gates.

## CI-Regel

CI #1574 lief in einem Durchgang vollständig grün. Es war kein Fix-Zyklus erforderlich.

## Folgepflege

#310 bleibt der aktuelle lokale Abnahmefokus. Erst nach dem tatsächlichen manuellen UI-Durchlauf wird auf #320 weitergeschaltet.
