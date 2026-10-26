"""Synthetic measurement boundaries; no real business measurements or model calls."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process
from test_issue_146_outcome_contract import process as process_fixture

from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiative_models import InitiativeImpactReview
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.services import create_use_case_from_selected_solution

pytestmark = pytest.mark.django_db
process = process_fixture


def intervention(owner, process, kind="hybrid", ai=True):
    initiative = bind_process(owner, process)
    option = process.solution_options.get(option_type="assistant")
    option.option_type = kind
    option.contains_ai_component = ai
    option.save()
    decision = select_preferred_solution(
        process_analysis=process,
        selected_option=option,
        rationale="Synthetischer begrenzter Vergleich, keine reale Nutzenbehauptung",
        actor=owner,
    )
    case = (
        create_use_case_from_selected_solution(decision=decision, actor=owner).use_case
        if option.starts_ai_use_case
        else None
    )
    return initiative, decision, case


def save(owner, initiative, data, *, finalize=True):
    initiative.refresh_from_db()
    return save_impact_review(
        initiative=initiative,
        actor=owner,
        expected_revision=initiative.revision,
        data={
            "effect_status": "unclear",
            "effect_reason": "Synthetisch: Geschäftswirkung nicht nachgewiesen",
            **data,
        },
        finalize=finalize,
    )


@pytest.mark.parametrize("kind", ["hybrid", "custom_software", "other"])
def test_ai_selection_cannot_finalize_independent_copy(owner, process, kind):
    initiative, decision, case = intervention(owner, process, kind)
    case.metric_name = "Bearbeitungszeit"
    case.save()
    with pytest.raises(ValidationError, match="referenzieren"):
        save(
            owner,
            initiative,
            {"selection": decision, "process_measurement": process.baseline_metrics},
        )


AI_TYPES = ["hybrid", "custom_software", "other", "assistant", "analytics_ml", "generative_ai"]
NON_AI_TYPES = [
    "hybrid",
    "custom_software",
    "other",
    "organizational",
    "rule_automation",
    "standard_software",
    "no_tech",
]
ORGANIZATIONAL = {
    "process_measurement_kind": "organizational",
    "process_measurement_boundary": (
        "Andere Groesse: Anteil verbindlicher Freigaben der Reiseorganisation; "
        "organisatorische Freigaberegel; Dokumentenpruefung aller Freigaben im Testzeitraum. "
        "Keine Bearbeitungszeit der KI, keine Addition und kein Kausalitaetsbeweis."
    ),
    "process_measurement": "Synthetischer Dokumentenpruefstand; keine reale Unternehmensmessung",
    "process_result": "achieved",
}


@pytest.mark.parametrize("kind", AI_TYPES)
def test_other_organizational_measurement_with_actual_ai_reference(owner, process, kind):
    initiative, decision, case = intervention(owner, process, kind)
    case.metric_name = "Bearbeitungszeit"
    case.save()
    review = save(owner, initiative, {"selection": decision, "use_case": case, **ORGANIZATIONAL})
    assert not review.review_required
    assert review.metric_history_id == case.history.first().history_id
    assert (
        review.history.first().process_measurement_boundary
        == ORGANIZATIONAL["process_measurement_boundary"]
    )
    initiative.refresh_from_db()
    assert initiative.effect_status == review.attribution == "unclear"
    assert review.business_measurement == ""


@pytest.mark.parametrize("kind", NON_AI_TYPES)
def test_non_ai_measurement_needs_no_artificial_case(owner, process, kind):
    initiative, decision, case = intervention(owner, process, kind, ai=False)
    assert case is None
    review = save(
        owner,
        initiative,
        {
            "selection": decision,
            "process_measurement": "Synthetischer Prozessnachweis",
            "process_result": "missed",
        },
    )
    assert not review.review_required and review.use_case_id is None


@pytest.mark.parametrize("kind", AI_TYPES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("process_measurement", "Kopie der KI-Messung"),
        ("process_result", "achieved"),
    ],
)
def test_no_implicit_copy_even_with_case(owner, process, kind, field, value):
    initiative, decision, case = intervention(owner, process, kind)
    with pytest.raises(ValidationError, match="referenzieren"):
        save(owner, initiative, {"selection": decision, "use_case": case, field: value})


def test_boundary_and_actual_reference_required_only_on_finalization(owner, process):
    initiative, decision, case = intervention(owner, process)
    data = {"selection": decision, **ORGANIZATIONAL, "process_measurement_boundary": ""}
    draft = save(owner, initiative, data, finalize=False)
    assert draft.review_required
    with pytest.raises(ValidationError, match="referenzieren"):
        save(owner, initiative, data)
    data["use_case"] = case
    with pytest.raises(ValidationError, match="abgrenzen"):
        save(owner, initiative, data)
    data["process_measurement_boundary"] = ORGANIZATIONAL["process_measurement_boundary"]
    data["process_measurement"] = ""
    with pytest.raises(ValidationError, match="Messdefinition"):
        save(owner, initiative, data)
    assert InitiativeImpactReview.objects.get().reviewed_at is None


@pytest.mark.parametrize("kind", ["hybrid", "custom_software", "other"])
def test_existing_ambiguous_draft_contract_remains(owner, process, kind):
    initiative, decision, _ = intervention(owner, process, kind)
    review = save(
        owner,
        initiative,
        {
            "selection": decision,
            "process_measurement": process.baseline_metrics,
        },
        finalize=False,
    )
    assert review.review_required and review.reviewed_at is None


@pytest.mark.parametrize("foreign_initiative", [False, True])
def test_declared_boundary_cannot_bypass_origin(owner, process, business_unit, foreign_initiative):
    from ki_radar.use_cases.models import UseCase

    initiative, decision, _ = intervention(owner, process)
    other = save_initiative(actor=owner, data={"title": "Anderes Vorhaben"})
    case = UseCase.objects.create(
        title="Unpassende Herkunft",
        business_unit=business_unit,
        business_owner=owner,
        initiative=other if foreign_initiative else initiative,
    )
    with pytest.raises(ValidationError, match=r"Vorhaben|Herkunft"):
        save(owner, initiative, {"selection": decision, "use_case": case, **ORGANIZATIONAL})
    assert not InitiativeImpactReview.objects.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_measurement_boundary", "Andere Population"),
        ("process_measurement_kind", ""),
        ("process_measurement", "Anderer Messstand"),
    ],
)
def test_boundary_is_material_and_history_preserved(owner, process, field, value):
    initiative, decision, case = intervention(owner, process)
    review = save(owner, initiative, {"selection": decision, "use_case": case, **ORGANIZATIONAL})
    original = review.history.first()
    # Simulate an external edit; it must not inherit the prior human confirmation.
    InitiativeImpactReview.objects.filter(pk=review.pk).update(**{field: value})
    review.refresh_from_db()
    assert review.review_required
    persisted = review.history.get(history_id=original.history_id)
    assert persisted.process_measurement_boundary == original.process_measurement_boundary
    assert persisted.process_measurement == original.process_measurement
    assert persisted.reviewed_at == original.reviewed_at
    restored = save(owner, initiative, {field: ORGANIZATIONAL[field]})
    assert not restored.review_required
    assert restored.history.count() == 2


def test_historical_ambiguous_review_visible_but_requires_reconfirmation(owner, process, client):
    initiative, decision, case = intervention(owner, process)
    review = save(owner, initiative, {"selection": decision})
    # Equivalent to the pre-fix row and its original audit record; no backfill.
    InitiativeImpactReview.objects.filter(pk=review.pk).update(
        process_measurement=process.baseline_metrics,
    )
    review.history.filter(reviewed_at=review.reviewed_at).update(
        process_measurement=process.baseline_metrics,
    )
    original = review.history.first()
    review.refresh_from_db()
    assert review.review_required and "referenzieren" in review.measurement_review_blocker
    client.force_login(owner)
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "Historische Messnachweise bleiben erhalten" in html
    assert process.baseline_metrics in html
    restored = save(
        owner,
        initiative,
        {
            "use_case": case,
            "process_measurement": "",
            "process_result": "unknown",
        },
    )
    assert not restored.review_required
    persisted = review.history.get(history_id=original.history_id)
    assert persisted.process_measurement == original.process_measurement
    assert persisted.process_measurement_kind == persisted.process_measurement_boundary == ""
    assert persisted.reviewed_at == original.reviewed_at


def test_real_form_keeps_boundary_input_and_draft_then_finalizes(owner, process, client):
    initiative, decision, case = intervention(owner, process)
    client.force_login(owner)
    url = reverse("use_cases:initiative_impact", args=[initiative.pk])
    initiative.refresh_from_db()
    data = {
        "expected_revision": initiative.revision,
        "selection": decision.pk,
        "use_case": case.pk,
        "effect_status": "unclear",
        "effect_reason": "Geschäftswirkung unbekannt",
        "attribution": "unclear",
        "action": "review",
        **ORGANIZATIONAL,
        "process_measurement_boundary": "",
    }
    response = client.post(url, data)
    assert response.status_code == 200
    assert response.context["form"]["process_measurement"].value() == data["process_measurement"]
    assert not InitiativeImpactReview.objects.exists()
    data["action"] = "draft"
    assert client.post(url, data).status_code == 302
    initiative.refresh_from_db()
    data.update(expected_revision=initiative.revision, action="review", **ORGANIZATIONAL)
    assert client.post(url, data).status_code == 302
    review = InitiativeImpactReview.objects.get()
    assert not review.review_required
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert ORGANIZATIONAL["process_measurement_boundary"] in html
    assert ORGANIZATIONAL["process_measurement"] in html
    assert "KI-Prozesswirkung: siehe referenzierte Originalmetrik" in html


def test_boundary_does_not_weaken_metric_freshness_or_metadata_rules(owner, process):
    initiative, decision, case = intervention(owner, process)
    review = save(owner, initiative, {"selection": decision, "use_case": case, **ORGANIZATIONAL})
    initiative.refresh_from_db()
    save_initiative(actor=owner, initiative=initiative, data={"title": "Nur neuer Titel"})
    review.refresh_from_db()
    assert not review.review_required
    case.metric_measurement_population = "Andere Population"
    case.save()
    review.refresh_from_db()
    assert review.review_required


def test_manipulated_option_origin_is_not_authorized_by_boundary(owner, process):
    from ki_radar.architecture.models import UseCaseOrigin

    initiative, decision, case = intervention(owner, process)
    UseCaseOrigin.objects.filter(use_case=case).update(
        solution_option=process.solution_options.exclude(pk=decision.selected_option_id).get(),
    )
    with pytest.raises(ValidationError, match="Herkunft"):
        save(owner, initiative, {"selection": decision, "use_case": case, **ORGANIZATIONAL})


@pytest.mark.django_db(transaction=True)
def test_migration_retains_old_measurements_and_audit_without_inferred_boundary(owner):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.utils import timezone

    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    target = [("use_cases", "0022_idea_intake_context")]
    executor.migrate(target)
    try:
        apps = executor.loader.project_state(target).apps
        initiative = apps.get_model("use_cases", "ImprovementInitiative").objects.create(
            title="Historischer Nachweis",
            created_by_id=owner.pk,
        )
        old = apps.get_model("use_cases", "InitiativeImpactReview").objects.create(
            initiative_id=initiative.pk,
            process_measurement="Historischer Originalmessstand",
            reviewed_at=timezone.now(),
            reviewed_by_id=owner.pk,
            metric_history_id=42,
        )
        old_values = {f.attname: getattr(old, f.attname) for f in old._meta.fields}
        audit = apps.get_model("use_cases", "HistoricalInitiativeImpactReview").objects.create(
            **old_values,
            history_type="+",
            history_date=timezone.now(),
            history_user_id=owner.pk,
        )
        audit_values = {f.attname: getattr(audit, f.attname) for f in audit._meta.fields}
    finally:
        MigrationExecutor(connection).migrate(leaves)
    review = InitiativeImpactReview.objects.get(pk=old.pk)
    assert all(getattr(review, field) == value for field, value in old_values.items())
    entry = review.history.get(history_id=audit.pk)
    assert all(getattr(entry, field) == value for field, value in audit_values.items())
    assert review.process_measurement_kind == review.process_measurement_boundary == ""
    assert entry.process_measurement_kind == entry.process_measurement_boundary == ""
