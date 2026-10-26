# Issue #199 – Bindungsvoraussetzungen und bestehende Vorbereitung

Stand: 26.10.2026. Ausgangspunkt: `main` / `7a96abf9655422d838627847b7cce80fe3d26a7b`.
Referenzen: #199, verbindlicher Re-Audit #196, gemeinsame Handoff-Regression #198.

## Umsetzung

- Der bestehende Aufwandscheck und die Anzeige verwenden dieselbe Liste fehlender
  Optionen. Jede betroffene Option erhält einen konkreten Grund und den bestehenden
  Bearbeitungslink mit Rückkehr zum Vergleich.
- `outcome_blockers(..., require_measurement_plan=True)` liefert dieselbe
  Messabsichtsregel für Vergleich, positive direkte Freigabe und den schreibenden
  Snapshot-Service. Alle fehlenden Outcome-Voraussetzungen werden gemeinsam benannt.
- Historische Aktualitätsvergleiche und der strategische Herkunftsrahmen behalten
  ihre bisherigen Verträge ohne nachträgliche Messplanpflicht. Fehlende Messabsicht
  erzeugt deshalb keinen irreführenden zusätzlichen Screeningblocker.
- Die bestehende `OutcomePreparationForm` erfasst die fünf `PLAN_FIELDS` und
  `measurement_change_reason` auf demselben Vorhaben. Ein vollständiger Plan oder
  begründet offene Messangaben bleiben zulässig. Keine neue Baseline-, ROI- oder
  Zahlenpflicht und kein zusätzliches Modell, Formularziel oder Speicherverfahren.
- Änderungsschutz, fachliche Wiederbestätigung, Entwurfssicherung, Revisionsticket,
  Rechte und historische Snapshots laufen weiterhin über die vorhandenen Services.

## Ausgeführte Verifikation

`tests/test_issue_199_binding_prerequisites.py`: **10 PostgreSQL-Fälle bestanden**:

1. Nur Aufwand fehlt: benannte Option, erreichbarer Editor, Rückkehr zum Vergleich,
   serverseitige Ablehnung eines trotzdem gesendeten Requests; danach erfolgreiche Wahl.
2. Nur Messabsicht fehlt: Vorprüfung und Snapshot-Service melden denselben fachlichen
   Mangel. Problem- und Strategiepfad jeweils mit vollständigem Plan oder begründeten
   Unknowns über die bestehende Vorbereitung korrigiert; anschließende echte Auswahl.
3. Echte strategische Materialisierung bei offenem globalem Screening: nur fehlende
   Messabsicht angezeigt; Ergänzung und Non-KI-Auswahl ohne erfundene Diagnose.
4. Direkter Use Case: bestehende Vorbereitungs- und Freigaberoute; fehlende Messabsicht
   in Vorprüfung und Service abgelehnt, nach Ergänzung unabhängige Freigabe erfolgreich.
5. Veraltete Revision und fehlende Änderungsbegründung erhalten alle Plan- und
   Geschäftstexte. Leserzugriff auf GET und POST bleibt verboten.
6. Unvollständiger früher Messplan bleibt als Entwurf speicherbar und wiederaufnehmbar;
   ausdrückliche Bestätigung und unveränderter Rückweg erhalten den Outcome-Vertrag.
7. Legacy-Auswahl erhält keine neue Messplanpflicht.

Zusätzlich **134 bestehende PostgreSQL-Regressionen bestanden** aus #146, #171,
#183 einschließlich #198, #185, #188 und #189. Damit sind unter anderem strategischer
KI-Handoff/Wiederaufnahme, problemgetriebene Diagnose, Kontextübernahme, Materialität,
Altverträge, Messplan und unabhängige Freigabe mitgeprüft.

Ruff, Formatprüfung, Django-Systemcheck und Migrationsprüfung bestanden;
keine Migration erforderlich. Die vollständige GitHub-CI wird im zugehörigen PR
für dessen aktuellen Commit geprüft, einschließlich PostgreSQL-Gesamtsuite,
Architecture-Real-DEMO-E2E, Security-/Abhängigkeitsprüfungen, Compose und Docker-Builds.
Der konkrete Lauf und sein Endergebnis stehen im PR.

## Desktop und Aussagegrenzen

Playwright-Prüfung bei **1440 × 1000** in einer isolierten synthetischen SQLite-
Datenbank: beide Blocker sichtbar, Aufwandslink öffnet den vorhandenen Editor;
Messabsichtslink öffnet die bestehende Vorbereitung mit geladenen Geschäftstexten
und allen Messfeldern. Bestehende semantische Stile, sichtbare Labels und echte Links;
keine neue versteckte Pflicht und kein zusätzlicher Lifecycle.

Die automatisierten fachlichen Route-/Servicetests verwenden PostgreSQL. Die Browser-
prüfung ist eine gezielte Desktopkontrolle, kein Ersatz für Menschentest #161 oder
für reale Messgüte, Geschäftswirkung und die übergreifende Gesamtabnahme aus #202.
Historische Auditberichte bleiben unverändert.

## Branch #198

PR #203 wurde am 26.10.2026 gemergt; sein Remote-Branch war bereits gelöscht.
Der lokale Branch `fix/198-strategic-ai-handoff` wurde erst nach geprüftem PR-Status
und leerem Inhaltsvergleich mit aktuellem `main` entfernt. `var/` bleibt unangetastet.
