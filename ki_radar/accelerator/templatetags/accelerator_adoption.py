from __future__ import annotations

from django import template
from django.urls import reverse

from ..adoption_policy import (
    AdoptionAction,
    allowed_adoption_actions,
    field_adoption_enabled,
)
from ..candidate_snapshot import canonical_text_hash, canonicalize_text
from ..field_registry import UnsupportedAdoptionField, assert_adoptable_field
from ..models import CaptureSession, FieldAdoptionCandidate

register = template.Library()


def _manual_edit_url(candidate: FieldAdoptionCandidate) -> str:
    if candidate.target_object_type == CaptureSession.CaptureType.VALUE_STREAM:
        return reverse(
            "architecture:value_stream_update",
            kwargs={"pk": candidate.target_object_id},
        )
    if candidate.target_object_type == CaptureSession.CaptureType.USE_CASE:
        return reverse("use_cases:edit", kwargs={"pk": candidate.target_object_id})
    return ""


@register.inclusion_tag("accelerator/_adoption_controls.html", takes_context=True)
def adoption_controls(context, analysis, target_field: str):
    request = context.get("request")
    if (
        request is None
        or not field_adoption_enabled()
        or analysis.session.owner_id != request.user.pk
    ):
        return {"review": None}

    candidate = (
        FieldAdoptionCandidate.objects.select_related("suggestion__analysis__session")
        .filter(
            suggestion__analysis=analysis,
            suggestion__target_group_key="",
            suggestion__target_field=target_field,
        )
        .first()
    )
    if candidate is None:
        return {"review": None}

    try:
        spec = assert_adoptable_field(
            target_type=candidate.target_object_type,
            field_name=candidate.target_field,
        )
    except UnsupportedAdoptionField:
        return {"review": None}

    target = spec.model.objects.filter(pk=candidate.target_object_id).first()
    current_value = ""
    can_edit = False
    field_changed = False
    if target is not None:
        current_value = canonicalize_text(getattr(target, candidate.target_field))
        can_edit = spec.can_edit(request.user, target)
        field_changed = canonical_text_hash(current_value) != candidate.previous_value_hash

    actions = allowed_adoption_actions(candidate.suggestion.uncertainty)
    is_open = candidate.status == FieldAdoptionCandidate.Status.OPEN
    is_conflict = candidate.status == FieldAdoptionCandidate.Status.CONFLICT or (
        is_open and field_changed
    )
    return {
        "review": {
            "candidate": candidate,
            "analysis": analysis,
            "session": analysis.session,
            "current_value": current_value,
            "target_missing": target is None,
            "can_edit": can_edit,
            "is_open": is_open,
            "is_conflict": is_conflict,
            "allow_direct": is_open
            and not is_conflict
            and can_edit
            and AdoptionAction.DIRECT in actions,
            "allow_edited": is_open
            and not is_conflict
            and can_edit
            and AdoptionAction.EDITED in actions,
            "allow_reject": is_open and can_edit and AdoptionAction.REJECT in actions,
            "preview_only": is_open
            and not is_conflict
            and can_edit
            and actions == frozenset({AdoptionAction.REJECT}),
            "manual_edit_url": _manual_edit_url(candidate),
            "status_label": candidate.get_status_display(),
        }
    }
