# #188 – menschlich begründeter Alternativenvergleich

## Auftrag und Grenze

Basis: `main` / `8dc317512890ba9bd60532c8e3efb4c9c9ef2446`, Parent #183,
ADR 0009. Der Auftraggeber hat die Phase-0-Variante B ausdrücklich angenommen und
die Umsetzung ausschließlich von #188 einschließlich Regressionen und Draft-PR beauftragt.
Die weiteren fachlichen Freigaben sind keine Umsetzung von #186, #187, #189 oder des
strategischen Auswahlvertrags in diesem Inkrement.

## Entscheidung und Implementierung

- `SolutionOption.effort_assessment` ergänzt die vorhandenen gemeinsamen Kriterien um
  einen qualitativen Rahmen für einmaligen, laufenden und organisatorischen Aufwand.
  Quellen, Unsicherheiten und unbekannte Kosten sollen ausdrücklich benannt werden.
  Leer bedeutet nicht kostenlos. Ein numerischer ROI ist nicht erforderlich.
- Beschreibung, erwarteter Beitrag, Outcome-Beitrag, Risiken, Evidenz und Time-to-Value
  bleiben die vorhandenen autoritativen Optionsfelder. Es gibt keine zweite Wirtschaftsrechnung.
- Neue bindende Auswahl benötigt ausdrücklich die menschliche Begründung unterschiedlicher
  Handlungshebel sowie der akzeptierten Unsicherheiten. Beide werden unveränderlich an
  derselben `SolutionSelectionDecision` gesichert; Aufwandsangaben stehen im vorhandenen
  `comparison_snapshot`, die Diagnoseeinordnung im vorhandenen `diagnosis_snapshot`.
- Die einfache Gegenprobe auf normalisierte Textgleichheit ignoriert Namen und Typbezeichnungen.
  Sie erkennt nur den engen Fall, dass alle aktiven Optionen dieselben maßgeblichen Texte
  tragen. Andere Formulierungen sind kein Beweis anderer Handlungshebel. Fachliche Güte,
  Wirtschaftlichkeit, Aussagen zu Aufwandskategorien und Evidenz bleiben menschlich zu prüfen.
- Problemgetrieben wird die Grundlage der Ursachenbestätigung eingeordnet: fachliche Annahme
  oder anhand benannter Evidenz beurteilte Ursache, jeweils mit Begründung/Quellen/Grenzen.
  Auch diese Einordnung ist eine menschliche Aussage, kein automatisch unabhängiger Nachweis.
  Die bestehende kombinierte Bestätigung/Validierung bleibt atomar; ihre Validierungsnotiz
  wird zusätzlich im Diagnose-Snapshot erhalten. Strategisch werden Potenzial und
  Validierungsschritt referenziert, keine Ursache erzwungen und kein Screeninggate geändert.

## Kompatibilität und Aktualität

- Migration 0026 erhält bestehende Prozesse mit `comparison_contract_version=0`; nur neue
  Prozesse erhalten den Default 1. Die neuen Bindungsanforderungen gelten bei aktivem
  Outcome- und Vergleichsvertrag. Historische Outcome-/Vergleichskohorten bleiben geschützt.
  Es gibt keinen erfundenen Aufwands- oder Evidenzbackfill und keine Umschreibung alter
  Entscheidungen. Die Oberfläche kennzeichnet fehlende historische Zusatznachweise.
- Die Vergleichskohorte ist nicht im Formular editierbar und kann bei Einzel- und
  QuerySet-/Bulk-Updates nicht zurückgestuft werden. Direkte neue Entscheidungen und
  Bulk-Entscheidungen umgehen den autorisierten zentralen Service nicht.
- Generator-/Prompt-/Source-Schemata und eingefrorene Investigation-/Übernahmeverträge
  ändern sich nicht. Entwürfe bleiben speicherbar und nach altem Vertrag übernehmbar;
  die Aufwandsangaben werden vor neuer bindender Auswahl menschlich ergänzt.
- Geänderte Aufwandsangaben einer der damals verglichenen Optionen gehen in die bestehende
  `outcome_review_required`-Prüfung ein. Handoff und positive Freigabe nutzen diese vorhandene
  Prüfung weiterhin. Kein zweiter Aktualitätsvalidator wird eingeführt.
- Die umfassende selektive Materialität von Risiko, Prozess, konkurrierenden Optionen,
  Fokus, Wirkungsaussage und Messung sowie die Behandlung rein formaler Änderungen bleiben
  #186. Der neue Aufwandsinhalt muss dort in denselben Vertrag übernommen werden.
- Keine Änderung an Hybrid-Messreferenzen, Ex-ante/Ex-post-Messvertrag, Delivery-, Pilot-,
  Go-live- oder strategischen Screeningregeln. Keine pauschale Rückstufung laufender Piloten.

## Nachweise und verbleibende Abnahme

`tests/test_issue_188_decision_quality.py` enthält einen ausdrücklich synthetischen,
RSD-nahen Kundenservicekontext auf Grundlage der bestehenden Fallakten aus
`tests/fixtures/issue133_methodology/A` und `B`. Geschäftsoutcome, Prozess, Diagnoseannahme,
Alternativen und Auswahlbegründungen sind auf denselben Kontext bezogen. In getrennten
Gegenfällen wird organisatorisch beziehungsweise KI gewählt; es werden keine realen
Kennzahlen, gemessener Geschäftserfolg oder unabhängig bewiesene Ursachen behauptet.

Die Tests prüfen unter anderem fehlende Entscheidungsbegründungen, unbekannte Aufwände,
umbenannte KI-Kopien, beide realen Auswahl-Views, atomaren Rollback der kombinierten
Diagnosebestätigung, unveränderliche Snapshots, geänderten Konkurrenzaufwand, Rechte,
Prozessversion, Kohortenschutz und Migration ohne historischen Backfill.

Diese Nachweise sind keine vollständige Discovery-bis-Wirkung-Abnahme. Die gemeinsame
A/B/C- und Mehrprozessabnahme verbleibt ausdrücklich in #189; der strategische Fall B
bleibt bei unbekanntem Screening bis zur gesonderten Umsetzung seines Auswahlvertrags
blockiert. #161 bleibt eine unabhängige menschliche Abnahme. Reale Modellqualität,
Kausalität und Praxis-ROI werden durch diese Tests nicht nachgewiesen.

Konkrete Prüfergebnisse und Einschränkungen stehen im zugehörigen Draft-PR.
