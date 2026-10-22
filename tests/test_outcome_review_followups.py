"""Regression for #147 follow-up: current business proof and metric-only staleness."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError

from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiatives import save_initiative
from test_issue_147_impact_reviews import case as case_fixture
from test_issue_147_impact_reviews import initiative as initiative_fixture

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
    completed = save_initiative(
        actor=owner, initiative=initiative, data={"status": "completed"}
    )
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


def test_unknown_business_effect_can_close_without_fake_proof(owner, initiative):
    completed = save_initiative(
        actor=owner, initiative=initiative, data={
            "status": "completed",
            "effect_status": "unclear",
            "effect_reason": "Wirkung nicht messbar; Gründe dokumentiert",
        },
    )
    assert completed.status == "completed"
