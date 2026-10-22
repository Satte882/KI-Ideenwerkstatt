# Screenshot-Index zu Issue #155 – Phase A

[Zum Prüfbericht](ISSUE_155_PHASE_A_UX_ABNAHME.md) · [Draft-PR #156](https://github.com/Satte882/KI-Ideenwerkstatt/pull/156)

60 unveränderte Originalbilder. Suchbar nach **F1–F6 / V1–V3**, Dateiname, Journey, Rolle und Desktopbreite. Der Index dokumentiert Belege; er ist keine Freigabe für Phase B.

## Befunde gezielt finden

| Befund | Beobachtung | Bilddateien |
| --- | --- | --- |
| F1 | Eingabeverlust beim Vorhabenladen | `06-load-loss.png`, `29-load-before.png`, `30-load-after.png` |
| F2 | Entwurf verliert Herkunft/Potenzial | `35-draft-path-before.png`, `36-draft-path-after.png` |
| F3 | Outcome-Gate erst nach Absenden | `03-compare-before.png`, `04-compare-error.png` |
| F4 | Fehlende semantische Navigationsmarkierung | `05-draft.png`, `08-initiative.png`, `10-capability-reviewed.png`, `31-prepare-error.png`, `32-prepare-1024.png`, `layout-1024-capability.png`, `layout-1024-impact.png`, `layout-1024-initiative.png`, `role-coordinator-capability.png`, `role-coordinator-initiative.png`, `role-owner-capability.png`, `role-owner-initiative.png`, `role-reader-capability.png`, `role-reader-initiative.png` |
| F5 | Indirekter Modellaufruf bei KI-Auswahl | `07-ki-selection.png`, `08-initiative.png`, `22-bottom-e2e-ki.png` |
| F6 | Abgeschnittene Navigation bei 1024 px | `32-prepare-1024.png`, `38-sidebar-1024-viewport.png`, `layout-1024-capability.png`, `layout-1024-impact.png`, `layout-1024-initiative.png`, `layout-1024-topCompare.png` |
| V1 | Umfang und Gliederung des Outcome-Formulars | `05-draft.png`, `31-prepare-error.png`, `32-prepare-1024.png`, `35-draft-path-before.png` |
| V2 | Entwurf wiederfinden | `37-draft-recovered.png` |
| V3 | Bestätigungs- und Fokusstand anzeigen | `08-initiative.png`, `28-bottom-ki-reviewed.png`, `37-draft-recovered.png` |

**Wichtig zu F5:** Bilder zeigen den UI-Kontext. Tokens/Kosten stammen aus dem im Prüfbericht dokumentierten Log; ein Screenshot belegt keine Abrechnung.

## Vollständiger Bildkatalog

Die konkrete bei der Abnahme besuchte Seiten-URL steht pro Bild im Manifest `screenshots.json`. Lokale Test-URLs sind Quellenangaben, keine im Cloud-Kontext erreichbaren Nachweise. Die Originaldateinamen stehen unten eindeutig zugeordnet. GitHub-Direktlinks werden nach dem Upload ergänzt; aktuell blockiert die fehlende Browserberechtigung den Upload.

| Datei / Original | Beschreibung | Journey | Rolle | Viewport | Befunde |
| --- | --- | --- | --- | --- | --- |
| `01-bottom-idea.png` | Bottom-up: Idee | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `02-discovery-start.png` | Discovery-Start und Vorbelegung | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `03-compare-before.png` | Vorprüfung: vor Outcome-Gate | Vorprüfung | Business Owner | 1440 × 1000 | F3 |
| `04-compare-error.png` | Vorprüfung: Fehler nach bindender Auswahl | Vorprüfung | Business Owner | 1440 × 1000 | F3 |
| `05-draft.png` | Vorprüfung: Outcome-Entwurf | Vorprüfung | Business Owner | 1440 × 1000 | F4, V1 |
| `06-load-loss.png` | Vorprüfung: Laden ersetzt Eingabe | Vorprüfung | Business Owner | 1440 × 1000 | F1 |
| `07-ki-selection.png` | Vorprüfung: KI-Auswahl; indirekter Realaufruf siehe Bericht | Vorprüfung | Business Owner | 1440 × 1000 | F5 |
| `08-initiative.png` | Vorhaben nach Vorprüfung | Vorprüfung | Business Owner | 1440 × 1000 | F4, F5, V3 |
| `09-capability-error.png` | Capability: Validierungsfehler | Vorprüfung | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `10-capability-reviewed.png` | Capability: fachlich dokumentiert | Vorprüfung | Business Owner | 1440 × 1000 | F4 |
| `11-impact-error.png` | Wirkungsreview: Intervention fehlt | Vorprüfung | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `13-strategic-compare.png` | Vorprüfung: strategischer Vergleich | Vorprüfung | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `14-nonki-selection.png` | Vorprüfung: Non-KI-Auswahl | Vorprüfung | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `16-nonki-reviewed.png` | Vorprüfung: Non-KI-Review | Vorprüfung | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `17-direct-approval.png` | Koordinator: direkte Freigabe mit Outcome-Blocker | Direkteinstieg | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `18-direct-return.png` | Koordinator: Rücksprung nach Outcome-Zuordnung | Direkteinstieg | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `19-bottom-discovery-review.png` | Bottom-up: deterministischer Discovery-Entwurf | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `20-bottom-investigation.png` | Bottom-up: übernommener Scope / Investigation wartet | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `21-bottom-materialized-process.png` | Bottom-up: materialisierte Prozessanalyse | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `22-bottom-e2e-ki.png` | Bottom-up: verbindliche KI-Auswahl, Provider gesperrt | Bottom-up / KI | Business Owner | 1440 × 1000 | F5 |
| `23-bottom-usecase-gates.png` | Bottom-up: KI-0003 und nächste Gates | Bottom-up / KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `24-top-discovery.png` | Top-down: Discovery-Entwurf | Top-down / Non-KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `25-top-process.png` | Top-down: Prozess, keine bestätigte Ursache | Top-down / Non-KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `26-top-e2e-nonki.png` | Top-down: verbindliche Non-KI-Auswahl | Top-down / Non-KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `27-top-nonki-reviewed.png` | Top-down: Non-KI-Prozesswirkung, Geschäftswirkung ungeklärt | Top-down / Non-KI | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `28-bottom-ki-reviewed.png` | Bottom-up: KI-Prozessmetrik separat referenziert | Bottom-up / KI | Business Owner | 1440 × 1000 | V3 |
| `29-load-before.png` | F1: ungespeicherter Text vor Laden | Bottom-up / KI | Business Owner | 1440 × 1000 | F1 |
| `30-load-after.png` | F1: Text nach Laden verloren | Bottom-up / KI | Business Owner | 1440 × 1000 | F1 |
| `31-prepare-error.png` | Fehlerhafter POST erhält übrige Angaben | Bottom-up / KI | Business Owner | 1440 × 1000 | F4, V1 |
| `32-prepare-1024.png` | 1024 px: Outcome-Formular mit Validierungsfehler | Bottom-up / KI | Business Owner | 1024 × 1000 | F4, F6, V1 |
| `34-compare-1024.png` | 1024 px: Lösungsvergleich | Bottom-up / KI | Business Owner | 1024 × 1000 | Pfad-/Rollenbeleg |
| `35-draft-path-before.png` | F2: neue Herkunft/Potenzial vor Entwurf sichern | Top-down / Non-KI | Business Owner | 1440 × 1000 | F2, V1 |
| `36-draft-path-after.png` | F2: Entwurf gesichert, Herkunft/Potenzial zurückgesetzt | Top-down / Non-KI | Business Owner | 1440 × 1000 | F2 |
| `37-draft-recovered.png` | Ungebundenen Entwurf ohne Direktlink über Vorhabenauswahl wiedergefunden | Top-down / Non-KI | Business Owner | 1440 × 1000 | V2, V3 |
| `38-sidebar-1024-viewport.png` | F6: abgeschnittene linke Navigation bei 1024 px | Top-down / Non-KI | Business Owner | 1024 × 1000 | F6 |
| `layout-1024-capability.png` | 1024 px: capability | Layoutprüfung | Business Owner | 1024 × 1000 | F4, F6 |
| `layout-1024-impact.png` | 1024 px: impact | Layoutprüfung | Business Owner | 1024 × 1000 | F4, F6 |
| `layout-1024-initiative.png` | 1024 px: initiative | Layoutprüfung | Business Owner | 1024 × 1000 | F4, F6 |
| `layout-1024-topCompare.png` | 1024 px: topCompare | Layoutprüfung | Business Owner | 1024 × 1000 | F6 |
| `role-coordinator-capability.png` | Rollenmatrix: coordinator / capability | Rollenmatrix | KI-Koordinator | 1440 × 1000 | F4 |
| `role-coordinator-compare.png` | Rollenmatrix: coordinator / compare | Rollenmatrix | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-coordinator-direct.png` | Rollenmatrix: coordinator / direct | Rollenmatrix | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-coordinator-initiative.png` | Rollenmatrix: coordinator / initiative | Rollenmatrix | KI-Koordinator | 1440 × 1000 | F4 |
| `role-coordinator-process.png` | Rollenmatrix: coordinator / process | Rollenmatrix | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-coordinator-topCompare.png` | Rollenmatrix: coordinator / topCompare | Rollenmatrix | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-coordinator-topProcess.png` | Rollenmatrix: coordinator / topProcess | Rollenmatrix | KI-Koordinator | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-owner-capability.png` | Rollenmatrix: owner / capability | Rollenmatrix | Business Owner | 1440 × 1000 | F4 |
| `role-owner-compare.png` | Rollenmatrix: owner / compare | Rollenmatrix | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-owner-direct.png` | Rollenmatrix: owner / direct | Rollenmatrix | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-owner-initiative.png` | Rollenmatrix: owner / initiative | Rollenmatrix | Business Owner | 1440 × 1000 | F4 |
| `role-owner-process.png` | Rollenmatrix: owner / process | Rollenmatrix | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-owner-topCompare.png` | Rollenmatrix: owner / topCompare | Rollenmatrix | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-owner-topProcess.png` | Rollenmatrix: owner / topProcess | Rollenmatrix | Business Owner | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-reader-capability.png` | Rollenmatrix: reader / capability | Rollenmatrix | Leser | 1440 × 1000 | F4 |
| `role-reader-compare.png` | Rollenmatrix: reader / compare | Rollenmatrix | Leser | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-reader-direct.png` | Rollenmatrix: reader / direct | Rollenmatrix | Leser | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-reader-initiative.png` | Rollenmatrix: reader / initiative | Rollenmatrix | Leser | 1440 × 1000 | F4 |
| `role-reader-process.png` | Rollenmatrix: reader / process | Rollenmatrix | Leser | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-reader-topCompare.png` | Rollenmatrix: reader / topCompare | Rollenmatrix | Leser | 1440 × 1000 | Pfad-/Rollenbeleg |
| `role-reader-topProcess.png` | Rollenmatrix: reader / topProcess | Rollenmatrix | Leser | 1440 × 1000 | Pfad-/Rollenbeleg |

## Herkunft und Integrität

Für jedes Bild enthält `screenshots.json` die konkrete Seiten-URL, Rolle, Viewport, tatsächliche PNG-Maße, Vollseiten-/Viewport-Kennzeichnung, Befundzuordnung und SHA-256. Vollseitenbilder können höher als 1000 Pixel sein. Eine PNG-Breite von 1425 bzw. 1009 Pixeln kann aus dem 1440er bzw. 1024er Viewport nach Abzug der Scrollbar entstehen. Die Bilddateien wurden nicht verändert.

Die Bilder 03–18 sind überwiegend Vorprüfungen; die durchgehenden Journeys sind besonders unter 19–28 dokumentiert. Rollen- und Layoutbelege tragen aussagekräftige Präfixe `role-…` bzw. `layout-1024-…`.
