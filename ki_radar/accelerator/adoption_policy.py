from __future__ import annotations

from enum import StrEnum

from django.conf import settings
from django.core.exceptions import PermissionDenied

from .models import CaptureFieldSuggestion, CaptureSession


class AdoptionAction(StrEnum):
    DIRECT = "direct"
    EDITED = "edited"
    REJECT = "reject"


UNCERTAINTY_ACTIONS = {
    CaptureFieldSuggestion.Uncertainty.LOW: frozenset(
        {AdoptionAction.DIRECT, AdoptionAction.EDITED, AdoptionAction.REJECT}
    ),
    CaptureFieldSuggestion.Uncertainty.MEDIUM: frozenset(
        {AdoptionAction.EDITED, AdoptionAction.REJECT}
    ),
    CaptureFieldSuggestion.Uncertainty.HIGH: frozenset({AdoptionAction.REJECT}),
}


def field_adoption_enabled() -> bool:
    return bool(getattr(settings, "ACCELERATOR_FIELD_ADOPTION_ENABLED", False))


def ensure_field_adoption_enabled() -> None:
    if not field_adoption_enabled():
        raise PermissionDenied("Die Feldübernahme ist serverseitig deaktiviert.")


def allowed_adoption_actions(uncertainty: str) -> frozenset[AdoptionAction]:
    """Return the fail-closed action set for one extraction uncertainty."""
    return UNCERTAINTY_ACTIONS.get(uncertainty, frozenset())


def adoption_action_allowed(*, uncertainty: str, action: AdoptionAction) -> bool:
    return action in allowed_adoption_actions(uncertainty)


def assert_direct_model_field_adoption_allowed(*, session: CaptureSession) -> None:
    ensure_field_adoption_enabled()
    if not session.target_object:
        raise PermissionDenied("Die Capture Session ist nicht an ein Zielobjekt gebunden.")
    raise PermissionDenied(
        "Direkte Feldübernahmen sind erst nach vollständiger "
        "Kandidaten- und Konfliktprüfung erlaubt."
    )
