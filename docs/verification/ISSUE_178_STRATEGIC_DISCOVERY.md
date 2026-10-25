# Issue 178 – strategische Discovery mit menschlichem Untersuchungsrahmen

## Fachliche Grenze und Umsetzung

Variante B wurde nach der Entscheidungsvorlage im Issue ausdrücklich freigegeben.
Nur **neue, ausdrücklich strategische autonome Sessions** erhalten Katalog 3.0 /
Answer 1.1. Der normale neue Problemweg bleibt 2.0; vorhandene Sessions werden auch
bei Wiederaufnahme nicht hochgestuft. Keine Migration oder neue Domain-Entität.

Der bestehende Einstieg bleibt: Arbeitsvorrat → Vorhaben erfassen → speichern →
Untersuchung starten/fortsetzen → gebundene Idee → bestehende Discovery → Prozessanalyse.
Die Einordnung der Vorhabenansicht unter Analyse ist ein lokaler Navigationskontext.
Ein direkter Use Case ist ein anderer, weiterhin gültiger Aufnahmeweg.

Im selben Discovery-Startformular gibt es einen optionalen Abschnitt für den
strategischen Untersuchungsrahmen. Erst das ausdrückliche Ankreuzen wählt v3.
Kein zusätzlicher Strategisch-Link und keine neue Landing-Journey. Scopebeginn,
Scopeende, Ausschluss, Auswahlgrund und konkreter Validierungsschritt stammen aus
der Benutzereingabe. Der Server speichert Identität, Zeitpunkt, Revision und explizite
strategische Auswahl und friert sie im bestehenden Quell-Snapshot ein. Ein vom Modell
behauptetes Bestätigungsflag reicht nicht. Änderungen erzeugen einen neuen Snapshot;
der bisherige Quellenstand bleibt unverändert.

| Bestandteil | Neue strategische Route | Bestand |
| --- | --- | --- |
| Capture / Answer | 3.0 / 1.1 | 1.0 und 2.0 / 1.0 unverändert |
| Discovery-Vertrag | ap1-discovery-v3 | v1/v2 unverändert |
| Generator und Repair | ap1-methodology-v15 | v13/v14 unverändert |
| Verifier-Vertrag | ap1-discovery-verifier-v2 | v1 unverändert |
| Verifier-Prompt | ap1-ver-method-v14 | bisheriger Stand unverändert |
| Menschlicher Quelleninput | ap1-discovery-input-v1 | bisherige Quellkohorten unverändert |

Typisierte Rückfragen unterscheiden Scopeentscheidungen und spätere Evidenzerhebung.
Fehlende Ist-Daten innerhalb eines verantwortbaren menschlichen Rahmens bleiben als
Unknowns sichtbar. Ein tatsächlich unentschiedener Bereich bleibt `waiting_human`.
Serverseitig werden Scopekopie, Quellenbezug, Methodik, Modellvertrag und Verifier
erneut geprüft. Ein `waiting_human` wird nicht pauschal freigeschaltet.

Bei bewusster Scopeübernahme verwendet v3 den vorhandenen Fokus-Kurzpfad mit der
menschlichen Begründung. Qualitative Ratings bleiben leer, Time-to-Value unbekannt,
der globale Fokus bleibt `CANDIDATE`. Bestehende nachgelagerte Screening-/Auswahlgates
bleiben wirksam. Der Prozess trägt den eingefrorenen strategischen Kontext mit dem
Hinweis, dass weder Ist-Prozess noch Screening oder bindende Freigabe bestätigt sind.
Die Idee-/Vorhabenbindung und Materialisierungs-Idempotenz verwenden bestehende Dienste.

## Prüfungen

Deterministische Tests decken menschlichen Scope und Manipulationsversuche, fehlende
Scopeentscheidung, erfundene Ratings/Zahlen/Ursachen, v1/v2-Kompatibilität, Rollen,
Scopeänderungen/Revisionen, unveränderliche Quellen, Kohortenfehler, Wiederaufnahme,
Idempotenz, legitime spätere Vorhabenbindung und unveränderte nachgelagerte Gates ab.
Der Formulartest prüft ausdrücklich, dass ein alter URL-Parameter ohne angekreuzte
strategische Auswahl keinen v3-POST erzwingt.

Ein früher PostgreSQL-Lauf mit wiederverwendetem Testbestand scheiterte an doppelten
Fixture-Datensätzen. Ein parallel gestarteter Diagnoselauf war ungeeignet und wurde
beendet. Der abschließende Lauf verwendet einen frisch angelegten PostgreSQL-Testbestand,
leere Provider-API-Schlüssel und deterministische Provider-Doubles. Produktdaten wurden
nicht bereinigt. Ein fehlerhafter UI-Double mit S1 statt U0 wurde korrigiert; die
Quellenvalidierung des Produkts wurde dabei beibehalten.

Abschließender PostgreSQL-Lauf: **180 bestanden, 11 Warnungen, 124,08 s**.
Getestet wurden `test_issue_178_strategic_discovery` (19 Fälle),
`test_issue_164_strategic_contracts`, `test_issue133_methodology`,
`test_issue_98_autonomous_business_discovery`, `test_idea_autonomous_discovery`,
`test_issue_177_initiative_discovery`, `test_discovery_business_unit_context` und
`test_capture_catalogs`. Der frische Datenbankaufbau beseitigte die lokale Fixture-Kollision.

Vollständige [CI für Produktstand 7ce02d8](https://github.com/Satte882/KI-Ideenwerkstatt/actions/runs/40130830730):
**2.560 Tests bestanden** (419,47 s), zusätzlich Demo-E2E bestanden (31,86 s).
Lockfile, Ruff, Django-System-/Migrationsprüfung, Bandit, Dependency-Audit,
Compose-Validierungen und beide Container-Builds bestanden. Keine bekannten
Abhängigkeitslücken im Audit. Bestehende Django-/Dependency-Warnungen bleiben sichtbar.

Browserprüfung ausschließlich Desktop **1440×1000**. Keine zweite Desktopauflösung,
Tablet- oder Mobileprüfung. Die Prüfung nutzt Playwright mit sichtbarem Browser.
Automatisierte synthetische Eingaben sind keine unabhängige menschliche Abnahme (#161).

## Ein autorisierter Realmodellfall

Genau eine neue synthetische strategische Sitzung ist freigegeben. Kein manueller Retry
oder zweiter Testfall bei Fehlschlag. Bestehende interne Generator-/Verifier-/Repair-
und Transportretry-Aufrufe werden einzeln protokolliert. Modelle, Limits und Timeouts
werden nicht umgestellt.

Vorbereitung: neues synthetisches Vorhaben zu wirtschaftlich tragfähigen
Vertragsverlängerungen aus bestehenden Serviceanfragen. Unbekannt sind Ist-Ablauf,
Rollen, Systeme, Ursachen, Mengen, Baseline und Margen. Der ausdrücklich eingegebene
Untersuchungsrahmen reicht vom Eingang einer Verlängerungsanfrage bis zur Vorbereitung
einer begründeten Entscheidung über das Angebot. Vertragsabschluss, Preisfestlegung und
Leistungserbringung sind ausgeschlossen. Nächster Validierungsschritt: mit fachlich
Verantwortlichen Ist-Ablauf und Verfügbarkeit von Anfrage-/Angebots-/Abschlussdaten erheben.
Diese Angaben sind synthetische Testanweisungen, keine Unternehmensnachweise.

Konfiguration vor dem Start offengelegt: OpenRouter, Discovery-Modell
`google/gemini-3.6-flash`. Der konfigurierte allgemeine Fallback
`deepseek/deepseek-v4.1-flash` ersetzt den Discovery-Override nicht. Keine Umstellung.

**Ergebnis am 24.10.2026: bestanden.** Genau eine Sitzung, eine Analyse, kein manueller
Retry und kein Transportretry. Alle vier tatsächlichen Calls liefen über OpenRouter
mit `google/gemini-3.6-flash`; Timeout jeweils unverändert 60 s.

| Aufruf | Beginn UTC | Dauer | Inputtokens | Outputtokens | Gesamttokens | Gemeldete Kosten USD |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| Generator v3 | 20:44:26,760 | 17,952 s | 2.382 | 3.499 | 5.881 | 0,01490775 |
| Verifier v2 | 20:44:44,732 | 26,775 s | 5.306 | 2.656 | 7.962 | 0,01393950 |
| internes Repair v3 | 20:45:11,573 | 6,444 s | 4.460 | 1.313 | 5.773 | 0,00826875 |
| erneuter Verifier v2 | 20:45:18,040 | 11,368 s | 4.816 | 2.713 | 7.529 | 0,01378575 |
| Summe | | 62,710 s inkl. Verarbeitung | 16.964 | 10.181 | 27.145 | 0,05090175 |

Das bestehende Kostenfeld rundet die Summe auf **0,050902 USD**. Die Werte stammen
aus den tatsächlich zurückgegebenen Provider-Usage-Feldern, nicht aus einer Preisschätzung.
Reasoningtokens je Aufruf: 2.425 / 2.465 / 250 / 2.632, in den Outputtokens enthalten.

Der erste Verifier erkannte `GROUNDING_INVENTED_ROLES`: Der Generator hatte unter
Stakeholdern Kundenbetreuung, Vertrieb und Fachbereich genannt, obwohl Rollen unbekannt
sind. Die begrenzte interne Reparatur durfte ausschließlich `value_stream.stakeholders`
leeren. Anschließend alle sieben Checks true, `approved`, keine blockierende Frage.
Beide Reviewrunden sind gespeichert. Diese Abweichung wurde innerhalb derselben
autorisierten Sitzung behoben; keine zweite Testausführung und keine Promptnachjustierung.

| Gespeicherter Bezug | ID / Stand |
| --- | --- |
| Vorhaben | `661bcf31-024e-4020-b40f-deeaeeb0c045` |
| Gebundene Idee | `e57a5aea-24a1-456e-85fd-ee7d8efda4ef` |
| Neue v3-Sitzung | `95aff57f-45ee-4550-846f-3123d9f04b80` |
| Analyse | `4666f7a4-e7d4-4c82-991c-ccbd8f37737f` |
| Discovery-Quellenstand | `3e586c2e-60f7-44d7-a84b-18c6ee17c8b2`, Revision 1 |
| Datei-Manifesthash | `88ec3c1b9ddd351e29ab6e233c145fddbfa720dc189d3dd4e648644f5e872550` |
| Menschlicher Scope gespeichert | 20:44:26,565 UTC, Benutzer 3, vor dem ersten Call |
| Scope-/Fokusübernahme | 20:46:10,935 UTC, Benutzer 3 |
| Prozessanalyse | `2ba3fe9f-3dd4-4e8c-aa3b-566624969bc3`, dasselbe Vorhaben |
| Investigation / Quellenhandover | `7e976aa5-9de7-4683-9b35-be4a183c570b` / `e3c3efa0-1fce-4f4a-813f-a83b603cf8ea` |

Tatsächlicher Materialisierungsendpunkt: **POST**
`/accelerator/value-stream/autonomous/95aff57f-45ee-4550-846f-3123d9f04b80/review/`,
Aktion `confirm`, UI-Schaltfläche „Scope & Fokus übernehmen“. Antwort 302 zur
bestehenden Investigation-Aktivitätsansicht. Es wurde kein separater
Materialisierungsweg verwendet.

Lesende PostgreSQL-Gegenprüfung bestätigt: gleiche Vorhaben-ID, Fokus `candidate`,
alle fünf Fokusratings leer, Kurzpfad mit gespeichertem menschlichem Grund und Akteur,
Baseline/Engpässe/bestätigte Ursachen leer, `current_flow = Ist-Ablauf unbekannt`,
bestehende Screeningblocker weiterhin aktiv. Der unveränderliche Prozessquellenstand
enthält die ursprüngliche menschliche Bereichsentscheidung.

Die nach der Scopeübernahme automatisch vorgemerkte Investigation wurde über die
bestehende UI ausdrücklich abgebrochen, bevor ein Worker sie ausführte. Ihr gespeichertes
Usage-Ledger weist **0 Modellcalls / 0 Providerattempts** aus. Das begrenzt den Test auf
die autorisierte Discovery und deren tatsächliche Materialisierung; kein Nachweis einer
abgeschlossenen vertieften Untersuchung.

Die Browsersteuerung erreichte beim Warten auf den Modell-POST und beim Abbruch-Redirect
ihr Zeitlimit. Beide Serveraktionen wurden ausgeführt und durch gespeicherte Zustände
und HTTP-Logs bestätigt. Es wurde weder erneut abgesendet noch ein Retry ausgelöst.
Die abschließende Browserkonsole enthält keine Fehler oder Warnungen; kein horizontaler
Überlauf (Viewport 1440×1000, Dokumentbreite 1425).

### Screenshots und gespeicherter Nachweis

Alle Screenshots zeigen einen Viewportausschnitt bei 1440×1000, keine verkleinerte
Ganzseitenaufnahme. Der erste Ausschnitt zeigt den geöffneten optionalen Scopeabschnitt.

- [Strategische Eingabe im bestehenden Formular](issue-178/01-human-scope.png)
- [Review mit menschlichem Rahmen und Explorationshinweis](issue-178/02-review.png)
- [Materialisierter Prozess mit weiterhin wirksamen Screening-Gates](issue-178/03-process.png)
- [Datensparsamer Laufnachweis mit Einzelcalls und Kontinuitätsprüfungen](issue-178/real-case.json)

## Rollback und Grenzen

`ACCELERATOR_STRATEGIC_DISCOVERY_ENABLED=false` verhindert neue v3-Ausführungen und
Materialisierung; vorhandene v3-Reviews bleiben lesbar, v1/v2 bleiben nutzbar. Bereits
gespeicherte v3-Zustände dürfen nicht als v2 umetikettiert werden. Der v3-Lesecode bleibt
für Recovery erhalten.

Keine Änderungen an #179, bestehenden Outcome-/Governance-Gates oder historischen
Entscheidungen. Die v3-Exploration ersetzt weder bestätigte Diagnose noch vollständig
bewertete Fokuswahl, wirtschaftlichen Wirkungsnachweis oder menschliche Abnahme.
