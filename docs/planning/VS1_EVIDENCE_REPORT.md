# VS1/3 – End-to-End-Nachweis

Issue: #4  
Implementierungs-PR: #8  
Stand: 21.09.2026

## Status

Die technische Nachweisstrecke ist implementiert, der externe Wirksamkeitsnachweis ist
**noch nicht abgeschlossen**.

Insbesondere wurden in diesem Implementierungsschritt noch **keine neun realen
A/B/C-Providerläufe**, kein realer Fixed-vs-Adaptive-Vergleich und kein unabhängiger
verblindeter menschlicher Fachreview durchgeführt. Daraus folgt ausdrücklich:

- keine finale VS1-Abnahme;
- keine 10x-Behauptung;
- keine Aussage, dass Ergebnisqualität bereits mindestens gleichwertig zur manuellen Referenz ist;
- technische Stub-/Regressionstests sind kein Ersatz für reale Providerläufe.

## Vorab festgelegter Vergleich

Die feste Kontrollstrecke ist vor den gewerteten realen Läufen als **vs1-fixed-route-v1** im Code festgelegt.

Sie führt für die kleinen eingefrorenen A/B/C-Packs in fixer Reihenfolge aus:

1. dieselbe vorab definierte Gegenbelegsuche (nicht);
2. vollständiges Lesen aller Manifestquellen des Packs;
3. Profilierung jeder CSV;
4. bis zu drei deterministisch aus den vorhandenen Spalten abgeleitete Gruppenchecks;
5. erst danach Synthese und Verifikation mit demselben Planner-/Verifier-Vertrag wie die adaptive Strecke.

Zusätzliche adaptive Toolwünsche der Kontrollstrecke werden nicht nachträglich erlaubt, sondern als sichtbare Grenze der festen Strecke berichtet.

Für einen gültigen Vergleich müssen gemäß assert_comparable_runs() identisch sein:

- ProcessAnalysis-Version;
- Source-Snapshot und Manifest-Hash;
- Run-Maximalbudgets;
- Modelltransport und Modellalias;
- Planner-Prompt/-Schema;
- Verifier-Prompt/-Schema;
- Toolvertrag;
- persistente Evidence-Campaign und deren autorisierte Revision.

Der Unterschied zwischen den Armen ist damit die Ablaufsteuerung, nicht ein absichtlich schwächeres Modell oder ein älterer Prompt.

## Reale Nachweis-Matrix

Noch nicht ausgeführt:

| Variante | Adaptive reale gewertete Läufe | Feste reale Vergleichsstrecke | Erwarteter fachlicher Prüfpunkt |
| --- | ---: | ---: | --- |
| A | 0 / 3 | 0 / mindestens 1 | Gegenbeleg finden, lesen und Zahlenprüfung für Kurswechsel nutzen |
| B | 0 / 3 | 0 / mindestens 1 | fehlende Bezugsgröße total_eligible → präzise HUMAN_CLARIFICATION, kein READY |
| C | 0 / 3 | 0 / mindestens 1 | andere gestützte Ursache als A → evidenzabhängige andere Empfehlung |

Alle Versuche einschließlich Kalibrierung, Warm-up, Fehler, Retry, Repair und Verifier müssen im selben persistenten Nachweisbudget erfasst werden. Es werden keine zusätzlichen realen Läufe allein zum Erzwingen eines grünen Ergebnisses durchgeführt.

## Gesamtbudget der realen Providerphase

Noch **nicht autorisiert**. Deshalb darf die reale Nachweisphase noch keinen kostenpflichtigen Provideraufruf starten.

Vor dem ersten realen Aufruf muss genau eine gemeinsame Evidence-Campaign für feste und adaptive Strecke angelegt werden mit positiven Gesamtgrenzen für:

- Provideraufrufe;
- Inputtokens;
- Outputtokens;
- optional Kosten, aber nur bei verlässlich versionierter Preisbasis inklusive Währung.

Unbekannte Kosten werden nicht als 0 behandelt. Ohne belastbare Preisbasis sind die harten Aufruf-/Tokenlimits die explizite Gesamtgrenze.

Timeout oder fehlende Usage-Metadaten halten die konservative Reservierung. Ein Neustart oder neuer Run setzt den Verbrauch nicht zurück. Eine Fortsetzung benötigt eine explizite versionierte Autorisierung und übernimmt den bisherigen Verbrauch.

## Automatisierte Nachweise

Automatisierte #4-Tests decken insbesondere ab:

- kein realer Evidence-Run und kein Fixed-Run ohne persistente Gesamtbudget-Campaign;
- atomare Reservierung bei parallelen Provider-Versuchen;
- konservativ gehaltene Reservierung bei unbekanntem Providerverbrauch;
- persistenter Verbrauch nach erneutem Laden aus der Datenbank;
- keine Überschreitung durch einen weiteren Aufruf;
- autorisierte Budgetfortsetzung mit unveränderter Historie und weitergeführtem Verbrauch;
- Variante-B-Datenprofil mit vollständig fehlender Bezugsgröße und HUMAN_CLARIFICATION statt READY;
- gleicher Execution-Contract für feste und adaptive Strecke;
- feste Strecke liest das komplette kleine Pack und führt Datenprüfungen aus;
- menschlich geänderte SolutionOption wird als Konflikt ausgewiesen und nicht überschrieben;
- keine automatische bestätigte Ursache, Preferred-Option oder ProcessValidation;
- sichtbare Quellen-/Budgetautorisierung und Start ohne Einzeldatei- oder Toolauswahl;
- unvollständiger Evidence-Report lässt Wirksamkeits- und 10x-Claims ausdrücklich falsch.

Diese Tests verwenden keine kostenpflichtigen Provideraufrufe.

## Menschlicher Review und Zeitmessung

Noch offen:

- unabhängiger, gegenüber Variante und gewünschtem Ergebnis verblindeter fachlicher Review der real erzeugten Decision Briefs;
- Reviewer-Korrekturen pro Brief;
- aktive menschliche Zeit aus echter Bedienung einschließlich Quellen-/Kontextvorbereitung und fachlicher Korrektur.

Bis diese Messungen vorliegen, bleibt die menschliche Bearbeitungszeit **„noch nicht gemessen“**.

## Abnahmeregel

VS1/3 ist erst extern wirksamkeitsseitig belegt, wenn mindestens:

1. alle neun realen adaptiven A/B/C-Läufe vollständig berichtet sind;
2. der vorab festgelegte reale Fixed-vs-Adaptive-Vergleich vorliegt;
3. Variante B wegen fehlender Evidenz und nicht wegen zu knapper Limits stoppt;
4. der unabhängige fachliche Review keine kritischen offenen Findings enthält;
5. alle Fehlversuche und der gesamte Providerverbrauch im gemeinsamen Budgetbericht enthalten sind.

Issue #1 bleibt unabhängig davon offen, bis dessen vollständige Definition of Done gegen die Baseline gemessen wurde.
