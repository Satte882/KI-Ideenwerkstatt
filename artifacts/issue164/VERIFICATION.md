# Issue #164 – Prüfstand

Die fachlich freigegebene Variante A trennt bestehende und neue Vertragskohorten anhand gespeicherter Versionen. Keine Bestandsmigration, keine Pfadableitung aus Freitext und keine Änderung an Freigabe-/Auswahlrechten.

| Vertrag | Bestand | Neue Value-Stream-Erfassungen / Läufe |
| --- | --- | --- |
| Capture-Katalog | 1.0 | 2.0 |
| Antwortformat / Extraktionsschema | 1.0 / 1.0 | 1.0 / 1.0 (gleiche Struktur) |
| Extraktionsprompt | 1.0 | 2.0 |
| Strukturierte Prozessinterpretation | 1 | 2 |
| Discovery-Schema / Prompt | ap1-discovery-v1 / ap1-methodology-v13 | ap1-discovery-v2 / ap1-methodology-v14 |
| Generatorquellen | block7_sources_v1 | block7_sources_v2 |
| Generatorschema / Prompt | 1.0 / 1.3; historisches Lesen auch 1.2 | 2.0 / 2.0 |
| Quality-Vertrag / Critic / Repair | 1.1 / 2.0 / 1.4 | 1.2 / 2.1 / 1.5 |
| Investigation-Übernahme | 1.0 bei fehlendem historischen Marker | 2.0 im unveränderlichen Ausführungssnapshot |

Unveränderte Use-Case-Kataloge bleiben bei 1.0. Ein neuer Generatorlauf auf einem bestehenden Prozess verwendet den neuen Vertrag; ein bestehender Lauf behält seine Kohorte. Strategische Entwurfsreife verlangt die vorhandene menschliche Pfadrevision mit Herkunft, Potenzial und Validierungsschritt. Der Problem-Pfad behält Engpass-/Baseline-Anforderungen. Kein Potenzial wird als bestätigte Ursache oder Wirkung übernommen.

## Automatisierte Nachweise

- PostgreSQL 17.5, Python 3.13, Django 5.2.17; ausschließlich Test-Doubles für Provideraufrufe.
- 75 gezielte Vertrags-, Adoptions-, Sicherheits- und Regressionsprüfungen bestanden: `targeted-postgres.log`.
- 71 Prüfungen für neue strategische Abläufe, eingefrorene Antworten, Extraktion und Candidate-Snapshots bestanden: `extraction-postgres.log`.
- 66 Discovery-/Methodik-/Realantwort-Replays bestanden: `replay-postgres.log`. Die historischen Realantworten werden unverändert unter ihrem v1-Vertrag abgespielt; keine neuen Modellaufrufe.
- Der aus unverändertem main (`2cbba9b1f368947c3333b6ecacaeae662cb4a2b3`) abgeleitete Golden-Nachweis `tests/fixtures/accelerator/issue164_legacy.json` friert Katalog, Antwort-Hash, Quellpayload und Quality-Hash ein.
- Ruff, Format, Django-Systemprüfung und Migrationsprüfung bestanden. Migration 0025 verändert nur die Feldvalidierung im Django-Zustand; PostgreSQL-SQL ist ein No-op. Alte Form-/Übernahmeverträge behalten ihre Pflichtangaben.
- Die vollständige Suite umfasst 2479 Tests. Der abschließende Status wird im PR und dessen CI-Checks ausgewiesen.

## Echte Desktop-Browserprüfung

Headed Chromium über Playwright CLI, ausschließlich 1440×1000 und 1024×1000 px. Alle zwölf geprüften Ansichten HTTP 200, kein horizontales Überlaufen. Neue Phasen-/Prozess-/Lösungsfragen, gespeicherte v1-Fragen sowie v1-/v2-Lösungsvorschauen visuell geprüft. Leere Diagnose im neuen Katalog gespeichert und nach Neuladen weiterhin leer; keine Formularfehler. Die neuen Quellen zeigen die menschliche Pfadentscheidung samt Revision, Potenzial und Validierungsschritt. Übernahmeaktionen bleiben explizite menschliche Aktionen.

Die Daten und Vorschauen sind synthetisch; diese Prüfung ist keine Realmodell-Evaluation. Kein Tablet-/Handy-Test und keine entsprechende UI-Arbeit. `DESIGN.md` enthält auf zusätzliche Nutzeranweisung jetzt diese dauerhafte Desktop-Grenze.

Details: `desktop-verification.json`. Die PNG-Dateien zeigen beide Breiten; `current-preview-sources-*.png` und `current-preview-adoption-*.png` sind lesbare Desktop-Ausschnitte der langen Vorschau. Bereits in v1 vorhandener Konsolenhinweis: Der Inline-Stil des Fortschrittsbalkens wird durch CSP blockiert. Keine neue Ausnahme und keine Lockerung der CSP.
