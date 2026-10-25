# Issue 179 – Neues Thema starten

## Freigabe und fachliche Grenze

Basis: integrierte #177/#178, main `6255219e5fbde4a03bd9746adba910d15083feef`.
Die [Entscheidungsvorlage](https://github.com/Satte882/KI-Ideenwerkstatt/issues/179#issuecomment-6396366567)
wurde vor Produkt-/Schemaänderungen veröffentlicht. Der Nutzer hat das einzelne Feld
`IdeaCandidate.intake_context` mit dem begrenzten Vertrag und additiver Migration
ausdrücklich freigegeben.

Es entsteht keine zusätzliche Analysemaschine oder bindende Pfadentscheidung. Alle drei
Anlässe verwenden dieselbe Kurzerfassung, bestehende Ideen und bestehende Discovery.
Problem, Ziel und Potenzialsuche sind unverbindliche Eingabehinweise. Die strategische
Untersuchung wird weiterhin ausdrücklich an der vorhandenen fachlichen Stelle gewählt.

## Umsetzung

- Auf dem Anwendungseinstieg/Arbeitsvorrat ist **Neues Thema starten** die dominante Aktion.
  Die fünf bisherigen Einzelaufnahmen bleiben als nachgeordnete Links erreichbar.
  Aufgabenlisten, Portfolio, lokale Next Actions, Login und das separate RSD-Demoportal
  werden nicht umgeleitet. Das Demoportal öffnet die Anwendung weiterhin über seinen
  vorhandenen Link zum Arbeitsvorrat.
- Drei funktionale Anlasskarten: **Etwas läuft nicht rund**, **Ich habe ein Ziel**,
  **Ich suche Potenziale**. Die direkte KI-Idee bleibt ein nachgeordneter Link zum
  bestehenden Intake mit Hinweis auf Problem/Ziel und geltende Freigaben.
- Ein gemeinsames kurzes Formular mit passender Frage und Beispiel, optionalen betroffenen
  Gruppen und einem deterministisch vorgeschlagenen, editierbaren Kurztitel. Ohne
  JavaScript wird der Titel serverseitig aus dem Satz vorgeschlagen. Lange Vorschläge
  enden nach einem Wort mit Auslassungszeichen.
- **Entwurf speichern und fortfahren** speichert ohne Modellaufruf eine Idee. Nur bei
  Ziel entsteht zusätzlich in derselben Transaktion ein über `bind_initiative()` gebundenes
  Vorhaben. Dessen `business_outcome` bleibt maßgeblich. Hat sich das Geschäftsergebnis
  später geändert, übernimmt der neue Zielweg diesen aktuellen Wert in den Discovery-Start;
  die historische ursprüngliche Eingabe bleibt erhalten. Bestehende Legacy-Vorbelegungen
  und bereits gestartete Sessions werden nicht umgeschrieben.
- Nach dem Speichern stehen Untersuchung starten/fortsetzen, Prozessanalyse öffnen oder
  Später fortsetzen oben in der bestehenden Ideenansicht. Der bisherige Abschlussbereich
  erhält dafür keine konkurrierende zweite Discovery-Hauptaktion.
- Vor **Analyse starten** zeigt das bestehende Startformular den tatsächlich konfigurierten
  Anbieterzugang und Discovery-Modell-Override bzw. Fallback sowie den Hinweis auf variable
  Kosten durch Umfang und Prüf-/Korrekturrunden. Es gibt keine erfundene Preisvorschau,
  automatische Analyse oder Modellumstellung.

### Daten und Duplikatschutz

Einziges neues Feld: `intake_context`, JSON, leerer Default `{}`, nicht über die allgemeine
Ideenbearbeitung editierbar. Vertrag `topic-intake-v1`: `occasion` aus problem/goal/explore,
optionale `perspectives` aus staff/leadership/customers/partners, unveränderter
`original_text`. Nur diese Schlüssel und die Vertragsversion sind erlaubt. Einreicher und
Zeitpunkt verwenden weiterhin `submitted_by/created_at`.

Der Originaltext bleibt bei späteren Beschreibungskorrekturen unverändert. Modell-Save,
QuerySet-Update und Bulk-Update verhindern das Überschreiben des Erfassungskontexts.
Die additive Migration `0022_idea_intake_context` klassifiziert keine historische Idee um.
Der bestehende historische Migrationstest prüft Datenerhalt plus leeren neuen Kontext.

Die vorab erzeugte Ideen-UUID wird an Benutzer und Anlass signiert. Sie bleibt in der
Erfassungs-URL und im Formular erhalten. Reload, Zurückspringen und gleicher POST erzeugen
kein zweites Thema. Ein bereits gespeicherter Erfassungslink öffnet den bestehenden
Eintrag. Unterschiedliche Inhalte unter derselben Kennung ergeben einen Konflikt.
Gleichzeitige POSTs werden über den eindeutigen Primärschlüssel und Transaktionen
zusammengeführt; Fehler bei Vorhabenerzeugung/Bindung rollen beide Objekte zurück.
Ein bewusst neu gestartetes Thema erhält eine neue Kennung, auch bei ähnlichem Text.

Perspektiven werden weder in `source_note` noch in `preparation_drafts` gespeichert und
nicht nach `ProcessDiscoveryPathDecision.origin_basis` kopiert. Der bestehende Herkunfts-
und Quellenweg friert den Erfassungskontext als ursprüngliche Nutzereingabe ein; die
verwaltete Ideenquelle bleibt U0 und wird nicht zur unabhängigen Bestätigung. Quell-Dateien
und Hashes bleiben im tatsächlichen Investigation-Handover identisch.

### Bestehende Rollen

Aktive angemeldete Personen können Ideen erfassen. Vorhabenanlage und Discovery bleiben
bei den vorhandenen berechtigten Rollen. Wer ein Zielvorhaben nicht anlegen darf, sieht
vor der Eingabe einen erklärten Weiterweg über Business Owner/KI-Koordination; es wird
weder ein ungebundenes Ersatz-Ziel angelegt noch das Berechtigungsmodell erweitert.
Bei einem Rechtewechsel während der Eingabe bleibt ein eingereichter Text im Fehlerfall
sichtbar. Aufnahme allein erzeugt keine Freigabe oder Diagnose.

## Deterministische PostgreSQL-Prüfung

Abschließender gezielter Lauf: **209 Tests bestanden, 11 Warnungen, 147,08 s**.
Danach wurde die vollständige neue Vertragsdatei einschließlich Rechtewechsel nochmals
separat geprüft: **26 bestanden, 11 Warnungen, 22,08 s**. Diese Fälle überschneiden sich
mit dem breiten Lauf; die Zahlen werden nicht als unabhängige Testmengen addiert.
Provider-Schlüssel wurden für die Tests geleert; neue Tests sperren den echten Provider
zusätzlich durch einen fehlschlagenden Double. Keine neuen Realmodellaufrufe.

Getestete Dateien: `test_issue_179_topic_intake`, `test_issue_178_strategic_discovery`,
`test_issue_177_initiative_discovery`, `test_idea_autonomous_discovery`,
`test_issue_98_autonomous_business_discovery`, `test_issue_422_idea_inbox`,
`test_issue_145_initiatives`, `test_discovery_business_unit_context`,
`test_issue_412_context_navigation`, `test_dashboard_control_room_ui`,
`test_reporting_dashboard`, `test_demo_portal`, `test_analysis_navigation`.

Die 26 neuen Fälle umfassen alle Anlässe, Originaltext und Perspektiven, atomare
Vorhabenbindung, konkurrierende Anfragen auf PostgreSQL, identische/abweichende POSTs,
signierte Erfassungslinks, manipulierte Kennungen, fremde Benutzer, Rollen und Rechtewechsel,
unveränderliche Kontexte, Logout/Login/Folgetag, Kostenhinweis ohne Autoanalyse,
aktuelles maßgebliches Geschäftsergebnis, Quellenhandover, Materialisierungs-Idempotenz
und Wiederaufnahme. Ein fehlender Untersuchungsbereich bleibt mit einer deterministischen
Verifier-Rückfrage `waiting_human`; es entsteht keine Prozessanalyse.

Ruff, Formatprüfung, Django-Systemprüfung und Migrationserkennung bestanden. Ergebnis
der vollständigen CI steht im PR-/Issue-Abschlusskommentar; keine Gleichsetzung dieses
gezielten Laufs mit der Vollsuite.

## Sichtbare Desktop- und Größenprüfung

Ausschließlich **1440×1000**, keine zweite Desktopauflösung, Tablet- oder Mobileprüfung.
Playwright-CLI mit sichtbarem Browser, isolierter SQLite-Datenbank und deterministischem
Provider-Double. PostgreSQL-/Sperrverhalten wurde davon unabhängig oben geprüft.

| Ansicht | Beobachtung / Korrektur |
| --- | --- |
| Arbeitsvorrat | Neues Thema starten als einzige primäre Erfassungsaktion; bisherige Wege bleiben sichtbar nachgeordnet. |
| Anlasskarten | Drei funktionale, vertikal angeordnete Auswahlen; 920 px Inhaltsbreite, einheitliche Titelhierarchie, KI-Direktweg nachgeordnet. |
| Kurzerfassung | 920 px Breite, Überschrift an bestehende Arbeitsansichten angepasst, Checkboxen lesbar und ausgerichtet; Speicheraktion ohne Scrollen sichtbar. |
| Feldzustände | Vorhandenen `form-guidance-ignore`-Mechanismus lokal verwendet: keine rot/amber hervorgehobenen Leerfelder vor erster Eingabe; echte Fehler bleiben sichtbar. |
| Seitennavigation | Themenerfassung im bestehenden Inbox-Kontext, keine falsche Use-Case-Markierung und kein umgebrochener lokaler Titel. |
| Gespeichertes Thema | Nächste Aktion und Später fortsetzen vor den weiteren Arbeitsbereichen sichtbar. |
| Discovery-Start | Konkreter Modell-/Anbieterhinweis direkt vor der tatsächlichen kostenpflichtigen Aktion sichtbar. |
| Fehlende Rechte | Erklärter Hinweis vor einem leeren, nicht ausführbaren Formular; kein primärer 403-Weg. |

Bei der Kurzerfassung wurden Viewport und Dokument jeweils als 1440×1000 gemessen:
kein horizontaler Überlauf, kein notwendiges vertikales Scrollen. Beide Browserkonsolen
(Business Owner und Leser) ohne Fehler/Warnungen. Fokus- und Auswahlzustände nutzen
bestehende semantische Tokens; keine neue Schrift, Farbenwelt oder globales Redesign.

Drei bewusst verschiedene synthetische Hintergründe wurden über die UI gespeichert
und bis zur bestehenden Scope-/Fokusübernahme geführt: operativer Angebotsvergleich mit
Mitarbeitenden-/Kundenperspektive, Geschäftsziel mit Führungs-/Kundenperspektive sowie
Potenzialsuche im eingegrenzten Partner-/Einkaufsbereich. Ergebnis: genau drei Ideen,
genau ein gebundenes Zielvorhaben, drei Capture-Sessions und drei Prozessanalysen.
Die vorgemerkten Folgeuntersuchungen wurden ohne Worker/Modellcalls abgebrochen.

**Wichtige Prüfgrenze:** Die Browserstrecke verwendet absichtlich dieselbe bekannte
synthetische Beschaffungs-Discovery-Fixture als Modellantwort. Ihre Prozessbezeichnung
ist kein geprüftes Modellurteil zum jeweiligen neuen Anliegen. Die Prüfung belegt UI,
Zuordnung, Herkunft, Re-Entry und Datenkontinuität, keine Modellqualität oder unabhängige
fachliche Abnahme. Sechs Rollenaufrufe gingen an den lokalen Double, **0 an reale
Provider**. Seine künstlichen Usage-/Kostenfelder sind keine tatsächlichen Kosten.

### Screenshots und Zustandsnachweis

- [Zentrale Aktion](issue-179/01-dashboard.png)
- [Drei Anlasskarten](issue-179/02-occasions.png)
- [Kompakte Problemaufnahme](issue-179/03-problem-form.png)
- [Ziel mit ausgewählten Perspektiven](issue-179/04-goal-form.png)
- [Potenzialsuche mit Partnerperspektive](issue-179/05-explore-form.png)
- [Gespeichertes Ziel und klare nächste Aktion](issue-179/06-goal-saved.png)
- [Modell-/Kostenhinweis vor dem tatsächlichen Start](issue-179/07-discovery-cost.png)
- [Berechtigungsgegenprobe](issue-179/08-reader-rights.png)
- [Wiederaufnahme desselben gespeicherten Ziels](issue-179/09-goal-resumed.png)
- [Maschinenlesbare UI-Zustände und Quellkontinuität](issue-179/ui-cases.json)

## Gelöste Probleme und Grenzen

Im neuen Testaufbau wurden ein falscher Service-Parameter/Helpername und die Annahme
einer Anmeldung über die bestehende Sitzungsdauer hinaus korrigiert; der Folgetagstest
meldet sich entsprechend den geltenden Regeln erneut an. Sichtbar aufgefallene
Größen-/Navigations-/Feldzustandsprobleme wurden wie oben beschrieben behoben.

Nach der ersten vollständigen CI meldete der Nutzer einen weiteren konkreten Fehler
im erhaltenen alten Einstieg `/use-cases/ideas/new/`: „Abbrechen“ nutzte bereits die
UUID der ungespeicherten ModelForm-Instanz und öffnete dadurch eine nicht existierende
Detailseite (404). Der Link speicherte keinen Eintrag. Das Abbruchziel kommt jetzt
aus dem View: Neuanlage → Inbox, Bearbeitung → gespeicherte Idee. Vier Regressionen
prüfen beide Wege mit und ohne Validierungsfehler sowie unveränderte Daten. Der
zugehörige PostgreSQL-Lauf mit Ideen-Inbox und neuer Themenerfassung bestand mit
**40 Tests, 11 Warnungen, 24,42 s**. Vollständige CI für die Korrektur im PR verlinkt.

Keine Änderungen an Discovery-Prompts, Verträgen, Readiness, fachlichen Auswahl- oder
Outcome-/Governance-Gates. Der Rückweg muss den neuen Kontext lesbar erhalten; ein
Rollback darf gespeicherte `intake_context`-Daten nicht durch Rücknahme der Spalte
vernichten. Historische Ideen mit `{}` und alte Einstiegspfade bleiben unterstützt.

Der Originaltext ist bewusst historischer Freitext. Die bestehenden Regeln für Umgang
mit personenbezogenen Eingaben gelten auch dafür; keine neue Aufbewahrungsregel.
Nach Integration bleibt die unabhängige Abnahme **#161 mit zwei Fachanwendern** offen.
Ein Agententest ersetzt dieses Urteil nicht. Draft-PR, nicht eigenständig mergen.
