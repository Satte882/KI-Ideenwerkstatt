from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from django import forms
from django.db import models, transaction

from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.models import UseCase

from .structured_models import StructuredAdoptionItem


class StructuredMetricError(ValueError):
    pass


class StructuredMetricConflict(StructuredMetricError):
    pass


class StructuredMetricValidationError(StructuredMetricError):
    def __init__(self, errors: dict[str, list[str]]):
        super().__init__("Die vollständige Metrikgruppe ist fachlich ungültig.")
        self.errors = errors


@dataclass(frozen=True)
class StructuredMetricResult:
    effective_values: dict[str, Any]
    sources: dict[str, str]
    changed_fields: frozenset[str]
    errors: dict[str, list[str]] = field(default_factory=dict)


METRIC_TARGET_TO_FIELD = {
    "use_case.metric.name": "metric_name",
    "use_case.metric.type": "metric_type",
    "use_case.metric.direction": "metric_direction",
    "use_case.metric.unit": "metric_unit",
    "use_case.metric.baseline": "metric_baseline",
    "use_case.metric.target": "metric_target",
    "use_case.metric.measurement_method": "metric_measurement_method",
}
METRIC_FIELDS = tuple(METRIC_TARGET_TO_FIELD.values())
_CONFIRMED_DECISIONS = {
    StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL,
    StructuredAdoptionItem.Decision.CONFIRMED_EDITED,
}


def _snapshot_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, models.Model):
        return str(value.pk)
    return value


def metric_value_hash(value: Any) -> str:
    payload = json.dumps(
        _snapshot_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_metric_field_snapshot(use_case: UseCase) -> dict[str, dict[str, Any]]:
    return {
        target_path: {
            "value": _snapshot_value(getattr(use_case, field_name)),
            "hash": metric_value_hash(getattr(use_case, field_name)),
        }
        for target_path, field_name in METRIC_TARGET_TO_FIELD.items()
    }


def _submission_value(field: forms.Field, value: Any) -> Any:
    if isinstance(field, forms.ModelChoiceField) and isinstance(value, models.Model):
        return value.pk
    if isinstance(field, forms.ModelMultipleChoiceField):
        return [item.pk for item in value]
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _current_form_payload(*, use_case: UseCase, actor) -> dict[str, Any]:
    current_form = UseCaseForm(instance=use_case, current_user=actor)
    payload = {
        name: _submission_value(field, current_form.get_initial_for_field(field, name))
        for name, field in current_form.fields.items()
    }
    payload["business_domain"] = payload.get("business_domain") or BusinessDomain.OTHER
    payload["business_capability"] = (
        payload.get("business_capability") or use_case.affected_process or use_case.title
    )
    payload["process_area"] = payload.get("process_area") or use_case.affected_process
    return payload


def _item_value(item: StructuredAdoptionItem) -> Any:
    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL:
        if "value" not in item.interpretation_snapshot:
            raise StructuredMetricError("Dem bestätigten Vorschlag fehlt der interpretierte Wert.")
        return item.interpretation_snapshot["value"]
    if item.decision == StructuredAdoptionItem.Decision.CONFIRMED_EDITED:
        if "edited_value" not in item.decision_snapshot:
            raise StructuredMetricError("Der bestätigten Bearbeitung fehlt der editierte Wert.")
        return item.decision_snapshot["edited_value"]
    raise StructuredMetricError("Das Item besitzt keine bestätigte Metrikentscheidung.")


def _confirmed_items(
    items: Iterable[StructuredAdoptionItem],
) -> dict[str, StructuredAdoptionItem]:
    confirmed: dict[str, StructuredAdoptionItem] = {}
    for item in items:
        if item.candidate_kind != StructuredAdoptionItem.CandidateKind.METRIC_SET:
            raise StructuredMetricError("Der Metrik-Merge akzeptiert nur Metrikitems.")
        if item.target_path not in METRIC_TARGET_TO_FIELD:
            raise StructuredMetricError("Das Metrikitem besitzt keinen freigegebenen Zielpfad.")
        if item.target_path in confirmed:
            raise StructuredMetricError("Ein Metrikziel ist im Batch mehrfach vorhanden.")
        if item.decision in _CONFIRMED_DECISIONS:
            if item.status != StructuredAdoptionItem.Status.CONFIRMED:
                raise StructuredMetricError(
                    "Bestätigte Metrikwerte benötigen den Status bestätigt."
                )
            confirmed[item.target_path] = item
        elif item.decision not in {
            StructuredAdoptionItem.Decision.PENDING,
            StructuredAdoptionItem.Decision.CURRENT_DATABASE,
            StructuredAdoptionItem.Decision.REJECTED,
        }:
            raise StructuredMetricError("Unbekannte Metrikentscheidung.")
    return confirmed


def _form_errors(form: UseCaseForm) -> dict[str, list[str]]:
    return {name: [str(message) for message in messages] for name, messages in form.errors.items()}


@transaction.atomic
def adopt_metric_items(
    *,
    use_case_id,
    actor,
    items: Iterable[StructuredAdoptionItem],
) -> StructuredMetricResult:
    use_case = UseCase.objects.select_for_update().get(pk=use_case_id)
    confirmed = _confirmed_items(items)
    payload = _current_form_payload(use_case=use_case, actor=actor)
    original_values = {name: getattr(use_case, name) for name in METRIC_FIELDS}
    effective_values: dict[str, Any] = {}
    sources: dict[str, str] = {}

    for target_path, field_name in METRIC_TARGET_TO_FIELD.items():
        item = confirmed.get(target_path)
        current_value = getattr(use_case, field_name)
        if item is None:
            effective_values[field_name] = current_value
            sources[field_name] = StructuredAdoptionItem.Decision.CURRENT_DATABASE
            continue
        expected_hash = item.field_snapshot.get("hash")
        if not expected_hash or expected_hash != metric_value_hash(current_value):
            raise StructuredMetricConflict(f"Das bestätigte Metrikfeld {field_name} ist veraltet.")
        effective_values[field_name] = _item_value(item)
        sources[field_name] = item.decision

    payload.update(effective_values)
    form = UseCaseForm(data=payload, instance=use_case, current_user=actor)
    if not form.is_valid():
        raise StructuredMetricValidationError(_form_errors(form))

    validated = form.save(commit=False)
    changed_fields = frozenset(
        field_name
        for field_name in METRIC_FIELDS
        if original_values[field_name] != form.cleaned_data[field_name]
    )
    for field_name in METRIC_FIELDS:
        setattr(use_case, field_name, getattr(validated, field_name))
    if changed_fields:
        use_case.save(update_fields=[*changed_fields, "updated_at"])

    return StructuredMetricResult(
        effective_values={name: getattr(use_case, name) for name in METRIC_FIELDS},
        sources=sources,
        changed_fields=changed_fields,
    )
