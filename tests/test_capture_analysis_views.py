from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator import views
from ki_radar.accelerator.analysis_service import CaptureAnalysisError
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession


def _session(owner, *, status=CaptureSession.Status.COMPLETED):
    catalog = get_capture_catalog("value_stream", "1.0")
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung",
        catalog_version="1.0",
        schema_version="1.0",
        answers={question.key: f"Antwort {question.key}" for question in catalog.questions},
        status=status,
        completed_at=now if status == CaptureSession.Status.COMPLETED else None,
        expires_at=now + timedelta(days=90),
    )


def _analysis(session, owner, *, status=CaptureAnalysis.Status.SUCCESS, error_code=""):
    now = timezone.now()
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=status,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        model_name="provider/model",
        prompt_version="1.0",
        extraction_schema_version="1.0",
        finished_at=now if status != CaptureAnalysis.Status.RUNNING else None,
        error_code=error_code,
    )


@pytest.mark.django_db
def test_review_get_never_starts_analysis_and_only_completed_session_has_action(
    client, owner, monkeypatch
):
    completed = _session(owner)
    draft = _session(owner, status=CaptureSession.Status.DRAFT)
    calls = 0

    def unexpected_call(**kwargs):
        nonlocal calls
        calls += 1

    monkeypatch.setattr(views, "execute_capture_analysis", unexpected_call)
    client.force_login(owner)

    completed_response = client.get(
        reverse("accelerator:capture_review", kwargs={"session_id": completed.pk})
    )
    draft_response = client.get(
        reverse("accelerator:capture_review", kwargs={"session_id": draft.pk})
    )

    assert calls == 0
    assert "Antworten analysieren" in completed_response.content.decode()
    assert "Antworten analysieren" not in draft_response.content.decode()


@pytest.mark.django_db
def test_analysis_endpoint_requires_post(client, owner):
    session = _session(owner)
    client.force_login(owner)

    response = client.get(reverse("accelerator:capture_analyze", kwargs={"session_id": session.pk}))

    assert response.status_code == 405


@pytest.mark.django_db
def test_explicit_analysis_post_redirects_to_new_preview(client, owner, monkeypatch):
    session = _session(owner)
    analysis = _analysis(session, owner)
    monkeypatch.setattr(views, "execute_capture_analysis", lambda **kwargs: analysis)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:capture_analyze", kwargs={"session_id": session.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk}
    )


@pytest.mark.django_db
def test_analysis_error_returns_to_review_and_preserves_existing_success(
    client, owner, monkeypatch
):
    session = _session(owner)
    successful = _analysis(session, owner)

    def fail(**kwargs):
        raise CaptureAnalysisError("Provider nicht verfügbar.", code="provider_unavailable")

    monkeypatch.setattr(views, "execute_capture_analysis", fail)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:capture_analyze", kwargs={"session_id": session.pk}),
        follow=True,
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Provider nicht verfügbar" in content
    assert reverse("accelerator:analysis_detail", kwargs={"analysis_id": successful.pk}) in content


@pytest.mark.django_db
def test_preview_shows_source_uncertainty_and_no_block5_actions(client, owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="value_stream.scope_in",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Angebote fachlich vergleichen",
        source_question="vs_scope_in",
        source_excerpt="Antwort vs_scope_in",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Explizit genannt.",
    )
    client.force_login(owner)

    response = client.get(
        reverse("accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "value_stream.scope_in" in content
    assert "Antwort vs_scope_in" in content
    assert "Unsicherheit: Niedrig" in content
    assert "Explizit genannt" in content
    assert "Übernehmen" not in content
    assert "Verwerfen" not in content


@pytest.mark.django_db
def test_preview_labels_estimated_llm_cost_in_usd(client, owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    analysis.total_tokens = 8901
    analysis.cost = Decimal("0.014670")
    analysis.save(update_fields=["total_tokens", "cost"])
    client.force_login(owner)

    response = client.get(
        reverse("accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "8901 Tokens" in content
    assert "Geschätzte LLM-Kosten: 0,014670 USD" in content
    assert "Kostenwert" not in content


@pytest.mark.django_db
def test_failed_preview_has_controlled_error_without_hiding_capture(client, owner):
    session = _session(owner)
    analysis = _analysis(
        session,
        owner,
        status=CaptureAnalysis.Status.FAILED,
        error_code="timeout",
    )
    client.force_login(owner)

    response = client.get(
        reverse("accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk})
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "konnte nicht abgeschlossen werden" in content
    assert "timeout" in content
    assert reverse("accelerator:capture_review", kwargs={"session_id": session.pk}) in content


@pytest.mark.django_db
def test_foreign_session_and_analysis_are_not_exposed(client, owner, other_owner):
    session = _session(owner)
    analysis = _analysis(session, owner)
    client.force_login(other_owner)

    assert (
        client.post(
            reverse("accelerator:capture_analyze", kwargs={"session_id": session.pk})
        ).status_code
        == 404
    )
    assert (
        client.get(
            reverse("accelerator:analysis_detail", kwargs={"analysis_id": analysis.pk})
        ).status_code
        == 404
    )


@pytest.mark.django_db
def test_unsupported_frozen_catalog_is_not_analyzable_and_direct_post_is_controlled(client, owner):
    session = _session(owner)
    CaptureSession.objects.filter(pk=session.pk).update(catalog_version="0.9")
    client.force_login(owner)

    review = client.get(reverse("accelerator:capture_review", kwargs={"session_id": session.pk}))
    post = client.post(
        reverse("accelerator:capture_analyze", kwargs={"session_id": session.pk}),
        follow=True,
    )

    assert "Antworten analysieren" not in review.content.decode()
    assert post.status_code == 200
    assert "wird nicht mehr unterstützt" in post.content.decode()
