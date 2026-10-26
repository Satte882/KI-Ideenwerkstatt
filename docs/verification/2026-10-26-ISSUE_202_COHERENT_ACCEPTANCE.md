# Fachlich kohärente technische Abnahme – #202

Prüfzeitraum: 26.–27.10.2026 (Europe/Berlin). Basis: aktuelles `main`,
`8a1c781` (PR #206, #201). Referenzen: verbindlicher Re-Audit #196,
Parent #197, integrierte Korrekturen #198 bis #201. Historische Auditberichte
bleiben unverändert. Der geprüfte Änderungsstand ist der Head dieses PR;
die vollständige CI ist diesem Commit zugeordnet.

## Aussage und Methode

Dies ist eine manuelle fachliche Durchsicht der synthetischen Testeingaben mit
ausführbaren technischen Integrationsprüfungen. Sie prüft keine wirtschaftliche
Wahrheit automatisch. Feste Providerantworten ersetzen Modellaufrufe. Daten,
Interviewaussagen, Unternehmensvorgänge, Rollen und Messprotokolle sind synthetisch.
Es gibt keine reale Intervention, Unternehmensmessung oder beobachtete Bedienung.
#161 wird weder durchgeführt noch geschlossen. Kein realer ROI wird behauptet.

Vorhaben, Prozess und Lösung werden weiter über die vorhandenen Services geführt.
Die Hilfsfunktion `bind_process` erlaubt ausdrücklich fallbezogene Herkunft,
Potenzial und Prüfschritt. Ihre alten Standardwerte bleiben für Bestandsregressionen
erhalten; die ausgewiesenen neuen Einkauf-/Servicefälle übergeben ihren Kontext.
Es gibt keine neue Produktlogik, Migration, Aggregation oder zusätzliche Freigabe.

## A – problemgetriebene Beschaffung

Ausführbar: `test_a_actual_discovery_to_ai_pilot_and_separate_business_review`
in `tests/test_issue_189_measurement_plan.py`.

- Zielgruppe: Einkauf und entscheidender Fachbereich im begrenzten Test-Einkaufsbereich.
  Outcome Owner: Einkaufsleitung. Ziel: fristgerechte, fachlich belastbare
  Beschaffungsentscheidungen. Beitrag: Angebote vergleichen.
- Discovery wird aus synthetischer Capture-Quelle tatsächlich materialisiert.
  Beobachtung: uneinheitliche Angebotsformate, manueller Vergleich.
  Wirkmechanismus: weniger manuelle Übertragung könnte rechtzeitige Entscheidungen
  ermöglichen. Ursache bleibt eine ausdrücklich bestätigte fachliche Annahme.
- Alternativen: Lieferanten auf gemeinsame Vorlage umstellen oder vorhandene
  Formate assistiert extrahieren. Ersteres verlangt Lieferantenadoption, Schulung
  und laufende Pflege; Letzteres Integration, Betrieb und menschliche Einzelprüfung.
  KI gewinnt für die begrenzte Erprobung, weil bestehende Formate kurzfristig
  erschlossen werden sollen und Lieferantenumstellung unsicher ist. Dies ist eine
  plausible synthetische Abwägung bei unbekannten Beträgen, kein Kostenvorteilsbeweis.
- Reale Vergleichsroute bestätigt Diagnose, speichert Auswahl und führt zum Use Case.
  Eine unabhängige berechtigte Person entscheidet über die echte Freigaberoute.
  Übergabe, Pilotstart und Beendigung laufen über reale Routen.
- Vorab-Kriterien: mindestens 18 von 100 Entscheidungen binnen vier Wochen
  fristgerecht und fachlich geprüft. Absolute Referenz ohne erfundene Vorperiode.
  Separat: Median der Vergleichsdauer, Ziel drei Tage, synthetischer Ist-Wert zwei.
  18/100 belegt im Szenario nur das absolute Geschäftskriterium; Attribution bleibt
  ungeklärt. Freigabe und Lieferfähigkeit sind weitere, nicht isolierte Faktoren.
- Der echte Markdownexport enthält den eingefrorenen Einkaufsbezug. Auswahl und
  Übergabesnapshot bleiben nach späterer Wirkungsprüfung und Abschluss unverändert;
  eine spätere bestätigte Aussage wird nicht in die frühere Übergabe zurückgeschrieben.

## B – strategischer Service, Non-KI und KI

Ausführbar: `test_complete_b_routes_external_non_ai_record_review_and_honest_completion`
und `test_strategic_ai_handoff_routes_retry_screening_and_independent_approval`
in `tests/test_issue_183_strategic_binding.py`.

Zielgruppe ist der Kundenservice für Kundenanfragen; Outcome Owner ist die
Serviceleitung. Ziel sind tragfähige Buchungen bei verlässlicher Betreuung.
Der begrenzte Beitrag klärt Anfragen bis zur verantworteten Antwort. Weniger
Klärarbeit könnte Kapazität schaffen; zusätzlicher Absatz folgt daraus nicht zwingend.
Ist-Ablauf, Ursachen, Baseline und globale Screeningwerte bleiben unbekannt.

Non-KI schafft eine verbindliche Quelle samt Zuständigkeit; Assistenz zeigt Quellen
und Widersprüche, kann deren Autorität aber nicht herstellen. Daher gewinnt im
Non-KI-Fall die organisatorische Regel. Umstellung, Quellenpflege und Schulung kosten
Aufwand; Adoption und Beträge sind offen. Buchungsvolumen und Servicequalität werden
getrennt vom Prozessaufwand beurteilt. Vorperiode und Vergleichbarkeit sind unbekannt.
Ein datierter, gehashter synthetischer externer Umsetzungsbeleg dokumentiert die
Umstellung, keine gemessene Wirkung. Auswahl, Wirkungsreview und ehrlicher Abschluss
mit ungeklärter Wirkung erfolgen über echte Routen; es entsteht kein KI-Use-Case.

Die zusätzliche strategische KI-Fortsetzung aus #198 verwendet denselben
Geschäftskontext, leere Diagnosefelder und bestätigten strategischen Anlass.
Ein begrenzter Quellenanzeigeversuch ist legitim; Betrieb, Prüfung und Kosten
bleiben offen. Wiederholte Fortsetzung erstellt keinen zweiten Use Case.
Nach ergänzt abgeschlossenem Screening verlangt die alte Auswahl neue Prüfung;
eine neue Auswahl und unabhängige Freigabe funktionieren ohne erfundenes Ist-Problem.
Alte Herkunfts- und Auswahlbelege bleiben unverändert.

## C – direkter Vertriebs-Use-Case

Ausführbar: `test_c_direct_ai_missing_baseline_unclear_end` in
`tests/test_issue_189_measurement_plan.py`.

Zielgruppe: Vertrieb mit Rückfragen zu freigegebenen Angeboten. Outcome Owner:
Vertriebsleitung. Weniger Rückfragen könnten wirtschaftliche Buchungen unterstützen.
Messabsicht: Buchungsprotokoll mit fachlicher Wirtschaftlichkeitsprüfung für 100
freigegebene Testangebote über vier Wochen, absolutes Ziel 18 wirtschaftlich tragfähige
Buchungen; Vorperiode, Kosten, Tragfähigkeitsnachweise und Kausalität unbekannt. Der direkte
Pfad behauptet keinen vorgelagerten Alternativenvergleich oder wirtschaftliche
Überlegenheit der KI. Die fachliche Freigabe ist eine begrenzte menschliche Entscheidung.

Die echte Freigaberoute lehnt zuerst ohne Vorhaben/Outcome ab. Bewusste Zuordnung
eines bestätigten Vertriebsbeitrags ermöglicht danach die unabhängige Freigabe.
Übergabe und Pilot sind möglich. Ohne erforderlichen Ist-Messwert wird Go-live
abgelehnt; es wird kein Go-live-Review gespeichert. Ein explizit ungeklärter
Geschäftswirkungsreview und die bewusste Beendigung bleiben möglich. Der originale
Freigabesnapshot bleibt unverändert. Es wird kein Prozess künstlich angelegt.

## Zwei Prozesse, eine begrenzte Reviewreferenz

Ausführbar: `test_multiple_process_contributions_keep_single_review_boundary` in
`tests/test_issue_189_measurement_plan.py`.

Einkauf und Fachbereich verfolgen dasselbe Beschaffungsziel unter Einkaufsleitung.
Erster Beitrag: Angebotsvergleich mit weniger Übertragung. Zweiter Beitrag:
Beschaffungsfreigabe mit klarer Verantwortung und weniger Rückfragen. Eigene
Prozessoutputs, Ursachenannahmen, Alternativen und Aufwände bleiben getrennt.
Beide aktuellen Vergleiche laufen über reale Auswahlrouten. Die organisatorischen
Hebel adressieren Quelle bzw. Verantwortung unmittelbar; Assistenz würde Nachweise
aufbereiten, benötigte aber ebenfalls fachliche Prüfung. Beträge bleiben unbekannt.

Der echte Wirkungsreview referenziert strukturiert nur den ersten Prozess und nennt
den zweiten als weiteren, nicht isoliert gemessenen Beitrag. Die Gesamtwirkung bleibt
ungeklärt; dieselbe Population und gemeinsame Ressourcen erlauben keine ROI-Addition.
Wird anschließend die Ursache des zweiten Prozesses materiell geändert, wird dessen
Auswahl prüfbedürftig. Der nur auf den ersten Prozess bezogene Review bleibt aktuell.
Das ist die dokumentierte Einzelreferenz aus P11, kein Gesamtnutzenbeweis. Beide
historischen Auswahlsnapshots bleiben unverändert.

## Negative Varianten und Regressionen

Die Gesamtabnahme verwendet auch die bereits integrierten spezialisierten Tests:

| Grenze | Ausführbarer Nachweis |
| --- | --- |
| Fehlender Aufwand/Messabsicht; Entwürfe speicherbar | #199: `test_only_effort_missing_has_named_blocker_and_working_correction`, `test_missing_measurement_matches_service_and_is_fixed_in_existing_route`, direkte/strategische Vorbereitung |
| Unzulässige Rolle | #183: `test_selection_permission_unchanged`, `test_selection_does_not_grant_initiative_review_permission`; #201: Export-/Übergaberechte |
| Materielle Änderung gegenüber formaler Korrektur | #200: Kriterien-/Messplanparameter, echte Vorbereitungsroute, bestätigter Abschluss; #146/#186: historische Outcome-Verträge |
| Veralteter Schreibstand | #183: `test_optimistic_process_conflict_preserved`; #189: Messplanänderung; #199: Vorbereitungsrevision |
| Wiederaufnahme | #183: gespeicherte Auswahl nach Handoff-Fehler und zweimalige Fortsetzung; keine Duplikate |
| Legacy | #146: positive Altfreigabe; #183: kein neuer strategischer Ausnahmevertrag für Altmaterialisierung; #199: kein neues Messgate; #201: alte Exportformen |
| Historische Aussagequalität | Alle 13 #201-Fälle: geprüft, ungeprüft, erneut prüfbedürftig, historisch nicht erfasst, echte Export- und Scale-Routen |

## Ausführung und Branchbereinigung

Lokale PostgreSQL-Regression auf dem Implementierungscommit `1db4589`:
**213 bestanden, keine übersprungen**, 269,09 Sekunden. Enthalten sind die Dateien
zu #146, #147, #183 (einschließlich #198), #186, #188, #189, #199, #200 und #201.
Die zusätzliche Fokusprüfung A/C/Mehrprozess bestand mit drei Fällen. Die elf
Warnungen betreffen den bestehenden zukünftigen URL-Schemawechsel in Django 6.
Nach der abschließenden Präzisierung von C auf wirtschaftlich tragfähige Buchungen
wurde dieser Fall erneut auf PostgreSQL bestanden (1 bestanden, 18 gezielt abgewählt).
Diese Auswahl ist keine übersprungene Prüfung der Gesamtsuite.
Lockfile, Ruff-Lint/Format, Django-Systemprüfung, Migrationsprüfung und Bandit
bestanden ebenfalls. Keine Produktänderung und keine zusätzliche Migration.

Die vollständige PR-CI ist über [PR #207](https://github.com/Satte882/KI-Ideenwerkstatt/pull/207/checks)
dem jeweiligen Head zugeordnet; Ergebnis und Gesamtsuitenzahl stehen im Check und
in der PR-Beschreibung. Sie umfasst die gesamte PostgreSQL-Suite,
Architecture Real-DEMO E2E, Lockfile, Lint/Format, System-/Migrationsprüfungen,
Bandit, Abhängigkeitsaudit sowie Compose-Validierungen und beide Container-Builds.
Die zusätzlichen pfadgebundenen Block-3/4/5-UI- und Block-9-Messworkflows werden
nicht ausgelöst, weil ihre Auslösepfade unverändert sind. Sie werden nicht als
Bestandteil der bestandenen Standard-CI oder als menschliche Beobachtung behauptet.
Keine echten Modellaufrufe, Produktionsmessungen oder Durchführung von #161.

Der #201-Branch `fix/201-historical-context-export` war über PR #206 squash-gemergt.
Vor Löschung: aktuelles `main` geholt, leerer vollständiger Inhaltsvergleich und
`git cherry main <branch>` ohne eigenständigen Patch. Der Remote-Branch war schon
entfernt. Nur dieser lokale Branch wurde gelöscht; `var/` und andere Branches sowie
Worktrees bleiben erhalten. Dieser PR wird ohne ausdrückliche Freigabe nicht gemergt.
