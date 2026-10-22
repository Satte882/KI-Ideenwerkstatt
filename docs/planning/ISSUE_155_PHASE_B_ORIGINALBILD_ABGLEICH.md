# Issue #155 – eigenständiger Abgleich aller 60 Originalbilder

Am 22.10.2026 wurden **alle 60 unveränderten Originale vor den Produktänderungen einzeln visuell geöffnet**. Die folgende Tabelle dokumentiert das Ergebnis je Datei. Metadaten/Hash/Original-URL stehen im [Phase-A-Manifest](ISSUE_155_SCREENSHOT_MANIFEST.json); die direkten Bildlinks im [Originalindex](ISSUE_155_SCREENSHOT_INDEX.md).

Ein Screenshot belegt sichtbare UI-Zustände. Er beweist weder Abrechnung noch HTTP-Berechtigungen oder fachliche Modellqualität. Die Rollen- und Netzwerkprüfungen wurden deshalb in Phase B erneut ausgeführt.

| Originaldatei | Visueller Abgleich |
| --- | --- |
| `01-bottom-idea.png` | Ideen-Einstieg nachvollziehbar; ursprüngliche Beschreibung sichtbar. |
| `02-discovery-start.png` | Discovery übernimmt den Ausgangskontext; noch keine verbindliche Lösungswahl. |
| `03-compare-before.png` | Bindende Auswahl trotz offenem Outcome angeboten: F3 bestätigt. |
| `04-compare-error.png` | Konkreter Outcome-Blocker erst nach POST; eingegebene Begründung bleibt sichtbar: F3. |
| `05-draft.png` | Outcome-Entwurf möglich; Hauptbereich Use Cases ohne passende lokale Position: F4. Formularumfang bleibt V1. |
| `06-load-loss.png` | Gespeicherter Stand geladen. Allein kein sicherer Verlustbeweis; dafür gezielt 29/30 heranziehen. |
| `07-ki-selection.png` | KI-Auswahl und automatisch vorbereitete Planung sichtbar: F5-Kontext. Aufruf/Kosten benötigen das separate Log. |
| `08-initiative.png` | Vorhaben unter Use Cases ohne passende lokale Position: F4. Prozessmetriken und Geschäftswirkung getrennt. |
| `09-capability-error.png` | Capability-Validierungsfehler sichtbar; falsche Navigationszuordnung: F4. |
| `10-capability-reviewed.png` | Geprüfter Capability-Nachweis bleibt getrennt von KI-/Betriebsfreigabe und Geschäftsnutzen. |
| `11-impact-error.png` | Wirkungsprüfung zeigt Fehler und trennt Prozess-/Geschäftsgröße; lokale Einordnung fehlt: F4. |
| `13-strategic-compare.png` | Strategischer Vergleich mit gleichwertigen KI-/Non-KI-Alternativen. |
| `14-nonki-selection.png` | Gültiger Non-KI-Endzustand ohne KI-Use-Case. |
| `16-nonki-reviewed.png` | Non-KI-Wirkungsprüfung getrennt vom Geschäftsergebnis dokumentiert. |
| `17-direct-approval.png` | Direkte Freigabe zeigt Outcome-Blocker und Personentrennung. |
| `18-direct-return.png` | Nach Outcome-Rückweg bleibt Personentrennung bestehen; keine automatische Freigabe. |
| `19-bottom-discovery-review.png` | Mock-Discovery enthält Supplier-Sourcing-Vorlage. Bediennachweis, kein Beleg fachlicher Modellqualität. |
| `20-bottom-investigation.png` | Investigation startet mit autorisierter Grundlage; kein Nachweis ausgeführter echter Untersuchung. |
| `21-bottom-materialized-process.png` | Materialisierter Prozess mit lokaler Analyse-Navigation nachvollziehbar. |
| `22-bottom-e2e-ki.png` | KI-Auswahl meldet blockierten impliziten Planungsaufruf: F5. |
| `23-bottom-usecase-gates.png` | Use-Case-Gates bleiben sichtbar; Entwurf ist keine Freigabe. |
| `24-top-discovery.png` | CEO-Einstieg enthält dieselbe Mock-Problemvorlage; strategische Herkunft muss bewusst dokumentiert werden. |
| `25-top-process.png` | Strategischer Prozesskontext nachvollziehbar; keine bestätigte Ursache erfinden. |
| `26-top-e2e-nonki.png` | Non-KI-Auswahl als abgeschlossener Analysepfad sichtbar. |
| `27-top-nonki-reviewed.png` | Non-KI-Prozesswirkung und Geschäftsergebnis werden getrennt beurteilt. |
| `28-bottom-ki-reviewed.png` | KI-Prozessmetrik und eigenständige Geschäftswirkung getrennt; Vorhabensnavigation weiterhin F4. |
| `29-load-before.png` | UNSAVED-155 vor Laden sichtbar: gezielter Ausgangsbeleg für F1. |
| `30-load-after.png` | UNSAVED-155 ohne Ersetzen-Wahl verschwunden: F1 bestätigt. |
| `31-prepare-error.png` | VALIDATION-155 bleibt nach ungültigem POST erhalten; kein Eingabeverlust in diesem Fall. |
| `32-prepare-1024.png` | Ungültige Eingabe bleibt erhalten; Marke/Navigation bei 1024 px tatsächlich abgeschnitten: F6, lokale Einordnung F4. |
| `34-compare-1024.png` | Vergleich bei 1024 px inhaltlich nutzbar; Seitennavigation abgeschnitten: F6. |
| `35-draft-path-before.png` | Geänderte Entwurfsherkunft und strategisches Potenzial vor Speichern sichtbar: Ausgang für F2. |
| `36-draft-path-after.png` | Nach Speichern alter verbindlicher Kontext statt Entwurf sichtbar: F2 bestätigt. |
| `37-draft-recovered.png` | Vorhabenstitel wiedergefunden, Entwurfs-Pfadkontext weiterhin verloren: F2. Wiederfinden bleibt V2. |
| `38-sidebar-1024-viewport.png` | Echter 1024-Pixel-Viewport bestätigt abgeschnittene Marke/Beschriftung: F6, kein Fullpage-Artefakt. |
| `layout-1024-capability.png` | 1024-Pixel-Layout: Inhalt umbrechend nutzbar, abgeschnittene Seitennavigation bestätigt F6. Lokale Outcome-Einordnung fehlt: F4. |
| `layout-1024-impact.png` | 1024-Pixel-Layout: Inhalt umbrechend nutzbar, abgeschnittene Seitennavigation bestätigt F6. Lokale Outcome-Einordnung fehlt: F4. |
| `layout-1024-initiative.png` | 1024-Pixel-Layout: Inhalt umbrechend nutzbar, abgeschnittene Seitennavigation bestätigt F6. Lokale Outcome-Einordnung fehlt: F4. |
| `layout-1024-topCompare.png` | 1024-Pixel-Layout: Inhalt umbrechend nutzbar, abgeschnittene Seitennavigation bestätigt F6. |
| `role-coordinator-capability.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-coordinator-compare.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-coordinator-direct.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Direkter Use-Case-Kontext nachvollziehbar. |
| `role-coordinator-initiative.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-coordinator-process.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-coordinator-topCompare.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-coordinator-topProcess.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-owner-capability.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-owner-compare.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-owner-direct.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Direkter Use-Case-Kontext nachvollziehbar. |
| `role-owner-initiative.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-owner-process.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-owner-topCompare.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-owner-topProcess.png` | Owner-/Koordinationsansicht mit den sichtbaren rollenabhängigen Aktionen. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-reader-capability.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-reader-compare.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-reader-direct.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Direkter Use-Case-Kontext nachvollziehbar. |
| `role-reader-initiative.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Vorhaben/Capability unter falschem Bereich ohne lokale Einordnung: F4. |
| `role-reader-process.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-reader-topCompare.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |
| `role-reader-topProcess.png` | Leseransicht ohne angebotene Bearbeitung/Generierung/Auswahl. Analyse-Hauptbereich und lokale Prozess-/Vergleichsposition stimmen. |

Alle F1–F6 sind nachvollziehbar. F1 ist besonders durch 29/30, F2 durch 35/36/37, F3 durch 03/04 und F6 durch den echten Viewport 38 belegt. Für F5 bleiben Log und Aufrufprüfung entscheidend. V1–V3 bleiben ausdrücklich außerhalb dieser Umsetzung.

