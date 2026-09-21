from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier

import pytest
from django.db import close_old_connections
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.adoption_service import (
    AdoptionOutcome,
    adopt_field_candidate,
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
    FieldAdoptionAudit,
    FieldAdoptionCandidate,
)
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.accounts.models import User
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase


@pytest.fixture(autouse=True)
def enable_field_adoption(settings):
    settings.ACCELERATOR_FIELD_ADOPTION_ENABLED = True


def make_value_stream(*, owner, business_unit) -> ValueStream:
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


def make_use_case(*, owner, business_unit) -> UseCase:
    return UseCase.objects.create(
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


def make_candidate(
    *,
    owner,
    target,
    field_name: str,
    proposed_value: str,
    source_hash: str,
) -> tuple[CaptureAnalysis, FieldAdoptionCandidate]:
    capture_type = (
        CaptureSession.CaptureType.VALUE_STREAM
        if isinstance(target, ValueStream)
        else CaptureSession.CaptureType.USE_CASE
    )
    session = create_capture_session(actor=owner, capture_type=capture_type)
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
        source_hash=source_hash,
        capture_type=capture_type,
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
        target_object_type=capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=proposed_value,
        source_question="identity",
        source_excerpt=proposed_value,
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )
    return analysis, create_adoption_candidates(analysis_id=analysis.pk)[0]


@pytest.mark.django_db
def test_adoption_routes_are_post_only_and_csrf_protected(owner, business_unit):
    target = make_value_stream(owner=owner, business_unit=business_unit)
    analysis, candidate = make_candidate(
        owner=owner,
        target=target,
        field_name="description",
        proposed_value="Neue Beschreibung",
        source_hash="1" * 64,
    )
    client = Client()
    client.force_login(owner)
    url = reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk])

    assert client.get(url).status_code == 405

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(owner)
    assert csrf_client.post(url, {"mode": "direct"}).status_code == 403
    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.OPEN


@pytest.mark.django_db
def test_foreign_session_owner_cannot_address_candidate_route(
    owner,
    other_owner,
    business_unit,
):
    target = make_value_stream(owner=owner, business_unit=business_unit)
    analysis, candidate = make_candidate(
        owner=owner,
        target=target,
        field_name="description",
        proposed_value="Neue Beschreibung",
        source_hash="2" * 64,
    )
    client = Client()
    client.force_login(other_owner)

    response = client.post(
        reverse("accelerator:candidate_adopt", args=[analysis.pk, candidate.pk]),
        {"mode": "direct"},
    )

    assert response.status_code == 404
    target.refresh_from_db()
    candidate.refresh_from_db()
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.OPEN


@pytest.mark.django_db
@pytest.mark.parametrize("tamper", ["target_id", "target_type", "target_field"])
def test_tampered_target_coordinates_never_mutate_domain_data(
    owner,
    business_unit,
    tamper,
):
    target = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis, candidate = make_candidate(
        owner=owner,
        target=target,
        field_name="description",
        proposed_value="Neue Beschreibung",
        source_hash="3" * 64,
    )
    if tamper == "target_id":
        other_target = make_value_stream(owner=owner, business_unit=business_unit)
        candidate.target_object_id = other_target.pk
        candidate.save(update_fields=["target_object_id", "updated_at"])
    elif tamper == "target_type":
        candidate.target_object_type = CaptureSession.CaptureType.USE_CASE
        candidate.save(update_fields=["target_object_type", "updated_at"])
    else:
        candidate.target_field = "unsupported_field"
        candidate.save(update_fields=["target_field", "updated_at"])

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert result.outcome in {
        AdoptionOutcome.STALE,
        AdoptionOutcome.TARGET_MISSING,
        AdoptionOutcome.FAILED,
    }
    assert target.description == "Bestehende Beschreibung"
    assert candidate.status in {
        FieldAdoptionCandidate.Status.STALE,
        FieldAdoptionCandidate.Status.FAILED,
    }
    assert FieldAdoptionAudit.objects.filter(candidate_id_snapshot=candidate.pk).count() == 1


@pytest.mark.django_db
def test_archived_deleted_and_changed_targets_fail_closed(owner, business_unit):
    archived = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis, archived_candidate = make_candidate(
        owner=owner,
        target=archived,
        field_name="description",
        proposed_value="Archivierter Vorschlag",
        source_hash="4" * 64,
    )
    archived.status = ValueStream.Status.ARCHIVED
    archived.save(update_fields=["status", "updated_at"])
    assert (
        adopt_field_candidate(
            candidate_id=archived_candidate.pk,
            actor=owner,
        ).outcome
        == AdoptionOutcome.TARGET_INACTIVE
    )

    deleted = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis, deleted_candidate = make_candidate(
        owner=owner,
        target=deleted,
        field_name="description",
        proposed_value="Gelöschter Vorschlag",
        source_hash="5" * 64,
    )
    deleted.delete()
    assert (
        adopt_field_candidate(
            candidate_id=deleted_candidate.pk,
            actor=owner,
        ).outcome
        == AdoptionOutcome.TARGET_MISSING
    )

    changed = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis, changed_candidate = make_candidate(
        owner=owner,
        target=changed,
        field_name="description",
        proposed_value="Konfliktvorschlag",
        source_hash="6" * 64,
    )
    changed.description = "Parallel geändert"
    changed.save(update_fields=["description", "updated_at"])
    result = adopt_field_candidate(candidate_id=changed_candidate.pk, actor=owner)
    changed.refresh_from_db()
    assert result.outcome == AdoptionOutcome.CONFLICT
    assert changed.description == "Parallel geändert"


@pytest.mark.django_db
def test_use_case_form_validation_preserves_history_and_workflow_gates(owner, business_unit):
    target = make_use_case(owner=owner, business_unit=business_unit)
    _analysis, candidate = make_candidate(
        owner=owner,
        target=target,
        field_name="problem_statement",
        proposed_value="",
        source_hash="7" * 64,
    )
    history_before = target.history.count()
    status_before = target.status
    decision_status_before = target.decision_status

    result = adopt_field_candidate(candidate_id=candidate.pk, actor=owner)

    target.refresh_from_db()
    assert result.outcome == AdoptionOutcome.VALIDATION_FAILED
    assert target.problem_statement == "Der Vergleich ist langsam."
    assert target.history.count() == history_before
    assert target.status == status_before
    assert target.decision_status == decision_status_before


@pytest.mark.django_db(transaction=True)
def test_parallel_double_click_mutates_and_audits_exactly_once(owner, business_unit):
    target = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis, candidate = make_candidate(
        owner=owner,
        target=target,
        field_name="description",
        proposed_value="Parallel geprüfte Beschreibung",
        source_hash="8" * 64,
    )
    barrier = Barrier(2)

    def adopt_once():
        close_old_connections()
        actor = User.objects.get(pk=owner.pk)
        barrier.wait()
        try:
            return adopt_field_candidate(candidate_id=candidate.pk, actor=actor)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(adopt_once) for _ in range(2)]
        results = [future.result() for future in futures]

    target.refresh_from_db()
    candidate.refresh_from_db()
    assert all(result.outcome == AdoptionOutcome.ADOPTED for result in results)
    assert sum(result.idempotent for result in results) == 1
    assert target.description == "Parallel geprüfte Beschreibung"
    assert candidate.status == FieldAdoptionCandidate.Status.ADOPTED
    assert FieldAdoptionAudit.objects.filter(candidate_id_snapshot=candidate.pk).count() == 1


@pytest.mark.django_db(transaction=True)
def test_two_users_can_update_distinct_fields_without_false_conflict_or_deadlock(
    owner,
    coordinator,
    business_unit,
):
    target = make_value_stream(owner=owner, business_unit=business_unit)
    _analysis_a, candidate_a = make_candidate(
        owner=owner,
        target=target,
        field_name="description",
        proposed_value="Neue Beschreibung",
        source_hash="9" * 64,
    )
    _analysis_b, candidate_b = make_candidate(
        owner=owner,
        target=target,
        field_name="trigger",
        proposed_value="Neuer Auslöser",
        source_hash="a" * 64,
    )
    barrier = Barrier(2)

    def adopt(candidate_id, actor_id):
        close_old_connections()
        actor = User.objects.get(pk=actor_id)
        barrier.wait()
        try:
            return adopt_field_candidate(candidate_id=candidate_id, actor=actor)
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(adopt, candidate_a.pk, owner.pk),
            executor.submit(adopt, candidate_b.pk, coordinator.pk),
        ]
        results = [future.result() for future in futures]

    target.refresh_from_db()
    assert [result.outcome for result in results] == [
        AdoptionOutcome.ADOPTED,
        AdoptionOutcome.ADOPTED,
    ]
    assert target.description == "Neue Beschreibung"
    assert target.trigger == "Neuer Auslöser"
    assert FieldAdoptionAudit.objects.filter(target_object_id=target.pk).count() == 2
