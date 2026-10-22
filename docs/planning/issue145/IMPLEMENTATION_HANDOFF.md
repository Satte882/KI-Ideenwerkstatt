# #145 – Implementierungsvertrag und Übergabe an #146

Basis: ADR 0009; lokaler Vollscan auf `main@cb8b518` vor Produktänderungen.
Die vollständigen Trefferlisten stehen im [Aufruferinventar](../ISSUE_144_OUTCOME_CALLER_INVENTORY.md#h-lokaler-vollscan-145--22102026-vor-produktänderungen).

## Ausgelieferte Vorbereitung

- `use_cases.initiative_models.ImprovementInitiative` ist der einzige neue fachliche
  Outcome-Träger im bestehenden Django-Kontext. Geschäftsergebnis, begrenzter Beitrag,
  Wirkannahme, qualitative/quantitative Prüfkriterien als Freitext, Evidenzgrad/-quelle,
  benannter Owner (Person/Funktion ohne Konto), Revision und Bestätigungsreferenz.
  Keine neue Messreihe, keine kopierten `UseCase.metric_*`.
- Nullable `initiative`-FKs mit `PROTECT` an `IdeaCandidate`, `ProcessAnalysis`, `UseCase`.
  0..n Artefakte pro Initiative; jedes Artefakt höchstens eine Initiative.
  Auch `HistoricalUseCase` erhält die optionale Referenz. Keine Datenbackfills.
- Minimale Zustände `draft`, `active`, `completed`, `cancelled`. Nur Abschluss benötigt
  `effect_status` (`confirmed`, `refuted`, `unclear`) und `effect_reason`; Abbruch benötigt
  `cancellation_reason`. Entwurf/Aktiv haben keine Outcome-/Owner-/Terminpflicht.
  Abschluss bedeutet keinen automatisch nachgewiesenen Erfolg.
- `save_initiative(actor, data, initiative=None, expected_revision=None)` ist die
  transaktionale Schreibgrenze. Koordinator oder anlegender Business Owner; ein freier
  Outcome-Owner-Name gibt keine Rechte. Row-Lock, optionaler Optimistic-Lock über Revision,
  Simple-History inklusive tatsächlichem Bearbeiter. Jede Änderung erhöht die Revision;
  Outcome-Feldänderungen entfernen alte Bestätigungsreferenzen, ohne Historie zu ändern.
  **Noch keine materielle Stale-/Freigabepolicy**; diese gehört in #146.
- `bind_initiative(initiative, artifact, actor)` verknüpft ausschließlich bereits
  vorhandene Objekte nach Prüfung beider Objektberechtigungen; idempotent, keine
  automatische Anlage, kein stilles Rebinding, Zuordnung im Vorhabensverlauf auditiert.
  Dieser Service erteilt keine Freigabe und setzt keine neue Kohorte. Keine produktiven
  Intake-/Discovery-/Approval-Aufrufer in #145. Die bewusste Bindungs-UX folgt mit #146.
- Bearbeitungsmaske über Dashboard-Kategorie; optionaler Review-Termin; explizites
  „Als Entwurf sichern“ auch nach einem unvollständigen Abschlussversuch.
  Leser können ein vorhandenes Vorhaben lesen, nicht ändern.
- `initiative_review_summary(today=...)` wird gemeinsam im bestehenden Dashboard und
  `scan_due_reviews` verwendet. Scan-JSON ergänzt **`details.initiatives`** mit
  `overdue`, `due_within_30_days`, `missing_review_date`; bestehende Use-Case-Zähler bleiben
  unverändert. Nur Entwurf/Aktiv zählen. Keine Mail, keine neue Reminder-Engine.

## Fokus und Historie

Die bestehende `StageFocusDecision` bleibt die isolierte globale **Legacy-Projektion**.
Die neue `architecture.stage_focus.InitiativeStageFocusDecision` ist die append-only
vorhabensbezogene Entscheidung mit Initiative + Value Stream + Phase + Revision +
Kriteriensnapshot + Begründung + tatsächlichem Entscheider. Sie verwendet denselben
Validierungsservice und den vorhandenen ImmutableDecisionManager.

- `save_stage_focus_decision(..., initiative=initiative)` erzeugt eine neue Revision,
  serialisiert auf dem Vorhabensdatensatz; UniqueConstraint über
  `(initiative, value_stream, revision)`; aktuell ist die höchste Revision.
- `get_stage_focus_decision(value_stream, initiative=initiative)` und
  `stage_is_selected(stage, initiative=initiative)` lesen ausschließlich diesen Kontext,
  **ohne globalen Fallback**. Ohne Argument bleiben die bisherigen Helper-Signaturen
  und Reverse-OneToOne-Aufrufer semantisch Legacy.
- `selected_stage` muss zum `value_stream` gehören. Berechtigung für Value Stream **und**
  Initiative nötig. Keine Ableitung eines Vorhabens aus Text oder globalem Screening.
- `post_save`-Kurzpfade überspringen gebundene Prozesse und Origins mit gebundenem Use
  Case oder Prozess. Kein globaler Fokus und keine neue Initiative werden dabei erzeugt.
  Bereits existierende Legacy-Fokussnapshots/Origins/Demos bleiben erhalten.
- `ValueStreamFocus`, `DEMO_FOCUS_DEFAULTS`, Blueprint-Feldpfade und historische
  Migrationen bleiben unverändert. Bestehende Exporte exportieren weiterhin Legacy-Kontext;
  Vorhabensfokus wird nicht als globale Freigabe ausgegeben.

## Harte Einführungsgrenze für #146

`ProcessAnalysis.outcome_contract_version` und `UseCase.outcome_contract_version` sind
serververwaltet und stehen **für Bestand und neue Aufnahmen weiter auf 0 (Legacy)**.
`LEGACY_OUTCOME_CONTRACT = 0` ist dokumentiert. Keine aktivierbare Feature-Flag mit
ungeprüftem Neupfad; keine Anlage/Bindung schaltet die Kohorte um. Neue positive
Entscheidungswege oder Non-KI-Bypasses werden in #145 nicht eingeführt.

#146 muss **atomar mit vollständigen Negativtests** entscheiden/implementieren:

1. Aktivierungsgrenze für **jede** danach neue bindende Lösungswahl, auch bei bisher
   vorhabenlosem Prozess und Non-KI, sowie neue positive direkte Use-Case-Freigaben.
   Nicht allein `initiative_id != null` als Kohortentest verwenden. Bestandsfälle und
   spätere Governance-/Pilot-/Go-live-Übergänge bleiben im bisherigen Vertrag.
2. Bewusst bestätigte minimale Anlage/Bindung über dieselben Services; bestehende
   Herkunftsketten beim Binden konsistent übernehmen/prüfen (keine automatische
   Propagation oder rückwirkliche Umschreibung von `UseCaseOrigin` in #145).
3. Outcome-ID/-Revision **und Fokusentscheidungs-ID/-Revision** in immutable
   SolutionSelection-/Approval-Snapshots; Datum/Bearbeiter, Quelle/Evidenz und
   tatsächliche menschliche Annahme. `confirmed_*` ist derzeit nur Schema-Vorbereitung;
   kein vorhandener Pfad setzt automatisch eine positive Bestätigung.
4. Materielle Revisions-/Stale-Semantik (Ziel, Empfänger, Wirkmechanismus, Prüfkriterien)
   statt jede Schreibkorrektur als fachliche Änderung zu behandeln. Der aktuelle
   `revision`-Zähler ist bewusst konservativ ein Änderungsstand, keine fertige Policy.
5. Problemgetriebene Ursache versus strategisches Potenzial/Hypothese unterscheiden,
   Validierungsschritt statt fingierter Ursache, ohne Pflicht-Kalendertermin.
6. Neue Kontextübergabe in bindenden Views/Services/Admin-/Lean-/API-Pfaden, Exporten
   und Accelerator-Contracts. Globale VS-/Stage-Ansichten bleiben globale Screening-
   bzw. Legacy-Ansichten und dürfen keine Vorhabensfreigabe vortäuschen.

## Prüfungen

95 gezielte Tests auf PostgreSQL 17.5 bestanden (inklusive Migrationserhalt,
Row-Lock-Konkurrenz, zwei Vorhaben, Signals, UI-Speichern/Fortsetzen, Legacy-Demos und
bestehender Intake-/Dashboard-Regression). Django-Systemcheck und Migrationsdriftcheck,
Ruff/Lint/Format und Bandit bestanden. Vollsuite und GitHub-CI werden im PR nachgewiesen.
Lokale Browserprobe: ungebundenes Vorhaben öffnen, leeren Entwurf speichern und wieder
öffnen; offene Angaben, aktive Speicheraktionen und separate Dashboard-Kategorie geprüft.
