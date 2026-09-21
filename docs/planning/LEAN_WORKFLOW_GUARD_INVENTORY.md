# Lean Workflow Guard Inventory

Issue: #402 · Parent: #401  
Geprüfter Stand: `main` @ `c1345f34019653ec7275c1410f5803acad3ab0d9`

## 1. Lesart

Dieses Dokument beschreibt ausschließlich die **heute wirksame Steuerlogik**. Es entscheidet noch nicht, was künftig `Advisory`, `Readiness` oder `Enforcement` sein soll; diese Soll-Entscheidung gehört in #403.

Verwendete Begriffe:

- **hard blocked**: Die konkrete Aktion kann serverseitig nicht gespeichert/ausgeführt werden (`PermissionDenied`, `ValidationError` oder Formfehler).
- **warning**: Hinweis ohne Verhinderung der Aktion.
- **journey blocked**: UI-/Journey-Projektion meldet `blocked`/`upcoming`; das ist nicht automatisch ein Domain-Guard.
- **nicht geprüft**: Für die genannte Bedingung existiert auf dem betrachteten Domain-Pfad kein Guard.

Ein Hard Block ist damit nicht automatisch ein globaler Workflow-Stopp. Wo er nur eine einzelne Transition schützt, ist das ausdrücklich vermerkt.

## 2. Guard-Inventar

### Intake, START_REVIEW und Assessment

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| Intake öffnen | Actor erfüllt `is_business_owner()`; semantisch zählen auch Koordinator/Tech-Admin/Superuser | hard blocked (Zugriff) | Permission/View | `use_cases/permissions.py::can_create_use_case`, `intake_views.py::use_case_intake` |
| Intake Schritt 1–5 | jeweiliges Django-Form ist valide | hard blocked für Wechsel zum nächsten Wizard-Schritt | Form/View | `use_cases/intake.py`, `intake_views.py::use_case_intake` |
| Intake Problem | sehr kurze technologiezentrierte Problemangabe (`chatbot`, `llm`, etc.) | hard blocked im Form | Form | `intake.py::ProblemStepForm.clean_problem_statement` |
| Intake Prozess | entweder verknüpfter Prozess oder `affected_process` | hard blocked im Form | Form | `intake.py::ProcessStepForm.clean` |
| Intake Metrik | Prozentwerte, sofern angegeben, 0–100 | hard blocked im Form | Form | `intake.py::BenefitStepForm.clean` |
| Intake Metrik | Baseline und Ziel, sofern beide angegeben, verschieden und passend zur Richtung | hard blocked im Form | Form | `intake.py::BenefitStepForm.clean` |
| Intake final speichern | alle Formfelder aus Schritten 1–5 wurden in der Session erfasst | hard blocked für Persistenz; Redirect zu Intake | View | `intake_views.py::use_case_intake` |
| Intake final speichern | Business Owner ist weiterhin aktiv/zulässig | hard blocked für Persistenz | View | `intake_views.py::_current_business_owner`, `use_case_intake` |
| Intake final speichern | `title`, `problem_statement`, `business_unit`, `affected_process`, `business_owner`, `expected_benefit`, `metric_name`, `metric_type`, `metric_direction`, `metric_unit`, `metric_measurement_method`, `data_sources` vorhanden | hard blocked für Persistenz | Domain/View | `use_cases/services.py::intake_blockers`, `INTAKE_REQUIREMENTS`; `intake_views.py::use_case_intake` |
| Intake final speichern | `metric_baseline`, `metric_target` | nicht erforderlich; Use Case kann ohne beide gespeichert werden | Domain | `services.py::INTAKE_REQUIREMENTS`; `intake.py::BenefitStepForm` |
| Nach Intake | Lifecycle-Status wird explizit auf `REVIEW` gesetzt | **nicht geprüft / nicht gesetzt**; Model-Default bleibt `IDEA`, `decision_status` wird `READY` | Model/View | `intake_views.py::_build_use_case`, `models.py::UseCase.Status` |
| START_REVIEW | `decision=START_REVIEW` verlangt `new_status=REVIEW` | hard blocked bei falschem Zielstatus | Form/Domain | `reviews/forms.py::ReviewForm.clean`, `reviews/services.py::_validate_review_transition` |
| START_REVIEW | Source-State muss `IDEA` sein | **nicht geprüft**; spätere Phasen können auf Service-Ebene mit `START_REVIEW` nach `REVIEW` gesetzt werden, sofern REVIEW-Felder vollständig sind | Domain | `reviews/services.py::_validate_review_transition`, `use_cases/services.py::validate_target_status` |
| Assessment anlegen | Actor erfüllt `is_coordinator()` | hard blocked (Zugriff/Service) | Permission/View/Domain | `decision_views.py::assessment_create`, `services.py::create_decision_assessment` |
| Assessment anlegen | Lifecycle ist exakt `REVIEW` | hard blocked; Direkt-URL wird umgeleitet, Service wirft `ValidationError` (#395) | View/Domain | `decision_views.py::assessment_create`, `services.py::create_decision_assessment` |
| Assessment Evidenz | ab `EXPERT_OPINION` ist `evidence_url` vorhanden | hard blocked über Form und `full_clean()` | Form/Model | `decision_forms.py::DecisionAssessmentForm`, `models.py::DecisionAssessment.clean` |
| Neues Assessment | es existiert noch keine finale Freigabe / finale negative Entscheidung | **nicht geprüft**; in `REVIEW` kann eine neue Bewertung versioniert werden und `decision_status` wieder auf `READY`/`CLARIFICATION` setzen | Domain | `services.py::create_decision_assessment` |

### Governance

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| Governance-Screening anlegen | Actor erfüllt `is_coordinator()` | hard blocked | View | `governance/views.py::assessment_create` |
| Governance-Screening anlegen | Decision Assessment existiert | **nicht geprüft**; Screening kann serverseitig vor der strukturierten Bewertung angelegt werden | View/Domain | `governance/views.py::assessment_create` |
| Governance-Screening anlegen | bestimmter Lifecycle-Status | **nicht geprüft** | View/Domain | `governance/views.py::assessment_create` |
| Screening: Fachprüfung nicht erforderlich | spezifische oder übergreifende Begründung vorhanden | hard blocked im Form | Form | `governance/forms.py::GovernanceAssessmentForm.clean` |
| Screening speichern | Required-Flags werden auf Use Case übertragen, Completion-Flags zurückgesetzt; Review-Artefakte werden angelegt | persistierte Folgeaktion, kein zusätzlicher Guard | Domain/View | `governance/views.py::assessment_create`, `governance/services.py::create_screening_review_artifacts` |
| Formale Fachprüfung öffnen | Screening existiert | UI hard/redirect zum Screening | View | `governance/views.py::review_create` |
| Formale Fachprüfung bearbeiten | Screening markiert den Review-Typ als erforderlich | nur dann Eingabeformular; sonst nur Statusanzeige | View | `governance/views.py::review_create` |
| Formale Fachprüfung abschließen | rationale vorhanden | hard blocked über `full_clean()` | Model | `governance/models.py::GovernanceReview.clean` |
| Formale Fachprüfung abschließen | result vorhanden | hard blocked | Model | `GovernanceReview.clean` |
| Formale Fachprüfung abschließen | evidence URL vorhanden | hard blocked | Model | `GovernanceReview.clean` |
| Ergebnis `PASSED_WITH_CONDITIONS` | `conditions` vorhanden | hard blocked | Model | `GovernanceReview.clean` |
| Ergebnis `FAILED` | `risks` und `measures` vorhanden | hard blocked | Model | `GovernanceReview.clean` |
| Journey Governance | Screening fehlt nach Assessment oder erforderliche Fachprüfung offen | `current` bzw. journey blocked; Approval wird in der Journey auf `upcoming` geschoben | Journey | `use_cases/governance_journey.py::_governance_step`, `_insert_governance` |
| Finale negative Entscheidung | Governance vollständig | Journey behandelt Governance als optional | Journey | `governance_journey.py::_governance_step`; siehe #396 |

### Approval und Second Approval

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| Approval anlegen | Actor erfüllt `is_coordinator()` | hard blocked | View/Domain | `decision_views.py::approval_decision_create`, `services.py::submit_approval_decision` |
| Approval anlegen | Lifecycle ist `REVIEW` | **nicht geprüft**; vorhandenes Assessment kann auch in späterem Lifecycle über Direktpfad erneut entschieden werden | Domain/View | `decision_views.py::approval_decision_create`, `services.py::approval_check` |
| Jede finale Entscheidung | vollständige `INTAKE_REQUIREMENTS` | hard blocked für Entscheidung | Domain | `services.py::approval_check` |
| Jede finale Entscheidung | aktuelles Decision Assessment vorhanden | hard blocked | Domain/View | `approval_check`, `approval_decision_create` |
| Jede finale Entscheidung | Entscheider ist nicht dieselbe Person wie Assessor | hard blocked | Domain | `approval_check` |
| Jede finale Entscheidung | Entscheidung entspricht Assessment-Empfehlung | **warning** bei Abweichung; Entscheidung bleibt möglich | Domain | `approval_check` |
| Positive Approval | `metric_baseline` vorhanden | hard blocked | Domain | `approval_check`, `APPROVAL_METRIC_REQUIREMENTS` |
| Positive Approval | `metric_target` vorhanden | hard blocked | Domain | `approval_check`, `APPROVAL_METRIC_REQUIREMENTS` |
| Positive Approval | Entscheider != Business Owner | hard blocked | Domain | `approval_check` |
| Positive Approval | Confidence != LOW | hard blocked | Domain | `approval_check` |
| Positive Approval | Technical Feasibility != LOW | hard blocked | Domain | `approval_check` |
| Positive Approval | Data Readiness != LOW | hard blocked | Domain | `approval_check` |
| Positive Approval | Risk/Complexity != HIGH | hard blocked | Domain | `approval_check` |
| Positive Approval | `assessment.governance_precheck_completed=True` | hard blocked | Domain | `approval_check` |
| Positive Approval | separate `governance_confirmed=True` durch Entscheider | hard blocked | Domain | `approval_check` |
| Positive Approval | alle als required markierten Privacy/Security/Legal-Flags sind completed | hard blocked | Domain | `approval_check` |
| Positive Approval | tatsächliches `GovernanceAssessment`/Screening existiert | **nicht geprüft**; Boolean-/Assessment-Flags können den Backend-Check erfüllen, während die Journey noch ein Screening verlangt | Domain vs Journey | `approval_check` vs `governance_journey.py::_governance_step` |
| `DEFERRED` / `NOT_PURSUED` | positive-spezifische Metrik-, Governance-, BO- und Risikoguards | **nicht geprüft**; werden absichtlich übersprungen, nur gemeinsame Approval-Guards gelten | Domain | `approval_check`; siehe #396 |
| `APPROVED_WITH_CONDITIONS` | `conditions`, `condition_owner`, `condition_due_date`, `second_approval_assignee` | hard blocked; teilweise in Form und Service dupliziert | Form/Domain | `decision_forms.py::ApprovalDecisionForm.clean`, `services.py::submit_approval_decision` |
| Zweitprüfer | aktiv, berechtigt und verschieden von Erstentscheider, aktuellem Assessor und Business Owner | hard blocked | Domain | `services.py::eligible_second_approvers`, `can_review_conditional_decision` |
| Zweitfreigabe bestätigen | Entscheidung noch pending und Assessment weiterhin aktuell | hard blocked | Domain | `services.py::confirm_conditional_decision` |
| Zweitfreigabe zurückgeben | Rückgabegrund nicht leer | hard blocked; in Form und Service dupliziert | Form/Domain | `SecondApprovalReviewForm.clean`, `return_conditional_decision` |

### Delivery und Handover

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| Delivery Package erzeugen | Actor erfüllt `is_coordinator()` | hard blocked im View | Permission/View | `delivery/permissions.py::can_create_package`, `delivery/views.py::package_create` |
| Delivery Package erzeugen | `decision_status` ist positiv | hard blocked | Domain | `delivery/services.py::delivery_eligibility`, `create_delivery_package` |
| Delivery Package erzeugen | finale positive `ApprovalDecision` mit `finalized_at` existiert | hard blocked | Domain | `delivery_eligibility`, `latest_final_approval` |
| Delivery Package erzeugen | bestimmter Lifecycle-Status | **nicht geprüft** | Domain | `create_delivery_package` |
| Delivery bearbeiten | Package ist nicht `HANDED_OVER`; Actor besitzt mindestens eine fachliche/technische Sektionsberechtigung | hard blocked für Edit; übergebenes Package unveränderlich | Permission/View | `delivery/permissions.py::allowed_edit_sections`, `can_edit_package` |
| Package `READY` setzen | Actor erfüllt `is_coordinator()` | hard blocked im View | Permission/View | `can_transition_package`, `package_mark_ready` |
| Package `READY` setzen | Technical Owner vorhanden und aktiv | hard blocked | Domain | `delivery/readiness.py::evaluate_delivery_readiness`, `mark_package_ready` |
| Package `READY` setzen | jede Delivery-Sektion besitzt Review + Source Manifest und ist nicht `BLOCKED`/`NEEDS_REVIEW` | hard blocked | Domain | `evaluate_delivery_readiness`, `blocking_findings` |
| Package `READY` setzen | erforderliche fachliche/technische Bestätigungen je Sektion vollständig und unabhängig | hard blocked; gleiche Person für beide Rollen erzeugt `INDEPENDENT_CONFIRMATION_MISSING` | Domain | `evaluate_delivery_readiness`, `review_delivery_section` |
| Package `READY` setzen | alle `READY_REQUIRED_FIELDS` sind befüllt und keine generischen Platzhalter | hard blocked; betrifft alle sieben Delivery-Sektionen | Domain | `delivery/readiness.py::READY_REQUIRED_FIELDS`, `evaluate_delivery_readiness` |
| Package `READY` setzen | Architekturartefakte existieren; Systemlandschaft, Verantwortungen, Datenflüsse/-zugriff, Integrationsverträge/-betrieb konkret | hard blocked | Domain | `ARCHITECTURE_REQUIRED_FIELDS`, `evaluate_delivery_readiness` |
| Package `READY` setzen | Approval-Auflagen besitzen Owner/Fälligkeit und sind in Handover Notes übertragen | hard blocked | Domain | `evaluate_delivery_readiness` |
| Package `READY` setzen | Technical-Owner-Quelländerung wurde entschieden | hard blocked | Domain | `readiness.py::_source_staleness_findings` |
| Package Readiness | andere Quellfelder wurden seit Snapshot geändert | **warning**; blockiert READY/Handover nicht | Domain | `_source_staleness_findings` |
| Package `READY` setzen | Output-/Confidence-/Grounding-/Rule-Semantik, Retention und Retry-/Latenzsemantik erfüllen die Parserregeln | hard blocked | Domain | `readiness.py::_output_semantic_findings`, `_retention_semantic_findings`, `_latency_semantic_findings` |
| Package Readiness | fehlende Testpopulation/Stichprobengröße/Unsicherheit/kritische Fehlerklassen bzw. Recall-positive Fälle | **warning** | Domain | `readiness.py::_quality_semantic_findings` |
| Handover | Actor erfüllt `is_coordinator()` | hard blocked im View | Permission/View | `can_transition_package`, `package_handover` |
| Handover | Package-Status ist `READY` | hard blocked | Domain | `delivery/services.py::hand_over_package` |
| Handover | sämtliche Readiness-Blocker sind weiterhin leer | hard blocked; vollständige Readiness wird erneut ausgeführt | Domain | `hand_over_package`, `blocking_findings` |

### START_PILOT

`check_pilot_start()` ist aktuell kein einzelner fachlicher Guard, sondern ein Sammler. Die folgenden Bedingungen gehen getrennt in dieselbe Blockerliste ein und werden bei der Transition gemeinsam zu `ValidationError`.

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| START_PILOT | Source-Lifecycle exakt `REVIEW` | hard blocked | Domain | `use_cases/services.py::check_pilot_start` |
| START_PILOT | Actor ist **explizite Gruppe** KI-Koordinator oder zugeordneter **expliziter** Business Owner | hard blocked | Permission/Domain | `use_cases/permissions.py::can_start_pilot`, `apply_status_transition` |
| START_PILOT | `title`, `problem_statement`, `affected_process`, `business_owner`, `expected_benefit` vorhanden | hard blocked | Domain | `check_pilot_start`, `BASE_REQUIREMENTS[REVIEW]` |
| START_PILOT | `data_sources` vorhanden | hard blocked | Domain | `check_pilot_start`, `BASE_REQUIREMENTS[PILOT]` |
| START_PILOT | `next_review_date` vorhanden | hard blocked | Domain | `check_pilot_start`, `BASE_REQUIREMENTS[PILOT]` |
| START_PILOT | `planned_pilot_end` vorhanden | hard blocked | Domain | `check_pilot_start`, `BASE_REQUIREMENTS[PILOT]` |
| START_PILOT | `metric_name`, `metric_type`, `metric_direction`, `metric_unit` vorhanden | hard blocked | Domain | `check_pilot_start`, `PILOT_METRIC_REQUIREMENTS` |
| START_PILOT | `metric_baseline`, `metric_target` vorhanden | hard blocked | Domain | `check_pilot_start`, `PILOT_METRIC_REQUIREMENTS` |
| START_PILOT | `metric_measurement_method` vorhanden | hard blocked | Domain | `check_pilot_start`, `PILOT_METRIC_REQUIREMENTS` |
| START_PILOT | aktuelles Delivery Package existiert | hard blocked | Domain | `check_pilot_start` |
| START_PILOT | aktuelles Delivery Package ist verbindlich übergeben | hard blocked | Domain | `check_pilot_start`, `validate_pilot_start_date` |
| START_PILOT | finale positive Decision-Status (`APPROVED`/`APPROVED_WITH_CONDITIONS`) | hard blocked | Domain | `check_pilot_start` |
| START_PILOT | mindestens ein `GovernanceAssessment`/Screening existiert | hard blocked | Domain | `check_pilot_start` |
| START_PILOT Datum | `pilot_start` vorhanden | hard blocked | Domain/Form | `validate_pilot_start_date`, `ReviewForm.clean` |
| START_PILOT Datum | `pilot_start <= heute` | hard blocked | Domain | `validate_pilot_start_date` |
| START_PILOT Datum | `pilot_start >= handed_over_at` | hard blocked | Domain | `validate_pilot_start_date` |
| START_PILOT Datum | `planned_pilot_end >= pilot_start` | hard blocked | Domain | `validate_pilot_start_date` |
| START_PILOT Qualität | Baseline == Ziel | **warning**, sofern beide Werte gesetzt | Domain | `check_pilot_start` |
| START_PILOT Planung | geplantes Pilotende liegt bereits in Vergangenheit | **warning** | Domain | `check_pilot_start` |

### Measurement

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| Messdaten bearbeiten | Actor darf Use Case bearbeiten (Koordinator oder zugeordneter BO) | hard blocked für Edit-Zugriff | Permission/View | `use_cases/permissions.py::can_edit_use_case`, `views.py::use_case_edit` |
| Messdaten bearbeiten | Lifecycle ist `PILOT` | **nicht geprüft**; Felder sind im generischen `UseCaseForm` auch davor/danach editierbar | Form/View | `use_cases/forms.py::UseCaseForm`, `views.py::use_case_edit` |
| Messung als vollständig werten | `metric_actual`, `metric_measurement_period`, `metric_measured_at`, `metric_evidence_url` vorhanden | Journey-/Outcome-Bedingung; Eingabe selbst nicht geblockt | Journey | `outcome_workspace.py::MEASUREMENT_REQUIRED_FIELDS`, `_measurement_complete` |
| Messung als aktuellen Pilot werten | `metric_measured_at >= pilot_start` | Journey-/Outcome-Bedingung; ältere Messung wird nicht als Pilotmessung anerkannt | Journey | `outcome_workspace.py::_measurement_complete`, `_measurement_predates_pilot` |
| Pilot läuft, Messung fehlt | fehlende Messfelder | `upcoming`, kein globaler Domain-Block | Journey | `outcome_workspace.py::_measurement_step` |
| Pilot gilt fachlich abgeschlossen, Messung fehlt | fehlende Messfelder | journey blocked | Journey | `_measurement_step` |
| END wurde dokumentiert | Messung fehlt | Journey stuft Messung als `optional` ein | Journey | `_measurement_step` |

### GO_LIVE und Scale Readiness

`GO_LIVE` wird derzeit von mehreren Schichten gleichzeitig abgesichert: Review-Form, Review-Service, `check_go_live()`/`validate_target_status()` und der zur Laufzeit installierte Scale-Readiness-Wrapper.

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| GO_LIVE Review | Actor erfüllt `is_coordinator()` | hard blocked im View; Tech-Admin/Superuser zählen hier als Koordinator | Permission/View | `reviews/views.py::review_create`, `accounts/permissions.py::is_coordinator` |
| GO_LIVE | `decision=GO_LIVE` verlangt `new_status=OPERATION` | hard blocked | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| GO_LIVE | Source-Lifecycle exakt `PILOT` | hard blocked | Domain | `reviews/services.py::_validate_review_transition` |
| GO_LIVE | `title`, `problem_statement`, `affected_process`, `business_owner`, `expected_benefit` vorhanden | hard blocked | Domain | `check_go_live`, `BASE_REQUIREMENTS[REVIEW]` |
| GO_LIVE | `data_sources`, `next_review_date`, `planned_pilot_end` vorhanden | hard blocked | Domain | `check_go_live`, `BASE_REQUIREMENTS[PILOT]` |
| GO_LIVE | `metric_name`, `metric_type`, `metric_direction`, `metric_unit`, `metric_baseline`, `metric_target`, `metric_measurement_method` vorhanden | hard blocked | Domain | `check_go_live`, `PILOT_METRIC_REQUIREMENTS` |
| GO_LIVE | `business_owner`, `technical_owner`, `one_time_cost`, `recurring_cost`, `support_responsibility`, `human_oversight`, `next_review_date` vorhanden | hard blocked | Domain | `check_go_live`, `BASE_REQUIREMENTS[OPERATION]` |
| GO_LIVE | `metric_actual`, `metric_measurement_period`, `metric_measured_at`, `metric_evidence_url` vorhanden | hard blocked | Domain | `check_go_live`, `GO_LIVE_METRIC_REQUIREMENTS` |
| GO_LIVE Messung | `metric_measured_at >= pilot_start` | **nicht geprüft im Go-live-Guard**; Outcome-Journey verlangt es anschließend | Domain vs Journey | `check_go_live` vs `outcome_workspace.py::_measurement_complete` |
| GO_LIVE | aktuelles Package verbindlich übergeben | hard blocked | Domain | `check_go_live` |
| GO_LIVE | positive Decision-Status | hard blocked | Domain | `check_go_live` |
| GO_LIVE | required Privacy/Security/Legal jeweils completed | hard blocked | Domain | `check_go_live` |
| GO_LIVE vor geplantem Pilotende | explizite Early-Go-live-Ausnahme | hard blocked ohne Ausnahme; mit Ausnahme Warning in `check_go_live` | Domain | `check_go_live`, `reviews/services.py::_validate_review_transition` |
| Early-Go-live-Ausnahme | Actor ist **explizite Gruppe** KI-Koordinator | hard blocked; Tech-Admin/Superuser ohne Gruppenmitgliedschaft reichen nicht | Permission/Domain | `can_confirm_early_go_live_exception`, `_validate_review_transition` |
| Early-Go-live-Ausnahme | rationale, evidence basis, unobserved risks, mitigation measures vorhanden | hard blocked | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| Pilotziel verfehlt | `metric_result == NOT_ACHIEVED` | `check_go_live` nur **warning**, der Review-Service verlangt aber explizite Ausnahme | Domain | `check_go_live`, `_validate_review_transition` |
| Go-live trotz verfehltem Ziel | Ausnahme bestätigt + konkrete rationale | hard blocked ohne beides | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| Go-live-Ausnahme | Actor ist **explizite Gruppe** KI-Koordinator | hard blocked | Permission/Domain | `can_confirm_go_live_exception`, `_validate_review_transition` |
| Scale Tailoring | Stufe A/B/C vorhanden und nicht unter governance-abgeleitetem Minimum | hard blocked für GO_LIVE | Domain/Form | `scale_readiness.py::_evaluate_tailoring`, `ReviewForm.clean` |
| Scale Pilot-Evidenz | `scale_pilot_validation_confirmed=True` | hard blocked für GO_LIVE | Domain/Form | `_evaluate_pilot`, `ReviewForm.clean` |
| Scale Pilotziel | Pilotziel nicht erreicht | `condition`, kein Scale-Blocker; separater Go-live-Ausnahmeguard greift dennoch hart | Domain | `_evaluate_pilot`, `_validate_review_transition` |
| ML Test Score | Data/Model/Infrastructure/Monitoring jeweils 0–7 vorhanden | hard blocked für GO_LIVE | Domain/Form | `scale_readiness.py::_evaluate_ml_score` |
| ML Test Score | Mindestwert 0–7 vorhanden und `min(dimensions) >= minimum` | hard blocked | Domain/Form | `_evaluate_ml_score` |
| ML Test Score | Version, Erhebungsdatum, Evidence URL vorhanden | hard blocked | Domain/Form | `_evaluate_ml_score` |
| ML Test Score | keine `failed_mandatory_checks` | hard blocked | Domain/Form | `_evaluate_ml_score` |
| ML Test Score | `open_core_checks` | `condition`, kein Blocker | Domain | `_evaluate_ml_score` |
| Deployment | Handed-over Package vorhanden | hard blocked; zusätzlich bereits in `check_go_live` | Domain | `_evaluate_deployment` |
| Deployment | `scale_production_version` vorhanden | hard blocked | Domain/Form | `_evaluate_deployment` |
| Deployment | Rollback/Deaktivierung praktisch getestet | hard blocked | Domain/Form | `_evaluate_deployment` |
| Betriebsvorbereitung | Scale-Evidence URL, technisches Monitoring und AI-/fachliches Qualitätsmonitoring vorhanden | hard blocked | Domain/Form | `_evaluate_operations` |
| Betriebsvorbereitung B/C | Incident-/Eskalationsprozess bestätigt | hard blocked | Domain/Form | `_evaluate_operations` |
| Verantwortung | Business Owner, Technical Owner, Supportverantwortung, Human Oversight vorhanden | hard blocked; teilweise zusätzlich `BASE_REQUIREMENTS[OPERATION]` | Domain | `_evaluate_responsibility` |
| Governance in Scale | required Review offen oder formaler Review `FAILED` | hard blocked | Domain | `_add_governance_findings` |
| Governance in Scale | formaler Review `PASSED_WITH_CONDITIONS` | `condition` | Domain | `_add_governance_findings` |
| Tailoring C | `scale_extended_controls_completed=True` | hard blocked | Domain/Form | `_evaluate_responsibility` |
| Scale Result `conditional` | `open_actions`, `action_owner`, `action_due_date` vorhanden | hard blocked für GO_LIVE, wenn eines fehlt | Form/Domain | `ReviewForm.clean`, `reviews/services.py::_validate_scale_decision` |
| Direkter Statuswechsel `PILOT -> OPERATION` | Scale Readiness ohne Blocker | hard blocked über zur Laufzeit gepatchtes `apply_status_transition` | Domain | `scale_readiness.py::_apply_status_transition_with_scale_readiness`, `use_cases/apps.py::ready` |
| Direkter Statuswechsel `!= PILOT -> OPERATION` | Scale Readiness | **nicht geprüft durch Scale-Wrapper**; `check_go_live` läuft weiter, aber ohne Scale-Blocker | Domain | `_apply_status_transition_with_scale_readiness` |
| Persistierter `OPERATION`-Status | passendes `GO_LIVE`-Review existiert | **nicht von `apply_status_transition` geprüft**; direkter Service-Aufruf kann Status ohne Review-Artefakt setzen, Outcome meldet danach Inkonsistenz | Domain vs Journey | `apply_status_transition`, `outcome_workspace.py::_operation_step` |

### Operation Reviews und RETURN

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| normales Review | Actor erfüllt `is_coordinator()` | hard blocked im View | Permission/View | `reviews/views.py::review_create` |
| `CONTINUE` / `PAUSE` / `REWORK` | `new_status == current status` | hard blocked bei Statusänderung | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| `CONTINUE` / `PAUSE` / `REWORK` | aktuelle Phase ist `OPERATION` | **nicht geprüft**; Entscheidungen sind auch in anderen Lifecycle-Phasen service-seitig möglich, solange der Status gleich bleibt | Domain | `_validate_review_transition` |
| normales Review | rationale nicht leer | im ModelForm hard required; **im Service nicht explizit geprüft**, `Review.save()` ruft kein `full_clean()` auf | Form vs Domain | `ReviewForm`, `reviews/services.py::create_review` |
| `CONTINUE` / `REWORK` während `PILOT` | Scale Readiness wird ausgewertet | Ergebnis wird als Snapshot erfasst, Blocker verhindern diese Entscheidungen nicht | Domain | `reviews/services.py::_validate_scale_decision` |
| RETURN | Zielstatus ist gesetzt und liegt in `STATUS_ORDER` vor aktueller Phase | hard blocked bei gleich/später | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| RETURN | konkrete erlaubte Source→Target-Kombination | nur über Ordnungsregel, keine eigene Transition-Matrix | Domain | `_validate_review_transition` |
| RETURN nach `PILOT` | Ziel `REVIEW` und REVIEW-Basisfelder vollständig | hard target-readiness, danach Rückstufung möglich | Domain | `apply_status_transition`, `validate_target_status` |
| RETURN nach `OPERATION`/`ENDED` | Ziel `PILOT` | **faktisch blockiert durch START_PILOT-Guards**: `check_pilot_start` verlangt als aktuellen Source-State `REVIEW`; RETURN und Pilotstart-Semantik kollidieren | Domain | `_validate_review_transition`, `apply_status_transition`, `check_pilot_start` |
| RETURN | Ziel `IDEA` | keine statusbezogenen Pflichtfelder | Domain | `decision_check_for_status`, `BASE_REQUIREMENTS` |

### END / Closure

| Action / Guard | Einzelbedingung | Aktuelles Verhalten | Ebene | Code-Stelle |
|---|---|---|---|---|
| END | `decision=END` verlangt `new_status=ENDED` | hard blocked | Form/Domain | `ReviewForm.clean`, `_validate_review_transition` |
| END | Source ist `PILOT` oder `OPERATION` | hard blocked seit #397 | Domain | `_validate_review_transition`; zusätzlich `use_cases/services.py::validate_target_status` |
| END | `ending_reason` vorhanden | hard blocked; Prüfung in Form + Review-Service + Zielstatus-Anforderungen | Form/Domain | `ReviewForm.clean`, `_validate_review_transition`, `BASE_REQUIREMENTS[ENDED]` |
| END | `data_and_access_handling` vorhanden | hard blocked; Prüfung in Form + Review-Service + Zielstatus-Anforderungen | Form/Domain | gleiche Stellen wie oben |
| END | `replacement_solution`, `final_assessment`, `lessons_learned` | optional; werden nur übernommen, wenn befüllt | Domain | `reviews/services.py::create_review` |
| END aus `PILOT` | Scale Readiness | wird ausgewertet/Snapshot möglich, aber Scale-Blocker verhindern END nicht | Domain | `_validate_scale_decision` |
| END | vollständige Wirkungsmessung | **nicht erforderlich**; nach dokumentiertem END darf Measurement in der Journey optional sein | Domain/Journey | `_validate_review_transition`, `outcome_workspace.py::_measurement_step` |
| END | Handover und Pilotstart tatsächlich vorhanden | **nicht direkt im END-Guard geprüft**; bei bereits inkonsistentem `PILOT/OPERATION` kann END gespeichert werden und Closure danach `blocked` sein | Domain vs Journey | `_validate_review_transition`, `outcome_workspace.py::_closure_step` |
| Direkter `apply_status_transition(..., ENDED)` | passendes END-Review existiert | **nicht geprüft**; aus `PILOT/OPERATION` kann bei vorhandenen Abschlussfeldern `ENDED` ohne Review-Artefakt gesetzt werden | Domain vs Journey | `use_cases/services.py::apply_status_transition`, `outcome_workspace.py::_closure_step` |
| END persistiert | `actual_end_date` vorhanden | wird beim Übergang automatisch gesetzt, falls leer | Domain | `apply_status_transition` |
| Closure als `complete` | `status=ENDED` + Handover + Pilotstart + passendes END-Review | Journey complete; sonst journey blocked (#399) | Journey | `outcome_workspace.py::_closure_step`, `build_outcome_workspace_journey` |

## 3. Duplikate und Widersprüche

1. **Form + Domain doppeln dieselben Review-Regeln.** Decision↔Status-Paare, RETURN-Ordnungsregel, Pilotstartdatum, Go-live-Ausnahmen, Scale-Go-live und END-Pflichtfelder werden teilweise zweimal geprüft. Die Domain-Prüfung ist nötig; die zusätzliche Formlogik erzeugt aber eine zweite Policy-Stelle.
2. **Journey und Backend verlangen bei Governance nicht dasselbe.** Die Journey positioniert tatsächliches Screening/Fachreviews vor Approval. `approval_check()` verlangt positive-spezifisch Flags und Bestätigungen, aber nicht die Existenz eines `GovernanceAssessment`; negative Entscheidungen überspringen diese positive Governance-Gruppe vollständig (#396).
3. **`check_pilot_start()` vermischt heterogene Gründe in einer Hard-Block-Liste.** Source-State, Rollen, Handover, positive Freigabe, Governance-Screening, Planungsdaten und Metrikvollständigkeit enden technisch gleich in `ValidationError`.
4. **Go-live ist mehrfach und teilweise unterschiedlich abgesichert.** `check_go_live`, Review-Service, Review-Form und Scale-Readiness-Wrapper enthalten überlappende Regeln. Beispiel: verfehltes Pilotziel ist im Check nur Warning, im Review-Service aber nur mit harter Ausnahme zulässig.
5. **Messzeitpunkt ist Journey-strenger als der Go-live-Service.** Outcome akzeptiert nur `metric_measured_at >= pilot_start`; `check_go_live()` prüft lediglich, dass `metric_measured_at` befüllt ist. Dadurch kann die Transition technisch durchkommen und die Journey danach Inkonsistenz anzeigen.
6. **`START_REVIEW` hat keinen Source-State-Guard.** Die Entscheidung kann eine spätere Phase nach `REVIEW` setzen, obwohl für Rückstufungen ein eigener `RETURN`-Mechanismus existiert.
7. **`RETURN -> PILOT` kollidiert mit dem Pilotstart-Guard.** RETURN erlaubt grundsätzlich jede frühere Phase, aber `apply_status_transition(..., PILOT)` ruft `check_pilot_start()` auf, das den aktuellen Status `REVIEW` verlangt. Aus `OPERATION/ENDED` ist die Rückkehr nach `PILOT` damit faktisch nicht nutzbar.
8. **Persistierter Lifecycle und Review-Artefakt sind nicht atomar als Invariante gekoppelt.** Direkte Aufrufe von `apply_status_transition(..., OPERATION/ENDED)` können den Lifecycle ohne passendes `GO_LIVE`-/`END`-Review setzen; die Outcome-Journey markiert das anschließend als inkonsistent.
9. **Rollenbegriffe sind nicht überall identisch.** `is_coordinator()` umfasst Tech-Admin/Superuser; Pilotstart und Go-live-Ausnahmen prüfen dagegen teilweise die explizite Gruppe `KI-Koordinator`. Gleich benannte UI-/Fachrollen können dadurch unterschiedliche Rechte haben.
10. **Delivery Readiness ist aktuell der dokumentationsintensivste Hard-Gate-Bereich.** Nahezu alle strukturellen Pflichtfelder, konkrete Architekturartefakte, Sektionsbestätigungen sowie mehrere semantische Textprüfungen blockieren `READY` und Handover; daneben existiert nur eine kleine Gruppe echter Warnings.

## 4. Wichtigste Beobachtungen für #403

1. **Pilotstart zuerst granular entscheiden.** Aktuell werden Risiko-/Freigabekriterien und reine Informations-/Planungsanforderungen technisch identisch behandelt.
2. **Delivery Readiness braucht die stärkste KISS-Prüfung.** Die Zahl harter Vollständigkeits- und Textsemantik-Blocker ist hier deutlich höher als in anderen Phasen. #403 sollte nicht automatisch jeden heutigen `blocker` als zukünftiges Enforcement übernehmen.
3. **Go-live muss eine einzige fachliche Quelle der Wahrheit bekommen.** Heute liegen Regeln in Check, Form, Review-Service und Runtime-Wrapper; vor #400 muss feststehen, welche Bedingung tatsächlich die Transition schützen soll.
4. **Measurement-Konsistenz schließen.** Entweder gehört `metric_measured_at >= pilot_start` zur verbindlichen Go-live-Aussage oder die Outcome-Journey darf den Go-live danach nicht als inkonsistent bewerten. Der heutige Zustand ist widersprüchlich.
5. **END-Felder einzeln bewerten.** `ending_reason` und `data_and_access_handling` sind heute beide Hard Stops; `replacement_solution`, `final_assessment`, `lessons_learned` sind optional. #399/#403 müssen klären, ob beide Hard Stops fachlich notwendig sind, ohne neue Closure-Schicht zu erfinden.
6. **Closure-Invariante von END-Aktion trennen.** Heute kann die END-Transition in einem bereits inkonsistenten PILOT/OPERATION erfolgen; die Journey fordert anschließend zusätzlich Handover, Pilotstart und END-Review. #403 muss festlegen, was `ENDED` selbst garantiert.
7. **Approval/Governance-Mindestregel explizit machen.** Journey, positive Backend-Prüfung und negative Backend-Prüfung haben heute drei unterschiedliche Grenzen (#396).
8. **Regression/RETURN sauber definieren.** START_REVIEW ohne Source-Guard und das nicht nutzbare RETURN→PILOT zeigen, dass die vorhandene Statusreihenfolge keine konsistente Transition-Policy ersetzt.
9. **Rollenmodell vereinheitlichen, ohne neue Rollen zu bauen.** Vor #400 festlegen, ob Tech-Admin/Superuser semantisch Koordinator-Aktionen ausführen dürfen oder ob bestimmte Aktionen bewusst der expliziten Gruppe vorbehalten bleiben.
10. **#395/#397 sind als Source-Guard-Bugs geschlossen, aber nicht die gesamte State-Policy.** #398 (DEFERRED), #399 (ENDED/Closure) und die hier gefundenen Cross-Layer-Gaps bleiben fachliche Inputs für #403; #400 soll erst danach zentralisieren.

---

### Referenzen zu bestehenden Issues

- #395: Assessment-Source-State `REVIEW` — behoben.
- #396: Governance-Regel für negative Entscheidungen — offen; Backend/Journey-Grenze ist im Inventar sichtbar.
- #397: END-Source-State auf `PILOT/OPERATION` — behoben; Closure-/Review-Artefakt-Kopplung bleibt getrennt zu klären.
- #398: Semantik von `DEFERRED` / Reaktivierung — offen; neue Assessments können in `REVIEW` den Decision-Status wieder verändern.
- #399: Semantik von `ENDED` / sauberem Abschluss — offen; Outcome fordert mehr als der reine Statuswechsel garantiert.

Dieses Inventar verändert keine Produktlogik.