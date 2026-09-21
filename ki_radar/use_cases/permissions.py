from ki_radar.accounts.permissions import (
    is_business_owner,
    is_coordinator,
)


def can_create_use_case(user) -> bool:
    return is_business_owner(user)


def can_edit_use_case(user, use_case) -> bool:
    return is_coordinator(user) or (
        is_business_owner(user) and use_case.business_owner_id == user.id
    )


def can_view_use_case(user, use_case) -> bool:
    return user.is_authenticated and not use_case.is_archived


def can_create_idea(user) -> bool:
    return bool(
        user
        and user.is_authenticated
        and user.is_active
        and not getattr(user, "is_anonymized", False)
    )


def can_edit_idea(user, idea) -> bool:
    return bool(can_create_idea(user) and idea.state == "open" and idea.submitted_by_id == user.id)


def can_triage_idea(user, idea) -> bool:
    return bool(idea.state == "open" and is_business_owner(user))


def can_promote_idea(user, idea) -> bool:
    return bool(
        idea.state == "open" and idea.promoted_use_case_id is None and can_create_use_case(user)
    )


def _can_accountable_transition(user, use_case) -> bool:
    if not user or not user.is_authenticated:
        return False
    if is_coordinator(user):
        return True
    return is_business_owner(user) and use_case.business_owner_id == user.id


def can_start_pilot(user, use_case) -> bool:
    """Allow Pilot start to a semantic coordinator or the assigned Business Owner."""

    return _can_accountable_transition(user, use_case)


def can_end_use_case(user, use_case) -> bool:
    """Allow END to a semantic coordinator or the assigned Business Owner."""

    return _can_accountable_transition(user, use_case)


def can_confirm_go_live_exception(user) -> bool:
    """Use the same semantic coordinator capability as the Go-live decision itself."""

    return bool(user and user.is_authenticated and is_coordinator(user))


def can_confirm_early_go_live_exception(user) -> bool:
    """Legacy early-Go-live capability follows semantic coordinator permissions."""

    return bool(user and user.is_authenticated and is_coordinator(user))
