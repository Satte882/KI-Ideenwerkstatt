from django.db.models import Count, Q

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.retention import expire_due_capture_sessions
from ki_radar.accounts.permissions import is_coordinator, is_technical_admin


def navigation_context(request):
    if not request.user.is_authenticated:
        return {}

    expire_due_capture_sessions(owner=request.user)
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
        "nav_is_coordinator": is_coordinator(request.user),
        "nav_is_technical_admin": is_technical_admin(request.user),
        "capture_draft_count": draft_summary["total"],
        "capture_value_stream_draft_count": draft_summary["value_stream"],
        "capture_use_case_draft_count": draft_summary["use_case"],
    }
