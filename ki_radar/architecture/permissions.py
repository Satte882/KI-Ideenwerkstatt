from ki_radar.accounts.permissions import is_business_owner, is_coordinator


def can_manage_architecture(user) -> bool:
    return is_business_owner(user)


def can_edit_value_stream(user, value_stream) -> bool:
    return is_coordinator(user) or (is_business_owner(user) and value_stream.owner_id == user.id)
