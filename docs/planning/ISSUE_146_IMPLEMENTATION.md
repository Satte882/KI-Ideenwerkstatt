# #146 – Outcome-Vertrag v1: Umsetzung und Übergabe

Basis: ADR 0009 und gemergter PR #150 (`main@0f0afaf`).
Die Aufruferprüfung steht in `issue146-callers.txt`; sie wurde vor den Produktänderungen
lokal mit `rg` durchgeführt. Die vormalige #145-Inventur bleibt die detaillierte
Fokus-/ORM-/Template-/Export-Landkarte.

## Aktivierung und Bestand

- Einführungsversion **1**: Nach Migration neu erzeugte `UseCase` und `ProcessAnalysis`
  bekommen serverseitig `outcome_contract_version=1`. Die Migration ändert ausschließlich
  den Default; alle bestehenden Zeilen und historischen Use-Case-Stände bleiben **0**.
  Keine Datumsheuristik bei späterer Freigabe, keine erfundenen Backfills.
- Version 0 bleibt der historische Vertrag; spätere Pilot-/Go-live-Übergänge erhalten
  keine zusätzliche Outcome-Prüfung. Eine explizite Übernahme ist in der separaten
  Outcome-Vorbereitung auswählbar und wird am Objekt gespeichert.
- Die drei kanonischen Demo-Seeds deklarieren ihren unveränderten historischen Vertrag
  ausdrücklich. Normale Intake-, Import-/Blueprint-, Copy- und Admin-Erfassung nutzt
  den neuen Default. Es gibt keine vom Browser setzbare Legacy-Option.
- Alte Regression-Fixtures für bereits bestehende Freigaben/Lösungsentscheidungen sind
  ausdrücklich mit Version 0 gekennzeichnet; es gibt keinen globalen Test-Schalter und
  keine automatisch umgeschriebene Test-Policy. Die neuen #146-Gegenproben testen v1.

## Zentrale Grenzen und Änderungen der Aufrufer

`use_cases.outcome_contract` enthält die gemeinsame Prüflogik. Sie greift ausschließlich
bei bindender Auswahl / positiver Freigabe und liest den aktuellen servereigenen Stand.

- `select_preferred_solution` sowie der kombinierte Diagnose-/Auswahlbefehl prüfen
  Outcome, bestätigte aktuelle Revision, vorhabenseigenen Fokus, Discovery-Pfad und
  vollständig bewertete aktive Alternativen. Jede Option benötigt erst beim Binden
  einen qualitativen `outcome_effect` auf dasselbe Ergebnis. Das bestehende
  `expected_value` bleibt interventionsspezifischer Beitrag, kein zweites Geschäftsziel.
- `submit_approval_decision` baut den Snapshot selbst unter Sperre; übergebene
  Snapshot-Daten werden abgelehnt. Positive Direktfreigaben nutzen denselben
  `ImprovementInitiative`-Träger. Negative/zurückgestellte Entscheidungen bleiben frei
  von Outcome-Pflichten. Unveränderte Governance- und Personentrennungsregeln gelten.
- `confirm_conditional_decision` prüft den ursprünglichen Snapshot vor der zweiten
  Freigabe erneut. Materielle Änderungen erfordern eine neue Entscheidung; der alte
  Snapshot wird nicht durch einen aktuellen Stand ersetzt.
- `create_use_case_from_selected_solution` übernimmt Initiative und Kohorte aus der
  menschlichen Lösungsauswahl, prüft aktuellen Prozess-/Lösungs-/Outcome-Stand und
  erzeugt keine neue Outcome-Definition oder erneute Pflichtabfrage.
- Model-/ORM-Grenzen schützen positive Statuswechsel, bevorzugte Optionen,
  Snapshot-Änderungen, unbestätigte Batch-Entscheidungen und Kohorten-Downgrades.
  Admin-Freigaben bleiben audit-only; Empfehlung ist im Lösungs-Admin schreibgeschützt.
- Comparison und Approval haben einen echten Link zur separaten Outcome-Vorbereitung.
  Aufnahme, Bearbeitung, Untersuchung und Lösungsgenerierung haben kein neues Gate.
  Ein fehlgeschlagener Bindungsversuch behält Formeingaben; „Als Entwurf sichern“ bleibt
  unabhängig von der fachlichen Vollständigkeit verfügbar.
- Generator-Quellen werden additiv um die vorhandene Initiative erweitert; keine neue
  Pflichtquelle. Der Quellenhash umfasst die Outcome-Revision. Alte ungebundene
  Quelle-/Replay-Verträge bleiben unverändert; der Generator erteilt keine Freigabe.
- Review-Export ergänzt Geschäftsergebnis, Wirkannahme, Evidenz- und Outcome-Revision;
  bestehende Rollen-/Prozess-/Value-Stream-Felder werden nicht umgedeutet.

## Revision, Evidenz und fachliche Herkunft

`ImprovementInitiative.revision` bleibt der Bearbeitungs-/Optimistic-Lock-Zähler;
`outcome_revision` ist die fachliche Revisionsidentität. Ziel, Beitrag, Wirkmechanismus,
Empfängergruppe, Prüfkriterien sowie Evidenz-/Owner-Änderungen erhöhen die fachliche
Revision und entfernen die vorige Bestätigung. Reine Metadaten/Whitespace ändern sie
nicht. Eine ausdrücklich begründete Schreibkorrektur bleibt auditierbar, ohne sämtliche
bestehenden Entscheidungen unnötig zu sperren. Alte Snapshots bleiben immer unverändert.

`confirm_initiative` verlangt einen berechtigten identifizierbaren Nutzer, den geprüften
Bearbeitungsstand und die dokumentierte fachliche Annahme. Owner darf Person/Funktion
ohne Login sein. Hypothese ist zulässig; keine numerische Baseline, kein Zielwert und
kein Review-Termin als Bindungspflicht. Ein höherer Evidenzgrad verlangt eine Quelle.
KI-Vorschläge über `save_initiative(source="ai")` bleiben Hypothese und unbestätigt;
fachliche Annahme ist kein automatischer Wirksamkeitsnachweis.

`ProcessDiscoveryPathDecision` hält die menschliche Herkunftseinordnung append-only:
Problem oder strategisches Potenzial, Herkunftsbegründung, tatsächlicher Entscheider,
Revision und bei Wechsel eine Begründung. Ein strategischer Pfad benötigt begründetes
Potenzial und einen prüfbaren Validierungsschritt, keine fingierte bestätigte Ursache.
Problemgetriebene Auswahl behält das bestehende Ursache-Gate. Ein Pfadwechsel wird
nicht vom Generator und nicht im Optionsauswahl-Click geraten.

## Snapshot und Schnittstelle für #147

`SolutionSelectionDecision.outcome_snapshot` und `ApprovalDecision.outcome_snapshot`
halten Vertrag 1, Initiative-ID, **outcome_revision**, die damaligen Outcome-Felder,
Owner/Evidenz/Herkunft, tatsächliche Bestätigung mit Zeitpunkt und Grund. Bei
Prozessherkunft kommen Fokus-ID/-Revision/Kriteriensnapshot und Pfad-ID/-Revision/
Herkunft/Wechsel/Validierungsschritt hinzu; abgeleitete KI-Freigaben referenzieren
`source_selection_id`. Der Optionenvergleich enthält pro Option `outcome_effect`,
`expected_value` und den bereits existierenden Evidenzgrad.

`outcome_review_required` / `snapshot_is_stale` sind abgeleitete Projektionen:
Änderungen am fachlichen Outcome, Fokus, Pfad oder ausgewählten Wirkbeitrag verlangen
Neubewertung. Historische leere Snapshots heißen **historisch nicht gebunden**, nicht
stale. Keine Umschreibung alter Entscheidungen und keine automatische neue Präferenz.

#147 kann diese Entscheidungs-/Initiativreferenzen für gemeinsame KI-/Non-KI-
Wirkungsreviews verwenden. `UseCase.metric_*` bleibt unverändert die KI-Pilotmetrik;
keine neue Messwertkopie, keine automatische Aggregation oder erfundene Kausalwirkung.
Die vorhandene separate Vorhabens-Review-Kategorie und `initiative_review_summary`
bleiben aus #145 bestehen. Keine zweite Reminder-/Delivery-/Messreihen-Engine.

## Nachweise

Migrations-, Soft-Guidance-, KI-/Non-KI-, Herkunfts-, Snapshot-/Stale-, Admin-/ORM-,
Zweitfreigabe- und UI-Gegenproben stehen in `tests/test_issue_146_outcome_contract.py`.
Der endgültige PostgreSQL-/CI-Nachweis steht im PR. SQLite-Vorläufe sind kein Nachweis
für die PostgreSQL-spezifischen Konkurrenz-/JSON-Prüfungen.
