from __future__ import annotations

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction

from ki_radar.architecture.models import ValueStream
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_edit_use_case

from .models import CaptureSession


class CaptureTargetBindingError(ValueError):
    pass


class CaptureTargetLocked(CaptureTargetBindingError):
    pass


def editable_target_queryset(*, actor, capture_type: str):
    if capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        candidates = ValueStream.objects.exclude(status=ValueStream.Status.ARCHIVED).order_by(
            "name"
        )
        editable_ids = [item.pk for item in candidates if can_edit_value_stream(actor, item)]
        return ValueStream.objects.filter(pk__in=editable_ids).order_by("name")
    if capture_type == CaptureSession.CaptureType.USE_CASE:
        candidates = UseCase.objects.filter(is_archived=False).order_by("title")
        editable_ids = [item.pk for item in candidates if can_edit_use_case(actor, item)]
        return UseCase.objects.filter(pk__in=editable_ids).order_by("title")
    raise CaptureTargetBindingError("Unbekannter Capture-Typ.")


class CaptureTargetBindingForm(forms.Form):
    target = forms.ModelChoiceField(
        queryset=ValueStream.objects.none(),
        required=False,
        label="Bestehendes Zielobjekt",
        help_text=(
            "Optional. Die Session kann genau einen bestehenden, von Ihnen bearbeitbaren Entwurf "
            "ergänzen. Eine automatische Neuanlage ist in Block 5 nicht vorgesehen."
        ),
    )

    def __init__(self, *args, actor, capture_type: str, **kwargs):
        super().__init__(*args, **kwargs)
        self.capture_type = capture_type
        self.fields["target"].queryset = editable_target_queryset(
            actor=actor,
            capture_type=capture_type,
        )
        self.fields["target"].empty_label = "Noch kein Zielobjekt binden"


@transaction.atomic
def bind_capture_target(*, actor, session_id, target_id=None) -> CaptureSession:
    session = CaptureSession.objects.select_for_update().get(pk=session_id, owner=actor)

    current_target_id = (
        session.target_value_stream_id
        if session.capture_type == CaptureSession.CaptureType.VALUE_STREAM
        else session.target_use_case_id
    )
    same_target = (
        target_id is not None
        and current_target_id is not None
        and str(current_target_id) == str(target_id)
    )
    if same_target:
        return session

    if session.analyses.filter(suggestions__isnull=False).exists():
        raise CaptureTargetLocked(
            "Das Ziel kann nach der Erzeugung von Feldvorschlägen nicht mehr geändert werden."
        )

    if target_id is None:
        session.target_value_stream = None
        session.target_use_case = None
        session.save(update_fields=["target_value_stream", "target_use_case", "updated_at"])
        return session

    queryset = editable_target_queryset(actor=actor, capture_type=session.capture_type)
    try:
        target = queryset.get(pk=target_id)
    except (ValueStream.DoesNotExist, UseCase.DoesNotExist) as exc:
        raise PermissionDenied("Das Zielobjekt ist nicht bearbeitbar oder nicht aktiv.") from exc

    if session.capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        if not isinstance(target, ValueStream):
            raise CaptureTargetBindingError("Das Ziel passt nicht zum Capture-Typ Value Stream.")
        session.target_value_stream = target
        session.target_use_case = None
    elif session.capture_type == CaptureSession.CaptureType.USE_CASE:
        if not isinstance(target, UseCase):
            raise CaptureTargetBindingError("Das Ziel passt nicht zum Capture-Typ Use Case.")
        session.target_use_case = target
        session.target_value_stream = None
    else:
        raise CaptureTargetBindingError("Unbekannter Capture-Typ.")

    session.save(update_fields=["target_value_stream", "target_use_case", "updated_at"])
    return session
