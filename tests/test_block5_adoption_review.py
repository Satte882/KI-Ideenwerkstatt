from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.candidate_snapshot import create_adoption_candidates
from ki_radar.accelerator.catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from ki_radar.accelerator.extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
)
from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionAudit,
    FieldAdoptionCandidate,
)
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.architecture.models import ValueStream


@pytest.fixture(autouse=True)
def enable_field_adoption(settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = True


def make_candidate(*, owner, business_unit, uncertainty):
    target = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        status=ValueStream.Status.ACTIVE,
        description="Bestehende Beschreibung",
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        created_by=owner,
    )
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.expires_at = timezone.now() + timedelta(days=90)
    session.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="b" * 64,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        provider="openrouter",
        model_name="test/model",
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureSession.CaptureType.VALUE_STREAM,
        target_field="description",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Neue geprüfte Beschreibung",
        source_question="identity",
        source_excerpt="Die Beschaffung soll künftig transparent beschrieben werden.",
        uncertainty=uncertainty,
        uncertainty_reason="Testregel",
    )
    candidate = create_adoption_candidates(analysis_id=analysis.pk)[0]
    return target, session, analysis, candidate


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("uncertainty", "direct_visible", "edited_visible", "preview_visible"),
    [
        (CaptureFieldSuggestion.Uncertainty.LOW, True, True, False),
        (CaptureFieldSuggestion.Uncertainty.MEDIUM, False, True, False),
        (CaptureFieldSuggestion.Uncertainty.HIGH, False, False, True),
    ],
)
def test_review_ui_follows_uncertainty_policy(
    client,
    owner,
    business_unit,
    uncertainty,
    direct_visible,
    edited_visible,
    preview_visible,
):
    _target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=uncertainty,
    )
    client.force_login(owner)

    response = client.get(reverse("accelerator:analysis_detail", args=[analysis.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert str(candidate.pk) in content
    assert ("Direkt übernehmen" in content) is direct_visible
    assert ("Bearbeitet übernehmen" in content) is edited_visible
    assert ("Hohe Unsicherheit" in content) is preview_visible
    assert "Verwerfen" in content
    assert "Bestehende Beschreibung" in content


@pytest.mark.django_db
def test_review_ui_resolves_prefixed_extraction_target_path(
    client,
    owner,
    business_unit,
):
    target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    suggestion = candidate.suggestion
    suggestion.target_field = "value_stream.description"
    suggestion.save(update_fields=["target_field", "updated_at"])
    client.force_login(owner)

    response = client.get(reverse("accelerator:analysis_detail", args=[analysis.pk]))
    content = response.content.decode()

    assert response.status_code == 200
    assert str(candidate.pk) in content
    assert "Direkt übernehmen" in content

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "direct"},
    )
    target.refresh_from_db()
    candidate.refresh_from_db()

    assert response.status_code == 302
    assert target.description == "Neue geprüfte Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.ADOPTED


@pytest.mark.django_db
def test_medium_direct_request_is_rejected_server_side(client, owner, business_unit):
    target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=CaptureFieldSuggestion.Uncertainty.MEDIUM,
    )
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "direct"},
    )

    assert response.status_code == 302
    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.FAILED
    assert candidate.error_code == "action_not_allowed"
    assert FieldAdoptionAudit.objects.get(candidate_id_snapshot=candidate.pk).outcome == (
        "action_not_allowed"
    )


@pytest.mark.django_db
def test_edited_adoption_route_uses_regular_field_update(client, owner, business_unit):
    target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "edited", "edited_value": "Manuell geprüfte Beschreibung"},
    )

    assert response.status_code == 302
    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.description == "Manuell geprüfte Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.ADOPTED_EDITED


@pytest.mark.django_db
def test_conflict_ui_shows_three_values_and_allows_discard(client, owner, business_unit):
    target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    target.description = "Zwischenzeitlich geänderter Wert"
    target.save(update_fields=["description", "updated_at"])
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "direct"},
    )
    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == FieldAdoptionCandidate.Status.CONFLICT

    response = client.get(reverse("accelerator:analysis_detail", args=[analysis.pk]))
    content = response.content.decode()
    assert "Damals" in content
    assert "Aktuell" in content
    assert "Vorschlag" in content
    assert "Zwischenzeitlich geänderter Wert" in content
    assert "Regulär bearbeiten" in content
    assert "Neu analysieren" in content
    assert "Verwerfen" in content

    response = client.post(
        reverse("accelerator:candidate_reject", args=[analysis.pk, candidate.pk])
    )
    assert response.status_code == 302
    candidate.refresh_from_db()
    assert candidate.status == FieldAdoptionCandidate.Status.REJECTED
    assert candidate.error_code == "conflict_discarded"
    assert FieldAdoptionAudit.objects.filter(candidate_id_snapshot=candidate.pk).count() == 1


@pytest.mark.django_db
def test_feature_flag_hides_controls_and_blocks_direct_request(
    client,
    owner,
    business_unit,
    settings,
):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = False
    target, _session, analysis, candidate = make_candidate(
        owner=owner,
        business_unit=business_unit,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    client.force_login(owner)

    response = client.get(reverse("accelerator:analysis_detail", args=[analysis.pk]))
    assert response.status_code == 200
    assert "data-adoption-candidate" not in response.content.decode()

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "direct"},
    )
    assert response.status_code == 404
    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.OPEN
