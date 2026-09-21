from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    in_group,
    is_coordinator,
    is_technical_admin,
)
from ki_radar.use_cases.permissions import can_view_use_case

from .models import DeliveryPackage

BUSINESS_SECTIONS = {
    "problem_and_target",
    "scope_and_users",
    "solution_direction",
    "acceptance_and_measurement",
    "delivery_control",
}
TECHNICAL_SECTIONS = {
    "solution_direction",
    "architecture_and_data",
    "requirements_and_governance",
    "delivery_control",
}


def can_view_package(user, package: DeliveryPackage) -> bool:
    return can_view_use_case(user, package.use_case)


def can_create_package(user) -> bool:
    return is_coordinator(user)


def can_confirm_business(user, package: DeliveryPackage, section_key: str) -> bool:
    return bool(
        section_key in BUSINESS_SECTIONS
        and (
            package.use_case.business_owner_id == user.id
            or in_group(user, GROUP_BUSINESS_OWNER)
            or in_group(user, GROUP_COORDINATOR)
            or is_technical_admin(user)
        )
    )


def can_confirm_technical(user, package: DeliveryPackage, section_key: str) -> bool:
    return bool(
        section_key in TECHNICAL_SECTIONS
        and (package.technical_owner_id == user.id or is_coordinator(user))
    )


def allowed_edit_sections(user, package: DeliveryPackage) -> set[str]:
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        return set()
    allowed: set[str] = set()
    for section_key in BUSINESS_SECTIONS | TECHNICAL_SECTIONS:
        if can_confirm_business(user, package, section_key) or can_confirm_technical(
            user, package, section_key
        ):
            allowed.add(section_key)
    return allowed


def can_edit_package(user, package: DeliveryPackage) -> bool:
    return bool(allowed_edit_sections(user, package))


def can_review_section(user, package: DeliveryPackage, section_key: str) -> bool:
    return bool(reviewer_roles(user, package, section_key))


def reviewer_roles(user, package: DeliveryPackage, section_key: str) -> set[str]:
    roles: set[str] = set()
    if can_confirm_business(user, package, section_key):
        roles.add("business")
    if can_confirm_technical(user, package, section_key):
        roles.add("technical")
    return roles


def can_use_admin_confirmation_override(user) -> bool:
    return is_technical_admin(user)


def confirmation_role_label(
    role: str,
    *,
    assigned: bool,
    admin_override: bool = False,
) -> str:
    if admin_override:
        return "Admin-Sonderbestätigung"
    if role == "business":
        return "Business Owner" if assigned else "Berechtigte fachliche Stellvertretung"
    return "Technical Owner" if assigned else "Berechtigte technische Stellvertretung"


def can_transition_package(user) -> bool:
    return is_coordinator(user)


def can_resolve_role_source(user, package: DeliveryPackage) -> bool:
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        return False
    return bool(
        package.use_case.business_owner_id == user.id
        or package.technical_owner_id == user.id
        or package.use_case.technical_owner_id == user.id
        or is_coordinator(user)
        or is_technical_admin(user)
    )
