from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.db import models

from ki_radar.architecture.forms import ValueStreamForm
from ki_radar.architecture.models import ValueStream
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_edit_use_case

from .models import CaptureSession


class UnsupportedAdoptionField(ValueError):
    pass


@dataclass(frozen=True)
class AdoptionTargetSpec:
    model: type[models.Model]
    form_class: type
    can_edit: Callable[[object, models.Model], bool]
    fields: frozenset[str]


ADOPTION_TARGETS: dict[str, AdoptionTargetSpec] = {
    CaptureSession.CaptureType.VALUE_STREAM: AdoptionTargetSpec(
        model=ValueStream,
        form_class=ValueStreamForm,
        can_edit=can_edit_value_stream,
        fields=frozenset(
            {
                "name",
                "description",
                "trigger",
                "outcome",
                "strategic_objective",
                "stakeholders",
                "constraints",
            }
        ),
    ),
    CaptureSession.CaptureType.USE_CASE: AdoptionTargetSpec(
        model=UseCase,
        form_class=UseCaseForm,
        can_edit=can_edit_use_case,
        fields=frozenset(
            {
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
        ),
    ),
}


def target_spec(target_type: str) -> AdoptionTargetSpec:
    try:
        return ADOPTION_TARGETS[target_type]
    except KeyError as exc:
        raise UnsupportedAdoptionField("Der Zieltyp ist nicht für Block 5 freigegeben.") from exc


def assert_adoptable_field(*, target_type: str, field_name: str) -> AdoptionTargetSpec:
    spec = target_spec(target_type)
    if field_name not in spec.fields:
        raise UnsupportedAdoptionField(
            f"Das Feld {target_type}.{field_name} ist nicht für Block 5 freigegeben."
        )
    model_field = spec.model._meta.get_field(field_name)
    if not isinstance(model_field, (models.CharField, models.TextField)):
        raise UnsupportedAdoptionField("Nur explizite Textfelder sind in Block 5 zulässig.")
    return spec


def adoption_field_label(*, target_type: str, field_name: str, target, actor) -> str:
    spec = assert_adoptable_field(target_type=target_type, field_name=field_name)
    form_kwargs = {"instance": target}
    if spec.form_class is UseCaseForm:
        form_kwargs["current_user"] = actor
    form = spec.form_class(**form_kwargs)
    field = form.fields.get(field_name)
    if field is not None and field.label:
        return str(field.label)
    return str(spec.model._meta.get_field(field_name).verbose_name)
