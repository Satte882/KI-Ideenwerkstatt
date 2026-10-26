# #186 – fachliche Aktualität von Auswahl und Wirkungsreview

## Auftrag und Basis

Umsetzung auf `main` / `6a9cc85` am 26.10.2026, nach #185 und #188.
Parent #183, Issue #186, ADR 0009 und die eingefrorenen D2-Gegenproben wurden
abgeglichen. Historische Auditdateien bleiben unverändert. Der aktuelle Auftrag
autorisiert ausschließlich die schmale Aktualitätskorrektur, keinen neuen
Vergleichs-/Messvertrag aus #189 und keine Änderung des strategischen Bindungsgates.

Die beiden D2-Fehler wurden zuerst auf dieser Basis mit isoliertem PostgreSQL 17.5
reproduziert: Risikoänderung nach KI-Handoff blieb scheinbar aktuell; eine geänderte
Prozessversion mit entfernter Ursache ließ den Non-KI-Wirkungsreview aktuell.
Zusätzlich entwerteten Titel und Review-Datum unveränderte Wirkungsreviews.
Der erste Lauf der neuen Regressionen ergab entsprechend vier Fehler und zwei
bestandene bestehende Schutzfälle für geänderte Wirkungsaussagen.

## Selektiver Vertrag und Wiederbestätigung

Die vorhandenen `comparison_snapshot`, `diagnosis_snapshot` und `outcome_snapshot`
bleiben die Entscheidungsgrundlage. `SolutionSelectionDecision.outcome_review_required`
ist weiterhin der gemeinsame Einstieg für Handoff, Herkunftsprüfung einer neuen
positiven Freigabe und zugehörigen Wirkungsreview. Der bisher zusätzliche
Handoff-Feldvergleich wird in denselben Auswahlservice verschoben.

| Inhalt | Fachliche Wirkung |
| --- | --- |
| Alle aktiven verglichenen Optionen | Identitäten und materieller Vergleichsinhalt zählen: Typ/KI-Bezug, Bewertung, Evidenz, Handlungshebel, erwarteter Nutzen, Outcome-Beitrag, Time-to-Value, Ursachenabdeckung, Machbarkeit, Daten/Integration/Technik, Risiken, Architekturfit und Aufwand aus #188. Neue/entfallene aktive Alternativen erfordern erneuten Vergleich. Ein neuer Entwurf darf gespeichert werden. |
| Optionsname, Übersetzungslabel, Änderungszeit, Reihenfolge | Entwerten den fachlichen Vergleich nicht. Whitespace/Unicode-Komposition werden normalisiert; keine semantische Gleichheit von umformulierten Aussagen wird behauptet. |
| Prozess und Diagnose | Neue Entscheidungen erfassen die inhaltlichen Prozessfelder im bestehenden Diagnose-Snapshot. Start/Ende, Ablauf, Rollen, Systeme/Daten, Regeln/Übergaben, Befunde/Ursachen/Constraints, Ausnahmen, Baseline und Zielprinzipien werden verglichen. Prozessname und Status allein ändern den fachlichen Inhalt nicht. Relevante Diagnoseänderungen werden auch ohne Versionssprung erkannt. |
| Prozessversion und Validierung | Schreib-/Versionsprüfungen bleiben erhalten. Bei vollständigem Inhalts-Snapshot löst ein formaler Versionssprung allein keine Neubewertung aus. Eine namensbedingte neue Version kann dieselbe ursprüngliche Validierung referenzieren; geänderte Evidenz/Notiz/Rolle zählt, bloß neue Bestätigungszeit nicht. Ältere gebundene Snapshots ohne vollständigen Prozessinhalt bleiben konservativ versionsgebunden. |
| Outcome, Pfad, Fokus | Vorhandene Outcome-Revision und menschliche Bestätigung sowie die eigene Vorhaben-/Stream-/Phasenrevision bleiben maßgeblich. Keine neue globale Fokusfusion; unabhängige Vorhaben und bereits legitimierte andere Phasen bleiben geschützt. |
| Wirkungsaussage und Review | Allgemeine Initiative-Revision ist weiterhin Schreibschutz, aber allein kein fachlicher Stale-Grund. Der ursprünglich geprüfte Inhalt wird anhand der vorhandenen Audit-Historie verglichen: Outcome-Felder sowie insbesondere `effect_status` und `effect_reason`, die die Outcome-Revision nicht erhöhen. |
| Intervention, Messung, Evidenz | Geänderte Reviewreferenzen, Geschäfts-/Prozessmessstand, Evidenz, Abgrenzung und Attribution übernehmen keine alte Bestätigung. KI-Metriken bleiben an den vorhandenen historischen Use-Case-Messstand gebunden; jeder bestehende Metrikbestandteil bleibt relevant. Für abgeleitete KI-Fälle gilt auch ohne explizite Review-Auswahl die gemeinsame Herkunftsprüfung. |
| Titel, optionales Review-Datum, erlaubte Schreibkorrektur | Unveränderte fachliche Nachweise und ihre ursprünglichen Historienreferenzen bleiben aktuell. Bestehende enge Regeln für Schreibkorrekturen und unveränderte Bestätigungen bleiben erhalten. |

Bei materiell geänderter Lösungsgrundlage: im vorhandenen Optionenvergleich erneut
menschlich bewerten/auswählen und danach den Wirkungsreview bewusst bestätigen.
Der Reviewabschluss benennt diesen Weg; Entwurfsspeicherung bleibt möglich.
Bei unveränderter gewählter Option verwendet ein neuer KI-Handoff den bestehenden
Use Case wieder. Alte Auswahl-, Diagnose-, Outcome- und Freigabesnapshots werden
dabei nicht umgeschrieben. Historische Messwerte werden nicht gelöscht.

## Schreibschutz und Kompatibilität

- Keine neue Tabelle, Migration, zweite Snapshot-Plattform oder zweiter Lifecycle.
  Bestehende Historie liefert den geprüften Review-/Initiative-Inhalt. Fehlt der
  historische Nachweis, gilt der Review konservativ als prüfbedürftig.
- `revision` / `expected_revision`, `select_for_update`, atomare Services,
  `expected_process_version`, Rollen und Immutable-Manager bleiben erhalten.
  Ein realer PostgreSQL-Gegentest mit zwei gleichzeitigen Metadatenschreibversuchen
  verlangt genau einen erfolgreichen Write und einen Konflikt, ohne verlorenes Update.
- Legacy-Auswahl ohne Outcome-Snapshot bleibt fachlich unverändert grandfathered;
  ihr bisheriger Handoff verlangt weiterhin Prozessversion und unveränderten
  ausgewählten Lösungsstand. Kein erfundener historischer Backfill.
- Keine pauschale Rückstufung bereits freigegebener oder laufender Piloten.
  Neue bindende Entscheidungen und die Interpretation betroffener Nachweise
  sind vom bestehenden Delivery-/Pilot-/Go-live-Lifecycle getrennt.

## Abgleich der Nutzerwege und Nachweise

`tests/test_issue_186_freshness.py` nutzt ausdrücklich synthetische Kontexte und
die vorhandenen #188-Fixtures, keine realen Unternehmensmessungen und keine LLM-Aufrufe.
Geprüft werden materielle Änderungen ausgewählter und konkurrierender Optionen,
Diagnoseänderung ohne Versionssprung, Prozessumbenennung über GET/POST,
Vorhabentitel/Termin über das reguläre Formular, formale Outcome-Korrektur,
erneute Auswahl mit Wiederverwendung des Use Case und neue unabhängige Freigabe
über das wirkliche Freigabeformular. Der Wirkungsreview wird bei veralteter Grundlage
mit Eingabeerhalt abgewiesen, als Entwurf gespeichert und nach Neuauswahl erneut
bestätigt. Historische Auswahl-/Review-/Freigabenachweise bleiben lesbar.

Gezielte Bestandstests umfassen #145, #146, #147, #158, Outcome-Review-Followups,
#185, #188 und die bisherige Auswahl-UX. CI prüft zusätzlich die vollständige Suite,
Lint/Format, System-/Migrationsprüfungen, Sicherheits-/Abhängigkeitsaudit,
Compose-Konfigurationen und beide Images. Konkrete finale Ergebnisse werden im
Draft-PR und im Chat berichtet.

## Verbleibende Grenzen

- Die Materialität von Freitext ist bewusst konservativ: echte Umformulierungen
  können erneute menschliche Prüfung verlangen; es gibt keine semantische
  Wahrheitsgarantie und keinen realen Modelltest.
- Ältere gebundene Snapshots ohne Prozessinhalt können formale Versionsänderungen
  nicht rückwirkend sicher unterscheiden. Sie verlangen gegebenenfalls eine neue
  Auswahl; alte Nachweise werden dafür nicht ergänzt oder verändert.
- Ein Vorhaben hat weiterhin einen aktuellen Wirkungsreview mit historisierten
  Interventionen; keine automatische Aggregation mehrerer Prozesswirkungen.
- #187, der neue Mess-/Wirkungsvertrag und die vollständige A/B/C-/Mehrprozessabnahme
  aus #189 sowie der unabhängige Menschentest #161 bleiben separate Aufgaben.
  Insbesondere bleibt der unbekannt gescreente strategische Bindungspfad unverändert.
- Grün belegt deterministisches technisches Verhalten, keine Praxisrendite,
  empirische Kausalität oder reale Modellqualität. Kein Merge und keine Änderung
  an Produktivdaten sind Teil dieses Auftrags.
