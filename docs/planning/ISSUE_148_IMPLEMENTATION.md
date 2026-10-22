# #148 – AI-first-Hypothesen, Capability-Tests und Learning Value

**Auftrag:** Nutzer hat die bisher nur optionale #148-Capability am 22.10.2026 ausdrücklich priorisiert. Umsetzung auf Basis von ADR 0009, #145–#147 und AGENTS.md. Keine neue operative Experiment- oder Freigabe-Journey.

## Relevante bestehende Verträge

- `ImprovementInitiative` ist weiterhin der einzige führende Träger des Geschäftsergebnisses.
- `SolutionOption` / `SolutionSelectionDecision` bleiben technologieoffen: Eine KI-Experimentnotiz legt keine bevorzugte KI-Lösung fest.
- `InitiativeImpactReview` und `UseCase.metric_*` bleiben exklusiv für Business-/Prozesswirkung und deren Belege; **Learning Value ist davon getrennt**.
- Bestehende Datenschutz-/Security-/Rollen-, Pilot-/Go-live- und Approval-Gates werden nicht verändert. Keine Änderung an outcome_contract_version oder historischen Fällen.

## Kleinster technisch tragfähiger Schnitt

`CapabilityExperiment` ist ein **optionaler, nicht bindender** Nachweis pro Verbesserungsvorhaben:

1. AI-first-Zielhypothese und erste realistisch betreibbare Ausbaustufe separat; beide dürfen zunächst fehlen.
2. Testbare Capability-Hypothese, konkrete Fall-IDs, separat deklarierte bisher unverbrauchte Holdout-Fall-IDs, Konfigurationsstand, Fehlerbilder, Daten-/Systemannahmen, Aufwand und Quellreferenz.
3. Synthetische Testdaten vs. Real-Daten unterscheidbar; für dokumentierten Abschluss eines Real-Daten-Tests eine Governance-Referenz erforderlich. Die Anwendung verarbeitet **keine Falldaten, versendet nichts an Modelle und genehmigt keine reale Datennutzung**. Governance-Referenzen sind **kein Ersatz** für tatsächliche Freigaben.
4. Ergebnis darf *gestützt*, *teilweise* oder *nicht gestützt* sein, niemals automatisch `AI is preferred`. Learning Value beschreibt überprüfbare neue Erkenntnisse und darf nicht als ROI/Geschäftserfolg ausgegeben werden.
5. Jeder Entwurf kann unvollständig gespeichert/weiterbearbeitet werden; erst der **bewusste** fachliche Nachweis verlangt Beispiel- und Holdout-Referenzen, Erklärung der Unverbrauchtheit, Ergebnis, Lernwert und Evidenz. Die Anwendung kann Unverbrauchtheit **nicht selbst überprüfen** – es bleibt ein explizites menschliches Attest.
6. Fachlich dokumentierte Datensätze sind unveränderlich; **sachliche Berichtigungen** werden als eigene, unveränderliche Nachtragsnotiz (alter/richtiger Wert und Grund, Person, Zeit) an den ursprünglichen Befund angehängt. Sie ändern weder die ursprüngliche Evidenz noch Governance-Freigaben. **Echte Retests** werden als neue Nachweise mit Referenz auf den früheren Test erfasst und brauchen bislang nicht verwendete Holdout-IDs. Fall-IDs bleiben reine opaque Referenzen, kein Cases-Repository und kein Live-Testmotor.
7. Berechtigungen entsprechen dem vorhandenen `can_edit_initiative`-Vertrag; bestehende Initiative-Lesesichtbarkeit bleibt. Für die Review-Form gilt die gleiche Desktop-UI-Archetypik wie für andere Vorhabensformulare.

**Bewusste Nicht-Ziele:** Kein Modell-Aufruf, keine automatisierte Datenweiterleitung/Dateiablage, kein neuer Experiment-Lifecycle, kein Test-Runner, keine doppelte Wirksamkeitsmessung, keine KI-Pflicht, keine neue Freigaberolle, keine Vorab-ROI-Berechnung.

## Abnahme / Regression

`tests/test_issue_148_capability_learning.py` deckt Entwurf, menschliches Capability-Attest, Gegenbeispiele, synthetisch/real, separate Governance-Referenz, Holdout-Überlappung und neue Nachtestfälle, Schutz finaler Records, Leserechte, UI-Eingaben bei Ablehnung und Nichtbeeinflussung von Geschäfts-Outcome/Freigaben ab. Bei PR-Abnahme sind die bestehenden CI- und Migrationstests nachzuweisen. Kein lokaler Checkout war über den verbundenen GitHub-Zugang erreichbar; **keine lokalen Vollsuite-Ergebnisse behaupten**.

## Gegenprüfung #144–#148 (Perplexity, 22.10.2026)

- Geprüfte Capability-Befunde erscheinen **rein lesend** bei der Lösungsauswahl für dieselbe Initiative, ausdrücklich ohne automatische KI-Präferenz, neue Gates oder Änderung historischer Snapshots. Ungeprüfte Entwürfe bleiben dort unsichtbar.
- Bei sachlich falscher Testklassifikation oder Referenz wird ein **append-only Korrekturvermerk** statt eines künstlichen Nachtests erfasst; echte Nachtests brauchen weiterhin neue Holdout-Fälle.
- Getrennte Verbesserungen für den Business-Impact-Review (nachweisgebundener positiver Vorhabensabschluss; kein Stale bei reinen Use-Case-Metadaten) werden in [PR #154](https://github.com/Satte882/KI-Ideenwerkstatt/pull/154) geprüft und **nicht** in #148 verdoppelt.
