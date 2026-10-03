from uuid import UUID

from django.core.exceptions import ValidationError
from django.utils import timezone

from ki_radar.accelerator.models import CaptureSession

from .idea_models import IdeaCandidate


def idea_origin_id(answers: dict) -> UUID | None:
    origin = answers.get("origin")
    if origin is None:
        return None
    if not isinstance(origin, dict):
        raise ValidationError("Die Discovery-Herkunft ist ungültig.")
    if origin.get("type") != "idea_candidate":
        return None
    try:
        return UUID(str(origin["idea_candidate_id"]))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValidationError("Die Ursprungsidee der Discovery ist ungültig.") from exc


def build_idea_origin(idea: IdeaCandidate) -> dict:
    return {
        "type": "idea_candidate",
        "idea_candidate_id": str(idea.pk),
        "title": idea.title,
        "source_note": idea.source_note,
        "captured_at": timezone.now().isoformat(),
        "idea_updated_at": idea.updated_at.isoformat(),
    }


def active_idea_discovery(idea: IdeaCandidate) -> CaptureSession | None:
    return (
        CaptureSession.objects.filter(
            capture_type=CaptureSession.CaptureType.VALUE_STREAM,
            mode=CaptureSession.Mode.AUTONOMOUS,
            status=CaptureSession.Status.DRAFT,
            expires_at__gt=timezone.now(),
            answers__origin__type="idea_candidate",
            answers__origin__idea_candidate_id=str(idea.pk),
        )
        .order_by("created_at")
        .first()
    )


def assert_idea_discovery_start(*, idea: IdeaCandidate, actor) -> None:
    if (
        idea.state != IdeaCandidate.State.OPEN
        or idea.promoted_use_case_id is not None
        or idea.discovery_process_analysis_id is not None
    ):
        raise ValidationError("Diese Idee besitzt bereits einen Abschluss oder eine Analyse.")
    if idea.business_unit_id is not None and idea.business_unit_id != actor.business_unit_id:
        raise ValidationError(
            "Die Organisationseinheit der Idee weicht von Ihrer Organisationseinheit ab. "
            "Bitte die Zuordnung vor dem Discovery-Start klären."
        )
