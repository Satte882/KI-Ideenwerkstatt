# Issue #155 – Phase B: F1–F6

Abnahmebericht vom 22.10.2026 für [PR #157](https://github.com/Satte882/KI-Ideenwerkstatt/pull/157). F1–F6 sind umgesetzt und im echten Browser nachgeprüft. **Zur menschlichen Abnahme, nicht mergen.** V1–V3 sind unverändert.

[Vorher-/Nachher-Index und alle 72 neuen Bilder](ISSUE_155_PHASE_B_SCREENSHOT_INDEX.md) · [Einzelabgleich aller 60 Originale](ISSUE_155_PHASE_B_ORIGINALBILD_ABGLEICH.md) · [GitHub-Nachweiskommentar](https://github.com/Satte882/KI-Ideenwerkstatt/pull/157#issuecomment-6347652458)

## Auftrag und Freigaben

Grundlage ist die [Phase-B-Freigabe mit Feedback](https://github.com/Satte882/KI-Ideenwerkstatt/issues/155#issuecomment-6346485531). Alle 60 Originalbilder der Phase A wurden vor den Produktänderungen einzeln visuell geöffnet und mit den Befunden abgeglichen. Die ursprünglichen Nachweise bleiben unverändert; Zuordnung siehe `ISSUE_155_SCREENSHOT_INDEX.md`.

Die ursprünglich ausgeschlossene Migration wurde für F2 ausdrücklich separat freigegeben. Antwort des Nutzers am 22.10.2026 im zugehörigen Codex-Chat: „Ein Feld plus Migration für F2 freigeben“. Diese Ausnahme umfasst ausschließlich das optionale JSON-Feld am bestehenden Vorhaben sowie die additive Migration einschließlich Historienmodell. V1–V3 werden nicht umgesetzt.

## Umsetzung

| Befund | Änderung | Technische Grenze |
| --- | --- | --- |
| F1 | „Vorhaben laden“ zeigt zunächst Ersetzen/Behalten. Auch unvollständige Eingaben bleiben bis zur ausdrücklichen Auswahl erhalten. | Laden und Abbrechen speichern nichts. |
| F2 – separate Speicheraufgabe | Unbestätigter Pfadkontext wird im bestehenden Vorhaben nach Herkunftsobjekt gespeichert und nach Redirect/Login wieder geladen. | Bestehende Revision, Rechte und Transaktion; keine verbindliche Pfad-/Fokusentscheidung durch Entwurf. Erst erfolgreiche ausdrückliche Bestätigung entfernt den Entwurf. |
| F3 | Vergleich nennt die tatsächlichen Outcome-Blocker vor der Auswahl und verlinkt die Vorbereitung. | Bestehende serverseitige Entscheidungsgates bleiben maßgeblich. |
| F4 | Outcome, Vorhaben, Capability und Wirkungsprüfung besitzen passenden Hauptbereich und lokale aktuelle Position. | Direktes Use-Case-Outcome bleibt im Use-Case-Kontext. |
| F5 – separate Aufrufaufgabe | Auswahl erzeugt den kanonischen KI-Use-Case ohne automatische Planung. Bestehende Planung läuft erst über „KI-Planungsentwürfe kostenpflichtig erstellen“, mit Hinweis und Rückmeldung. | Bestehende Planungsdienste, Provenance, Fehlerbehandlung und Governance bleiben erhalten. |
| F6 | Beschriftete bestehende Seitennavigation auch bei 1024 px; lokale Beschriftungen dürfen umbrechen. | Vorhandenes Layout und Design-Tokens; kein neuer Navigationsmodus. |

## Prüfbedingungen

Isolierte Kopie synthetischer Testdaten; echter sichtbarer Chromium-Browser. Keine echten LLM-Aufrufe: Schlüssel leer, externe Netzwerkverbindungen gesperrt, deterministische Antworten ausschließlich an der Provider-Grenze. Fachliche Dienste werden im Browser unverändert durchlaufen. Diese Prüfung bewertet Ablauf, Zustand, Rechte und Darstellung; sie belegt keine Qualität echter Modellantworten und keine Geschäftswirkung.

Produktstand der Nachprüfung: `0e0823fe5367cfcf8d986d1029ce3f9be966f04a`. Nachfolgende Commit-Änderungen betreffen ausschließlich Tests und Dokumentation. 1440 × 1000 und 1024 × 1000 CSS-Pixel; volle Seiten sind zusätzlich scrollbar aufgenommen. Der tatsächliche Bildausschnitt kann wegen der vertikalen Browser-Scrollbar 15 Pixel schmaler sein. Die Viewport-Nachweise zeigen die feste Navigation ohne Fullpage-Scrollartefakt.

## Klickpfade und Ergebnisse

### J1 – Problemgetrieben, KI mit gleichwertiger regelbasierter Alternative

Business Owner: „Phase B: Kundenservice-Antwortzeiten“ → „Geschäftsproblem untersuchen“ → vorbefüllte Business Discovery → „Analyse starten“ (Provider-Double) → Review → „Scope & Fokus übernehmen“ → Untersuchungsstart → „Zur Prozessanalyse“. Der Hintergrund-Untersuchungsstart bleibt sichtbar; eine tatsächlich ausgeführte Investigation wird hier nicht vorgetäuscht. Für die UX-Prüfung wurden zwei bewertete Alternativen über „Erste Lösungsoption ergänzen“ / „Option ergänzen“ manuell dokumentiert: Service-KI und Service-Regeln, beide mit derselben noch unbewiesenen Geschäftswirkung.

„Optionen vergleichen“ nennt vor dem Absenden den fehlenden Outcome-Bezug und die noch offene Diagnose. „Diagnose ergänzen“ → ausdrücklich als synthetisch gekennzeichneter Prüfbefund → Speichern → Vergleich → „Outcome-Bezug vorbereiten / bestätigen“. Geschäftsergebnis „Mehr wirtschaftliche Serviceverträge“, Beitrag „Qualifizierte Antworten früher bereitstellen“, getrennte Prüfkriterien, dokumentierte Herkunft, problemgetriebener Pfad und Fokusbegründung → „Wirkannahme fachlich annehmen und zuordnen“ → Rückkehr zum nun freigegebenen Auswahlformular.

„Service-KI E2E“ auswählen → Trade-off begründen → „Bevorzugte Option auswählen“. Ergebnis: eine unveränderliche Lösungsentscheidung und genau ein kanonischer KI-Use-Case, **null automatische Planungsaufrufe**. Erst „KI-Planungsentwürfe kostenpflichtig erstellen“ nach sichtbarem Kosten-/Governance-Hinweis führt zu den drei simulierten Planungsantworten. Die Rückmeldung trennt Metrik/Pilot, Architektur und Entscheidungs-/Governance-Entwurf; sie erteilt keine Freigabe.

„Gemeinsame KI-/Non-KI-Wirkungsprüfung“ → Vorhaben → „Capability-Test erfassen“ → Titel und ausdrücklich ungeprüfte Zielhypothese → „Als Entwurf sichern“. Der Leser sieht später „Ungeprüfter Entwurf“, keinen Capability-Nachweis. Über „Zum Vorhaben“ → „Wirkungsprüfung bearbeiten“ bleiben KI-Prozessmetrik, Geschäftsergebnis und Attribution getrennt. Baseline, Zielwert, Ist-Wert und Messnachweis wurden nicht erfunden. Eine positive Freigabe oder ein Pilotstart war wegen offener Governance/Messung nicht Teil dieses Durchlaufs.

### J2 – CEO-Potenzial, gültiger Non-KI-Abschluss

Business Owner: „Phase B: CEO-Servicepotenzial“ → Discovery-Start → Analyse (Double) → Scope/Fokus übernehmen → Prozess. Der deterministische Discovery-Double enthält eine allgemeine Anfragevergleichs-Vorlage; seine fachliche Qualität wird nicht bewertet. Über „Bearbeiten“ wurde der tatsächliche synthetische CEO-Auftrag ausdrücklich eingetragen, Ursachenhypothese und bestätigte Ursache blieben leer. So wird der Mock-Inhalt nicht als bestätigte strategische Diagnose ausgegeben.

Zwei gleichwertige Alternativen manuell erfassen → vergleichen → Outcome vorbereiten → vorhandenes gemeinsames Vorhaben wählen → „Vorhaben laden“ → sichtbare Ersetzen-Wahl → ausdrücklich ersetzen → strategischen Pfad, CEO-Herkunft, Potenzial, Validierungsschritt und Fokus begründen → fachlich annehmen → Vergleich. Die Auswahl ist ohne erfundene bestätigte Problemursache möglich, weil die bestehenden strategischen Voraussetzungen erfüllt sind.

„Service-Regeln E2E“ → begründete Auswahl. Ergebnis: gültiger Non-KI-Endzustand, kein zusätzlicher KI-Use-Case und kein Planungsaufruf. Vorhaben → Wirkungsprüfung → diese Non-KI-Entscheidung auswählen, Prozesswirkung „Noch nicht nachgewiesen“, Geschäftsergebnis und Attribution begründet „Noch ungeklärt“ → „Wirkungsstand prüfen“. Die anschließend sichtbare Prüfung dokumentiert den offenen Nachweisstand; sie behauptet keinen Geschäftserfolg. Die spätere bewusste Zuordnung des direkten Use-Cases ändert den gemeinsamen Vorhabensstand und macht diese frühere Wirkungsprüfung erwartungsgemäß erneut prüfbedürftig. Diese Schutzwirkung blieb erhalten.

### J3 – Direkter bestehender KI-Use-Case, Outcome und Rückkehr zur Freigabe

KI-Koordination: direkte KI-Serviceassistenz → „Freigabe entscheiden“ → Outcome-Zuordnung und Personentrennung als harte Blocker sichtbar → „Outcome-Bezug vorbereiten / bestätigen“. Dort ist **Use Cases** aktiv, mit lokaler Position „Outcome-Bezug vorbereiten“. Gemeinsames Vorhaben auswählen → Laden → Ersetzen ausdrücklich bestätigen → Annahme begründen → zuordnen → automatische Rückkehr zur Entscheidung.

Der Outcome-Blocker entfällt. Die Personentrennung bleibt hart gesperrt, weil dieselbe synthetische Koordination bewertet und entscheiden würde. Keine Entscheidung, keine Freigabe und kein Pilotstart wurden gespeichert. Dass daneben die zugewiesene Koordination im Lifecycle noch fehlt, bleibt sichtbar; die bestehenden Gates wurden nicht angepasst.

### J4 – Entwurf, Laden, Fehler, Wiederaufnahme und Browser-Historie

Ungebundener Vergleich → Outcome vorbereiten → Titel, Herkunft `DRAFT-ORIGIN-155B`, strategisches Potenzial `DRAFT-POTENTIAL-155B` und Validierungsschritt → „Als Entwurf sichern“ → Redirect mit Vorhabens-ID. Die Felder bleiben erhalten. Abmelden über Benutzermenü → erneut anmelden → denselben gespeicherten Vorhabensbezug öffnen: Herkunft, Potenzial und Validierung sind wieder vorhanden, mit Hinweis auf den unverbindlichen Entwurf. Die Datenbankprüfung bestätigt weiterhin keinen Pfad, keinen Fokus und keine Zuordnung für diesen Prozess.

Geschäftsergebnis mit `UNSAVED-155B` ändern → „Vorhaben laden“: Ersetzen/Behalten wird vor Datenersatz angezeigt. „Eingaben behalten“ erhält die genaue Eingabe. Erst „Eingaben ersetzen und Vorhaben laden“ übernimmt ausdrücklich den gespeicherten Stand. Beide Zweige und unvollständige Eingaben sind zusätzlich automatisiert geprüft. Die abschließenden 1440-Aufnahmen wiederholen diesen Ablauf mit dem finalen Navigationslayout.

Bei unvollständiger Bestätigung fehlt die Fokusbegründung: verständliche Fehlermeldung statt Serverfehler, `VALIDATION-155B` bleibt im Herkunftsfeld. Die Transaktion hinterlässt keinen verbindlichen Pfad/Fokus. Ein älterer Vorhabensstand kann keinen inzwischen geänderten Entwurf überschreiben. Vergleich → Outcome → Browser-Zurück → Browser-Vorwärts bei 1024 px führt zu den richtigen Seiten und eindeutiger aktiver Position.

## F2 – separate technische Speicheraufgabe

`preparation_drafts` ist ein leeres optionales JSON-Feld am vorhandenen `ImprovementInitiative`, einschließlich des bestehenden Historienmodells in Migration 0020. Der Schlüssel kombiniert Herkunftsobjekt und ID. Gespeichert werden Pfad, Herkunft, Wechselgrund, Potenzial, Validierung und eingegebene Begründungen. Der bestehende Vorhabensdienst übernimmt Rechte, Zeilensperre, Revision und Historie. Normale Vorhabensbearbeitung löscht den Kontext nicht.

Der Entwurf ist kein Eingang für Outcome-Gates oder Entscheidungssnapshots. Bestehende verbindliche Entscheidungen bleiben bei alleiniger Änderung des Pfadentwurfs erhalten. Änderungen der eigentlichen Outcome-Felder behalten die bisherige Revisions-/Neubestätigungslogik. Erst erfolgreiche ausdrückliche Bestätigung wendet bestehende Pfad-, Bindungs-, Fokus- und Annahmedienste an und entfernt den betroffenen Kontext atomar. Bei Fehlern wird alles zurückgerollt. Kein neuer Domain-Typ, kein zweiter Workflow und keine parallele Session-Wahrheit.

## F5 – separate technische Aufrufaufgabe

Die Auswahl verwendet weiterhin `create_use_case_from_selected_solution`, startet dabei aber keinen der drei Planungsdienste. Der vorhandene ausdrückliche `continue_ai_handoff`-Auftrag führt die bisherigen Metrik-/Pilot-, Architektur- und Governance-Dienste aus. Fehlerbehandlung, Wiederaufnahme und Provenance bleiben erhalten. Neue Rückmeldungen zeigen die jeweiligen erfolgreichen Entwürfe und ihre Grenzen.

Der Regressionstest zählt **0** Dienstaufrufe bei Auswahl und anschließendem GET sowie genau die drei vorgesehenen Dienstaufrufe beim ausdrücklichen Auftrag. Im Browser entstanden genau drei Provider-Double-Protokolle mit passenden Run-IDs; ihre Antworten deklarieren Modell `mock/ux155`, null Tokens und null reale Kosten. Die gespeicherten drei Tasks endeten erfolgreich. Da der Double die Provider-Grenze ersetzt, sind die produktiven Abrechnungsfelder in diesen Test-Tasks leer; diese leeren Werte werden **nicht** als Abrechnungsnachweis interpretiert. Der Nachweis für keine realen Aufrufe besteht aus den leeren Schlüsseln, der externen Socket-Sperre und den ausschließlich lokalen deterministischen Antworten. Der in Phase A dokumentierte reale Aufruf ist historischer Bestand der kopierten Testdaten und wird nicht der Phase-B-Prüfung zugerechnet.

## Rollen, Darstellung und angebotene Links

| Rolle | Geprüfte Ansichten | Ergebnis |
| --- | --- | --- |
| Business Owner | 8 Seiten × 2 Breiten = 16 | Eigene Prozess-/Vorhabensbearbeitung verfügbar; Koordinations-/Freigabeaktionen bleiben begrenzt. |
| KI-Koordination | 8 Seiten × 2 Breiten = 16 | Zulässige Bearbeitung/Planung verfügbar; bestehende Personentrennung bleibt verbindlich. |
| Leser | 7 Seiten × 2 Breiten = 14 | Lesen ohne bearbeitbare Felder oder Mutationsbuttons; Capability-Entwurf ausdrücklich ungeprüft. |

Seiten: beide Prozesse, beide Vergleiche, gemeinsames Vorhaben, Capability-Entwurf, direkter Use-Case und für berechtigte Rollen Wirkungsbearbeitung. 46 Ansichten wurden auf Hauptbereich, lokale Position, Sidebar-/Dokumentüberlauf und abgeschnittene Beschriftungen geprüft und als Screenshots gesichert. Keine dieser Prüfungen meldete seitlichen Überlauf oder abgeschnittene Seitennavigation. Die Navigation wurde ergänzend visuell anhand der Bilder geprüft; die 1024-Viewport-Aufnahmen bestätigen lesbare Marke und Beschriftungen. Seitenüberschriften und Formulare umbrechen im verbleibenden Inhaltsbereich.

29 angebotene relevante Links wurden tatsächlich angeklickt, jeweils nach dem konkreten `href`, auch bei gleichnamigen „Option bearbeiten“-Links. Kein angebotener Link führte zu 403/500. Die für Leser **nicht angebotene** direkte Wirkungs-Bearbeitungs-URL antwortet erwartungsgemäß mit 403; die Zusammenfassung ist im lesbaren Vorhaben erreichbar. Automatisierte unerlaubte POSTs für Laden, Speichern, Bestätigen und Planung bleiben ebenfalls 403.

## Regression und CI

- Neue Regressionen: Ersetzen/Behalten mit unvollständigen Eingaben, sichtbare Blocker bei weiterhin hartem POST-Gate, semantische Navigation einschließlich direktem Intake, Leserrechte, keine implizite Planung, bestehende explizite Dienste, dauerhafte Wiederaufnahme, Rollback und konkurrierende Revision. **11 Tests bestanden**; Provider-Schlüssel leer, externe Sockets gesperrt.
- Bestehende Integrations-/Wiederaufnahmeprüfungen an den ausdrücklichen Planungsauftrag angepasst; fachliche Auswahl und Governance bleiben geprüft.
- Lokale vollständige Suite mit PostgreSQL wie in CI: **2393 bestanden, 2 übersprungen**, 83 % Gesamt-Coverage, für den Implementierungsstand. Die zwei Ausnahmen betreffen unter Windows nicht erlaubte Symlink-Erstellung. Der anschließend ergänzte direkte Navigationstest ist im separaten grünen Lauf der elf Regressionen enthalten.
- Der erste SQLite-Gesamtlauf hatte 2380 bestandene und 6 fehlgeschlagene Tests: eine bisherige implizite Planungserwartung wurde angepasst; die anderen fünf betrafen SQLite-UUID-/Parallelitätssemantik. Mit PostgreSQL bestehen diese Tests. Keine fachlichen Locks/Gates wurden dafür verändert.
- Ruff, Format, Django-Systemprüfung, Migrations-Drift und Diff-Prüfung lokal bestanden.
- [Vollständige GitHub-CI für Produktstand 0e0823f](https://github.com/Satte882/KI-Ideenwerkstatt/actions/runs/39824265642): **2395 Tests bestanden**, Real-DEMO-E2E, Migrationen, Bandit, Dependency-Audit, alle Compose-Prüfungen sowie Produktions-/Entwicklungs-Build grün. Die genaue abschließende PR-Head-SHA und der zugehörige CI-Lauf werden im Abnahmekommentar auf [PR #157](https://github.com/Satte882/KI-Ideenwerkstatt/pull/157) festgehalten; maßgeblich sind die grünen Checks am aktuellen Head.

Der wiederholbare Browser-DOM-Check steht unter `tests/browser/issue155_navigation.js`. Auf einer authentifizierten betroffenen Seite mit `playwright-cli run-code` ausführen. Er prüft beide Breiten und erzeugt bei Überlauf oder mehrdeutiger aktiver Position einen Fehler; er startet keine Modellaufrufe.

## Grenzen und unveränderter Umfang

Keine echten Modellantworten, keine reale Untersuchung, keine reale Capability-Messung, kein wirtschaftlicher Nachweis und keine Freigabe wurden durch diese UX-Prüfung behauptet. Die allgemeinen Mock-Vorlagen enthalten einzelne unpassende Beschaffungsformulierungen; deren semantische Qualität ist kein Gegenstand dieser Prüfung. Die beobachteten bestehenden Inline-Script-CSP-Meldungen auf der Freigabeseite wurden protokolliert; die geprüften serverseitigen Formular-/Rückwege funktionierten. Es wurde dafür keine Sicherheitseinstellung verändert.

Der umfangreiche Formularaufbau, zusätzliche Wiederfinde-Oberflächen und weitere Statusdarstellungen aus V1–V3 bleiben außerhalb des Auftrags. Der Capability-Entwurf bleibt ungeprüft, auch wenn die bestehende Speicher-Rückmeldung allgemein „Nachweis dokumentiert“ formuliert. Keine neue fachliche Prüfung wurde daraus abgeleitet. Bestehende Architektur, Design-Tokens und Governance wurden beibehalten. Migration 0020 ist die ausdrücklich genehmigte, additive F2-Ausnahme. PR bleibt zur Abnahme offen; kein Merge und keine automatische Merge-Freigabe.
