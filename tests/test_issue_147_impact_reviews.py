from decimal import Decimal

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process, select
from test_issue_146_outcome_contract import process as process_fixture

from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiative_models import InitiativeImpactReview
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db
process = process_fixture


@pytest.fixture
def initiative(owner):
    return save_initiative(actor=owner, data={"title": "Wirkung offen"})


@pytest.fixture
def case(owner, business_unit, initiative):
    return UseCase.objects.create(
        title="KI-Prozess",
        business_unit=business_unit,
        business_owner=owner,
        initiative=initiative,
        metric_name="Bearbeitungszeit",
        metric_direction="lower",
        metric_unit="Minuten",
        metric_baseline=Decimal(20),
        metric_target=Decimal(10),
        metric_actual=Decimal(8),
        metric_measurement_method="Zeitmessung",
    )


def save(owner, initiative, data=None, finalize=False):
    initiative.refresh_from_db()
    return save_impact_review(
        initiative=initiative,
        actor=owner,
        expected_revision=initiative.revision,
        data=data or {},
        finalize=finalize,
    )


def test_empty_review_draft_no_new_intake_gate(owner, initiative):
    review = save(owner, initiative)
    assert review.review_required and review.reviewed_at is None
    assert review.process_result == "unknown"
    assert review.attribution == "unclear"
    assert review.business_measurement == ""
    assert not UseCase.objects.exists()


def test_non_ai_selection_is_open_until_explicit_review(client, owner, process):
    initiative = bind_process(owner, process)
    select(owner, process)
    initiative.refresh_from_db()
    client.force_login(owner)
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "Wirkungsprüfung offen" in html and "Organisieren" in html
    assert not UseCase.objects.exists()
    decision = process.solution_selection_decisions.first()
    snapshot = decision.outcome_snapshot.copy()
    review = save(
        owner,
        initiative,
        {
            "selection": decision,
            "process_result": "achieved",
            "process_measurement": "Rückfragen je Angebot; Juni; 5 statt 10; CRM-Bericht 1",
            "effect_status": "unclear",
            "effect_reason": "Buchungen noch nicht gemessen",
        },
        finalize=True,
    )
    assert not review.review_required
    initiative.refresh_from_db()
    assert initiative.status == "draft" and initiative.effect_status == "unclear"
    assert review.attribution == "unclear" and review.business_measurement == ""
    decision.refresh_from_db()
    assert decision.outcome_snapshot == snapshot
    assert not UseCase.objects.exists()


def test_achieved_ai_metric_never_confirms_business_success(client, owner, initiative, case):
    assert case.metric_result == "achieved"
    review = save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "unclear",
            "effect_reason": "Konversion unbekannt",
        },
        finalize=True,
    )
    assert not review.review_required
    assert review.process_measurement == ""
    initiative.refresh_from_db()
    assert initiative.effect_status == "unclear"
    assert case.status == "idea" and case.approval_decisions.count() == case.reviews.count() == 0
    client.force_login(owner)
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "Bearbeitungszeit" in html and "Konversion unbekannt" in html
    assert "Noch nicht gemessen / offen" in html
    assert "Keine automatische Addition" in html


@pytest.mark.parametrize(
    "field,value",
    [
        ("process_measurement", "8 Minuten"),
        ("process_result", "achieved"),
    ],
)
def test_ai_metric_cannot_be_copied(owner, initiative, case, field, value):
    with pytest.raises(ValidationError, match="referenzieren"):
        save(owner, initiative, {"use_case": case, field: value})
    assert not InitiativeImpactReview.objects.exists()


def test_final_claim_requires_distinct_measurement_and_evidence_but_draft_saves(
    owner, initiative, case
):
    data = {"use_case": case, "effect_status": "confirmed", "effect_reason": "Fachliche Aussage"}
    with pytest.raises(ValidationError, match="Nachweis"):
        save(owner, initiative, data, finalize=True)
    review = save(owner, initiative, data)
    assert review.review_required
    data.update(
        business_measurement="Konversion: 20 von 100 Angeboten im Juni",
        business_evidence="CRM Juni",
    )
    with pytest.raises(ValidationError, match="abgrenzen"):
        save(owner, initiative, data, finalize=True)
    data["measurement_difference"] = "Buchungsquote statt Bearbeitungszeit; keine Addition"
    review = save(owner, initiative, data, finalize=True)
    assert not review.review_required and review.attribution == "unclear"


def test_foreign_reference_and_forged_server_fields_rejected(
    owner, other_owner, coordinator, initiative, case
):
    other = save_initiative(actor=other_owner, data={"title": "Fremd"})
    with pytest.raises(ValidationError, match="anderen Vorhaben"):
        save(coordinator, other, {"use_case": case})
    with pytest.raises(ValidationError, match="Serververwaltete"):
        save(owner, initiative, {"reviewed_by": other_owner})


def test_permissions_owner_label_and_optimistic_lock(client, owner, reader, initiative):
    for actor in [reader]:
        with pytest.raises(PermissionDenied):
            save(actor, initiative)
    client.force_login(reader)
    assert (
        client.get(reverse("use_cases:initiative_impact", args=[initiative.pk])).status_code == 403
    )
    with pytest.raises(ValidationError, match="inzwischen"):
        save_impact_review(initiative=initiative, actor=owner, expected_revision=0, data={})


def test_outcome_and_metric_changes_request_review_preserve_history(owner, initiative, case):
    review = save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "unclear",
            "effect_reason": "Offen",
        },
        finalize=True,
    )
    prior_metric = review.metric_history_id
    assert not review.review_required
    case.metric_actual = Decimal(7)
    case.save()
    review.refresh_from_db()
    assert review.review_required
    assert case.history.get(history_id=prior_metric).metric_actual == Decimal(8)
    saved = save_initiative(
        actor=owner, initiative=initiative, data={"business_outcome": "Anderes Ziel"}
    )
    review.refresh_from_db()
    assert review.review_required and review.outcome_revision != saved.outcome_revision
    assert review.history.first().reviewed_by == owner


def test_failed_review_retains_input_and_empty_draft_saves(client, owner, initiative):
    client.force_login(owner)
    url = reverse("use_cases:initiative_impact", args=[initiative.pk])
    data = {
        "action": "review",
        "expected_revision": initiative.revision,
        "process_result": "unknown",
        "attribution": "unclear",
        "business_measurement": "Noch unvollständiger Stand",
    }
    response = client.post(url, data)
    assert response.status_code == 200
    assert "Noch unvollständiger Stand" in response.content.decode()
    assert "Als Entwurf sichern" in response.content.decode()
    assert not InitiativeImpactReview.objects.exists()
    data["action"] = "draft"
    response = client.post(url, data)
    assert response.status_code == 302
    assert InitiativeImpactReview.objects.get().business_measurement == data["business_measurement"]


def test_failed_edit_does_not_display_unsaved_evidence_as_reviewed(client, owner, initiative, case):
    review = save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "unclear",
            "effect_reason": "Noch offen",
        },
        finalize=True,
    )
    initiative.refresh_from_db()
    client.force_login(owner)
    response = client.post(
        reverse("use_cases:initiative_impact", args=[initiative.pk]),
        {
            "action": "review",
            "expected_revision": initiative.revision,
            "use_case": case.pk,
            "process_result": "unknown",
            "attribution": "unclear",
            "business_measurement": "Ungeprüfte Änderung",
            "effect_status": "confirmed",
            "effect_reason": "Versuch ohne Nachweis",
        },
    )
    assert response.status_code == 200
    assert response.context["form"]["business_measurement"].value() == "Ungeprüfte Änderung"
    assert response.context["impact_review"].business_measurement == ""
    assert response.context["impact_review"].reviewed_at == review.reviewed_at
    assert response.context["initiative"].effect_status == "unclear"


@pytest.mark.parametrize("previous_review", [False, True])
@pytest.mark.parametrize("read_only", [False, True])
def test_draft_confirmed_statement_is_explicitly_unreviewed(
    client, owner, reader, initiative, case, previous_review, read_only
):
    if previous_review:
        review = save(
            owner,
            initiative,
            {
                "use_case": case,
                "effect_status": "confirmed",
                "effect_reason": "Geprüfter Befund",
                "business_measurement": "Buchungsquote: 20 von 100 Angeboten im Juni",
                "business_evidence": "CRM Juni",
                "measurement_difference": "Quote statt Zeit",
            },
            finalize=True,
        )
        assert not review.review_required
    review = save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "confirmed",
            "effect_reason": "Ungeprüfte Behauptung",
            "business_measurement": "",
            "business_evidence": "",
        },
    )
    initiative.refresh_from_db()
    assert initiative.effect_status == "confirmed"  # Keep all draft input.
    assert review.reviewed_at is None and review.review_required
    assert initiative.effect_statement_label == "Ungeprüfte Wirkungsaussage (Entwurf): Bestätigt"
    client.force_login(reader if read_only else owner)
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "Ungeprüfte Wirkungsaussage (Entwurf): Bestätigt" in html
    assert "<dd>Bestätigt" not in html
    assert "<dd>Geprüfte Wirkungsaussage" not in html
    dashboard = client.get(reverse("reporting:dashboard")).content.decode()
    assert "Wirkungsprüfung offen" in dashboard
    assert "Wirkungsstand geprüft · Bestätigt" not in dashboard
    if previous_review:
        assert review.history.count() == 2
        assert review.history.last().business_evidence == "CRM Juni"


def test_business_statement_only_qualified_as_reviewed_for_current_review(owner, initiative, case):
    # Also covers the existing initiative-edit path without a review record.
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "effect_status": "confirmed",
            "effect_reason": "Ungeprüfte Aussage",
        },
    )
    assert initiative.effect_statement_label.startswith("Ungeprüfte")
    save(
        owner,
        initiative,
        {
            "use_case": case,
            "business_measurement": "Buchungsquote: 20 von 100 im Juni",
            "business_evidence": "CRM Juni",
            "measurement_difference": "Quote statt Zeit",
        },
        finalize=True,
    )
    initiative.refresh_from_db()
    assert initiative.effect_statement_label == "Geprüfte Wirkungsaussage: Bestätigt"
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={"effect_reason": "Nachträglich geänderte Aussage"},
    )
    assert initiative.effect_statement_label.startswith("Ungeprüfte")


def test_invalid_initiative_edit_cannot_label_unsaved_claim_as_reviewed(
    client, owner, initiative, case
):
    save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "unclear",
            "effect_reason": "Noch offen",
        },
        finalize=True,
    )
    initiative.refresh_from_db()
    client.force_login(owner)
    response = client.post(
        initiative.get_absolute_url(),
        {
            "title": initiative.title,
            "status": "completed",
            "evidence_level": "hypothesis",
            "effect_status": "confirmed",
            "effect_reason": "",
            "expected_revision": initiative.revision,
        },
    )
    assert response.status_code == 200
    assert response.context["form"]["effect_status"].value() == "confirmed"
    assert response.context["initiative"].effect_status == "unclear"
    assert "<dd>Geprüfte Wirkungsaussage: Bestätigt" not in response.content.decode()
