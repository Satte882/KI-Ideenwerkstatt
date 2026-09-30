from ki_radar.accounts.permissions import (
    GROUP_COORDINATOR,
    in_group,
    is_business_owner,
    is_coordinator,
    is_technical_admin,
)


def can_manage_architecture(user) -> bool:
    return is_business_owner(user)


def can_edit_value_stream(user, value_stream) -> bool:
    return is_coordinator(user) or (is_business_owner(user) and value_stream.owner_id == user.id)


def process_validator_role(user) -> str:
    if is_technical_admin(user):
        return "Technischer Administrator"
    if in_group(user, GROUP_COORDINATOR):
        return "KI-Koordinator"
    return "Business Owner"
