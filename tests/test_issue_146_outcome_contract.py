from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from test_solution_selection_ux import make_option, make_process

from ki_radar.architecture.models import SolutionSelectionDecision
from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.architecture.stage_focus import save_stage_focus_decision
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase
from ki_radar.use_cases.outcome_contract import (
    confirm_initiative,
    set_discovery_path,
    snapshot_is_stale,
)
from ki_radar.use_cases.services import (
    approval_check,
    confirm_conditional_decision,
    create_use_case_from_selected_solution,
    submit_approval_decision,
)

pytestmark = pytest.mark.django_db


@pytest.fixture
def process(owner, business_unit):
    return outcome_process(owner, business_unit)


def outcome_process(owner, business_unit, *, stage=None):
    process = make_process(owner, business_unit)
    if stage is not None:
        process.stage = stage
    process.outcome_contract_version = 1
    process.save()
    for name, kind in (("Organisieren", "organizational"), ("KI-Assistent", "assistant")):
        option = make_option(process, owner, name=name, option_type=kind, assessed=True)
        option.outcome_effect = (
            f"{name}: weniger Rückfragen kann wirtschaftliche Buchungen fördern."
        )
        option.save()
    return process


def confirmed(owner):
    initiative = save_initiative(
        actor=owner,
        data={
            "title": "Buchungsbeitrag",
            "measurement_unknowns": "Messdesign unbekannt; vor Versuch mit Owner klären.",
            "business_outcome": "Mehr wirtschaftliche Buchungen",
            "contribution": "Weniger Rückfragen bei freigegebenen Angeboten",
            "impact_hypothesis": "Wenn die Rückfragen sinken, können mehr Angebote gebucht werden.",
            "evaluation_criteria": "Review der Buchungsabbrüche; Zusammenhang bleibt Hypothese",
            "outcome_owner": "Vertriebsleitung (ohne Systemkonto)",
        },
    )
    return confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Fachlich plausible, noch zu prüfende Hypothese",
        expected_revision=initiative.revision,
    )


def bind_process(owner, process, *, path="problem", initiative=None, path_context=None):
    initiative = initiative or confirmed(owner)
    bind_initiative(initiative=initiative, artifact=process, actor=owner)
    process.refresh_from_db()
    set_discovery_path(
        process=process,
        actor=owner,
        path=path,
        **(
            path_context
            or {
                "origin_basis": "Fachlicher Auftrag zur Untersuchung",
                "strategic_potential": "Zusätzliche Buchungen aus vorhandenen Angeboten",
                "validation_step": "Rückfragen und Buchungsabbrüche qualitativ vergleichen",
            }
        ),
    )
    save_stage_focus_decision(
        initiative=initiative,
        value_stream=process.stage.value_stream,
        selected_stage=process.stage,
        criteria_snapshot={},
        rationale="Begrenzter Beitrag dieser Phase",
        actor=owner,
        is_short_path=True,
        short_path_reason="Explizite fachliche Phasenwahl",
    )
    return initiative


def select(owner, process, *, ai=False):
    option = process.solution_options.get(option_type="assistant" if ai else "organizational")
    return select_preferred_solution(
        process_analysis=process,
        selected_option=option,
        rationale="Begründeter Vergleich derselben Wirkung",
        actor=owner,
    )


def direct(owner, coordinator, business_unit, *, version=1):
    case = UseCase.objects.create(
        title="Direkter Use Case",
        business_unit=business_unit,
        business_owner=owner,
        outcome_contract_version=version,
        status="review",
        problem_statement="Fachliches Problem",
        affected_process="Angebote bearbeiten",
        expected_benefit="Rückfragen verringern",
    )
    DecisionAssessment.objects.create(
        use_case=case,
        assessed_by=coordinator,
        version=1,
        recommendation="approved",
        evidence_quality=1,
        evidence_recency=1,
        evidence_coverage=1,
        independent_review=1,
        assumptions_resolved=1,
    )
    GovernanceAssessment.objects.create(
        use_case=case, assessment_date=timezone.localdate(), basis_version="Test", result="no_flags"
    )
    return case


@pytest.mark.parametrize("ai", [True, False])
def test_new_unbound_process_has_no_legacy_outcome_bypass(process, owner, ai):
    assert process.initiative_id is None
    with pytest.raises(ValidationError, match="Vorhaben"):
        select(owner, process, ai=ai)
    assert not SolutionSelectionDecision.objects.exists()
    assert not process.solution_options.filter(recommendation="preferred").exists()
    process.name = "Weiter untersuchen"
    process.save()
    assert process.initiative_id is None


def test_both_solution_classes_share_one_immutable_outcome(process, owner):
    initiative = bind_process(owner, process)
    decision = select(owner, process)
    frozen = deepcopy(decision.outcome_snapshot)
    assert frozen["initiative_id"] == str(initiative.pk)
    assert frozen["fields"]["business_outcome"] == initiative.business_outcome
    assert all(item["outcome_effect"] for item in decision.comparison_snapshot)
    assert {item["contains_ai_component"] for item in decision.comparison_snapshot} == {True, False}
    assert not decision.outcome_review_required
    save_initiative(
        actor=owner, initiative=initiative, data={"impact_hypothesis": "Anderer Wirkmechanismus"}
    )
    process.refresh_from_db()
    assert snapshot_is_stale(process, frozen)
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen
    assert decision.outcome_review_required


def test_strategic_path_does_not_invent_a_cause(process, owner):
    process.confirmed_causes = ""
    process.save()
    bind_process(owner, process, path="strategic")
    decision = select(owner, process)
    assert decision.outcome_snapshot["discovery_path"]["path"] == "strategic"
    assert not decision.outcome_snapshot["discovery_path"]["confirmed_cause_available"]
    assert decision.diagnosis_snapshot["confirmed_causes"] == ""
    process.refresh_from_db()
    assert process.confirmed_causes == ""


def test_problem_path_still_requires_confirmed_cause(process, owner):
    bind_process(owner, process)
    process.confirmed_causes = ""
    process.save()
    with pytest.raises(ValidationError, match="bestätigte Ursache"):
        select(owner, process)


def test_path_switch_is_explicit_audited_and_stales_decision(process, owner):
    bind_process(owner, process)
    decision = select(owner, process)
    with pytest.raises(ValidationError, match="Pfadwechsel"):
        set_discovery_path(
            process=process, actor=owner, path="strategic", origin_basis="Neuer Auftrag"
        )
    set_discovery_path(
        process=process,
        actor=owner,
        path="strategic",
        origin_basis="Neuer Auftrag",
        change_reason="Fachlich neu abgegrenzter strategischer Auftrag",
        strategic_potential="Qualitativer Beitrag",
        validation_step="Interviews auswerten",
    )
    assert decision.outcome_review_required
    assert process.discovery_path_decisions.count() == 2


def test_ai_proposal_remains_hypothesis_without_human_confirmation(owner):
    initiative = save_initiative(
        actor=owner,
        source="ai",
        data={
            "title": "KI-Vorschlag",
            "impact_hypothesis": "Ungeprüfter Zusammenhang",
            "evidence_level": "measured",
        },
    )
    assert initiative.evidence_level == "hypothesis" and initiative.hypothesis_origin == "ai"
    assert initiative.confirmed_by is None


def test_title_date_and_declared_typo_correction_do_not_stale_outcome(process, owner):
    initiative = bind_process(owner, process)
    frozen = select(owner, process).outcome_snapshot
    changed = save_initiative(
        actor=owner, initiative=initiative, data={"title": "Korrigierter Titel"}
    )
    assert changed.outcome_revision == initiative.outcome_revision
    save_initiative(
        actor=owner,
        initiative=changed,
        data={"business_outcome": "Mehr wirtschaftliche Buchungen."},
        correction_reason="Nur fehlenden Satzpunkt ergänzt",
    )
    process.refresh_from_db()
    assert not snapshot_is_stale(process, frozen)


def test_positive_direct_approval_needs_shared_context_negative_does_not(
    owner,
    coordinator,
    technical_admin,
    business_unit,
):
    case = direct(owner, coordinator, business_unit)
    assert case.initiative_id is None and case.metric_baseline is None
    with pytest.raises(ValidationError, match="Vorhaben"):
        submit_approval_decision(
            use_case=case,
            actor=technical_admin,
            data={"decision_status": "approved", "rationale": "Positiv"},
        )
    negative = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "deferred", "rationale": "Noch prüfen"},
    )
    assert negative.outcome_snapshot == {}
    initiative = confirmed(owner)
    bind_initiative(initiative=initiative, artifact=case, actor=technical_admin)
    case.refresh_from_db()
    decision = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "approved", "rationale": "Fachlich gewählt"},
    )
    assert decision.outcome_snapshot["initiative_id"] == str(initiative.pk)
    assert decision.outcome_snapshot["evidence_level"] == "hypothesis"
    decision.outcome_snapshot = {}
    with pytest.raises(ValidationError):
        decision.save()


def test_admin_orm_and_cohort_downgrade_cannot_bypass_new_approval(
    owner,
    coordinator,
    technical_admin,
    business_unit,
):
    case = direct(owner, coordinator, business_unit)
    with pytest.raises(ValidationError):
        ApprovalDecision.objects.create(
            use_case=case, decision_status="approved", decided_by=technical_admin
        )
    with pytest.raises(ValidationError):
        UseCase.objects.filter(pk=case.pk).update(decision_status="approved")
    with pytest.raises(ValidationError):
        UseCase.objects.filter(pk=case.pk).update(outcome_contract_version=0)
    case.decision_status = "approved"
    with pytest.raises(ValidationError):
        case.save()
    case.outcome_contract_version = 0
    with pytest.raises(ValidationError):
        case.save()


def test_legacy_positive_decision_retains_its_contract(
    owner, coordinator, technical_admin, business_unit
):
    case = direct(owner, coordinator, business_unit, version=0)
    decision = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "approved", "rationale": "Historisch"},
    )
    assert decision.outcome_snapshot == {} and not decision.outcome_review_required


def test_new_positive_snapshot_cannot_be_submitted_by_caller(
    owner, coordinator, technical_admin, business_unit
):
    case = direct(owner, coordinator, business_unit)
    with pytest.raises(ValidationError, match="serverseitig"):
        submit_approval_decision(
            use_case=case,
            actor=technical_admin,
            data={
                "decision_status": "approved",
                "rationale": "Fälschung",
                "outcome_snapshot": {"ok": True},
            },
        )


def test_draft_preparation_does_not_bind_or_require_outcome(client, process, owner):
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": process.pk})
    response = client.post(
        url,
        {
            "title": "Unvollständiger Entwurf",
            "status": "draft",
            "evidence_level": "hypothesis",
            "action": "save_draft",
        },
        follow=True,
    )
    assert response.status_code == 200
    process.refresh_from_db()
    assert process.initiative_id is None
    assert ImprovementInitiative.objects.get().confirmed_by is None
    assert "Als Entwurf sichern" in response.content.decode()


def test_selection_ui_preserves_input_and_offers_preparation(client, process, owner):
    client.force_login(owner)
    option = process.solution_options.first()
    response = client.post(
        reverse("architecture:solution_option_compare", args=[process.pk]),
        {
            "selected_option": option.pk,
            "process_version": process.version,
            "rationale": "Nicht verlieren",
        },
    )
    assert response.status_code == 200
    assert "Nicht verlieren" in response.content.decode()
    assert "Outcome-Bezug vorbereiten" in response.content.decode()
    assert not SolutionSelectionDecision.objects.exists()


def test_missing_effect_is_binding_only(process, owner):
    bind_process(owner, process)
    option = process.solution_options.first()
    option.outcome_effect = ""
    option.save()
    with pytest.raises(ValidationError, match="Geschäftsergebnis fehlt"):
        select(owner, process)


def test_stale_ai_handoff_is_rejected_without_rewriting_snapshot(process, owner):
    initiative = bind_process(owner, process)
    decision = select(owner, process, ai=True)
    changed = save_initiative(
        actor=owner, initiative=initiative, data={"business_outcome": "Anderes Ziel"}
    )
    confirm_initiative(
        initiative=changed,
        actor=owner,
        rationale="Neues Ziel angenommen",
        expected_revision=changed.revision,
    )
    with pytest.raises(ValidationError, match="Outcome-Grundlage"):
        create_use_case_from_selected_solution(decision=decision, actor=owner)
    assert not UseCase.objects.exists()


def test_changed_preferred_option_is_still_draft_editable_but_requires_new_review(process, owner):
    bind_process(owner, process)
    decision = select(owner, process)
    option = decision.selected_option
    option.outcome_effect = "Noch ungeklärter anderer Beitrag"
    option.save()
    assert decision.outcome_review_required


def test_batch_paths_cannot_create_positive_binding(process, owner, business_unit):
    with pytest.raises(ValidationError):
        process.solution_options.update(recommendation="preferred")
    with pytest.raises(ValidationError):
        SolutionSelectionDecision.objects.bulk_create(
            [
                SolutionSelectionDecision(
                    process_analysis=process,
                    selected_option=process.solution_options.first(),
                    rationale="Batch-Bypass",
                    decided_by=owner,
                )
            ]
        )
    with pytest.raises(ValidationError):
        UseCase.objects.bulk_create(
            [
                UseCase(
                    title="Batch",
                    business_unit=business_unit,
                    business_owner=owner,
                    decision_status="approved",
                )
            ]
        )


def test_bound_ai_use_case_reuses_confirmation_without_duplicate_input(
    process,
    owner,
    coordinator,
    technical_admin,
):
    bind_process(owner, process)
    decision = select(owner, process, ai=True)
    result = create_use_case_from_selected_solution(decision=decision, actor=owner)
    case = result.use_case
    assert case.initiative_id == process.initiative_id and case.outcome_contract_version == 1
    DecisionAssessment.objects.create(
        use_case=case,
        assessed_by=coordinator,
        version=1,
        recommendation="approved",
        evidence_quality=1,
        evidence_recency=1,
        evidence_coverage=1,
        independent_review=1,
        assumptions_resolved=1,
    )
    GovernanceAssessment.objects.create(
        use_case=case, assessment_date=timezone.localdate(), basis_version="Test", result="no_flags"
    )
    approval = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "approved", "rationale": "Unabhängig geprüft"},
    )
    assert approval.outcome_snapshot["source_selection_id"] == decision.pk
    assert approval.outcome_snapshot["confirmed_by"] == owner.pk


@pytest.mark.parametrize("material", [True, False])
def test_conditional_approval_rechecks_material_revision_and_preserves_snapshot(
    owner,
    coordinator,
    technical_admin,
    business_unit,
    material,
):
    from django.contrib.auth.models import Group

    from ki_radar.accounts.models import User
    from ki_radar.accounts.permissions import GROUP_COORDINATOR

    second = User.objects.create_user(username="second-outcome", password="TestOnlyPassword123!")
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    second.groups.add(group)
    case = direct(owner, coordinator, business_unit)
    initiative = confirmed(owner)
    bind_initiative(initiative=initiative, artifact=case, actor=technical_admin)
    case.refresh_from_db()
    decision = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={
            "decision_status": "approved_with_conditions",
            "rationale": "Bedingte Freigabe",
            "conditions": "Fachlich prüfen",
            "condition_owner": owner,
            "condition_due_date": timezone.localdate(),
            "second_approval_assignee": second,
        },
    )
    original = deepcopy(decision.outcome_snapshot)
    save_initiative(
        actor=owner,
        initiative=initiative,
        data={"business_outcome": "Neues Ziel" if material else "Mehr wirtschaftliche Buchungen."},
        correction_reason="" if material else "Nur Satzpunkt ergänzt",
    )
    if material:
        with pytest.raises(ValidationError, match="Outcome-Grundlage"):
            confirm_conditional_decision(decision=decision, actor=second)
    else:
        assert (
            confirm_conditional_decision(decision=decision, actor=second).finalized_at is not None
        )
    decision.refresh_from_db()
    assert decision.outcome_snapshot == original


def test_human_confirmation_and_binding_can_be_completed_in_ui(
    client, owner, coordinator, business_unit
):
    case = direct(owner, coordinator, business_unit)
    client.force_login(owner)
    response = client.post(
        reverse("use_cases:prepare_outcome", kwargs={"kind": "usecase", "pk": case.pk}),
        {
            "title": "Direkter Beitrag",
            "status": "draft",
            "evidence_level": "hypothesis",
            "business_outcome": "Weniger Buchungsabbrüche",
            "contribution": "Weniger Rückfragen",
            "impact_hypothesis": "Schnellere Klärung kann Buchungen fördern",
            "outcome_owner": "Vertrieb",
            "evaluation_criteria": "Abbruchsgründe qualitativ prüfen",
            "confirmation_reason": "Fachlich angenommen",
            "action": "confirm",
        },
    )
    assert response.status_code == 302
    case.refresh_from_db()
    assert case.initiative.confirmed_by_id == owner.pk
    assert not ApprovalDecision.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_activation_migration_preserves_existing_rows_and_marks_only_new_rows(owner, business_unit):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    from ki_radar.architecture.models import ProcessAnalysis

    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    targets = [
        ("architecture", "0023_processanalysis_initiative_and_more"),
        ("use_cases", "0015_historicalusecase_outcome_contract_version_and_more"),
    ]
    executor.migrate(targets)
    try:
        apps = executor.loader.project_state(targets).apps
        old = apps.get_model("use_cases", "UseCase").objects.create(
            title="Bestehende Freigabe",
            business_unit_id=business_unit.pk,
            business_owner_id=owner.pk,
            status="pilot",
            decision_status="approved",
        )
    finally:
        MigrationExecutor(connection).migrate(leaves)
    case = UseCase.objects.get(pk=old.pk)
    assert case.outcome_contract_version == 0 and case.initiative_id is None
    assert (case.status, case.decision_status) == ("pilot", "approved")
    assert not approval_check(use_case=case, target_status="deferred", actor=owner).blockers
    assert UseCase._meta.get_field("outcome_contract_version").default == 1
    assert ProcessAnalysis._meta.get_field("outcome_contract_version").default == 1


def test_orm_selection_cannot_bind_even_with_current_outcome_snapshot(process, owner):
    from ki_radar.architecture.solution_selection import (
        build_comparison_snapshot,
        build_diagnosis_snapshot,
        ordered_solution_options,
    )
    from ki_radar.use_cases.outcome_contract import build_outcome_snapshot

    bind_process(owner, process)
    options = ordered_solution_options(process)
    with pytest.raises(ValidationError, match="Entscheidungsservice"):
        SolutionSelectionDecision.objects.create(
            process_analysis=process,
            selected_option=options[0],
            decided_by=owner,
            rationale="Auch mit aktuellem Snapshot kein direkter Schreibpfad",
            outcome_snapshot=build_outcome_snapshot(process),
            comparison_snapshot=build_comparison_snapshot(options),
            diagnosis_snapshot=build_diagnosis_snapshot(process),
            process_version=process.version,
        )


def test_orm_approval_cannot_bypass_governance_with_valid_outcome(
    owner, coordinator, technical_admin, business_unit
):
    from ki_radar.use_cases.outcome_contract import build_outcome_snapshot

    case = direct(owner, coordinator, business_unit)
    initiative = confirmed(owner)
    bind_initiative(initiative=initiative, artifact=case, actor=technical_admin)
    case.refresh_from_db()
    with pytest.raises(ValidationError, match="Entscheidungsservice"):
        ApprovalDecision.objects.create(
            use_case=case,
            decided_by=technical_admin,
            decision_status="approved",
            rationale="Ein Outcome-Snapshot ersetzt keine Governance-Prüfung",
            finalized_at=timezone.now(),
            outcome_snapshot=build_outcome_snapshot(case),
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_outcome", "Anderes Ziel"),
        ("contribution", "Ganz anderer Pilotbeitrag"),
        ("impact_hypothesis", "Weniger Rückfragen senken die Buchungen"),
        ("target_group", "Andere Empfänger"),
        ("evaluation_criteria", "Jetzt nur noch Kosten prüfen"),
        ("outcome_owner", "Andere Leitung"),
        ("evidence_level", "measured"),
        ("evidence_note", "Andere Quelle"),
    ],
)
def test_correction_reason_cannot_preserve_material_confirmation(process, owner, field, value):
    initiative = bind_process(owner, process)
    decision = select(owner, process)
    frozen = deepcopy(decision.outcome_snapshot)
    changed = save_initiative(
        actor=owner,
        initiative=initiative,
        data={field: value},
        correction_reason="Tippfehler" + ("x" * 200 if field == "business_outcome" else ""),
    )
    assert getattr(changed, field) == value  # Draft still saves, even if incomplete.
    assert changed.outcome_revision == initiative.outcome_revision + 1
    assert changed.confirmed_revision is None and changed.confirmed_by is None
    assert changed.confirmed_at is None and not changed.confirmation_reason
    assert decision.outcome_review_required
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen
    with pytest.raises(ValidationError, match="Outcome"):
        select(owner, process)


@pytest.mark.parametrize("ai", [False, True])
def test_repeated_process_confirmation_preserves_decision_references(client, owner, process, ai):
    initiative = bind_process(owner, process, path="strategic")
    decision = select(owner, process, ai=ai)
    frozen = deepcopy(decision.outcome_snapshot)
    original_confirmation = (initiative.confirmed_by_id, initiative.confirmed_at)
    original_path = process.discovery_path_decisions.first()
    from ki_radar.architecture.stage_focus import get_stage_focus_decision

    original_focus = get_stage_focus_decision(process.stage.value_stream, initiative=initiative)
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": process.pk})
    for _ in range(2):
        form = client.get(url).context["form"]
        data = {name: form[name].value() or "" for name in form.fields}
        data.update(action="confirm", confirmation_reason="Unverändert fachlich angenommen")
        response = client.post(url, data)
        assert response.status_code == 302
    initiative.refresh_from_db()
    assert (initiative.confirmed_by_id, initiative.confirmed_at) == original_confirmation
    assert process.discovery_path_decisions.count() == 1
    assert process.discovery_path_decisions.first().pk == original_path.pk
    focus = get_stage_focus_decision(process.stage.value_stream, initiative=initiative)
    assert (focus.pk, focus.revision) == (original_focus.pk, original_focus.revision)
    assert not decision.outcome_review_required
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen
    # A real provenance change still creates a revision and requires review.
    set_discovery_path(
        process=process,
        actor=owner,
        path=original_path.path,
        origin_basis="Neu eingeordneter Auftrag",
        strategic_potential=original_path.strategic_potential,
        validation_step=original_path.validation_step,
    )
    assert process.discovery_path_decisions.count() == 2
    assert decision.outcome_review_required


def test_identical_focus_service_call_keeps_current_revision(process, owner):
    from ki_radar.architecture.stage_focus import get_stage_focus_decision

    initiative = bind_process(owner, process)
    focus = get_stage_focus_decision(process.stage.value_stream, initiative=initiative)
    repeated = save_stage_focus_decision(
        initiative=initiative,
        value_stream=process.stage.value_stream,
        selected_stage=process.stage,
        criteria_snapshot=focus.criteria_snapshot,
        rationale=focus.rationale,
        actor=owner,
        is_short_path=focus.is_short_path,
        short_path_reason=focus.short_path_reason,
    )
    assert (repeated.pk, repeated.revision) == (focus.pk, focus.revision)
    changed = save_stage_focus_decision(
        initiative=initiative,
        value_stream=process.stage.value_stream,
        selected_stage=process.stage,
        criteria_snapshot=focus.criteria_snapshot,
        rationale="Neuer fachlicher Fokusgrund",
        actor=owner,
        is_short_path=True,
        short_path_reason="Neu begründet",
    )
    assert changed.pk != focus.pk and changed.revision == focus.revision + 1
