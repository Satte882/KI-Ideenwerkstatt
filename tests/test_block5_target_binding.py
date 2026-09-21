from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.adoption_policy import field_adoption_enabled
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import (
    CaptureTargetBindingForm,
    CaptureTargetLocked,
    bind_capture_target,
)
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase


def make_value_stream(*, business_unit, owner, name="Beschaffung", archived=False):
    return ValueStream.objects.create(
        name=name,
        business_unit=business_unit,
        owner=owner,
        status=ValueStream.Status.ARCHIVED if archived else ValueStream.Status.ACTIVE,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
        created_by=owner,
    )


def make_use_case(*, business_unit, owner, title="Angebotsvergleich", archived=False):
    return UseCase.objects.create(
        title=title,
        problem_statement="Der Vergleich ist langsam.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        business_owner=owner,
        expected_benefit="Bearbeitungszeit senken",
        submitter=owner,
        is_archived=archived,
    )


@pytest.mark.django_db
def test_value_stream_binding_uses_exact_edit_permission(
    owner,
    other_owner,
    business_unit,
):
    own = make_value_stream(business_unit=business_unit, owner=owner, name="Eigen")
    foreign = make_value_stream(
        business_unit=business_unit,
        owner=other_owner,
        name="Fremd",
    )
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    bound = bind_capture_target(actor=owner, session_id=session.pk, target_id=own.pk)

    assert bound.target_value_stream == own
    assert bound.target_use_case is None
    with pytest.raises(PermissionDenied):
        bind_capture_target(actor=owner, session_id=session.pk, target_id=foreign.pk)


@pytest.mark.django_db
def test_use_case_binding_uses_exact_edit_permission(owner, other_owner, business_unit):
    own = make_use_case(business_unit=business_unit, owner=owner, title="Eigen")
    foreign = make_use_case(
        business_unit=business_unit,
        owner=other_owner,
        title="Fremd",
    )
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    bound = bind_capture_target(actor=owner, session_id=session.pk, target_id=own.pk)

    assert bound.target_use_case == own
    assert bound.target_value_stream is None
    with pytest.raises(PermissionDenied):
        bind_capture_target(actor=owner, session_id=session.pk, target_id=foreign.pk)


@pytest.mark.django_db
def test_coordinator_can_bind_active_targets(coordinator, owner, business_unit):
    value_stream = make_value_stream(business_unit=business_unit, owner=owner)
    use_case = make_use_case(business_unit=business_unit, owner=owner)
    value_session = create_capture_session(
        actor=coordinator,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    use_case_session = create_capture_session(
        actor=coordinator,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )

    assert (
        bind_capture_target(
            actor=coordinator,
            session_id=value_session.pk,
            target_id=value_stream.pk,
        ).target_value_stream
        == value_stream
    )
    assert (
        bind_capture_target(
            actor=coordinator,
            session_id=use_case_session.pk,
            target_id=use_case.pk,
        ).target_use_case
        == use_case
    )


@pytest.mark.django_db
def test_binding_form_offers_only_active_editable_targets(
    owner,
    other_owner,
    business_unit,
):
    own = make_value_stream(business_unit=business_unit, owner=owner, name="Eigen")
    make_value_stream(business_unit=business_unit, owner=other_owner, name="Fremd")
    make_value_stream(
        business_unit=business_unit,
        owner=owner,
        name="Archiv",
        archived=True,
    )

    form = CaptureTargetBindingForm(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    assert list(form.fields["target"].queryset) == [own]


@pytest.mark.django_db
def test_archived_target_and_wrong_target_type_are_rejected(owner, business_unit):
    archived = make_value_stream(business_unit=business_unit, owner=owner, archived=True)
    use_case = make_use_case(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    with pytest.raises(PermissionDenied):
        bind_capture_target(actor=owner, session_id=session.pk, target_id=archived.pk)
    with pytest.raises(PermissionDenied):
        bind_capture_target(actor=owner, session_id=session.pk, target_id=use_case.pk)


@pytest.mark.django_db
def test_database_constraint_rejects_wrong_and_double_binding(owner, business_unit):
    value_stream = make_value_stream(business_unit=business_unit, owner=owner)
    use_case = make_use_case(business_unit=business_unit, owner=owner)

    with pytest.raises(IntegrityError), transaction.atomic():
        CaptureSession.objects.create(
            owner=owner,
            capture_type=CaptureSession.CaptureType.VALUE_STREAM,
            catalog_version="1.0",
            schema_version="1.0",
            target_use_case=use_case,
            expires_at=timezone.now() + timedelta(days=30),
        )

    with pytest.raises(IntegrityError), transaction.atomic():
        CaptureSession.objects.create(
            owner=owner,
            capture_type=CaptureSession.CaptureType.USE_CASE,
            catalog_version="1.0",
            schema_version="1.0",
            target_value_stream=value_stream,
            target_use_case=use_case,
            expires_at=timezone.now() + timedelta(days=30),
        )


@pytest.mark.django_db
def test_target_change_is_locked_after_suggestions_exist(owner, business_unit):
    first = make_value_stream(
        business_unit=business_unit,
        owner=owner,
        name="Erstes Ziel",
    )
    second = make_value_stream(
        business_unit=business_unit,
        owner=owner,
        name="Zweites Ziel",
    )
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    bind_capture_target(actor=owner, session_id=session.pk, target_id=first.pk)
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=0,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version="1.0",
        answer_schema_version="1.0",
        prompt_version="1.0",
        extraction_schema_version="1.0",
        finished_at=timezone.now(),
    )
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Neuer Name",
        source_question="identity",
        source_excerpt="Neuer Name",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Direkte Aussage",
    )

    with pytest.raises(CaptureTargetLocked):
        bind_capture_target(actor=owner, session_id=session.pk, target_id=second.pk)

    session.refresh_from_db()
    assert session.target_value_stream == first


@pytest.mark.django_db
def test_same_target_binding_is_idempotent_after_suggestions(owner, business_unit):
    target = make_value_stream(business_unit=business_unit, owner=owner)
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    first = bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)
    second = bind_capture_target(actor=owner, session_id=session.pk, target_id=target.pk)

    assert first.target_value_stream == target
    assert second.target_value_stream == target


def test_field_adoption_feature_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("ACCELERATOR_FIELD_ADOPTION_ENABLED", raising=False)
    with override_settings():
        assert field_adoption_enabled() is False


def test_field_adoption_feature_can_be_enabled_explicitly():
    with override_settings(ACCELERATOR_FIELD_ADOPTION_ENABLED=True):
        assert field_adoption_enabled() is True
