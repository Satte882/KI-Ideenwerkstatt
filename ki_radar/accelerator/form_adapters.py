from __future__ import annotations

import copy
from dataclasses import dataclass

from django import forms
from django.core.exceptions import FieldDoesNotExist
from django.db import models

from ki_radar.use_cases.forms import UseCaseForm

from .field_registry import UnsupportedAdoptionField, assert_adoptable_field


class AdoptionFormValidationError(ValueError):
    pass


@dataclass
class PreparedFieldUpdate:
    form: forms.ModelForm
    target_type: str
    field_name: str
    original_value: str
    proposed_value: str
    changed_model_fields: frozenset[str]

    @property
    def is_valid(self) -> bool:
        return not self.form.errors and self.changed_model_fields == {self.field_name}


def _submission_value(field: forms.Field, value):
    if isinstance(field, forms.ModelChoiceField) and isinstance(value, models.Model):
        return value.pk
    if isinstance(field, forms.ModelMultipleChoiceField):
        return [item.pk for item in value]
    if value is None:
        return ""
    return value


def _form_kwargs(*, form_class, target, actor, data=None):
    kwargs = {"instance": target}
    if data is not None:
        kwargs["data"] = data
    if form_class is UseCaseForm:
        kwargs["current_user"] = actor
    return kwargs


def _model_field_names(form: forms.ModelForm) -> tuple[str, ...]:
    names = []
    for field_name in form._meta.fields:
        try:
            form._meta.model._meta.get_field(field_name)
        except FieldDoesNotExist:
            continue
        names.append(field_name)
    return tuple(names)


def _model_state(instance, field_names: tuple[str, ...]) -> dict[str, object]:
    return {
        field_name: instance._meta.get_field(field_name).value_from_object(instance)
        for field_name in field_names
    }


def prepare_field_update(
    *,
    target_type: str,
    target,
    actor,
    field_name: str,
    proposed_value: str,
) -> PreparedFieldUpdate:
    if not isinstance(proposed_value, str):
        raise AdoptionFormValidationError("Der Übernahmewert muss Text sein.")
    spec = assert_adoptable_field(target_type=target_type, field_name=field_name)
    if not isinstance(target, spec.model):
        raise UnsupportedAdoptionField("Das Zielobjekt passt nicht zum freigegebenen Zieltyp.")

    validation_target = copy.copy(target)
    current_form = spec.form_class(
        **_form_kwargs(form_class=spec.form_class, target=validation_target, actor=actor)
    )
    payload = {
        name: _submission_value(field, current_form.get_initial_for_field(field, name))
        for name, field in current_form.fields.items()
    }
    payload[field_name] = proposed_value

    model_field_names = _model_field_names(current_form)
    original_state = _model_state(validation_target, model_field_names)
    form = spec.form_class(
        **_form_kwargs(
            form_class=spec.form_class,
            target=validation_target,
            actor=actor,
            data=payload,
        )
    )
    form.is_valid()
    current_state = _model_state(validation_target, model_field_names)
    changed_fields = frozenset(
        name for name in model_field_names if original_state[name] != current_state[name]
    )

    return PreparedFieldUpdate(
        form=form,
        target_type=target_type,
        field_name=field_name,
        original_value=str(original_state[field_name] or ""),
        proposed_value=proposed_value,
        changed_model_fields=changed_fields,
    )


def apply_prepared_field_update(*, prepared: PreparedFieldUpdate, target):
    if not prepared.is_valid:
        raise AdoptionFormValidationError(
            "Die reguläre Formvalidierung hat die Feldänderung nicht freigegeben."
        )
    spec = assert_adoptable_field(
        target_type=prepared.target_type,
        field_name=prepared.field_name,
    )
    if not isinstance(target, spec.model) or target.pk != prepared.form.instance.pk:
        raise UnsupportedAdoptionField("Das gesperrte Ziel passt nicht zur validierten Änderung.")

    cleaned_value = prepared.form.cleaned_data[prepared.field_name]
    if not isinstance(cleaned_value, str):
        raise AdoptionFormValidationError("Der validierte Übernahmewert ist kein Text.")
    setattr(target, prepared.field_name, cleaned_value)
    target.save(update_fields=[prepared.field_name, "updated_at"])
    return target
