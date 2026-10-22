# Issue #155 – Phase A: Outcome-first-UX-Abnahme

**Stand:** 22.10.2026, Europe/Berlin · **Prüfbasis:** `5c09c94f28452a82e4bd9135f423dc64858c3b76` (`origin/main`).
**Ergebnis:** Die zwei Browser-Journeys und der kurze Direkteinstieg wurden durchlaufen. Die UX ist wegen reproduzierter Eingabeverluste und weiterer Befunde **nicht vorbehaltlos abgenommen**. Keine Produktänderungen. Phase B ist nicht freigegeben.

## Nachweise und Grenzen

- Echter sichtbarer Chromium-Browser mit Playwright CLI; primär **1440 × 1000**, kritische Formulare/Vergleiche zusätzlich **1024 × 1000**. Screenshots sind Vollseitenbilder und daher teilweise höher als 1000 Pixel.
- Separate SQLite-Datenbank außerhalb des Repositorys; synthetische Organisation, drei normale Benutzer mit echten Gruppen **Business Owner**, **KI-Koordinator**, **Leser**. Keine Superuser-Abkürzung und keine Änderung an Berechtigungen oder Gates.
- Das lokale Repository war vor Beginn sauber. `git fetch origin` und `git merge --ff-only origin/main` aktualisierten `main` von `eb76bf7` auf `5c09c94`; keine lokalen Änderungen wurden überschrieben.
- Referenzen: [Issue #155](https://github.com/Satte882/KI-Ideenwerkstatt/issues/155), `AGENTS.md`, [ADR 0009](../adr/0009-outcome-first-vorhaben-und-wirkung.md), [vorhandene Discovery-Browserprüfung](../accelerator/IDEA_DISCOVERY_UI_VERIFICATION.md). Keine UI-Implementierung und damit keine Änderung des Design-Systems.
- Zwei anfangs vorbereitete Prozess-/Optionssätze dienten der isolierten Outcome-Vorprüfung. Sie ersetzen die E2E-Journeys **nicht**. Danach wurden beide Ideen tatsächlich über Discovery, Scope-/Fokusübernahme, materialisierten Prozess und im Browser erfasste Optionen weitergeführt. Die Bildtitel unterscheiden Vorprüfung und E2E.
- Discovery-/Verifier-Antworten wurden deterministisch aus der vorhandenen Testfixture abgeleitet. Sie sind **keine Prüfung der Modellqualität**. Die gemockte Discovery-Korrektur prüft Erreichbarkeit und Fortsetzung, nicht die semantische Umsetzung durch ein Modell. Investigation-Worker wurden nicht ausgeführt; „Start angefordert / Wartet auf Ausführung“ wurde nicht als fertige Diagnose bewertet.
- **Abweichung vom Auftrag:** In der frühen Vorprüfung löste die bindende KI-Auswahl indirekt einen echten Metrik-/Pilotentwurf aus (F5). Das Protokoll meldete 4492 Tokens, `cost=0.002417`; Währung im Log nicht ausgewiesen. Die zunächst nur am Discovery-Provider gesetzte Sperre war unvollständig. Nach Erkennen wurde der Server gestoppt, auch der OpenRouter-Schlüssel für die Testinstanz geleert und eine ausgehende Socket-Sperre außerhalb Loopback gesetzt. Der spätere durchgehende KI-Pfad zeigt ausdrücklich den fehlenden Provider-Key. **Der Lauf ist deshalb nicht als durchgehend mock-only oder kostenfrei auszugeben.** Inhalte aus diesem Realaufruf im Vorprüfungs-Use-Case KI-0002 sind kein Qualitätsnachweis.
- **Kein menschlicher Kaltdurchlauf:** Verständlichkeit und Zögern eines Anwenders wurden nicht behauptet. Dieser ergänzende Schritt und die Befundpriorisierung bleiben beim Auftraggeber.

### Screenshot-Paket

[Durchsuchbarer Screenshot-Index nach Befund, Journey, Rolle und Breite](ISSUE_155_SCREENSHOT_INDEX.md).

**60 PNGs**, eine aufklappbare Offline-Galerie `index.html`, `screenshots.json` mit URL/Rolle/Bildmaßen/SHA-256, `SCREENSHOT_INDEX.md`, `roles-final.json`, `layouts.json`, `incident.json` und `persisted-state.json` stehen in der Codex-Ausgabe **`issue155-phase-a-evidence.zip`** bereit. ZIP entpacken, `issue155/index.html` öffnen. Die Galerie verlinkt jedes Originalbild.

- ZIP-SHA-256: `12f4a5b7b10dd4770f0969fe24aad898a9289e45d19db36d095ebc3b4b4cc89b`.
- Keine Bilder, Datenbanken, Browserprofile oder Testskripte wurden in das Git-Repository aufgenommen.
- **Remote-Anhang noch nicht verfügbar:** Der Upload über das vorhandene GitHub-Issue-Anhangsfeld scheiterte an der fehlenden Edge-Erweiterungsberechtigung „Allow access to file URLs“. Diese Berechtigung wurde nicht verändert. Die Bilder sind direkt als lokale Codex-Ausgabe/Galerie zugänglich; ein GitHub-Anhang bzw. CI-Artefakt wird hier ausdrücklich **nicht** behauptet. Die Sichtung kann mit dem lokal bereitgestellten Paket erfolgen.
- Bildnummern unten sind Dateipräfixe im ZIP; vollständige Zuordnung in `screenshots.json`. Lokale Test-URLs verwenden `http://127.0.0.1:8775` und erfordern die isolierte Testinstanz; die Screenshots sind unabhängig davon lesbar.

## Tatsächlich geklickte Journeys

### A1 – Kundenservice, problemgetrieben, KI-Gewinner

Als **Business Owner**:

1. Idee `117fa1fd-ef0a-4546-a602-f17b6010a054` → **Geschäftsproblem untersuchen**. Beschreibung und Organisation sind vorbefüllt; Rücklink zur Ursprungsidee ist vorhanden. Bilder **01–02**.
2. **Analyse starten** → Discovery-Review `875da58f-8044-4b6b-ae34-df86a369511d` → **Value Stream korrigieren** → Korrekturfeld → **Mit Korrektur neu analysieren** → **Scope & Fokus übernehmen**. Bilder **19–20**.
3. Investigation `614c5b85-4f2b-4205-8004-e113b22fb7cb` → **Zur Prozessanalyse** → Prozess `afeb8e51-d4b8-4c8a-80d8-d837e3066acc`. Scope, Fokus und Ursprung bleiben erreichbar. **Bearbeiten** führt zum vorhandenen Formular. Eine ausdrücklich synthetische bestätigte Ursache wurde für den problemgetriebenen Entscheidungsvertrag eingetragen; die Baseline bleibt „noch offen“. Bild **21**.
4. **Erste Lösungsoption ergänzen** → KI-Option und Regelalternative einzeln erfassen/bewerten → **Vergleichsmatrix öffnen**. Beschreibungen, erwarteter Beitrag und eigene Wirkung auf das gemeinsame Geschäftsergebnis wurden bewusst getrennt erfasst.
5. **Outcome-Bezug vorbereiten / bestätigen** → vorhandenes Vorhaben **Serviceverträge #155 laden** → Geschäftsergebnis „Mehr wirtschaftliche Serviceverträge“, begrenzter Beitrag, Wirkannahme, Prüfkriterien und Owner werden wiederverwendet → problemgetriebenen Pfad/Fokus begründen → **Wirkannahme fachlich annehmen und zuordnen** → Rücksprung zum Vergleich.
6. **Service-KI E2E** wählen → Trade-off gegenüber Regeln begründen → **Bevorzugte Option auswählen**. Entscheidung persistiert; KI-0003 wird angelegt; fehlender Provider-Key lässt Metrikentwurf offen und löscht die Entscheidung nicht. Bild **22**.
7. KI-0003 öffnen → Zustand und nächste Bewertungs-/Governance-Schritte prüfen. **Keine positive Freigabe und kein Pilotstart behauptet:** Assessment und weitere fachliche Nachweise fehlen; Gates wurden nicht umgangen. Bild **23**.
8. Über gemeinsames Vorhaben: **Capability-Test erfassen** → nur Titel als Entwurf speichern → unvollständige fachliche Dokumentation absenden → verständliche Fehler → synthetische Fall-/Holdout-Referenzen und Erkenntnis ergänzen → fachlich dokumentieren. Ergebnis **„Teilweise / mit Grenzen“**, keine automatische Freigabe/Geschäftswirkung. Bilder **09–10**; der Test wurde bereits in der Vorprüfung am selben Vorhaben dokumentiert und ist auch im E2E-Vergleich sichtbar.
9. **Gemeinsame KI-/Non-KI-Wirkungsprüfung** → **Wirkungsprüfung bearbeiten** → KI-0003 als führende Prozessmetrik referenzieren; Non-KI-Messfelder leer; Geschäftsergebnis und Attribution **noch ungeklärt** → **Wirkungsstand prüfen**. Bild **28**. „Geprüft“ bezeichnet den dokumentierten Review-Stand, keinen positiven Geschäftserfolg.

### A2 – CEO-Potenzial, strategisch, Non-KI-Gewinner

Als **Business Owner**:

1. Idee `db0716ce-0598-4cc9-b833-7f2ffc93ae02` → **Geschäftsproblem untersuchen** → CEO-Potenzial ohne bestätigte Ursache formulieren → **Analyse starten** → Review `4029e978-9561-4af1-b668-6f9573dd073e`. Bild **24**.
2. Review unterbrechen: **Benutzermenü → Abmelden** → Review erneut öffnen → Login mit `next` → derselbe Review ist wieder erreichbar → **Scope & Fokus übernehmen** → **Zur Prozessanalyse**. Prozess `43c49909-0e2c-4eb6-8610-a258e451f1b6`, Bild **25**. Bestätigte Ursache blieb auch in der Datenbank und im Entscheidungssnapshot **leer**. Der Mock enthält Ursachenhypothesen; diese wurden nicht als bestätigt ausgegeben.
3. KI- und Regeloption im Browser erfassen → Vergleich → dasselbe Vorhaben/Geschäftsergebnis laden → **Strategisches Potenzial** auswählen; Herkunft, Potenzial, Validierungsschritt und Fokus begründen → fachlich annehmen → Vergleich.
4. **Service-Regeln E2E** auswählen: klare Kategorien, kurzfristiger Betrieb, geringerer Aufwand; kein belegter KI-Mehrwert → bindend speichern. **Kein KI-Use-Case** für diesen Prozess erzeugt. Bild **26**, zusätzlich persistierter Snapshot.
5. Gemeinsames Vorhaben → Wirkungsprüfung → Non-KI-Entscheidung referenzieren, **keinen** KI-Metrikträger auswählen → synthetische Prozessmessung „Median Antwortzeit 48 auf 24 Stunden, 20 Testanfragen, Testwoche, Protokoll UX155-N“ dokumentieren → Geschäftsergebnis/Attribution weiterhin ungeklärt und begründen → **Als Entwurf sichern** → Review wieder öffnen → **Wirkungsstand prüfen**. Bild **27**. Keine Behauptung eines realen Nutzens.

### A3 – kurzer Direkteinstieg

Als **KI-Koordinator**: bestehender direkter Use Case KI-0001 `1c5f8b02-aba0-48f4-9a4f-246668c725f6` → `/decision/new/` → **Outcome-Bezug vorbereiten / bestätigen** → vorhandenes Vorhaben laden → fachlich annehmen → Rücksprung exakt nach `/decision/new/`. Bilder **17–18**. Browser zurück/vor führt wieder zwischen Vorbereitung und Entscheidung.

Der erste Zustand ohne Assessment bot nur negative Portfolioentscheidungen. Anschließend wurde ein **synthetisches vorhandenes Assessment samt Governance-Grundlage** als Testfixture ergänzt, damit der Outcome-Übergang prüfbar ist. Der Koordinator ist zugleich Bewertender; die unabhängige positive Freigabe bleibt deshalb korrekt gesperrt. Der Business Owner erhielt bei einem bewusst direkt aufgerufenen Koordinator-Entscheidungslink 403; dieser Link war ihm nicht als Aktion angeboten. Das ist kein Befund eines angebotenen kaputten Links.

## Rollen, Navigation und Wiederaufnahme

Die finale Matrix umfasst **21 Seitenzustände**: beide E2E-Prozesse, beide Vergleiche, Vorhaben, Capability-Nachweis und direkter Use Case, jeweils als Koordinator, Business Owner und Leser. Alle Seiten antworteten mit 200. Die angebotenen Outcome-, Optionsbearbeitungs-, Wirkungsreview- und Capability-Erfassungswege wurden zusätzlich angeklickt; kein geprüfter angebotener Übergang endete in einer unerklärten 403. Im ersten Matrixskript wurde bei gleich beschrifteten Optionslinks jeweils der erste Treffer gewählt; die Aussage ist daher **keine vollständige Prüfung jedes einzelnen Links**. Berechtigungen zum Durchführen bindender Entscheidungen wurden im Owner-Hauptpfad geprüft, nicht durch erneute Entscheidungen mit jeder Rolle.

| Bereich | Owner / Koordinator | Leser | Beleg |
| --- | --- | --- | --- |
| Prozess / Vergleich | Bearbeitungs- und Outcome-Wege erreichbar | keine bindenden Auswahl-/Bearbeitungsbuttons | `role-*-process`, `role-*-compare`, `role-*-topProcess`, `role-*-topCompare` |
| Vorhaben / Review | Speichern, Wirkungsprüfung, Capability-Erfassung angeboten | lesbare Darstellung, keine Speicher-/Review-Aktion | `role-*-initiative` |
| Geprüfter Capability-Nachweis | Historie unverändert, Berichtigung möglich | keine Berichtigungsaktion | `role-*-capability` |
| Direkter Use Case | rollenabhängige nächste Aufgabe | lesbar, keine Bearbeitungsaktion | `role-*-direct` |

- Browser zurück/vor wurde für **beide** E2E-Vergleiche → Outcome-Vorbereitung geprüft: Geschäftsergebnis bleibt identisch. Beim Direkteinstieg stimmt der Rückweg.
- Erneutes Login führte sowohl zum gespeicherten Discovery-Review als auch zum geprüften Vorhaben zurück; Review-Stand und Inhalt blieben vorhanden.
- Ein **ungebundener Entwurf** wurde ohne seinen Direktlink wiedergefunden: Vergleich → Outcome-Vorbereitung → Dropdown → **Offener Wiederaufnahme-Entwurf #155 → Vorhaben laden**. Bild **37**. Eine eigenständige Vorhabenliste fehlt; „unauffindbar“ ist damit widerlegt, die Auffindbarkeit bleibt ein UX-Vorschlag V2.
- Fehlerhafter POST bei leerem Vorhabentitel erhält `VALIDATION-155 bleibt erhalten` im Geschäftsergebnis (Bild **31**). Vergleichsfehler erhält Radioauswahl/Begründung (**04**), Capability-Fehler Titel (**09**), Review-Fehler eingegebenen Grund (**11**).
- Kein horizontaler Dokumentüberlauf in der 1440er Rollenmatrix oder bei den 1024er Ansichten Outcome, Vergleich, Vorhaben, Capability, Wirkungsreview. Bilder **32**, **34**, `layout-1024-*`. **Das schließt abgeschnittene Navigation nicht aus: visuell bestätigt, siehe F6 und Bild 38.** Dies ist keine vollständige WCAG-/Mobile-Abnahme.

## Befunde zur menschlichen Klassifikation

P1 = Verlust von Anwenderarbeit bzw. unbemerkter kostenpflichtiger Seiteneffekt; P2 = erhebliche Orientierungs-/Entscheidungsreibung. **Keine der folgenden Empfehlungen ist eine Umsetzungsfreigabe.**

### F1 · P1 · „Vorhaben laden“ verwirft Eingaben ohne Warnung

- **Verhalten:** `UNSAVED-155: zusätzliche wirtschaftliche Serviceverträge` wird durch den gespeicherten Text „Mehr wirtschaftliche Serviceverträge“ ersetzt; keine Warnung oder Wiederherstellung angeboten.
- **Erwartung:** Vor dem ersetzenden Laden Eingaben sichern oder den Verlust ausdrücklich bestätigen lassen.
- **Reproduktion:** Owner → `/use-cases/outcome/process/afeb8e51-d4b8-4c8a-80d8-d837e3066acc/` → Geschäftsergebnis ändern → **Vorhaben laden**.
- **Nachweis:** **29** vorher, **30** nachher; zusätzliche Vorprüfung **06**.
- **Vorschlag:** Schutz beim ersetzenden Laden; keine neue Domainlogik oder implizite Zuordnung.

### F2 · P1 · „Als Entwurf sichern“ verliert Pfadkontext

- **Verhalten:** Vorhabentitel wird gespeichert, neu eingegebene Herkunft und strategisches Potenzial werden nach Redirect durch den bisherigen Prozesspfad ersetzt. Die Eingaben `DRAFT-ORIGIN-155` und `DRAFT-POTENTIAL-155` verschwinden.
- **Erwartung:** Eine als Entwurf gespeicherte Formularfassung behält die dort sichtbaren Angaben oder benennt vor dem Speichern eindeutig, welche Angaben nicht gesichert werden. Kein bindender Pfadwechsel als Nebenwirkung.
- **Reproduktion:** Owner → `/use-cases/outcome/process/43c49909-0e2c-4eb6-8610-a258e451f1b6/` → Auswahl vorhandenen Vorhabens leeren → neuer Titel → Herkunft/Potenzial ändern → **Als Entwurf sichern**.
- **Nachweis:** **35** vorher, **36** nachher, **37** wiedergefundener Vorhabentitel. Bestehender bestätigter Prozesspfad blieb in der Datenbank geschützt; der Defekt betrifft den verlorenen Entwurfstext.
- **Vorschlag:** Speicherumfang/Erhaltung separat entscheiden. Eine persistente neue Pfadentwurfslogik wäre außerhalb eines bloßen Template-Fixes und darf nicht stillschweigend ergänzt werden.

### F3 · P2 · Outcome-Gates erst nach bindendem Auswahlversuch

- **Verhalten:** Bei vollständig bewerteten Optionen und fehlendem Vorhaben ist **Bevorzugte Option auswählen** aktiv. Oberhalb steht nur der allgemeine offene Vorhabensbezug; die konkrete Auswahlblockade erscheint erst nach dem POST.
- **Erwartung:** Fehlende Outcome-Voraussetzung und Korrekturweg vor dem bindenden Versuch am Auswahlbereich sichtbar machen. Erkundung/Bearbeitung weiterhin ermöglichen.
- **Reproduktion:** Owner → Vorprüfungsprozess `8c18fc41-2bc8-426e-a68b-b097969aea67/options/compare/` ohne Vorhaben → KI wählen und begründen → auswählen.
- **Nachweis:** **03** vorher, **04** Fehler. Hard Gate arbeitet korrekt, Auswahl und Begründung bleiben nach Fehler erhalten.
- **Vorschlag:** Bestehenden Gate-Befund sichtbar projizieren; keine Abschwächung des serverseitigen Vertrags.

### F4 · P2 · Navigation verliert den semantischen Kontext

- **Verhalten:** Auf Outcome-Vorbereitung, Vorhaben, Capability und Wirkungsreview fehlt in der linken Navigation `aria-current`. **Use Cases** ist lediglich per CSS markiert, auch beim Einstieg aus der Prozessanalyse. Auf Prozess-/Vergleichsseiten funktionieren `Analyse` und lokale aktuelle Ansicht.
- **Erwartung:** Hauptbereich und lokale Position konsistent ausweisen und einen erkennbaren Rück-/Fortsetzungsweg bieten.
- **Reproduktion:** Vergleich → Outcome-Vorbereitung; gemeinsames Vorhaben → Capability bzw. Wirkungsreview. DOM-Inspektion der sichtbaren Navigation: null `aria-current` in diesen vier Bereichen.
- **Nachweis:** **05**, **08**, **10**, `role-*-initiative`, `role-*-capability`, `layout-1024-impact`; `roles-final.json`.
- **Vorschlag:** Bestehende Navigationsprojektion ergänzen. Keine zweite Journey.

### F5 · P1 · Verbindliche KI-Auswahl stößt ohne gesonderte KI-Aktion Modellaufruf an

- **Verhalten:** In der Vorprüfung startete **Bevorzugte Option auswählen** nach Erzeugung des KI-Use-Cases einen echten Metrik-/Pilotentwurf. Ein getrenntes Anklicken eines KI-Entwurfsbuttons war dafür nicht nötig. Der Seiteneffekt war durch die anfängliche Discovery-Sperre nicht abgedeckt.
- **Erwartung für diese Abnahme:** Ausschließlich Mocks/gespeicherte Antworten, keine echten Tokenkosten. Produktseitig sollte ein solcher Seiteneffekt vor der Aktion erkennbar und kontrollierbar sein.
- **Reproduktion:** KI-Option bindend wählen; `_continue_selected_ai_solution` ruft bei fehlender `ap2_planning_provenance` `generate_and_apply_ap2_metric_pilot` auf. Browserbefund **07–08**; nach umfassender Sperre derselbe E2E-Übergang **22** mit offengebliebenem Entwurf.
- **Nachweis:** Testserverlog `ap2_metric_pilot_draft`, Modell `deepseek/deepseek-v4.1-flash`, Run `0d7cf802-9e1e-47d3-a859-237227dd1c8c`, 4492 Tokens, `cost=0.002417`. Die Kostenaussage beruht auf dem Log, nicht auf einem Screenshot oder einer Abrechnungsprüfung.
- **Vorschlag:** Separat priorisieren. Testharness-Sperre ist korrigiert; kein Produktfix. Service-/LLM-Verhalten liegt außerhalb der Direkt-Fix-Grenze von Phase B.

### F6 · P2 · Linke Navigation bei 1024 Pixeln abgeschnitten

- **Verhalten:** Die Seitenleiste schrumpft auf 84 Pixel, zeigt aber weiterhin Textlabels und Marke. „Arbeitsvorrat“, „Portfolio“, „Analyse“ und andere Einträge sind abgeschnitten bzw. ungünstig umgebrochen; Teile der Icons/Marke fehlen. Die Hauptseite selbst hat keinen horizontalen Überlauf.
- **Erwartung:** Auch bei der geforderten ergänzenden Desktopbreite sind Navigationsziele eindeutig lesbar oder sauber als zugängliche Icon-Navigation dargestellt.
- **Reproduktion:** Outcome-Vorbereitung bei Viewport **1024 × 1000** öffnen; linke Leiste ansehen. Nicht nur `scrollWidth` prüfen.
- **Nachweis:** **38** ist ein unbeschnittener echter Viewport-Screenshot; **32** und `layout-1024-*` zeigen denselben Zustand in Vollseitenbildern. DOM-Messung: Sidebarbreite 84 Pixel.
- **Vorschlag:** Bestehenden kompakten Navigationsmodus konsistent darstellen; keine neue Navigation/Journey.

## UX-Vorschläge und bewusst akzeptierte Zustände

| ID | Beobachtung / Erwartung | Einordnung und Nachweis |
| --- | --- | --- |
| V1 | Outcome-Formular zeigt 18 sichtbare Eingaben einschließlich Pfadwechsel, Bestätigung und Schreibkorrektur gleichzeitig; die jeweiligen Bestätigungsvoraussetzungen sind nicht an den Feldern erläutert. | P3, Vorschlag: vorhandene Felder nach Entwurf/Annahme/seltenen Korrekturen ordnen und Aktionsumfang erklären. Keine behauptete Anwenderverwirrung. **05**, **31–32**, **35**. |
| V2 | Vorhaben sind über den Kontext und die Vorhabenauswahl erreichbar, nicht über eine eigene Liste. | P3, Auffindbarkeit verbessern separat vorschlagen; keine neue Liste ohne Produktentscheidung. Wiederfinden **37** bestanden. |
| V3 | Bestätigungs- und Fokusbegründung sind beim Wiederöffnen leer. Vorhabenstatus kann trotz fachlich angenommener Wirkannahme weiterhin „Entwurf“ sein; Annahmestand ist im Vorhabenformular nicht als eigener aktueller Status ausgewiesen. | P3, bestätigten Stand und bestehende Fokusbegründung sichtbar machen, ohne verschiedene Zustände gleichzusetzen. **08**, **28**, **37**. `focus_reason` leer bestätigt; **keine Fokusüberschreibung** beim erneuten Bestätigen mit leerem Fokusgrund: davor/danach vier identische Fokusdatensätze, unveränderte Revisionen/Rationales/Kriterien. Verdacht einer leeren Historisierung im geprüften Fall widerlegt. |

Akzeptiert: Bearbeitung über eindeutig benannte vorhandene Formulare statt Inline-Editor; Entwurf ohne Owner/Review-Datum; fachliche Annahme ohne positive Freigabe; dokumentierte Capability ohne Geschäftserfolg; Non-KI-Endzustand ohne künstlichen KI-Use-Case; „noch ungeklärt mit Grund“ als geprüfter Review. KI-Messdefinition und Geschäftsergebnis werden weder kopiert noch addiert. Ein gemeinsamer aktueller Review wird bewusst aktualisiert; vorangegangene Stände bleiben historisch dokumentiert, nicht als zusätzliche parallele Reviews erfunden.

## Datenkontinuität und LLM-Inventar

| Information | Im Browser verifiziert |
| --- | --- |
| Idee → Discovery | Beschreibung und Organisation vorbefüllt; Ursprung als Rücklink erhalten. |
| Discovery → Prozess | Fachlicher Scope, Fokus und Prozessfelder übernommen; Quellenstand referenziert. Keine erfundene Zahlenbaseline. |
| Gemeinsames Geschäftsergebnis / Vorhabensbeitrag / Wirkannahme | Beim Laden desselben Vorhabens wiederverwendet; im Vergleich Geschäftsergebnis/Wirkannahme referenziert; kein zweites Outcome-Objekt je Option. |
| Erwarteter Lösungsbeitrag / Outcome-Wirkung | Zwei eigene Optionsfelder; in der Vergleichsmatrix getrennte Zeilen. Bewusst interventionsspezifisch eingegeben, keine automatische Übernahme aus dem Geschäftsergebnis behauptet. |
| Fokus / Pfad | Herkunft, Pfad, strategisches Potenzial und Validierungsschritt nach fachlicher Annahme wieder vorbefüllt; Fokusbegründung fehlt, gespeicherte Entscheidung blieb erhalten. Entwurfslücke F2. |
| Messdaten | KI-Review referenziert den Use Case; Non-KI-Prozessmessung eigenständig erfasst; Geschäftsmessung bleibt offen. KI-0003 hat keine erfundenen Messwerte. |

Vorhandene, nicht ausgebaute Assistenzpfade: Idee → autonome Discovery (`architect_service`, hier gemockt); Prozess/Vergleich → **3 Lösungsentwürfe mit KI erstellen** und vorhandene Preview-/Übernahmewege; geführte Accelerator-Erfassung/Extraktion und feldweise Übernahme in vorhandenen Services; KI-Auswahl → automatischer Metrik-/Pilotentwurf; **Mit AI-Entscheidungsgrundlage fortfahren** → bestehende Architektur-/Assessment-/Governance-Entwürfe; Use-Case-Detail → **OpenRouter Review-Copilot anzeigen**. Die UI-Erreichbarkeit der benannten Buttons/Links wurde inventarisiert; nicht alle Generierungen wurden ausgeführt. Wiederverwendung dieser vorhandenen Quellen-/Entwurfsmechanismen wäre denkbar, bedarf aber gesonderter Produktentscheidung und Modellfreigabe. Kein Ausbau und keine echte Generierung nach F5.

## Übergabe und Stopp

- Reiner Dokumentationsstand; keine Produktdatei, Migration, Berechtigung oder Testdefinition geändert. Browserprüfung und persistierte Zustandskontrolle bilden die Validierung dieses Berichts; keine neue vollständige Produkt-CI behauptet.
- Auftraggeber klassifiziert **F1–F6 und V1–V3** jeweils als **direkt beheben / separat vorschlagen / nicht ändern**. Insbesondere F2/F5 dürfen bei Bedarf an ausgeschlossene Schichten nur eskaliert werden.
- Für den menschlichen Kaltdurchlauf: ohne Entwicklerhilfe einen Entwurf wiederfinden, Outcome-Kontext korrigieren, eine Alternative begründet wählen und anschließend Prozess- und Geschäftswirkung erklären lassen. Unklarheiten und längeres Zögern als Beobachtung notieren. Noch nicht durchgeführt.
- **STOPP nach Phase A. Keine automatische Fortsetzung zu Phase B, kein Fix und kein Merge.**
