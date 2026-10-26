"""Material freshness through the real commands; synthetic data, no model calls."""

from copy import deepcopy
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from test_issue_188_decision_quality import QUALITY, choose
from test_issue_188_decision_quality import comparison as comparison_fixture

from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.services import (
    create_use_case_from_selected_solution,
    submit_approval_decision,
)

pytestmark = pytest.mark.django_db
comparison = comparison_fixture


def review_selection(owner, process, decision):
    initiative = process.initiative
    initiative.refresh_from_db()
    return save_impact_review(
        initiative=initiative,
        actor=owner,
        expected_revision=initiative.revision,
        data={
            "selection": decision,
            "effect_status": "unclear",
            "effect_reason": "Synthetisch: Geschäftswirkung weiterhin unbekannt",
        },
        finalize=True,
    )


def test_selected_risk_change_after_handoff_does_not_allow_new_approval(
    comparison, owner, coordinator
):
    decision = choose(comparison, owner, ai=True, **QUALITY)
    case = create_use_case_from_selected_solution(decision=decision, actor=owner).use_case
    frozen = deepcopy(decision.comparison_snapshot)
    option = decision.selected_option
    option.risks = "Neues wesentliches Datenschutzrisiko"
    option.save()
    decision.refresh_from_db()
    assert decision.outcome_review_required
    with pytest.raises(ValidationError, match=r"Grundlage|Lösungsstand"):
        create_use_case_from_selected_solution(decision=decision, actor=owner)
    with pytest.raises(ValidationError, match="Outcome-Bezug"):
        submit_approval_decision(
            use_case=case, actor=coordinator, data={"decision_status": "approved"}
        )
    decision.refresh_from_db()
    assert decision.comparison_snapshot == frozen


def test_changed_process_version_leaves_non_ai_effect_review_stale(comparison, owner):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    assert not review.review_required
    comparison.version += 1
    comparison.confirmed_causes = ""
    comparison.save()
    review.refresh_from_db()
    assert review.review_required


@pytest.mark.parametrize("competitor", [False, True])
@pytest.mark.parametrize(
    "field,value",
    [
        ("risks", "Neues kritisches Risiko"),
        ("description", "Ein anderer Handlungshebel"),
        ("expected_value", "Anderer erwarteter Nutzen"),
        ("outcome_effect", "Anderer Outcome-Beitrag"),
        ("effort_assessment", "Höherer organisatorischer Aufwand"),
        ("evidence_basis", "indicative"),
        ("time_to_value", "short"),
        ("bottleneck_coverage", "Andere Ursachenabdeckung"),
        ("architecture_fit", "Andere Architekturannahme"),
        ("data_requirements", "Zusätzliche sensible Daten"),
    ],
)
def test_material_option_changes_share_one_boundary(comparison, owner, competitor, field, value):
    decision = choose(comparison, owner, ai=True, **QUALITY)
    review = review_selection(owner, comparison, decision)
    option = (
        comparison.solution_options.exclude(pk=decision.selected_option_id).get()
        if competitor
        else decision.selected_option
    )
    setattr(option, field, value)
    option.save()
    decision.refresh_from_db()
    review.refresh_from_db()
    assert decision.outcome_review_required and review.review_required
    with pytest.raises(ValidationError, match="Grundlage"):
        create_use_case_from_selected_solution(decision=decision, actor=owner)


@pytest.mark.parametrize("field", ["confirmed_causes", "diagnostic_observations", "constraints"])
def test_diagnosis_edits_without_version_bump_are_detected(comparison, owner, field):
    decision = choose(comparison, owner, **QUALITY)
    setattr(comparison, field, "Geänderter materieller Befund")
    comparison.save()
    decision.refresh_from_db()
    assert decision.process_version == comparison.version
    assert decision.outcome_review_required


def test_process_and_option_names_and_unchanged_confirmation_are_formal(comparison, owner, client):
    from ki_radar.architecture.models import ProcessValidation
    from ki_radar.use_cases.outcome_contract import confirm_initiative

    comparison.baseline_metrics = "Keine Ist-Messung vorhanden; Erhebung noch offen."
    comparison.save()
    ProcessValidation.objects.create(
        process_analysis=comparison,
        process_version=comparison.version,
        validated_by=owner,
        validator_role="Fachlicher Owner",
        note="Unveränderter Befund",
    )
    decision = choose(comparison, owner, ai=True, **QUALITY)
    review = review_selection(owner, comparison, decision)
    client.force_login(owner)
    url = reverse("architecture:process_analysis_update", args=[comparison.pk])
    form = client.get(url).context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data["name"] = "Rein formale Umbenennung"
    response = client.post(url, data)
    assert response.status_code == 302, response.context["form"].errors
    option = decision.selected_option
    option.name = "Neuer Titel ohne Wirkungsänderung"
    option.description = "  " + option.description + "\n"
    option.save()
    initiative = comparison.initiative
    initiative.refresh_from_db()
    confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Unverändert angenommen",
        expected_revision=initiative.revision,
    )
    decision.refresh_from_db()
    review.refresh_from_db()
    assert not decision.outcome_review_required and not review.review_required
    create_use_case_from_selected_solution(decision=decision, actor=owner)


def test_risk_reassessment_through_comparison_restores_independent_approval(
    comparison, owner, coordinator, technical_admin, client
):
    from ki_radar.governance.models import GovernanceAssessment
    from ki_radar.use_cases.models import DecisionAssessment

    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[comparison.pk])
    data = {
        "selected_option": comparison.solution_options.get(option_type="assistant").pk,
        "process_version": comparison.version,
        "rationale": "Synthetische, begrenzte menschliche Auswahl",
        **QUALITY,
    }
    assert client.post(url, data).status_code == 302
    decision = comparison.solution_selection_decisions.first()
    frozen = deepcopy(
        (decision.comparison_snapshot, decision.diagnosis_snapshot, decision.outcome_snapshot)
    )
    case = decision.selected_option.use_case_origins.get().use_case
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
    approval_data = {"decision_status": "approved", "rationale": "Unabhängige Prüfung"}
    old_approval = submit_approval_decision(
        use_case=case, actor=technical_admin, data=approval_data
    )
    frozen_approval = deepcopy(old_approval.outcome_snapshot)
    decision.selected_option.risks = "Neu zu prüfendes Risiko"
    decision.selected_option.save()
    client.force_login(technical_admin)
    approval_url = reverse("use_cases:approval_decision_create", args=[case.pk])
    response = client.post(approval_url, approval_data)
    assert response.status_code == 200
    assert case.approval_decisions.count() == 1
    with pytest.raises(ValidationError, match="Outcome-Bezug"):
        submit_approval_decision(use_case=case, actor=technical_admin, data=approval_data)
    client.force_login(owner)
    data["rationale"] = "Risiko erneut bewusst fachlich beurteilt"
    assert client.post(url, data).status_code == 302
    new = comparison.solution_selection_decisions.first()
    assert new.pk != decision.pk and not new.outcome_review_required
    assert create_use_case_from_selected_solution(decision=new, actor=owner).use_case.pk == case.pk
    client.force_login(technical_admin)
    assert client.post(approval_url, approval_data).status_code == 302
    case.refresh_from_db()
    assert case.approval_decisions.count() == 2
    decision.refresh_from_db()
    old_approval.refresh_from_db()
    assert (
        decision.comparison_snapshot,
        decision.diagnosis_snapshot,
        decision.outcome_snapshot,
    ) == frozen
    assert old_approval.outcome_snapshot == frozen_approval


def test_stale_review_form_keeps_measurements_and_can_reconfirm_after_reselection(
    comparison, owner, client
):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    client.force_login(owner)
    url = reverse("use_cases:initiative_impact", args=[comparison.initiative_id])
    form = client.get(url).context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data.update(action="review", business_measurement="Synthetischer Messstand bleibt erhalten")
    comparison.confirmed_causes = "Geänderte fachliche Ursachenannahme"
    comparison.version += 1
    comparison.save()
    response = client.post(url, data)
    assert response.status_code == 200
    assert "Optionenvergleich" in str(response.context["form"].errors)
    assert response.context["form"]["business_measurement"].value() == data["business_measurement"]
    data["action"] = "draft"
    assert client.post(url, data).status_code == 302
    review.refresh_from_db()
    assert review.review_required and review.business_measurement == data["business_measurement"]
    new = choose(comparison, owner, **QUALITY)
    form = client.get(url).context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data.update(action="review", selection=new.pk)
    assert client.post(url, data).status_code == 302
    review.refresh_from_db()
    assert not review.review_required
    assert review.history.filter(selection_id=decision.pk).exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_measurement", "Anderer Messstand"),
        ("business_evidence", "Andere Evidenz"),
        ("process_measurement", "Andere Messdefinition"),
        ("attribution_reason", "Andere Attribution"),
    ],
)
def test_direct_review_content_edits_do_not_inherit_confirmation(comparison, owner, field, value):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    setattr(review, field, value)
    review.save()
    assert review.review_required


@pytest.mark.django_db(transaction=True)
def test_concurrent_metadata_writes_keep_optimistic_revision_guard(comparison, owner):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections, connection

    assert connection.vendor == "postgresql"
    initiative = comparison.initiative
    initiative.refresh_from_db()
    revision = initiative.revision
    barrier = Barrier(2)

    def write(title):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            try:
                save_initiative(
                    actor=owner,
                    initiative=initiative,
                    expected_revision=revision,
                    data={"title": title},
                )
                return "saved"
            except ValidationError:
                return "conflict"
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(write, ["Erster Stand", "Zweiter Stand"]))
    assert sorted(results) == ["conflict", "saved"]
    initiative.refresh_from_db()
    assert initiative.revision == revision + 1


@pytest.mark.parametrize(
    "data",
    [{"title": "Formaler neuer Titel"}, {"next_review_date": date(2026, 11, 5)}],
)
def test_initiative_metadata_preserves_review_and_conflict_guard(comparison, owner, data):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    initiative = comparison.initiative
    initiative.refresh_from_db()
    old_revision = initiative.revision
    save_initiative(actor=owner, initiative=initiative, expected_revision=old_revision, data=data)
    review.refresh_from_db()
    assert not review.review_required
    with pytest.raises(ValidationError, match="inzwischen"):
        save_initiative(
            actor=owner,
            initiative=initiative,
            expected_revision=old_revision,
            data={"title": "Veralteter Schreibstand"},
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("effect_status", "refuted"),
        ("effect_reason", "Neue Interpretation ohne Review"),
    ],
)
def test_changed_effect_invalidates_review_without_outcome_revision_change(
    comparison, owner, field, value
):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    initiative = comparison.initiative
    initiative.refresh_from_db()
    revision = initiative.outcome_revision
    saved = save_initiative(actor=owner, initiative=initiative, data={field: value})
    assert saved.outcome_revision == revision
    review.refresh_from_db()
    assert review.review_required


def test_review_intervention_edit_requires_new_interpretation(comparison, owner):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    replacement = choose(comparison, owner, **QUALITY)
    review.selection = replacement
    review.save()
    assert review.review_required
    # Evidence of the earlier intervention remains readable.
    assert review.history.filter(selection_id=decision.pk).exists()


def test_material_outcome_content_is_checked_even_without_a_service_revision(comparison, owner):
    decision = choose(comparison, owner, **QUALITY)
    initiative = comparison.initiative
    initiative.business_outcome = "Anderes Geschäftsergebnis"
    initiative.save()
    decision.refresh_from_db()
    assert decision.outcome_review_required


def test_formal_outcome_correction_and_metadata_view_keep_original_review(
    comparison, owner, client
):
    decision = choose(comparison, owner, **QUALITY)
    review = review_selection(owner, comparison, decision)
    initiative = comparison.initiative
    initiative.refresh_from_db()
    original_revision = review.initiative_revision
    original_proof = review.history.first().history_id
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={"business_outcome": initiative.business_outcome.rstrip(".") + "."},
        correction_reason="Nur abschließenden Punkt ergänzt",
    )
    client.force_login(owner)
    form = client.get(initiative.get_absolute_url()).context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data.update(title="Umbenannt", next_review_date="2026-11-05")
    assert client.post(initiative.get_absolute_url(), data).status_code == 302
    review.refresh_from_db()
    assert not review.review_required
    assert review.initiative_revision == original_revision
    assert review.history.first().history_id == original_proof
    decision.refresh_from_db()
    assert not decision.outcome_review_required


@pytest.mark.parametrize("change", ["added", "retired"])
def test_changed_active_comparison_membership_requires_review(comparison, owner, change):
    from test_solution_selection_ux import make_option

    from ki_radar.architecture.solution_retirement import retire_solution_option

    decision = choose(comparison, owner, **QUALITY)
    if change == "added":
        make_option(
            comparison, owner, name="Neuer Lösungsentwurf", option_type="no_tech", assessed=False
        )
    else:
        retire_solution_option(
            option=comparison.solution_options.exclude(pk=decision.selected_option_id).get(),
            actor=owner,
        )
    decision.refresh_from_db()
    assert decision.outcome_review_required


def test_existing_bound_snapshot_without_full_process_basis_is_not_rewritten(comparison, owner):
    # Simulate a persisted pre-#186 bound decision using the historical model.
    from django.apps import apps
    from django.db.migrations.state import ProjectState

    decision = choose(comparison, owner, **QUALITY)
    historical_model = ProjectState.from_apps(apps).apps.get_model(
        "architecture", "SolutionSelectionDecision"
    )
    diagnosis = deepcopy(decision.diagnosis_snapshot)
    diagnosis.pop("process_basis")
    historical_model.objects.filter(pk=decision.pk).update(diagnosis_snapshot=diagnosis)
    decision.refresh_from_db()
    assert not decision.outcome_review_required
    comparison.version += 1
    comparison.save()
    decision.refresh_from_db()
    assert decision.outcome_review_required
    assert decision.diagnosis_snapshot == diagnosis
