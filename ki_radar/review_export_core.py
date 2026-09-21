from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import models

CONTRACT_VERSION = "llm-review-v1"

SHARING_UNCHANGED = "unchanged"
SHARING_PSEUDONYMIZE = "pseudonymize"
SHARING_OMIT = "omit"
SHARING_APPROVED_TARGET = "approved-target-only"

PERSON_FIELDS = {
    "owner",
    "business_owner",
    "coordinator",
    "technical_owner",
    "submitter",
    "created_by",
    "updated_by",
    "assessed_by",
    "decided_by",
    "condition_owner",
    "second_approval_assignee",
}
ORG_FIELDS = {"business_unit"}
URL_FIELDS = {"evidence_url", "metric_evidence_url", "external_delivery_url"}
UNCHANGED_FIELDS = {
    "status",
    "focus_status",
    "evaluation_status",
    "evidence_basis",
    "priority",
    "solution_type",
    "hosting_type",
    "metric_type",
    "metric_direction",
    "business_value",
    "technical_feasibility",
    "data_readiness",
    "risk_complexity",
}


@dataclass(frozen=True)
class ReviewQuestion:
    section: str
    question_id: str
    label: str
    answer: str
    status: str
    requirement: str = "optional"
    relevance: str = "now"
    enforcement: str = "none"
    condition: str = "-"
    purpose: str = ""
    sharing_class: str = SHARING_APPROVED_TARGET
    canonical_source: str = ""
    answer_source: str = ""
    instance_ref: str = "-"
    evidence: str = "-"


@dataclass
class ReviewContext:
    anchor: str
    title: str
    reference: str
    lifecycle: str
    source_revision: str
    questions: list[ReviewQuestion] = field(default_factory=list)
    upstream_context: list[str] = field(default_factory=list)
    readiness_gaps: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    traceability: list[str] = field(default_factory=list)


def is_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def answer_status(value: Any, *, applicable: bool = True, complete: bool = True) -> str:
    if not applicable:
        return "not_applicable"
    if not is_present(value):
        return "open"
    return "answered" if complete else "partial"


def compound_status(values: list[Any], *, applicable: bool = True) -> str:
    if not applicable:
        return "not_applicable"
    present = sum(is_present(value) for value in values)
    if present == 0:
        return "open"
    if present == len(values):
        return "answered"
    return "partial"


def sharing_class(field_name: str) -> str:
    if field_name in PERSON_FIELDS or field_name in ORG_FIELDS:
        return SHARING_PSEUDONYMIZE
    if field_name in URL_FIELDS:
        return SHARING_OMIT
    if field_name in UNCHANGED_FIELDS:
        return SHARING_UNCHANGED
    return SHARING_APPROVED_TARGET


def _choice_display(obj: Any, field_name: str, value: Any) -> Any:
    display = getattr(obj, f"get_{field_name}_display", None)
    if callable(display) and is_present(value):
        try:
            return display()
        except (ValueError, TypeError):
            pass
    return value


def answer_value(obj: Any, field_name: str) -> str:
    value = getattr(obj, field_name, None)
    sharing = sharing_class(field_name)
    if sharing == SHARING_OMIT:
        return "[Link vorhanden - im Export ausgelassen]" if is_present(value) else ""
    if sharing == SHARING_PSEUDONYMIZE:
        if not is_present(value):
            return ""
        if field_name in ORG_FIELDS:
            return "[Organisationseinheit pseudonymisiert]"
        return f"[Person/Rolle {field_name} zugeordnet - Identitaet pseudonymisiert]"
    value = _choice_display(obj, field_name, value)
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, models.Model):
        return str(value)
    return "" if value is None else str(value)


def form_question(
    *,
    form,
    obj,
    field_name: str,
    section: str,
    question_id: str,
    canonical_source: str,
    requirement: str | None = None,
    relevance: str = "now",
    enforcement: str = "none",
    condition: str = "-",
    instance_ref: str = "-",
    answer_source: str = "",
    answer_override: str | None = None,
    status_override: str | None = None,
    sharing_override: str | None = None,
    evidence: str = "-",
) -> ReviewQuestion:
    field_obj = form.fields[field_name]
    answer = answer_value(obj, field_name) if answer_override is None else answer_override
    return ReviewQuestion(
        section=section,
        question_id=question_id,
        label=str(field_obj.label or field_name),
        purpose=str(field_obj.help_text or ""),
        requirement=requirement or ("required" if field_obj.required else "optional"),
        relevance=relevance,
        enforcement=enforcement,
        condition=condition,
        status=status_override or answer_status(answer),
        sharing_class=sharing_override or sharing_class(field_name),
        canonical_source=canonical_source,
        answer_source=answer_source or f"{obj.__class__.__name__}.{field_name}",
        instance_ref=instance_ref,
        answer=answer,
        evidence=evidence,
    )


def model_question(
    *,
    obj,
    field_name: str,
    section: str,
    question_id: str,
    canonical_source: str,
    requirement: str = "optional",
    relevance: str = "now",
    enforcement: str = "none",
    condition: str = "-",
    instance_ref: str = "-",
    answer_override: str | None = None,
    status_override: str | None = None,
    sharing_override: str | None = None,
    evidence: str = "-",
) -> ReviewQuestion:
    model_field = obj._meta.get_field(field_name)
    answer = answer_value(obj, field_name) if answer_override is None else answer_override
    return ReviewQuestion(
        section=section,
        question_id=question_id,
        label=str(model_field.verbose_name).capitalize(),
        purpose=str(getattr(model_field, "help_text", "") or ""),
        requirement=requirement,
        relevance=relevance,
        enforcement=enforcement,
        condition=condition,
        status=status_override or answer_status(answer),
        sharing_class=sharing_override or sharing_class(field_name),
        canonical_source=canonical_source,
        answer_source=f"{obj.__class__.__name__}.{field_name}",
        instance_ref=instance_ref,
        answer=answer,
        evidence=evidence,
    )


def source_revision(obj: Any, *, prefix: str = "") -> str:
    updated_at = getattr(obj, "updated_at", None)
    suffix = updated_at.isoformat() if updated_at else "stored-state"
    return f"{prefix}{suffix}"
