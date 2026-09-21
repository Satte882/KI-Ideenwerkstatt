# Gap-Analyse zu Issue #308

**Basis:** `main` auf Commit `7d37c919782e3ecca00fa1b16b4adb66bd2d5d85`  
**Scope:** methodische Guardrails und kontextsensitive Hilfe für die bestehende Value-Stream-Journey

## Ergebnis je Pflichtfrage

1. **Start und Darstellung der geführten Value-Stream-Erfassung:** Der Einstieg läuft über `accelerator.views.start_capture()` und `templates/accelerator/capture_start.html`; die eigentliche mehrstufige Erfassung über `accelerator.views.capture_step()` und `templates/accelerator/capture_wizard.html`. Der bestehende Capture-Typ trennt `value_stream` und `use_case`, sodass die Methodik-Hilfe gezielt nur für Value Streams eingeblendet werden kann.
2. **Wiederverwendbare Help-/UI-/Dokumentationspatterns:** Feldbezogene Hinweise werden bereits über Django-`help_text` und `.form-text` dargestellt. Page-Header verwenden ruhige Sekundäraktionen mit `btn btn-outline-secondary`. Bootstrap 5.3 inklusive Bundle ist global vorhanden und kann für eine kompakte Modal-Hilfe ohne neue JavaScript-Infrastruktur verwendet werden. Für versionierte Methodik existiert mit `docs/DELIVERY_METHODOLOGY.md`, `delivery.views.methodology_reference()` und `methodology_download()` bereits das Pattern „Repository-Markdown als kanonische Quelle plus In-App-Referenz/Download“.
3. **Bestehende Hilfetexte:** `accelerator/catalogs.py` erklärt bereits Trigger/Outcome, Scope-In/Scope-Out, Stakeholder/Leitplanken sowie Phasen, verwendet bei `vs_stages` aber noch primär die Formulierung „Aktivität, Ergebnis und Reihenfolge“. `ValueStreamForm` erklärt Scope-In/Scope-Out und Rollen; `ValueStreamStageForm` besitzt aktuell keine feldbezogenen Help-Texte. `stage_form.html` beschreibt eine E2E-Phase bereits allgemein als Wertbeitrag und Kontext, rendert jedoch bislang keine `help_text`-Zeile je Feld.
4. **Tatsächliche Score-Felder:** `ValueStreamFocus` verwendet `strategic_impact`, `economic_potential`, `pain_intensity`, `data_accessibility` und `change_effort`. Die Fokusphasen-Priorisierung verwendet `impact`, `pain_intensity`, `data_accessibility` und `change_effort` je Stage. Beide Pfade verwenden `core.taxonomy.ScreeningLevel` mit `LOW/MEDIUM/HIGH` = `Niedrig/Mittel/Hoch`; es gibt in diesen Pfaden keine numerische 1–5-Skala.
5. **Fachlich kompatible Skalenanker:** Die bestehende dreistufige Semantik bleibt unverändert. Anker werden kriterienspezifisch formuliert, weil „Hoch“ je Kriterium unterschiedlich wirkt: hoher Impact/Pain bedeutet hohe Relevanz bzw. hohen Handlungsbedarf, hohe Datenzugänglichkeit eine gute Ausgangslage, hoher Veränderungsaufwand dagegen hohen Aufwand. Eine Umstellung auf 1/3/5 findet nicht statt.
6. **Ort der Methodik-Dokumentation:** `docs/VALUE_STREAM_METHODOLOGY.md` ergänzt die bestehende `docs/`-Struktur und folgt der englischen Dateinamenskonvention von `DELIVERY_METHODOLOGY.md`; der Inhalt bleibt deutschsprachig passend zur Value-Stream-Journey. Es wird keine zweite Dokumentationsstruktur eingeführt.
7. **Download ohne Drift:** `docs/VALUE_STREAM_METHODOLOGY.md` bleibt die einzige vollständige Methodikquelle. Ein Download liest diese Datei direkt aus dem Repository-Arbeitsbaum. Die In-App-Modal-Hilfe ist bewusst nur ein kurzer Cheat Sheet und keine zweite Vollkopie der Methodik.

## Wiederverwendung bestehender Vorarbeiten

- **#54:** Die vorhandene `StageFocusDecision`-Journey zur Auswahl der Fokusphase bleibt führend und unverändert.
- **#57:** Bestehende getrennte Felder `scope_in` und `scope_out` werden weiterverwendet; keine parallelen Scope-Felder.
- **#119:** Die persistente, wiederaufnehmbare Capture-Session und der versionierte Fragenkatalog bleiben unverändert die geführte Erfassung; keine zweite Erfassungsschicht.
- **#122:** Bestehende strukturierte Adoption in Value-Stream-Phasen und `ProcessAnalysis`-Entwürfe bleibt der Übernahmepfad; keine neuen Entwurfsobjekte oder Fokusentscheidungen.

## Abgrenzung vorhandener Provenance

`ki_radar/architecture/provenance.py` bildet Herkunftssnapshots fachlicher Stage-, ProcessAnalysis- und Use-Case-Felder und erkennt spätere Quelldifferenzen. Diese Provenance ist nicht für Methodikversionierung zuständig und bleibt in Issue #308 unverändert. Die Methodikversion wird ausschließlich im versionierten Repository-Dokument geführt.

## UX-Entscheidung

Für Value-Stream-Capture wird **„Methodik & Beispiel“ sowohl auf der Startseite als auch im laufenden Wizard** als ruhige Sekundäraktion angeboten. Beide Einstiege öffnen dieselbe kompakte Modal-Hilfe. Der Use-Case-Capture erhält diese Aktion nicht. Die primäre Journey und ihre bestehenden Aktionen bleiben unverändert.

## Umsetzungsentscheidung

- Keine neuen Domain Models, Lifecycle-Zustände, Fokusentscheidungen oder Pflichtfelder.
- Keine Datenbankmigration.
- `Entrance → Transformation → Value Item → Exit` bleibt Denkmodell, nicht Datenmodell.
- `Business Importance × Transformation Need` wird als pragmatische Auswahlheuristik erklärt, nicht als Portfolio- oder Scoring-Modul implementiert.
- Bestehende `ScreeningLevel`-Werte bleiben unverändert; nur Help-Texte/Skalenanker werden ergänzt.
- KI bleibt eine mögliche Lösungsoption nach Prozess-/Problemanalyse; kein AI-Suitability-Gate.
- Keine neue allgemeine Help-Infrastruktur; vorhandene Bootstrap-, Form-Help- und Markdown-Download-Patterns werden wiederverwendet.

## Abnahmekriterien → Nachweis/Test

| AC | Kriterium | Geplanter Nachweis |
|---|---|---|
| AC1 | Gap-Analyse gegen aktuellen `main` dokumentiert | diese Datei |
| AC2 | #54/#57/#119/#122 werden wiederverwendet und nicht dupliziert | Architektur-/Diff-Review plus bestehende Regressionstests |
| AC3 | „Methodik & Beispiel“ leicht erreichbar | UI-Test für Value-Stream-Start und -Wizard; Negativtest für Use-Case-Capture |
| AC4 | Hilfe erklärt Begriffe, Trigger/Outcome, Scope, Granularität und Stage-Wertfortschritt | Content-Test der gemeinsamen Modal-Hilfe |
| AC5 | `Business Importance × Transformation Need` wird erklärt, ohne Pflichtmodul | Content-Test; keine neuen Form-/Model-Felder |
| AC6 | Stage-Erfassung enthält Wertfortschritt-/Vorher-Nachher-Hinweis | Test für Capture-Katalog und reguläres Stage-Formular |
| AC7 | keine neuen Pflichtfelder | Form-/Capture-Regression und Migrationscheck |
| AC8 | relevante qualitative Scores besitzen verständliche Anker | Form-/UI-Test für Value-Stream- und Stage-Fokus |
| AC9 | Score-Semantik bleibt unverändert | Assert auf `ScreeningLevel`-Choices und bestehende Feldwerte |
| AC10 | kein neues AI-Suitability-Gate | Architektur-/Journey-Regression |
| AC11 | kompakte Methodik versioniert im Repo | `docs/VALUE_STREAM_METHODOLOGY.md` mit sichtbarer Version |
| AC12 | Download nutzt dieselbe Quelle / keine driftanfällige Doppelpflege | Download-Test gegen Dateiinhalt |
| AC13 | keine neue BA-/Portfolio-/Capability-/Regel-Engine | Diff-Review und Migrationscheck |
| AC14 | bestehende Tests bleiben grün; neue Navigation-/Help-Regressionen | vollständige CI plus neue Issue-#308-Tests |

## Verbindliche Scope-Guards für Review

1. `python manage.py makemigrations --check --dry-run` muss ohne neue Migration enden.
2. Keine Änderungen an `models.py`, Journey-State, Approval, Governance oder Delivery-Gates sind für #308 vorgesehen.
3. Neue Tests müssen mindestens die Value-Stream-spezifische Sichtbarkeit der Methodik-Hilfe, den Markdown-Download, Stage-Wertfortschritt und die bestehende Screening-Semantik abdecken.
4. Bei einem fehlgeschlagenen CI-Lauf werden zuerst alle relevanten Workflow-Läufe und Job-Logs vollständig ausgewertet; Fixes werden anschließend gesammelt in einem Commit vorgenommen. Eine Ausnahme gilt nur, wenn ein Fehler Folge-Jobs technisch blockiert und deren Ergebnisse deshalb nicht entstehen.
