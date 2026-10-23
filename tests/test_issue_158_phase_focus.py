from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from test_issue_146_outcome_contract import bind_process, outcome_process, select

from ki_radar.architecture.models import ValueStreamStage
from ki_radar.architecture.stage_focus import (
    CRITERIA_KEYS,
    get_phase_focus_decision,
    get_stage_focus_decision,
    save_stage_focus_decision,
)
from ki_radar.architecture.templatetags.architecture_focus import process_stage_focus_decision
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.review_export_architecture import build_process_review_context
from ki_radar.use_cases.models import DecisionAssessment
from ki_radar.use_cases.outcome_contract import (
    build_outcome_snapshot,
    outcome_blockers,
    snapshot_is_stale,
)
from ki_radar.use_cases.services import (
    approval_check,
    create_use_case_from_selected_solution,
    submit_approval_decision,
)

pytestmark = pytest.mark.django_db


def test_two_binding_phases_remain_valid(owner, business_unit, coordinator, technical_admin):
    first = outcome_process(owner, business_unit)
    initiative = bind_process(owner, first)
    decision_a = select(owner, first, ai=True)
    frozen_a = deepcopy(decision_a.outcome_snapshot)
    stage_b = ValueStreamStage.objects.create(
        value_stream=first.stage.value_stream, sequence=2, name="Zweite Phase"
    )
    second = outcome_process(owner, business_unit, stage=stage_b)
    bind_process(owner, second, initiative=initiative)
    decision_b = select(owner, second)
    # A separate initiative may use the same stream and phase independently.
    other = outcome_process(owner, business_unit, stage=first.stage)
    bind_process(owner, other)
    other_decision = select(owner, other)
    assert not decision_b.outcome_review_required
    assert not decision_a.outcome_review_required
    assert not outcome_blockers(first)
    assert not snapshot_is_stale(first, frozen_a)
    assert build_outcome_snapshot(first) == frozen_a
    decision_a.refresh_from_db()
    assert decision_a.outcome_snapshot == frozen_a

    # Both handoff and new positive approval from A still work after B.
    case = create_use_case_from_selected_solution(decision=decision_a, actor=owner).use_case
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
    assert not approval_check(
        use_case=case, target_status="approved", actor=technical_admin
    ).blockers
    approval = submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "approved", "rationale": "Aktuelle Herkunft aus A"},
    )
    frozen_approval = deepcopy(approval.outcome_snapshot)
    focus_a = get_phase_focus_decision(first.stage, initiative=initiative)
    focus_b = get_phase_focus_decision(second.stage, initiative=initiative)
    assert get_stage_focus_decision(first.stage.value_stream, initiative=initiative) == focus_b
    assert process_stage_focus_decision(first) == focus_a
    assert process_stage_focus_decision(second) == focus_b
    context = build_process_review_context(first, owner)
    assert f"Vorhabensfokus: {focus_a.pk} · Revision {focus_a.revision}" in context.upstream_context
    repeated = save_focus(owner, initiative, first.stage, focus_a)
    assert repeated.pk == focus_a.pk  # Idempotent even with B as current priority.
    changed = save_focus(owner, initiative, first.stage, focus_a, rationale="Neue Begründung A")
    assert changed.revision == focus_b.revision + 1
    assert decision_a.outcome_review_required and approval.outcome_review_required
    assert not decision_b.outcome_review_required
    assert not other_decision.outcome_review_required
    assert outcome_blockers(case)  # True stale origin still blocks new approval.
    with pytest.raises(ValidationError):
        create_use_case_from_selected_solution(decision=decision_a, actor=owner)
    for obj, frozen in ((decision_a, frozen_a), (approval, frozen_approval)):
        obj.refresh_from_db()
        assert obj.outcome_snapshot == frozen


def save_focus(owner, initiative, stage, focus, **changes):
    values = {
        "criteria_snapshot": focus.criteria_snapshot,
        "rationale": focus.rationale,
        "is_short_path": focus.is_short_path,
        "short_path_reason": focus.short_path_reason,
    }
    return save_stage_focus_decision(
        actor=owner,
        initiative=initiative,
        value_stream=stage.value_stream,
        selected_stage=stage,
        **(values | changes),
    )


@pytest.mark.parametrize("short_path", [False, True])
def test_rewording_preserves_assessment_and_phase_provenance(
    client, owner, business_unit, short_path
):
    process = outcome_process(owner, business_unit)
    initiative = bind_process(owner, process)
    original = get_phase_focus_decision(process.stage, initiative=initiative)
    stage_b = ValueStreamStage.objects.create(
        value_stream=process.stage.value_stream, sequence=2, name="Andere Phase"
    )
    criteria = {
        str(process.stage_id): {
            **{key: "high" for key in CRITERIA_KEYS},
            "time_to_value": "short",
            "evidence_basis": "hypothesis",
            "source": "Fachlicher Workshop",
        }
    }
    criteria[str(stage_b.pk)] = deepcopy(criteria[str(process.stage_id)])
    focus = save_focus(
        owner,
        initiative,
        process.stage,
        original,
        criteria_snapshot=criteria,
        rationale="Bewerteter Fokus A",
        is_short_path=short_path,
        short_path_reason="Bewusst begrenzt" if short_path else "",
    )
    decision = select(owner, process)
    frozen = deepcopy(decision.outcome_snapshot)
    save_stage_focus_decision(
        actor=owner,
        initiative=initiative,
        value_stream=stage_b.value_stream,
        selected_stage=stage_b,
        criteria_snapshot={},
        rationale="Fokus B",
        is_short_path=True,
        short_path_reason="Begrenzte Phase B",
    )
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": process.pk})
    form = client.get(url).context["form"]
    assert form["focus_reason"].value() == focus.rationale
    data = {name: form[name].value() or "" for name in form.fields}
    data.update(
        action="confirm", focus_reason="Präzisierte Begründung A", confirmation_reason="Bestätigt"
    )
    response = client.post(url, data)
    assert response.status_code == 302
    revised = get_phase_focus_decision(process.stage, initiative=initiative)
    assert revised.rationale == data["focus_reason"]
    assert revised.criteria_snapshot == focus.criteria_snapshot
    assert revised.is_short_path == focus.is_short_path
    assert revised.short_path_reason == focus.short_path_reason
    assert revised.selected_by == owner and revised.pk != focus.pk
    assert decision.outcome_review_required
    assert client.get(url).context["form"]["focus_reason"].value() == revised.rationale
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen
    form = client.get(url).context["form"]
    repeat = {name: form[name].value() or "" for name in form.fields}
    assert (
        client.post(
            url, {**repeat, "action": "confirm", "confirmation_reason": "Bestätigt"}
        ).status_code
        == 302
    )
    assert get_phase_focus_decision(process.stage, initiative=initiative).pk == revised.pk


def test_new_phase_does_not_inherit_criteria(client, owner, business_unit):
    first = outcome_process(owner, business_unit)
    initiative = bind_process(owner, first)
    original = get_phase_focus_decision(first.stage, initiative=initiative)
    save_focus(owner, initiative, first.stage, original, criteria_snapshot={"source": "Nur A"})
    stage = ValueStreamStage.objects.create(
        value_stream=first.stage.value_stream, sequence=2, name="Neue Phase"
    )
    second = outcome_process(owner, business_unit, stage=stage)
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": second.pk})
    form = client.get(url, {"initiative": initiative.pk}).context["form"]
    assert not form["focus_reason"].value()
    data = {name: form[name].value() or "" for name in form.fields}
    data.update(
        action="confirm",
        focus_reason="Eigener Fokus B",
        path="problem",
        origin_basis="Auftrag B",
        confirmation_reason="Bestätigt",
    )
    assert client.post(url, data).status_code == 302
    focus = get_phase_focus_decision(stage, initiative=initiative)
    assert focus.criteria_snapshot == {} and focus.is_short_path
    assert focus.short_path_reason == "Eigener Fokus B"


def test_legacy_process_display_keeps_global_projection(owner, business_unit):
    process = outcome_process(owner, business_unit)
    stage_b = ValueStreamStage.objects.create(
        value_stream=process.stage.value_stream, sequence=2, name="Legacy-Fokus B"
    )
    legacy = save_stage_focus_decision(
        actor=owner,
        value_stream=stage_b.value_stream,
        selected_stage=stage_b,
        criteria_snapshot={},
        rationale="Historische Wahl",
        is_short_path=True,
        short_path_reason="Historischer Kurzpfad",
    )
    assert process_stage_focus_decision(process) == legacy
    assert get_phase_focus_decision(process.stage, initiative=None) == legacy
