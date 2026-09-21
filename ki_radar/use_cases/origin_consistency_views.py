from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ki_radar.core.llm_tasks import LLMTaskError, LLMTaskQuotaExceeded

from .models import UseCase
from .origin_consistency import (
    OriginConsistencyContextError,
    OriginConsistencyValidationError,
    generate_origin_consistency_review,
    log_origin_consistency_event,
    origin_consistency_run_for_actor,
)
from .permissions import can_view_use_case

SAFE_PROVIDER_MESSAGE = (
    "Die KI-Herkunftsprüfung konnte nicht sicher abgeschlossen werden. "
    "Der Use Case und seine Herkunft bleiben unverändert."
)


def _use_case(pk):
    return get_object_or_404(
        UseCase.objects.select_related(
            "architecture_origin__process_analysis",
            "architecture_origin__solution_option",
        ),
        pk=pk,
    )


def _error_response(exc: Exception) -> JsonResponse:
    code = getattr(exc, "code", "provider_error")
    if isinstance(exc, OriginConsistencyContextError):
        return JsonResponse(
            {"ok": False, "code": code, "message": str(exc)},
            status=409,
        )
    if isinstance(exc, LLMTaskQuotaExceeded):
        return JsonResponse(
            {"ok": False, "code": code, "message": str(exc)},
            status=429,
        )
    if isinstance(exc, OriginConsistencyValidationError):
        status = 409 if code == "source_stale" else 502
        return JsonResponse(
            {"ok": False, "code": code, "message": SAFE_PROVIDER_MESSAGE},
            status=status,
        )
    if isinstance(exc, LLMTaskError):
        if code in {"input_too_large", "invalid_task_context", "invalid_source_hash"}:
            status = 400
        elif code.endswith("_quota_exceeded") or code == "rate_limit":
            status = 429
        else:
            status = 503
        return JsonResponse(
            {"ok": False, "code": code, "message": SAFE_PROVIDER_MESSAGE},
            status=status,
        )
    return JsonResponse(
        {"ok": False, "code": "provider_error", "message": SAFE_PROVIDER_MESSAGE},
        status=503,
    )


@login_required
@require_POST
def origin_consistency_review(request, pk):
    use_case = _use_case(pk)
    if not can_view_use_case(request.user, use_case):
        return JsonResponse(
            {"ok": False, "code": "forbidden", "message": "Keine Berechtigung."},
            status=403,
        )

    regenerated = request.POST.get("regenerate") == "1"
    try:
        result = generate_origin_consistency_review(
            use_case=use_case,
            actor=request.user,
            regenerated=regenerated,
        )
    except (OriginConsistencyContextError, OriginConsistencyValidationError, LLMTaskError) as exc:
        return _error_response(exc)

    return JsonResponse(
        {
            "ok": True,
            "run_id": result.run_id,
            "source_hash": result.source_hash,
            "result": result.result,
            "findings": list(result.findings),
            "missing_context": list(result.missing_context),
        }
    )


@login_required
@require_POST
def origin_consistency_feedback(request, pk):
    use_case = _use_case(pk)
    if not can_view_use_case(request.user, use_case):
        return JsonResponse(
            {"ok": False, "code": "forbidden", "message": "Keine Berechtigung."},
            status=403,
        )

    action = request.POST.get("action", "")
    if action not in {"helpful", "not_helpful"}:
        return JsonResponse(
            {"ok": False, "code": "invalid_action", "message": "Ungültige Aktion."},
            status=400,
        )
    run = origin_consistency_run_for_actor(
        use_case=use_case,
        actor=request.user,
        run_id=request.POST.get("run_id", ""),
    )
    if run is None:
        return JsonResponse(
            {"ok": False, "code": "unknown_run", "message": "KI-Lauf nicht gefunden."},
            status=404,
        )

    log_origin_consistency_event(
        "feedback",
        use_case=use_case,
        actor=request.user,
        run_id=run.pk,
        helpful=action == "helpful",
    )
    return JsonResponse({"ok": True})
