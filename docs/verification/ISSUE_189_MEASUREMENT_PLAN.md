# #189 – Vorab-Messabsicht und historischer Wirkungsabgleich

## Auftrag, Basis und Schutzgrenze

26.10.2026, Basis `main` / `2b5a2d4` einschließlich #185, #188, #186 und #187.
Grundlage: vollständige Issues #183 und #185–#189, historischer Audit auf
`abbfb302`, ADR 0009, tatsächliche Services/Views und die ausdrücklich angenommene
Phase-0-Variante B aus dem Analysechat. Der aktuelle Auftrag autorisiert deren
Umsetzung, Regressionen, CI und Draft-PR. Historische Auditdateien bleiben unverändert.

Das strategische globale Bindungsgate wird **nicht** verändert. Parent #183 und
Menschentest #161 werden durch diesen Nachweis nicht abgeschlossen. Alle Beispiele
und Zahlen sind deterministische synthetische Testdaten, keine Unternehmensmessung.
Keine realen Modellaufrufe, Produktivdatenänderungen oder automatischen Merges.

## Minimaler Vertrag

`ImprovementInitiative.evaluation_criteria` bleibt der einzige führende Geschäftskriterien-
text. Vier optionale Business-Planfelder ergänzen Methode, Zeitraum, Population und
Referenz-/Vergleichsverfahren. `measurement_unknowns` hält offene Angaben mit Grund
und vorgesehenem Klärungspunkt; unbekannt ist kein Nullwert. Eine gemessene Baseline
wird weder beim Intake noch beim Pilotstart neu verlangt. Ein absolutes Ziel kann ohne
Vorher-Wert beurteilt werden; Verbesserung verlangt eine geeignete Vergleichsreferenz.
Die fachliche Eignung der Angaben bleibt menschliche Verantwortung.

Vor **neuer** bindender Auswahl oder positiver direkter KI-Freigabe wird die vorhandene
Outcome-Snapshot-Erzeugung um die dokumentierte Messabsicht erweitert. Entweder sind
die vier Planbestandteile angegeben oder offene Angaben werden ausdrücklich begründet.
Dieselbe berechtigte Auswahl-/Freigabeperson übernimmt den zuvor fachlich bestätigten
Vorhabensstand; vorhandene Rechte, Rollentrennung und atomare Services bleiben zuständig.
Leere frühe Entwürfe bleiben zulässig. Es gibt keinen separaten Planfreigabe-Dialog.

Snapshots enthalten die Planfelder, ihren Zustand `documented/open` und den vorhandenen
Vorhaben-Historienbezug. Positive direkte Freigaben referenzieren zusätzlich den damaligen
Use-Case-Historienstand als Prozessmetrik-Definitionsbezug. Die Werte werden nicht in ein
zweites Metrikmodell kopiert. Die Non-KI-Auswahl ist der vorhandene Entscheidungsanker
für externe Umsetzung; Diagnose-/Vergleichssnapshot und Prozesshistorie bleiben erhalten.
Es gibt keinen künstlichen Non-KI-Pilot oder weiteren Delivery-Lifecycle.

Wesentliche spätere Messplan-/Kriterienänderungen benötigen einen dokumentierten Grund;
Person und Zeitpunkt entstehen aus der vorhandenen Historie. Der Grund steht als Feld
in derselben Historie. Eine Änderung wird nicht zurückdatiert. Eine Ergänzung vor Beginn
kann anhand der datierten Historie fachlich geprüft werden; sie ersetzt den ursprünglichen
Entscheidungsmaßstab nicht. Gerade für externe Non-KI-Umsetzung gibt es keinen strukturierten
Startbeleg: Ohne zusätzliche datierte Evidenz ist keine sichere Ex-ante-Zuordnung behauptet.

## Drei unterscheidbare Stände im Review

1. **Ursprünglicher Entscheidungsmaßstab:** früheste bindende Auswahl derselben Option
   bzw. beim direkten KI-Fall früheste finalisierte positive Freigabe. Eine spätere
   Neuauswahl/Freigabe ersetzt diesen Anker nicht. Bei KI-Herkunft bleibt die ursprüngliche
   Prozessauswahl führend; die unabhängige Freigabe bleibt zusätzlich erhalten.
2. **Beim Review aktueller Stand:** Vorhabenfelder und historischer Vorhabensbezug werden
   beim ausdrücklichen Prüfabschluss gesichert. Spätere heutige Angaben sind davon über
   die weiterhin sichtbare Vorhaben-/Reviewhistorie unterscheidbar.
3. **Ex-post-Befund:** bestehende Geschäftsmessung und Evidenz, KI-Originalmetrik über
   `metric_history_id`, ggf. abgegrenzter organisatorischer Messstand, unabhängige Attribution
   sowie neuer ausdrücklicher Kriterienabgleich mit zeitlicher Einordnung und Abweichungen.

`confirmed/refuted` brauchen weiterhin Geschäftsmessstand und Nachweis, bei KI die
inhaltliche Abgrenzung zur Prozessmetrik, zusätzlich Kriterienabgleich und zeitliche
Einordnung. Ein belegter vollständiger ursprünglicher Plan ist Voraussetzung für die
Einordnung `original`. Bei späteren Kriterien-/Planabweichungen muss deren Grenze erklärt
werden. Fehlt dieser Vorab-Beleg, bleibt eine ausdrücklich `retrospective` eingeordnete
Bewertung mit Zeitpunkt, Grund und Evidenzgrenzen möglich. Sie heißt nicht Erfüllung einer
ursprünglichen Vereinbarung. Nicht belastbar beurteilbare Geschäftswirkung darf begründet
`unclear` bleiben. Ein Prozessziel und ein Kriterienfreitext allein bestätigen nichts.
Attribution bleibt getrennt: Auch bestätigtes Geschäftsergebnis kann Attribution `unclear`
haben. Das System prüft Vollständigkeit/Herkunft, nicht semantische Wahrheit oder Kausalität.

## Aktualität, Bestand und Schreibkonflikte

Die neuen Planfelder sind Teil derselben `OUTCOME_FIELDS/MATERIAL_FIELDS` aus #186.
Wesentliche Änderungen verlangen erneute fachliche Bestätigung und machen betroffene
Auswahlen, neue positive Freigaben und Reviews prüfbedürftig. Die neuen Review-Inhalte und
der serverseitige Kriterien-Snapshot werden im bestehenden historischen Inhaltsvergleich
berücksichtigt. Titel/Termin bleiben bei unverändertem Inhalt unschädlich. Technische
Revision, `expected_revision`, Sperren und atomare Schreibpfade bleiben erhalten.

Additive Migrationen ergänzen ausschließlich leere Text-/JSON-Felder an aktuellem Modell
und Historie. Kein Messwert, Kriterienbeleg, Entscheider oder Zeitpunkt wird rückwirkend
erfunden. Alte Snapshots ohne Plan bleiben unverändert und lesbar; fehlende Inhalte werden
bei der bestehenden Aktualitätsprüfung nicht allein wegen des ergänzten Schemas für stale
erklärt. Neue bindende Entscheidungen verlangen Messabsicht oder begründete Unknowns.
Neue belastbare Wirkungsaussagen unter dem Outcome-Vertrag benötigen den expliziten
Kriterienabgleich, bei fehlendem ursprünglichem Plan mit nachträglicher Einordnung.
Legacy-Interventionen ohne Outcome-Vertrag behalten ihre bisherigen Regeln. Bereits
historisch abgeschlossene Reviews werden durch die Migration nicht pauschal entwertet.

## Delivery, Skalierung und mehrere Beiträge

Das bestehende Delivery-Entscheidungsbild und der echte Wirkungs-/Entscheidungsworkspace
zeigen aktuellen Outcome, Beitrag, Messabsicht, ursprünglichen Entscheidungsbezug und
Wirkungs-/Attributionsstand. Native Disclosures halten Details erreichbar. Die reale
`lean_views`-Übergabe sichert diesen Kontext am vorhandenen unveränderlichen Package;
der ältere strengere Kompatibilitätsservice nutzt denselben Context-Builder. Beim bestehenden
Pilot-Folgeentscheid wird er im Scale-Snapshot (Schema 3) mitgesichert und ist historisch
sichtbar. Alte Packages/Snapshots behalten leeren Zusatzkontext. Kein zusätzlicher Gate,
kein Pflichtdialog und keine automatische Rückstufung laufender Piloten.

Der gemeinsame OneToOne-Review referenziert weiterhin **eine Auswahl und einen Use Case**.
Ein optionaler Abgrenzungstext benennt weitere Beiträge, Wechselwirkungen und nicht
isoliert gemessene Teile. Die Grenze ist sichtbar; kein vollständiges strukturiertes
Mehrprozessmodell, keine Messreihe und keine automatische ROI-Addition. #187 bleibt
zuständig für die bereits implementierte explizite organisatorische Teilwirkung neben KI.

## Integrationsmatrix nach #183

| Fall | Tatsächliche Strecke, Evidenz und Entscheidung | Automatisiert belegt / Grenze |
|---|---|---|
| A: operatives Problem, KI | Synthetisches Einkaufsproblem und eingefrorene Interviewquelle → echte Discovery-Extraktion und Verifikation mit deterministischen Providerantworten → reale Materialisierung ohne vorab vorhandene Optionen → menschlich eingeordnete Diagnoseannahme → Lieferantenformat vereinheitlichen gegenüber assistierter Extraktion → begründete KI-Wahl mit Aufwand/Unsicherheit nach #188 → regulärer Prüfungsbeginn → unabhängige positive Freigabe → Package-Erzeugung und reale Lean-Ready/Handover-Views → Pilot → vorhandene Prozessmetrik, davon getrennte absolute Geschäftszielauswertung und Attribution ungeklärt → reguläre Beendigung mit Scale-/Wirkungskontext. | Technische Kette und synthetisch schlüssiger Hebelvergleich belegt. Discovery nutzt den weiterhin unterstützten eingefrorenen v1-Vertrag, keine vorgefüllte Prozess-/Optionsfixture als Start. Keine reale Modellqualität, wirtschaftliche Überlegenheit oder kausale Rendite nachgewiesen. |
| B: Strategie ohne Ist-Daten, Non-KI | Menschlicher Scope → echte strategische Discovery/Materialisierung → sofortiges GET/POST/Wiederaufnahme des Prozessentwurfs → reguläre Non-KI-Optionsanlage ohne vorgezogene Pfadbestätigung → später bewusster Outcome-/Pfad-/Phasenbezug → Bindungsversuch. Keine Ursache, Baseline oder Screening-Ratings erfunden. | **Teilweise / blockiert:** globale strategische Bindungsentscheidung aus #183 offen. Auswahl, externe Umsetzung, durchgehender Wirkungsreview und Folge-/Abschlussentscheidung dieser B-Kette nicht erreicht. Der erwartete Schutztest ist grün; die vollständige fachliche B-Abnahme ist es nicht. |
| C: direkter KI-Fall | Direkter Use Case ohne Idee/Prozess → bestätigter Business-Messplan → unabhängige positive Freigabe mit historischem Use-Case-Bezug → reale Lean-Übergabe → Pilot ohne Baseline → fehlende Ist-Messung blockiert Go-live → begründet ungeklärte Geschäftswirkung und Attribution → zulässige Beendigung. | Technisch und deterministisch belegt; keine erfundene Wirkung. `refuted` zusätzlich in gezielten Vertragsfällen geprüft, nicht als zweiter vollständiger C-Lifecycle behauptet. |
| Mehrprozessfall | Angebotsvergleich und nachgelagerte Beschaffungsfreigabe als zwei eigene Phasen-/Interventionsbeiträge zum selben synthetischen Geschäftsziel; je eigene Optionen und bindende Entscheidung. Beide bleiben nach zweiter Phasenwahl gültig. Gemeinsamer Review referenziert Vergleich; Freigabebeitrag und Ressourcenwechselwirkung ausdrücklich nicht isoliert gemessen. | Phasen-/Vorhabensschutz und die einzelne strukturierte Reviewreferenz belegt. Keine vollständige strukturierte Gesamtwirkung, keine ROI-Addition, kein zweiter End-to-End-Discovery-/Delivery-Nachweis für beide Beiträge behauptet. |

Zusätzlich RSD-naher synthetischer Servicefall mit Vorab-Plan und ehrlichem `unclear`;
dieser schmale Vertragstest ersetzt die obige Matrix nicht. Non-KI-Vertragsfälle prüfen
`confirmed/refuted/unclear` sowie Prozessmessung ohne künstlichen Use Case. Externe reale
Umsetzung bleibt eine außerhalb dieser deterministischen Tests zu belegende Tätigkeit.

## Verifikation und verbleibende Blocker

`tests/test_issue_189_measurement_plan.py`: 18 zielgerichtete PostgreSQL-Fälle, darunter
nach Ergebniskenntnis geänderte Kriterien, frühester Anker trotz Neuauswahl, fehlender
Vorab-Plan, Unknowns vor neuer Bindung, absolute Ziele ohne Baseline, fehlende Ist-Evidenz,
Metadaten, Materialität, Schreibkonflikt, manipulierte Serverfelder, View-Eingabeerhalt,
A/B/C und zwei Phasen. Der bestehende #187-Migrationstest prüft zusätzlich, dass die
neuen Kriterien-/Planfelder auch an historischen Mess-/Auditzeilen leer bleiben.
Bestehende gezielte #145/#146/#147/#158/#185–#188-, Delivery-, Scale- und Followup-Prüfungen
bleiben erhalten. Geänderte ältere Fixtures benennen ausdrücklich unbekanntes Messdesign
oder nachträgliche Bewertung; sie fingieren keine frühere Vereinbarung.

Vollständige CI bleibt unverändert: Lockfile, Ruff, Django-/Migrationsprüfung, frische
Migrationen, separater Architecture-Real-DEMO-E2E, Gesamtsuite mit Coverage, Bandit,
Abhängigkeitsaudit, alle drei Compose-Konfigurationen und beide Docker-Images.
Konkrete Endzahlen und CI-Link stehen im Draft-PR/Chat. Browserprüfung verwendet nur
die isolierte synthetische PostgreSQL-Datenbank bei 1440×1000.

Offen bleiben strategischer Bindungsvertrag und dadurch vollständige B-Integration,
Menschentest #161, echte Modell-/Nutzerqualität, reale externe Umsetzung, Messgüte und
kausaler Praxisnutzen. Freitext und menschliche Einordnung garantieren keine inhaltliche
Wahrheit. Der konservative ursprüngliche Anker verschmilzt spätere Präzisierungen nicht
mit einer ursprünglichen Vereinbarung; ein vollständiges Interventions-/Messreihenmodell
ist ausdrücklich nicht implementiert.
