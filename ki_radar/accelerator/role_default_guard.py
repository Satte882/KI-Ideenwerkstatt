from __future__ import annotations

from collections.abc import Callable

from django.core.exceptions import ValidationError

from .role_defaults import (
    EXISTING,
    PREFILL,
    SUGGESTION,
    RoleDefaultResolution,
    resolve_second_approver,
    resolve_use_case_business_owner,
)

ACCEPTABLE_SELECTION_STATES = frozenset({EXISTING, PREFILL, SUGGESTION})


def _normalize_user_id(value: int | str | None) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Ungültige Rollenperson.") from exc


def _fresh_instance(instance):
    if instance is None or instance.pk is None:
        return instance
    return instance.__class__._default_manager.filter(pk=instance.pk).first()


def validate_role_default_submission(
    *,
    submitted_user_id: int | str | None,
    resolution_factory: Callable[[], RoleDefaultResolution],
    existing_user_id: int | str | None = None,
) -> RoleDefaultResolution | None:
    """Validate a role-default selection immediately before the regular save action."""
    submitted_id = _normalize_user_id(submitted_user_id)
    if submitted_id is None:
        return None

    current_existing_id = _normalize_user_id(existing_user_id)
    if current_existing_id is not None and submitted_id != current_existing_id:
        raise ValidationError(
            "Ein bestehender Rollenwert darf nicht durch einen Rollen-Default überschrieben werden."
        )

    resolution = resolution_factory()
    if resolution.state not in ACCEPTABLE_SELECTION_STATES or resolution.user_id is None:
        raise ValidationError("Für diese Rolle liegt aktuell kein zulässiger Personen-Default vor.")
    if resolution.user_id != submitted_id:
        raise ValidationError(
            "Die übermittelte Rollenperson entspricht nicht dem aktuell zulässigen Vorschlag."
        )
    return resolution


def validate_business_owner_suggestion(
    *,
    submitted_user_id: int | str | None,
    value_stream,
    existing_user_id: int | str | None = None,
) -> RoleDefaultResolution | None:
    """Re-resolve the Value-Stream source and validate a Business-Owner suggestion."""

    def current_resolution() -> RoleDefaultResolution:
        current_value_stream = _fresh_instance(value_stream)
        return resolve_use_case_business_owner(value_stream=current_value_stream)

    return validate_role_default_submission(
        submitted_user_id=submitted_user_id,
        resolution_factory=current_resolution,
        existing_user_id=existing_user_id,
    )


def validate_second_approver_suggestion(
    *,
    submitted_user_id: int | str | None,
    use_case,
    first_decider,
    assigned=None,
) -> RoleDefaultResolution | None:
    """Reuse the authoritative second-approver eligibility check at submission time."""

    def current_resolution() -> RoleDefaultResolution:
        current_use_case = _fresh_instance(use_case)
        current_first_decider = _fresh_instance(first_decider)
        current_assigned = _fresh_instance(assigned)
        if current_use_case is None:
            raise ValidationError("Der Use Case ist nicht mehr verfügbar.")
        return resolve_second_approver(
            use_case=current_use_case,
            first_decider=current_first_decider,
            assigned=current_assigned,
        )

    current_assigned = _fresh_instance(assigned)
    return validate_role_default_submission(
        submitted_user_id=submitted_user_id,
        resolution_factory=current_resolution,
        existing_user_id=current_assigned.pk if current_assigned is not None else None,
    )
