# Issue #177 – Outcome-first Stufe 1a: Abnahmenachweis

## Umfang und Ausgangsprüfung

Arbeitsbasis: GitHub `main` / `a1e2471b52edc6e1e26661ae3bea0c584054cbaf`.
`AGENTS.md`, `DESIGN.md`, ADR 0009 und das vollständige Issue #177 wurden gelesen.
Geprüft wurden `ImprovementInitiative`, `IdeaCandidate`, `ProcessAnalysis`,
`bind_initiative()`, Rollenvererbung, Discovery-Start/Ownership/Retention,
Materialisierung, Herkunfts-Snapshots, vorhandene Templates und CI.

Keine neuen Felder, Migrationen oder Rollenverträge waren erforderlich. Die bestehende
Discovery verwendet weiterhin ausschließlich `origin.type=idea_candidate`.
Discovery-Verträge, Prompts, Readiness, Verifier und fachliche Gates sind unverändert.
#178 und #179 sind nicht umgesetzt. Auf ausdrücklichen Nutzerwunsch gilt ausschließlich
**1440×1000 px** als Desktop-Referenz; `DESIGN.md` wurde entsprechend angepasst.

## Umsetzung und Akzeptanz

| Kriterium | Umsetzung / Nachweis |
| --- | --- |
| Minimalanlage | Titel und Geschäftsergebnis sichtbar; weitere bestehende Felder über natives `details/summary`. Bestehende Bearbeitungsansicht unverändert. Fehler öffnen die optionalen Angaben. Entwurf ohne Owner, Kennzahl, Ursache oder Termin speicherbar. |
| Einheitlicher Ursprung | POST erzeugt bei Bedarf eine Idee und bindet sie über `bind_initiative()`. Vorhabenssperre serialisiert konkurrierende Starts. Eine vorhandene Idee wird wiederverwendet. Mehrere Ideen werden ausdrücklich zur Auswahl angezeigt; der Service wählt keine zufällige Herkunft. |
| Eingabe statt Beweis | Geschäftsziel und Erfassungsherkunft stehen als editierbare Eingabe bereit. Ursprünglicher Zieltext bleibt in der Herkunftsnotiz erhalten; keine Erklärung zum bestätigten Engpass. |
| Fortsetzung | Aktive eigene Discovery wird fortgesetzt. Fremde Sessions zeigen Zustand und verantwortliche Person sowie den zugänglichen Ideenpfad. Abgelaufene Sessions werden nicht überschrieben; ein neuer Versuch nutzt dieselbe Idee. Vorhandene Prozessanalysen werden geöffnet. |
| Prozesszuordnung | Erfolgreiche, bereits nach bestehendem Vertrag zulässige Materialisierung liest die Ursprungsidee unter Sperre und bindet deren Vorhaben über `bind_initiative()`. Keine Vorhaben-ID aus Request-Parametern. Unzulässige Zuordnung rollt die gesamte Materialisierung zurück. |
| Datenkontinuität | Wiederholung und konkurrierende Materialisierung liefern denselben Prozess. Widersprüchliche bestehende Zuordnungen werden abgelehnt. Historische abgeschlossene, ungebundene Analysen werden nicht nachträglich umgeschrieben. |
| Navigation | Vorhaben → Idee/Discovery/Prozess sowie Rücklinks aus Idee, Discovery-Start, Review und Prozess. Kein zusätzliches Lifecycle-Modell. |
| Rechte | Business Owner: eigenes Vorhaben; KI-Koordination: bestehende erweiterte Bearbeitung. Fremder Business Owner/Leser erhalten keinen Start-CTA. Session-Ownership und Domain-Bindungsrechte bleiben bestehen. |
| Legacy / direkte Use Cases | Bestehende Ideen-/Intake-/Materialisierungs-/Migrationsregressionen bestehen. Kein globaler Zwang zu Idee oder Vorhaben und keine neue Freigabe aus dem Einstieg. |

## PostgreSQL und technische Prüfungen

Lokaler separater PostgreSQL-Testbestand `test_ki_radar_issue177`, keine Produktdaten:

```text
uv run pytest -vv --reuse-db --no-cov
  tests/test_issue_177_initiative_discovery.py
  tests/test_idea_autonomous_discovery.py
  tests/test_issue_145_initiatives.py
  tests/test_issue_98_autonomous_business_discovery.py

101 passed, 11 warnings in 126.08s
```

Die 13 neuen Fälle prüfen Minimalanlage, Rollen-Gegenproben, Vorbelegung,
Wiederverwendung/Ownership/Expiry, mehrdeutige Herkunft, konfliktierende Bindung,
erfolgreiche und unberechtigte Materialisierung, historische abgeschlossene Sessions,
Konflikte im gespeicherten Ergebnis und echte PostgreSQL-Parallelität für Start und
Materialisierung. Bestehende Regressionen prüfen zusätzlich direkte Intake-Pfade,
Retention, Migrationen, Scope- und Fokuskonflikte und unveränderte Readiness.

Zusätzlich erfolgreich: Lockfile-Prüfung, Ruff-Lint/Format, Django-Systemprüfung,
Prüfung auf fehlende Migrationen und `git diff --check`.
Die vollständige unveränderte GitHub-CI einschließlich Gesamtsuite, Security-Prüfungen,
Compose und beider Container-Builds wird über die Checks in PR #180 nachgewiesen;
das endgültige Ergebnis und der konkrete Lauf werden dort kommentiert.

## Sichtbare Browserprüfung

Headed Chromium, Playwright CLI, **1440×1000 px**, isolierte SQLite-UI-Datenbank.
Die Datenbank- und Parallelitätsregressionen liefen getrennt auf PostgreSQL.
Minimalanlage, editierbares Geschäftsziel, Start, Rückweg, Fortsetzung derselben
Session, Scope-Materialisierung, Prozess und Rückweg wurden tatsächlich geklickt.
Am Prozess gemessen: Viewport 1440×1000, Dokumentbreite 1425 px; kein horizontaler
Überlauf. Screenshots wurden visuell geprüft.

**0 echte LLM-Aufrufe.** Ein zunächst verwendeter deterministischer Provider-Draft
konvergierte im bestehenden Review nicht. Für den positiven Materialisierungsnachweis
wurde deshalb der vorhandene Testhelfer `_approved_analysis()` mit dem gespeicherten
Discovery-Quellenstand verwendet, wie im Issue für Stufe 1a vorgesehen. Das ist ein
synthetischer freigegebener Fixture-Fall, kein Nachweis strategischer Readiness oder
realer Geschäftsevidenz. Es wurde kein Gate verändert. Die anschließende Investigation
bleibt ohne Worker bei „Start angefordert“; es fand keine Modellverarbeitung statt.

1. [Minimalanlage](issue-177/issue177-01-create.png)
2. [Vorbelegter Discovery-Start](issue-177/issue177-02-start.png)
3. [Bestehender freigegebener Review-Fixture](issue-177/issue177-03-approved-review.png)
4. [Fortsetzung vom Vorhaben](issue-177/issue177-04-resume.png)
5. [Materialisierung / Investigation angefordert](issue-177/issue177-05-investigation.png)
6. [Gebundener Prozess mit Rücklinks](issue-177/issue177-06-process.png)
7. [Zurück beim Vorhaben mit Prozessaktion](issue-177/issue177-07-linked-initiative.png)

## Verbleibende Grenzen

- Strategische Discovery-Readiness und `waiting_human` gehören weiterhin zu #178.
- Die globale Fokusentscheidung der bestehenden Discovery wird nicht zur
  vorhabensbezogenen Freigabe umgedeutet. Der gebundene Prozess zeigt vorhandene
  offene Fokus-/Evidenzfragen und bleibt als Entwurf bearbeitbar.
- Mehrere historische Ideen benötigen eine ausdrückliche Auswahl. Fremde Sessions
  werden nicht übernommen; ihre verantwortliche Person muss fortsetzen.
- Bestehende Django-6.0-Deprecation-Warnungen bleiben außerhalb dieses Issues.
- Merge erst nach vollständiger grüner CI und menschlichem Review; PR bleibt Draft.
