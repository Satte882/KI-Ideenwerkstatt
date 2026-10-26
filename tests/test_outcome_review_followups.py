"""Regression for #147 follow-up: current business proof and metric-only staleness."""

from datetime import date
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_147_impact_reviews import case as case_fixture
from test_issue_147_impact_reviews import initiative as initiative_fixture

from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.initiatives import save_initiative

pytestmark = pytest.mark.django_db
initiative = initiative_fixture
case = case_fixture


def reviewed(owner, initiative, case, effect="confirmed"):
    initiative.refresh_from_db()
    return save_impact_review(
        initiative=initiative,
        actor=owner,
        expected_revision=initiative.revision,
        data={
            "use_case": case,
            "business_measurement": "Buchungsquote 18/100; Quartal 3",
            "business_evidence": "CRM-Auswertung A",
            "measurement_difference": "Buchungsquote statt Bearbeitungszeit",
            "effect_status": effect,
            "effect_reason": "Buchungsquote fachlich gemessen",
        },
        finalize=True,
    )


@pytest.mark.parametrize("effect", ["confirmed", "refuted"])
def test_positive_completion_without_current_review_rejected_even_by_orm(owner, initiative, effect):
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        save_initiative(
            actor=owner,
            initiative=initiative,
            data={
                "status": "completed",
                "effect_status": effect,
                "effect_reason": "Unbelegter Erfolg",
            },
        )
    initiative.refresh_from_db()
    initiative.status = "completed"
    initiative.effect_status = effect
    initiative.effect_reason = "Unbelegter Erfolg"
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        initiative.save()
    initiative.refresh_from_db()
    assert initiative.status == "draft"


@pytest.mark.parametrize("effect", ["confirmed", "refuted"])
def test_proven_completion_keeps_existing_review_current(owner, initiative, case, effect):
    review = reviewed(owner, initiative, case, effect)
    assert not review.review_required
    initiative.refresh_from_db()
    completed = save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})
    review.refresh_from_db()
    assert completed.status == "completed"
    assert completed.effect_status == effect
    assert not review.review_required
    assert review.initiative_revision == completed.revision


def test_review_is_not_reused_for_changed_effect_claim(owner, initiative, case):
    reviewed(owner, initiative, case)
    initiative.refresh_from_db()
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        save_initiative(
            actor=owner,
            initiative=initiative,
            data={
                "status": "completed",
                "effect_status": "refuted",
                "effect_reason": "Andere, nicht bestätigte Interpretation",
            },
        )
    initiative.refresh_from_db()
    assert initiative.status == "draft"


def test_unrelated_use_case_metadata_does_not_invalidate_review(owner, initiative, case):
    review = reviewed(owner, initiative, case)
    assert not review.review_required
    previous_history = review.metric_history_id
    case.title = "Umbenannt ohne neue Messung"
    case.save()
    review.refresh_from_db()
    assert case.history.first().history_id != previous_history
    assert not review.review_required
    case.metric_actual = Decimal("6.0000")
    case.save()
    review.refresh_from_db()
    assert review.review_required


def test_measurement_evidence_update_requires_review(owner, initiative, case):
    review = reviewed(owner, initiative, case)
    case.metric_evidence_url = "https://example.com/updated-proof"
    case.save()
    review.refresh_from_db()
    assert review.review_required


def test_metric_history_reference_cannot_adopt_a_new_measurement_without_review(
    owner, initiative, case
):
    review = reviewed(owner, initiative, case)
    original = review.metric_history_id
    case.metric_actual = Decimal("6.0000")
    case.save()
    review.metric_history_id = case.history.first().history_id
    review.save()
    assert review.review_required
    assert case.history.get(history_id=original).metric_actual == Decimal("8.0000")
    assert review.history.filter(metric_history_id=original).exists()


def test_unknown_business_effect_can_close_without_fake_proof(owner, initiative):
    completed = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "status": "completed",
            "effect_status": "unclear",
            "effect_reason": "Wirkung nicht messbar; Gründe dokumentiert",
        },
    )
    assert completed.status == "completed"


@pytest.mark.parametrize("via_service", [True, False])
@pytest.mark.parametrize(
    "field,value",
    [
        ("effect_status", "refuted"),
        ("business_outcome", "Ein anderes Geschäftsergebnis"),
    ],
)
def test_completion_cannot_reuse_proof_for_a_changed_claim(
    owner, initiative, case, via_service, field, value
):
    reviewed(owner, initiative, case)
    initiative.refresh_from_db()
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        if via_service:
            save_initiative(
                actor=owner, initiative=initiative, data={"status": "completed", field: value}
            )
        else:
            initiative.status = "completed"
            setattr(initiative, field, value)
            initiative.save()


@pytest.mark.parametrize("method", ["update", "bulk_update", "bulk_create"])
def test_bulk_paths_cannot_create_an_unproven_completion(owner, initiative, method):
    with pytest.raises(ValidationError):
        if method == "update":
            ImprovementInitiative.objects.filter(pk=initiative.pk).update(
                status="completed", effect_status="confirmed", effect_reason="Ohne Nachweis"
            )
        elif method == "bulk_update":
            initiative.status = "completed"
            initiative.effect_status = "confirmed"
            initiative.effect_reason = "Ohne Nachweis"
            ImprovementInitiative.objects.bulk_update(
                [initiative], ["status", "effect_status", "effect_reason"]
            )
        else:
            ImprovementInitiative.objects.bulk_create(
                [
                    ImprovementInitiative(
                        title="Ohne Nachweis",
                        status="completed",
                        effect_status="confirmed",
                        effect_reason="Ohne Nachweis",
                        created_by=owner,
                        updated_by=owner,
                    )
                ]
            )


@pytest.mark.parametrize(
    "field,value",
    [
        ("metric_name", "Andere Kennzahl"),
        ("metric_type", "count"),
        ("metric_direction", "higher"),
        ("metric_unit", "Sekunden"),
        ("metric_baseline", Decimal(21)),
        ("metric_target", Decimal(9)),
        ("metric_actual", Decimal(7)),
        ("metric_measurement_method", "Andere Methode"),
        ("metric_measurement_period", "Juli"),
        ("metric_measurement_population", "Andere Population"),
        ("metric_measured_at", date(2026, 10, 22)),
        ("metric_evidence_url", "https://example.invalid/other"),
    ],
)
def test_every_metric_component_invalidates_the_review(owner, initiative, case, field, value):
    review = reviewed(owner, initiative, case)
    setattr(case, field, value)
    case.save()
    review.refresh_from_db()
    assert review.review_required


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "Anderer Titel"),
        ("next_review_date", date(2026, 11, 1)),
        ("expected_benefit", "Neue Beschreibung"),
        ("status", "review"),
    ],
)
def test_non_metric_edits_keep_the_original_measurement_reference(
    owner, initiative, case, field, value
):
    review = reviewed(owner, initiative, case)
    original = review.metric_history_id
    setattr(case, field, value)
    case.save()
    review.refresh_from_db()
    assert not review.review_required
    assert review.metric_history_id == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("business_evidence", ""),
        ("business_measurement", ""),
        ("reviewed_by", None),
    ],
)
def test_incomplete_review_cannot_prove_completion(owner, initiative, case, field, value):
    review = reviewed(owner, initiative, case)
    setattr(review, field, value)
    review.save()
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})


def test_legacy_completion_is_preserved_until_its_claim_changes(owner, initiative):
    # Reproduce a pre-gate stored record through Django's internal base manager.
    ImprovementInitiative._base_manager.filter(pk=initiative.pk).update(
        status="completed", effect_status="confirmed", effect_reason="Historische Aussage"
    )
    saved = save_initiative(actor=owner, initiative=initiative, data={"title": "Schreibkorrektur"})
    assert saved.status == "completed"
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        save_initiative(actor=owner, initiative=saved, data={"effect_reason": "Neue Aussage"})
    draft = save_initiative(
        actor=owner,
        initiative=saved,
        data={
            "status": "draft",
            "effect_reason": "Neue Aussage",
            "business_outcome": "Noch offen",
        },
    )
    assert draft.status == "draft"


def test_bulk_draft_capture_remains_available(owner):
    rows = ImprovementInitiative.objects.bulk_create(
        [ImprovementInitiative(title="Offener Eingang", created_by=owner, updated_by=owner)]
    )
    ImprovementInitiative.objects.filter(pk=rows[0].pk).update(title="Neuer Titel")
    rows[0].refresh_from_db()
    assert rows[0].status == "draft" and rows[0].business_outcome == ""


def test_completion_form_without_proof_retains_input_and_can_save_draft(client, owner, initiative):
    client.force_login(owner)
    data = {
        "title": "Eingaben behalten",
        "status": "completed",
        "evidence_level": "hypothesis",
        "effect_status": "confirmed",
        "effect_reason": "Ungeprüfte Behauptung",
        "expected_revision": initiative.revision,
    }
    response = client.post(initiative.get_absolute_url(), data)
    assert response.status_code == 200
    assert response.context["form"]["effect_reason"].value() == data["effect_reason"]
    assert "Wirkungsreview" in response.content.decode()
    data["action"] = "save_draft"
    assert client.post(initiative.get_absolute_url(), data).status_code == 302
    initiative.refresh_from_db()
    assert initiative.status == "draft" and initiative.effect_reason == data["effect_reason"]


def test_completion_form_accepts_the_same_reviewed_statement(client, owner, initiative, case):
    review = reviewed(owner, initiative, case)
    client.force_login(owner)
    form = client.get(initiative.get_absolute_url()).context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data["status"] = "completed"
    assert (
        client.post(reverse("use_cases:initiative_edit", args=[initiative.pk]), data).status_code
        == 302
    )
    initiative.refresh_from_db()
    review.refresh_from_db()
    assert initiative.status == "completed" and not review.review_required
