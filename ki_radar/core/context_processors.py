from django.db.models import Count, Q

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.retention import expire_due_capture_sessions
from ki_radar.accounts.permissions import is_coordinator, is_technical_admin


def navigation_context(request):
    if not request.user.is_authenticated:
        return {}

    expire_due_capture_sessions(owner=request.user)
    match = request.resolver_match
    nav_is_discovery = bool(
        match
        and match.namespace == "accelerator"
        and match.url_name.startswith("autonomous_discovery_")
    )
    outcome_labels = {
        "prepare_outcome": "Outcome-Bezug vorbereiten",
        "initiative_edit": "Vorhaben",
        "initiative_create": "Vorhaben",
        "capability_experiment_edit": "Capability-Test",
        "capability_experiment_create": "Capability-Test",
        "initiative_impact": "Wirkungsprüfung",
    }
    nav_outcome_label = (
        outcome_labels.get(match.url_name, "") if match and match.namespace == "use_cases" else ""
    )
    outcome_in_analysis = bool(nav_outcome_label) and not (
        match.url_name == "prepare_outcome" and match.kwargs.get("kind") == "usecase"
    )
    nav_is_analysis = bool(
        match
        and (
            match.namespace == "architecture"
            or outcome_in_analysis
            or nav_is_discovery
            or (match.namespace == "accelerator" and match.url_name.startswith("investigation_"))
        )
    )
    draft_summary = CaptureSession.objects.filter(
        owner=request.user,
        status=CaptureSession.Status.DRAFT,
    ).aggregate(
        total=Count("id"),
        value_stream=Count(
            "id",
            filter=Q(capture_type=CaptureSession.CaptureType.VALUE_STREAM),
        ),
        use_case=Count(
            "id",
            filter=Q(capture_type=CaptureSession.CaptureType.USE_CASE),
        ),
    )
    return {
        "nav_is_analysis": nav_is_analysis,
        "nav_outcome_label": nav_outcome_label,
        "nav_is_discovery": nav_is_discovery,
        "nav_is_coordinator": is_coordinator(request.user),
        "nav_is_technical_admin": is_technical_admin(request.user),
        "capture_draft_count": draft_summary["total"],
        "capture_value_stream_draft_count": draft_summary["value_stream"],
        "capture_use_case_draft_count": draft_summary["use_case"],
    }
