from __future__ import annotations

import re

from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from ki_radar.core.llm_tasks import LLMTaskError, LLMTaskQuotaExceeded

from .ai_draft import (
    EDITABLE_CONTEXT_FIELDS,
    DeliveryDraftContextError,
    DeliveryDraftValidationError,
    build_mvp_scope_context,
    delivery_draft_run_for_actor,
    generate_mvp_scope_draft,
    log_ai_assist_event,
    source_hash_is_current,
)
from .models import DeliveryPackage
from .permissions import allowed_edit_sections

SAFE_PROVIDER_MESSAGE = (
    "Der KI-Entwurf konnte nicht sicher erstellt werden. Die vorhandenen Eingaben bleiben "
    "unverändert."
)
_PROMPT_INJECTION_RE = re.compile(
    r"(?:"
    r"\b(?:ignore|disregard)\b[^\n.;]{0,80}\b(?:instruction|instructions|prompt)\b"
    r"|\b(?:ignoriere|missachte)\b[^\n.;]{0,80}\b(?:anweisung|anweisungen|prompt)\b"
    r"|\bsystem\s*prompt\b"
    r"|\bdeveloper\s*(?:message|nachricht)\b"
    r"|(?:^|\n)\s*(?:system|assistant|developer)\s*:"
    r")",
    re.IGNORECASE,
)


def _package(pk):
    return get_object_or_404(
        DeliveryPackage.objects.select_related("use_case"),
        pk=pk,
    )


def _overrides(request) -> dict[str, str]:
    return {field_name: request.POST.get(field_name, "") for field_name in EDITABLE_CONTEXT_FIELDS}


def _contains_prompt_injection(package: DeliveryPackage, overrides: dict[str, str]) -> bool:
    context = build_mvp_scope_context(package, overrides=overrides)
    return any(_PROMPT_INJECTION_RE.search(source.value) for source in context.sources)


def _error_response(exc: Exception) -> JsonResponse:
    code = getattr(exc, "code", "provider_error")
    if isinstance(exc, DeliveryDraftContextError):
        missing = ", ".join(exc.missing_labels)
        return JsonResponse(
            {
                "ok": False,
                "code": exc.code,
                "message": f"Für den KI-Entwurf fehlen noch: {missing}.",
            },
            status=400,
        )
    if isinstance(exc, LLMTaskQuotaExceeded):
        return JsonResponse(
            {"ok": False, "code": code, "message": str(exc)},
            status=429,
        )
    if isinstance(exc, DeliveryDraftValidationError):
        return JsonResponse(
            {"ok": False, "code": code, "message": SAFE_PROVIDER_MESSAGE},
            status=502,
        )
    if isinstance(exc, LLMTaskError):
        if code in {"input_too_large", "invalid_task_context", "invalid_source_hash"}:
            status = 400
        elif code == "rate_limit":
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


def _prompt_injection_response() -> JsonResponse:
    return JsonResponse(
        {
            "ok": False,
            "code": "prompt_injection_detected",
            "message": (
                "Der ausgewählte Kontext enthält instruktionsartige Inhalte und wird nicht "
                "an den KI-Provider übertragen. Bitte den fachlichen Quelltext prüfen."
            ),
        },
        status=400,
    )


@login_required
@require_POST
def generate_mvp_scope_draft_view(request, pk):
    package = _package(pk)
    if "scope_and_users" not in allowed_edit_sections(request.user, package):
        return JsonResponse(
            {
                "ok": False,
                "code": "not_editable",
                "message": "Diese Delivery-Sektion ist nicht bearbeitbar.",
            },
            status=403,
        )

    overrides = _overrides(request)
    if _contains_prompt_injection(package, overrides):
        log_ai_assist_event(
            "ai_assist_failed",
            package=package,
            actor=request.user,
            error_code="prompt_injection_detected",
        )
        return _prompt_injection_response()

    try:
        result = generate_mvp_scope_draft(
            package=package,
            actor=request.user,
            overrides=overrides,
            regenerated=request.POST.get("regenerate") == "1",
        )
    except (DeliveryDraftContextError, DeliveryDraftValidationError, LLMTaskError) as exc:
        return _error_response(exc)

    return JsonResponse(
        {
            "ok": True,
            "run_id": result.run_id,
            "source_hash": result.source_hash,
            "draft_text": result.draft_text,
            "sources": list(result.sources),
            "missing_facts": list(result.missing_facts),
            "assumptions": list(result.assumptions),
            "conflicts": list(result.conflicts),
            "uncertainty": {
                "level": result.uncertainty_level,
                "reason": result.uncertainty_reason,
            },
        }
    )


@login_required
@require_POST
def mvp_scope_draft_event(request, pk):
    package = _package(pk)
    if "scope_and_users" not in allowed_edit_sections(request.user, package):
        return JsonResponse(
            {"ok": False, "code": "not_editable", "message": "Sektion nicht bearbeitbar."},
            status=403,
        )

    action = request.POST.get("action", "")
    if action not in {"adopt", "discard", "helpful", "not_helpful"}:
        return JsonResponse(
            {"ok": False, "code": "invalid_action", "message": "Ungültige Aktion."},
            status=400,
        )

    try:
        run = delivery_draft_run_for_actor(
            package=package,
            actor=request.user,
            run_id=request.POST.get("run_id", ""),
        )
    except (ValidationError, ValueError):
        run = None
    if run is None:
        return JsonResponse(
            {"ok": False, "code": "unknown_run", "message": "KI-Lauf nicht gefunden."},
            status=404,
        )

    if action == "adopt":
        overrides = _overrides(request)
        if _contains_prompt_injection(package, overrides):
            return _prompt_injection_response()
        posted_hash = request.POST.get("source_hash", "")
        if posted_hash != run.source_hash or not source_hash_is_current(
            package=package,
            expected_hash=run.source_hash,
            overrides=overrides,
        ):
            return JsonResponse(
                {
                    "ok": False,
                    "code": "source_stale",
                    "message": (
                        "Der fachliche Kontext hat sich seit der Generierung geändert. "
                        "Bitte den KI-Entwurf neu erzeugen."
                    ),
                },
                status=409,
            )
        log_ai_assist_event(
            "ai_draft_adopted_to_field",
            package=package,
            actor=request.user,
            run_id=run.pk,
        )
    elif action == "discard":
        log_ai_assist_event(
            "ai_draft_discarded",
            package=package,
            actor=request.user,
            run_id=run.pk,
        )
    else:
        log_ai_assist_event(
            "ai_feedback_submitted",
            package=package,
            actor=request.user,
            run_id=run.pk,
            helpful=action == "helpful",
        )

    return JsonResponse({"ok": True})
