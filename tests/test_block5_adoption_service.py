from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from ki_radar.accelerator.adoption_service import (
    AdoptionDisabled,
    AdoptionOutcome,
    adopt_field_candidate,
    reject_field_candidate,
)
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
    FieldAdoptionCandidate,
)
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_field_adoption(settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = True


def make_value_stream(*, business_unit, owner):
    return ValueStream.objects.create(
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


def make_use_case(*, business_unit, owner):
    use_case = UseCase.objects.create(
        title="Angebotsvergleich",
        summary="Bestehende Kurzbeschreibung",
        problem_statement="Der Vergleich ist langsam.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        target_users="Einkauf",
        business_owner=owner,
        expected_benefit="Bearbeitungszeit senken",
        submitter=owner,
    )
    use_case.classification.capability = "Supplier Management"
    use_case.classification.save(update_fields=["capability", "updated_at"])
    return use_case


def make_candidate(*, actor, target, field_name, proposed_value):
    capture_type = (
        CaptureSession.CaptureType.VALUE_STREAM
        if isinstance(target, ValueStream)
        else CaptureSession.CaptureType.USE_CASE
    )
    session = create_capture_session(actor=actor, capture_type=capture_type)
    bind_capture_target(actor=actor, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.expires_at = timezone.now() + timedelta(days=90)
    session.save(update_fields=["status", "completed_at", "expires_at", "updated_at"])
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=actor,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        finished_at=timezone.now(),
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=proposed_value,
        source_question="identity",
        source_excerpt=proposed_value,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )
    return create_adoption_candidates(analysis_id=analysis.pk)[0], session


@pytest.mark.django_db
def test_value_stream_field_is_adopted_atomically(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="description",
        proposed_value="Neue geprüfte Beschreibung",
    )
    original_scope = target.scope_in
    original_status = target.status

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.ADOPTED
    assert result.final_value == "Neue geprüfte Beschreibung"
    assert target.description == "Neue geprüfte Beschreibung"
    assert target.scope_in == original_scope
    assert target.status == original_status
    assert candidate.status == FieldAdoptionCandidate.Status.ADOPTED
    assert candidate.resolved_at is not None


@pytest.mark.django_db
def test_edited_use_case_adoption_preserves_history_status_and_classification(
    owner,
    business_unit,
):
    target = make_use_case(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="summary",
        proposed_value="Automatisierter Angebotsvergleich",
    )
    history_before = target.history.count()
    status_before = target.status
    decision_status_before = target.decision_status
    classification_updated_before = target.classification.updated_at

    result = adopt_field_candidate(
        candidate_id=candidate.pk,
        actor=owner,
        edited_value="  Assistierter Angebotsvergleich\r\n",
    )

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.ADOPTED_EDITED
    assert result.final_value == "Assistierter Angebotsvergleich"
    assert target.summary == "Assistierter Angebotsvergleich"
    assert target.status == status_before
    assert target.decision_status == decision_status_before
    target.classification.refresh_from_db()
    assert target.classification.capability == "Supplier Management"
    assert target.classification.updated_at == classification_updated_before
    assert target.history.count() == history_before + 1
    assert candidate.status == FieldAdoptionCandidate.Status.ADOPTED_EDITED


@pytest.mark.django_db
def test_field_conflict_never_overwrites_current_value(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    target.name = "Zwischenzeitlich geändert"
    target.save(update_fields=["name", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.CONFLICT
    assert result.previous_value == "Beschaffung"
    assert result.current_value == "Zwischenzeitlich geändert"
    assert result.proposed_value == "Strategische Beschaffung"
    assert result.target_updated_at_changed is True
    assert target.name == "Zwischenzeitlich geändert"
    assert candidate.status == FieldAdoptionCandidate.Status.CONFLICT
    assert candidate.error_code == AdoptionOutcome.CONFLICT


@pytest.mark.django_db
def test_unrelated_field_change_does_not_create_false_conflict(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    target.description = "Parallel ergänzte Beschreibung"
    target.save(update_fields=["description", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    assert result.outcome == AdoptionOutcome.ADOPTED
    assert result.target_updated_at_changed is True
    assert target.name == "Strategische Beschaffung"
    assert target.description == "Parallel ergänzte Beschreibung"


@pytest.mark.django_db
def test_permission_denial_is_terminal_and_changes_no_domain_field(
    owner,
    other_owner,
    business_unit,
):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=other_owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.PERMISSION_DENIED
    assert target.name == "Beschaffung"
    assert candidate.status == FieldAdoptionCandidate.Status.FAILED
    assert candidate.error_code == AdoptionOutcome.PERMISSION_DENIED
    assert candidate.resolved_at is not None


@pytest.mark.django_db
def test_stale_candidate_is_resolved_without_target_change(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    session.revision += 1
    session.save(update_fields=["revision", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.STALE
    assert target.name == "Beschaffung"
    assert candidate.status == FieldAdoptionCandidate.Status.STALE
    assert candidate.error_code == "stale_candidate"


@pytest.mark.django_db
def test_non_completed_session_is_stale(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    session.status = CaptureSession.Status.DRAFT
    session.completed_at = None
    session.save(update_fields=["status", "completed_at", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.STALE
    assert target.name == "Beschaffung"
    assert candidate.status == FieldAdoptionCandidate.Status.STALE


@pytest.mark.django_db
def test_inactive_and_missing_targets_have_distinct_results(owner, business_unit):
    inactive_target = make_value_stream(business_unit=business_unit, owner=owner)
    inactive_candidate, _session = make_candidate(
        actor=owner,
        target=inactive_target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    inactive_target.status = ValueStream.Status.ARCHIVED
    inactive_target.save(update_fields=["status", "updated_at"])

    inactive_result = adopt_field_candidate(
        candidate_id=inactive_candidate.pk,
        actor=owner,
    )

    inactive_candidate.refresh_from_db()
    assert inactive_result.outcome == AdoptionOutcome.TARGET_INACTIVE
    assert inactive_candidate.status == FieldAdoptionCandidate.Status.STALE
    assert inactive_candidate.error_code == AdoptionOutcome.TARGET_INACTIVE

    missing_target = make_value_stream(business_unit=business_unit, owner=owner)
    missing_candidate, _session = make_candidate(
        actor=owner,
        target=missing_target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    missing_target.delete()

    missing_result = adopt_field_candidate(
        candidate_id=missing_candidate.pk,
        actor=owner,
    )

    missing_candidate.refresh_from_db()
    assert missing_result.outcome == AdoptionOutcome.TARGET_MISSING
    assert missing_candidate.status == FieldAdoptionCandidate.Status.STALE
    assert missing_candidate.error_code == AdoptionOutcome.TARGET_MISSING


@pytest.mark.django_db
def test_regular_form_validation_failure_changes_nothing(owner, business_unit):
    target = make_use_case(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="problem_statement",
        proposed_value="",
    )
    history_before = target.history.count()

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.VALIDATION_FAILED
    assert "problem_statement" in result.errors
    assert target.problem_statement == "Der Vergleich ist langsam."
    assert target.history.count() == history_before
    assert candidate.status == FieldAdoptionCandidate.Status.FAILED
    assert candidate.error_code == AdoptionOutcome.VALIDATION_FAILED


@pytest.mark.django_db
def test_repeated_click_is_idempotent_and_does_not_create_second_history(owner, business_unit):
    target = make_use_case(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="summary",
        proposed_value="Assistierter Angebotsvergleich",
    )

    first = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)
    history_after_first = target.history.count()
    first_updated_at = UseCase.objects.get(pk=target.pk).updated_at
    second = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    assert first.outcome == AdoptionOutcome.ADOPTED
    assert second.outcome == AdoptionOutcome.ADOPTED
    assert second.idempotent is True
    assert target.history.count() == history_after_first
    assert target.updated_at == first_updated_at


@pytest.mark.django_db
def test_rejection_is_idempotent_and_never_changes_target(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="description",
        proposed_value="Neue Beschreibung",
    )

    first = reject_field_candidate(candidate_id=candidate.pk, actor=owner)
    second = reject_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert first.outcome == AdoptionOutcome.REJECTED
    assert second.outcome == AdoptionOutcome.REJECTED
    assert second.idempotent is True
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.REJECTED


@pytest.mark.django_db
def test_tampered_candidate_field_is_stale_without_domain_change(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )
    candidate.suggestion.target_field = "description"
    candidate.suggestion.save(update_fields=["target_field", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome == AdoptionOutcome.STALE
    assert target.name == "Beschaffung"
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.STALE
    assert candidate.error_code == "candidate_integrity_failed"


@pytest.mark.django_db
def test_disabled_feature_flag_is_effectless(owner, business_unit, settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = False
    target = make_value_stream(business_unit=business_unit, owner=owner)
    candidate, _session = make_candidate(
        actor=owner,
        target=target,
        field_name="name",
        proposed_value="Strategische Beschaffung",
    )

    with pytest.raises(AdoptionDisabled):
        adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.name == "Beschaffung"
    assert candidate.status == FieldAdoptionCandidate.Status.OPEN
    assert candidate.processing_by is None
