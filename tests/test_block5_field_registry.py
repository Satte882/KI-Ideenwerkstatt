from __future__ import annotations

import pytest

from ki_radar.accelerator.field_registry import (
    ADOPTION_TARGETS,
    UnsupportedAdoptionField,
    adoption_field_label,
    assert_adoptable_field,
)
from ki_radar.accelerator.form_adapters import (
    AdoptionFormValidationError,
    prepare_field_update,
)
from ki_radar.accelerator.models import CaptureSession
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase

VALUE_STREAM_FIELDS = {
    "name",
    "description",
    "trigger",
    "outcome",
    "strategic_objective",
    "stakeholders",
    "constraints",
}
USE_CASE_FIELDS = {
    "title",
    "summary",
    "problem_statement",
    "affected_process",
    "target_users",
    "source_systems",
    "data_sources",
    "interface_description",
    "intended_users",
    "intended_purpose",
    "expected_benefit",
    "benefit_category",
    "human_oversight",
    "support_responsibility",
}


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


def test_registry_contains_only_the_approved_green_mvp_fields():
    assert ADOPTION_TARGETS[CaptureSession.CaptureType.VALUE_STREAM].fields == VALUE_STREAM_FIELDS
    assert ADOPTION_TARGETS[CaptureSession.CaptureType.USE_CASE].fields == USE_CASE_FIELDS


@pytest.mark.parametrize(
    ("target_type", "field_name"),
    [
        (CaptureSession.CaptureType.VALUE_STREAM, "scope_in"),
        (CaptureSession.CaptureType.VALUE_STREAM, "status"),
        (CaptureSession.CaptureType.USE_CASE, "provider"),
        (CaptureSession.CaptureType.USE_CASE, "business_owner"),
        (CaptureSession.CaptureType.USE_CASE, "metric_name"),
    ],
)
def test_registry_rejects_yellow_red_and_unlisted_fields(target_type, field_name):
    with pytest.raises(UnsupportedAdoptionField):
        assert_adoptable_field(target_type=target_type, field_name=field_name)


@pytest.mark.django_db
def test_label_prefers_the_bound_form_label(owner, business_unit):
    use_case = make_use_case(business_unit=business_unit, owner=owner)

    label = adoption_field_label(
        target_type=CaptureSession.CaptureType.USE_CASE,
        field_name="target_users",
        target=use_case,
        actor=owner,
    )

    assert label == "Zielgruppe"


@pytest.mark.django_db
def test_value_stream_adapter_validates_only_the_requested_field(owner, business_unit):
    value_stream = make_value_stream(business_unit=business_unit, owner=owner)

    prepared = prepare_field_update(
        target_type=CaptureSession.CaptureType.VALUE_STREAM,
        target=value_stream,
        actor=owner,
        field_name="description",
        proposed_value="Neue, geprüfte Beschreibung",
    )

    assert prepared.is_valid is True
    assert prepared.changed_model_fields == {"description"}
    assert prepared.original_value == "Bestehende Beschreibung"
    assert prepared.form.instance.description == "Neue, geprüfte Beschreibung"
    value_stream.refresh_from_db()
    assert value_stream.description == "Bestehende Beschreibung"
    assert value_stream.scope_in == "Bedarf bis Bestellung"


@pytest.mark.django_db
def test_use_case_adapter_preserves_references_classification_and_status(owner, business_unit):
    use_case = make_use_case(business_unit=business_unit, owner=owner)

    prepared = prepare_field_update(
        target_type=CaptureSession.CaptureType.USE_CASE,
        target=use_case,
        actor=owner,
        field_name="summary",
        proposed_value="Beschleunigter, nachvollziehbarer Angebotsvergleich",
    )

    assert prepared.is_valid is True
    assert prepared.changed_model_fields == {"summary"}
    assert prepared.form.instance.business_unit_id == business_unit.pk
    assert prepared.form.instance.business_owner_id == owner.pk
    assert prepared.form.instance.status == UseCase.Status.IDEA
    assert prepared.form.cleaned_data["business_capability"] == "Supplier Management"
    use_case.refresh_from_db()
    assert use_case.summary == "Bestehende Kurzbeschreibung"
    assert use_case.classification.capability == "Supplier Management"


@pytest.mark.django_db
def test_adapter_returns_regular_form_validation_errors(owner, business_unit):
    use_case = make_use_case(business_unit=business_unit, owner=owner)

    prepared = prepare_field_update(
        target_type=CaptureSession.CaptureType.USE_CASE,
        target=use_case,
        actor=owner,
        field_name="problem_statement",
        proposed_value="",
    )

    assert prepared.is_valid is False
    assert "problem_statement" in prepared.form.errors


@pytest.mark.django_db
def test_adapter_rejects_wrong_target_type_and_non_text_value(owner, business_unit):
    value_stream = make_value_stream(business_unit=business_unit, owner=owner)

    with pytest.raises(UnsupportedAdoptionField):
        prepare_field_update(
            target_type=CaptureSession.CaptureType.USE_CASE,
            target=value_stream,
            actor=owner,
            field_name="summary",
            proposed_value="Falsch zugeordnet",
        )
    with pytest.raises(AdoptionFormValidationError):
        prepare_field_update(
            target_type=CaptureSession.CaptureType.VALUE_STREAM,
            target=value_stream,
            actor=owner,
            field_name="name",
            proposed_value=42,
        )
