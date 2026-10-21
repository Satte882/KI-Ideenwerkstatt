# Issue #133: Ergebnis der fachlichen Validierung

Datum: 21.10.2026. Geprüfter Produktstand: `095062aa52efe5b2a9a3770b6bd04b1a3f41907e`.
Auftrag: [Issue #133](https://github.com/Satte882/KI-Ideenwerkstatt/issues/133).
Szenarien und Karten: [ISSUE_133_RSD_SCENARIOS.md](ISSUE_133_RSD_SCENARIOS.md).

**Ergebnis:** Die bestehenden Formulare und Regeln können A als manuell begleiteten
Problem-/Diagnoseentwurf aufnehmen. Ein fachlich autonomer End-to-End-Erfolg ist
unter der Vorgabe „keine kostenpflichtigen Provider-Aufrufe“ nicht nachgewiesen.
Die automatische Strecke endet bereits vor dem Discovery-Entwurf. Die separat
fortgesetzte manuelle Strecke endet vor Ursachenbestätigung und Lösungsentscheidung.
Für Produkt- oder Architekturänderungen ergibt dieser Lauf noch keinen belegten Bedarf.

Alle Personen, Aussagen, Buchungen und Zusatzinformationen sind synthetisch.
Es wurde kein reales RSD-Problem festgestellt und kein Nutzen oder Pilot gemessen.

## Testumgebung und Aussagekraft

- Echte Django-Requests über den vorhandenen Testclient: Routing, Middleware,
  Rollen, Formulare, Speicherung und gerenderte Antwortkontexte aktiv.
- Vorhandene `config.settings.test`, `USE_SQLITE_FOR_TESTS=1`, frische temporäre
  SQLite-Testdatenbank; keine Verbindung zur lokalen PostgreSQL-Datenbank.
  Vorhandene Migrations-Stammdaten bleiben verfügbar, keine fachlichen Demo-Fälle
  als Ausgangsbasis für A. Eigene temporäre Quellenablage im pytest-Verzeichnis.
- Vorhandene Fixture `owner`: ausschließlich Business Owner, kein Superuser.
  Die synthetische Testeinheit hat im isolierten Katalog den Auswahlstatus
  `productive`; das bezeichnet nur Formularzulässigkeit, keinen echten Unternehmensbereich.
- API-Schlüssel und Schlüsseldateiverweise für OpenRouter/OpenAI sowie Sentry
  werden im Runner geleert. Ausgehende Socket-Verbindungen sind prozessweit
  gesperrt. Keine erfundenen Providerantworten im Szenariotest, kein gestarteter Worker.
- Keine Änderungen an Produktcode, Prompts, Modellen, Architektur oder Gates.
  Ergänzt wurden Test, Offline-Runner, Szenarien und Nachweise.
- Dies ist eine fachlich bewertete Integrationserprobung, **keine aktuelle
  Browser-/Bedienbarkeitsabnahme**, kein PostgreSQL-Concurrency-Test und kein
  Nachweis realer Modellqualität. Vorhandene Browser-Nachweise mit simuliertem
  Provider wurden gelesen, aber nicht als fachliche Modellleistung angerechnet.

## Reproduktion

Im angegebenen lokalen Repository mit dessen vorhandener Python-Umgebung:

```powershell
$env:RSD_REPORT_DIR = 'artifacts/issue133'
.\.venv\Scripts\python.exe scripts/validate_rsd_issue133.py
```

Das exportierte `artifacts/issue133/scenario-a-transcript.json` enthält tatsächliche
Eingaben, Routen, Statuscodes, Redirects, Meldungen, Formularfehler, Kartenfreigaben,
Blocker und Endzustand. IDs und Zeitstempel ändern sich bei Wiederholung;
die exportierten URLs sind historische Test-URLs, keine dauerhaft laufende Umgebung.
Die Testdatenbank wird nach dem Lauf verworfen. Kein Produktdatensatz wird zurückgesetzt.

Ergänzende bestehende Regressionen wurden mit demselben Offline-Runner ausgeführt:

```powershell
.\.venv\Scripts\python.exe scripts/validate_rsd_issue133.py `
  tests/test_issue133_rsd_validation.py `
  tests/test_issue_422_idea_inbox.py `
  tests/test_idea_autonomous_discovery.py `
  tests/test_stage_focus_and_process_findings.py `
  tests/test_solution_selection_ux.py `
  tests/test_guided_intake_hard_gates.py `
  tests/test_golden_path_to_closure.py `
  tests/test_scale_readiness.py
```

Ergebnis: **123 bestanden**, 11 bestehende Django-6.0-Deprecation-Warnungen.
Nach präzisierten Szenariotexten wurde A separat erneut geprüft. Ruff Check und
Formatprüfung der beiden ergänzten Python-Dateien bestanden. Die ergänzenden
Regressionen verwenden teilweise simulierte Provider und vorbereitete Evidenz;
ihre Ergebnisse zählen ausschließlich als Mechanismenprüfung, nicht als A-Ergebnis.

## Tatsächlicher Ablauf A

| Schritt | Was die Anwendung selbst tat | Unterstützung / fachliche Bewertung |
|---|---|---|
| 01–02 Inbox | Originaltext unverändert gespeichert und im Discovery-Einstieg vorbelegt | Titel, Testkennzeichnung und Organisation durch Testautor. Keine Analyse, Ursache oder Metrik abgeleitet. |
| 03–04 automatische Discovery | Quellen-/Sitzungsmechanismus ausgeführt; Analyse `failed / not_configured`; Meldung „Discovery konnte nicht abgeschlossen werden: Kein OpenRouter API-Key konfiguriert.“ Sitzung bleibt `draft`, kein Value Stream erzeugt | Keine Modellantwort, keine selbst entwickelten Rückfragen, kein vorgeschlagener Wertstrom. **Hier endet die automatische fachliche Kette.** |
| K1 / 05–06 manuelle Fortsetzung | Vorhandene Value-Stream- und Phasenformulare speichern Entwürfe | Testautor fragt A-K1 ab und formuliert selbst den Service-Wertstrom sowie drei Phasen. Dies ist ein separater Zweig, kein automatischer Fallback der gescheiterten Discovery. |
| 07–09 Fokus | Prozessanlage zunächst per Redirect blockiert; Screening und Phasenvergleich speichern die Testeingaben | Testautor setzt synthetisches Screening und Fokusphase. Alle qualitativen Kriterien `medium`, Zeit bis Wirkung `unknown`, Evidenz `hypothesis`. Das ermöglicht eine Methodenprobe; es belegt keine wirtschaftliche Relevanz und keinen überlegenen Fokus. Keine reale Scope-/Fokusfreigabe. |
| K2–K3 / 10 Prozess | Beobachtung, Hypothesen, leere bestätigte Ursache und unbekannte Baseline speicherbar | Testautor fragt Fälle/Gegenfälle/Messung ab. Kartenfreigaben stehen separat im Protokoll. Angaben kommen erst jetzt in Prozessfelder, nicht rückwirkend in die Inbox. |
| 11 Lösungsraum | Drei Optionen als `draft / hypothesis / candidate` gespeichert | Alle vom Testautor: Klärweg/Zuständigkeit, vorhandene Buchungsansicht und quellengebundene Suchhilfe. Die App erzeugte, bewertete oder priorisierte diese Optionen nicht. |
| 12–14 Vergleich/Ende | Unvollständige Bewertungen und „bestätigte Ursache“ als Blocker angezeigt; Auswahl ohne Ursachenbestätigung mit Formularfehler abgelehnt | Kein Text in `confirmed_causes` eingefüllt, keine Prozessvalidierung oder Lösungsentscheidung gespeichert. Keine kompakte agentische Entscheidungsfläche vorhanden (`null`), da kein Investigation-Brief materialisiert wurde. |

Der erste technische Probelauf scheiterte an einer Testeingabe: das Pflichtfeld
`bottlenecks` war leer. Die Wiederholung nennt ausdrücklich nur das berichtete
lokale Suchproblem und den unbekannten systemweiten Engpass. Es wurde keine Ursache
zur Umgehung des Pflichtfelds eingetragen und kein Produktcode angepasst.

## Fachliche Qualität und unbelegte Aussagen

| Prüfaspekt | Bewertung | Begründung / verbleibende Grenze |
|---|---|---|
| Treue zum Erstproblem | Erfüllt für Speicherung; autonome Analyse nicht geprüft | Wortlaut bleibt erhalten. Keine automatisch erkannte Geschäftsursache. |
| Abgrenzung des Wertstroms | Teilweise | Serviceanliegen bis geprüfte Antwort passt zur Person; Informationssuche ist eine Phase. Abgrenzung und Wertfortschritt stammen vollständig vom Testautor, nicht von der App oder einer Fachfreigabe. |
| Diagnose | Teilweise | A-K2 enthält widersprechende Transferzeiten, A-K3 einen Fall ohne Widerspruch. H1 widersprechende Stände, H2 fehlende Rechte und H3 verspätete Rückmeldungen bleiben unbestätigt. Nur H1 hat ein synthetisches Indiz; H2/H3 sind zusätzliche Testautoren-Hypothesen ohne Beleg. Keine Wiederholungshäufigkeit, Repräsentativität oder Kausalität nachgewiesen. |
| Fehlende Fakten | Erfüllt für Erfassung/Stop; semantische Prüfung offen | Keine Kennzahl ersetzt unbekannte Messung. Zahlen 09:00/10:00 sind erfundene Quellenangaben, keine Leistungskennzahlen. Formulierung „unbekannt“ wurde durch den Testautor eingegeben. Die App prüft damit nicht die Wahrheit des Inhalts. |
| Lösungsoffenheit | Erfüllt für Speicherung; Auswahlqualität offen | Organisatorische, Standardsoftware- und Assistenzoption nebeneinander. Keine bevorzugte Lösung. Regelbasierte oder unveränderte Bearbeitung bleiben Vergleichsmöglichkeiten, wurden nicht als vierte Option ausgearbeitet. |
| Technische Eignung | Offen | Quellenzugang, Rechte, Schnittstellen, führender Datenstand und Kosten unbekannt. Weder Integration noch KI ist als geeignet nachgewiesen. |
| Nutzen und Wirkung | Offen | Keine Such-/Wartezeitmessung, Mengen, Antwortkorrektheit, Wiederholkontakte oder Kostenbasis. Keine Ersparnis, kein ROI, kein Baseline-/Ziel-/Istwert und keine Pilotwirkung behauptet. |
| Menschliche Entscheidung | Grenze eingehalten | Synthetischer Fokus ist Testsetup. Keine verbindliche Ursachenbestätigung, Prozessvalidierung, Lösungspräferenz, Freigabe, Übergabe oder Lifecycle-Entscheidung ersetzt. |
| Herkunft über gesamte Strecke | Teilweise; im manuellen Zweig unterbrochen | Automatischer Einstieg erhält Ideenursprung. Manuell erzeugter Prozess hat den vorhandenen Phasen-Quellsnapshot, aber `idea.discovery_process_analysis_id = null`. Kartenbezug steht im Protokoll/Freitext, nicht als automatisch aufgebaute Provenance. |

Die abgelehnte Auswahl beweist nur den leeren Pflichtinhalt und die vorhandenen
Regeln. Sie beweist nicht, dass die App eine sachlich falsche, aber ausgefüllte
Ursachenbestätigung erkennen würde. Auch „Hypothese“ und „unbekannt“ sind hier
bewusst eingetragene Inhalte, keine selbst erkannten Unsicherheiten des Modells.

## Fachlicher Endpunkt und notwendige Fortsetzung

Endzustand A: Inbox offen; Discovery-Sitzung Entwurf; ein manuell angelegter
Wertstrom mit drei Phasen und eine Prozessanalyse im Entwurf; drei Kandidaten.
**Null** Prozessvalidierungen, Lösungsentscheidungen, Use Cases, Delivery Packages
und Lifecycle Reviews. Die Fachkette endet vor belastbarer Diagnose und Auswahl.

| Noch nicht erreichte Stufe | Was vor einer seriösen Fortsetzung fehlt |
|---|---|
| Ursache / bevorzugte Lösung | Verifizierter aktueller Stand, Zuständigkeiten und Rechte; mehrere untersuchte Fälle samt Gegenbelegen; fachliche Bestätigung und ausgearbeiteter Alternativenvergleich durch zuständige Person. |
| KI-Use-Case | Erst klären, ob eine begründete Lösung überhaupt eine KI-Komponente braucht. Ein Non-AI-Abschluss ist zulässig. |
| Bewertung / Governance / Freigabe | Belastbare Nutzen- und Datenbasis, soweit erforderlich Baseline und Ziel, Risiko-/Prüfkontext sowie unabhängige berechtigte Personen. |
| Delivery / Pilot | Freigegebener Scope, konkrete Anforderungen, Verantwortliche, Test-/Messplan und verbindliche Übergabe; kein fiktiver Pilotstart. |
| Messung / Ergebnisentscheidung / Betrieb / Abschluss | Tatsächlich durchgeführter Pilot, nachvollziehbare Messung, Betriebsnachweise und explizite menschliche Entscheidung. Nicht durch Demo-Messwerte ersetzen. |

Vorhandene Lifecycle-Regressionen bestehen, aber **A hat diese Stufen nicht erreicht**.
Aus ihrem grünen Ergebnis folgt weder eine Freigabe für A noch eine validierte
Problemlösung. Der Umfang „möglichst vollständig“ endet an dieser Evidenzgrenze.

## Können B–D ohne Produktänderung getestet werden?

**Ja als manuell begleitete, hypothetische Discovery-Proben; nein als unveränderte
autonome Vollstrecke bis Betrieb/Abschluss.** Für B–D liegt eine Dokumentations- und
Mechanismenprüfung vor, noch kein ausgeführter Szenariolauf.

| Szenario | Vorhandener Ansatz | Besondere Testkorrektur |
|---|---|---|
| B | Inbox, Business Discovery, mehrere Wertströme/Fokus, Prozessanalyse | Vor Prozesswahl mehrere Bereiche prüfen. Keine fiktiven Wachstums-/FTE-Zahlen für Pflichtfelder. Nicht das Kundenservice-Setup von A übernehmen. |
| C | Rollen-/Kundenperspektive im Problem, Quellen und Widersprüche, Prozessentwurf | Gültigkeit, Erreichbarkeit und Offline-Fall prüfen; keine Portal-/KI-Lösung vorgeben und keine reale Reiseauskunft erteilen. |
| D | Rollen, Übergaben, Geschäftsregeln, offene Fragen, Lösungsvergleich | Unternehmensgrenzen, Bestätigung und Vollmacht explizit erfragen; kein Partnerzugriff oder Auftrag durch bloße Modellannahme. |

Empfehlung für die folgenden Läufe:

1. Vorbereitete Ersttexte unverändert verwenden, Karten einzeln und sichtbar freigeben.
2. Kostenfreien manuellen Lauf getrennt von einer Modellqualitätsmessung bewerten.
   Ohne nachweislich kostenfreien vorhandenen Provider bleibt die automatische
   Strecke ungeprüft; keine Modellantworten vorschreiben und als Erkennung zählen.
3. Menschliche Fachprüfung von Ursache/Scope/Präferenz als tatsächlichen Übergabepunkt
   planen. Fehlt sie, mit offenem Befund stoppen. Kein festes Soll „bis Betrieb“.
4. Herkunft des manuellen Zweigs ausdrücklich im Bericht führen. Falls durchgängige
   Produkt-Provenance zwingendes Abnahmekriterium ist, ist dieser Zweig dafür kein
   Ersatz. Kein neues Verknüpfungsfeature allein aus diesem Offline-Workaround ableiten.
5. Pro Lauf separat bewerten, was die App selbst leistet und was der Testautor
   liefert. Erst wiederholbare fachliche Lücken in einem ausführbaren Pfad rechtfertigen
   einen gezielten Produktauftrag.

Der Testansatz muss also vor B–D korrigiert werden: **Discovery mit ehrlicher
Abbruchgrenze und getrennten Leistungsnachweisen**. Die Szenarioausgangspunkte
selbst können bestehen bleiben. Issue #133 ist damit als Vorbereitung und erster
begrenzter Lauf bearbeitet; eine uneingeschränkte fachliche E2E-Abnahme bleibt offen.

## Gelesene Nachweise

Neben Issue #133 und den im Szenariodokument genannten Produktunterlagen:
`tests/test_issue_422_idea_inbox.py`, `tests/test_idea_autonomous_discovery.py`,
`tests/test_issue_98_autonomous_business_discovery.py`,
`tests/test_architecture_discovery.py`, `tests/test_focus_prioritization.py`,
`tests/test_golden_path_to_closure.py`,
`docs/accelerator/IDEA_DISCOVERY_UI_VERIFICATION.md`.
Die tatsächlichen Assertions/Requests des neuen Laufs stehen unter
`tests/test_issue133_rsd_validation.py`, der abgesicherte Einstieg unter
`scripts/validate_rsd_issue133.py`. Es wurden keine GitHub-Kommentare oder
Statusänderungen vorgenommen; der Nachweis liegt lokal zur Prüfung vor.
