from django import template
from django.conf import settings
from django.urls import reverse

from ki_radar.use_cases.origin_consistency import origin_consistency_eligibility
from ki_radar.use_cases.permissions import can_view_use_case

register = template.Library()


@register.inclusion_tag("use_cases/includes/origin_consistency_panel.html", takes_context=True)
def origin_consistency_panel(context, use_case):
    request = context.get("request")
    state = origin_consistency_eligibility(use_case)
    provider_configured = bool(settings.OPENROUTER_API_KEY)
    permitted = bool(
        request and request.user.is_authenticated and can_view_use_case(request.user, use_case)
    )
    enabled = state.eligible and provider_configured and permitted
    disabled_reason = state.message
    if state.eligible and not provider_configured:
        disabled_reason = "OpenRouter ist für diese optionale Prüfung nicht konfiguriert."
    elif state.eligible and not permitted:
        disabled_reason = "Für diese Prüfung fehlt die Berechtigung."
    return {
        "show_origin_consistency": state.show,
        "origin_consistency_enabled": enabled,
        "origin_consistency_disabled_reason": disabled_reason,
        "origin_consistency_generate_url": reverse(
            "use_cases:origin_consistency_review",
            kwargs={"pk": use_case.pk},
        ),
        "origin_consistency_feedback_url": reverse(
            "use_cases:origin_consistency_feedback",
            kwargs={"pk": use_case.pk},
        ),
    }
