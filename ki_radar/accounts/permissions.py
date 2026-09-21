from django.contrib.auth.models import Group

GROUP_TECH_ADMIN = "Technischer Administrator"
GROUP_COORDINATOR = "KI-Koordinator"
GROUP_BUSINESS_OWNER = "Business Owner"
GROUP_READER = "Leser"
ALL_GROUPS = [GROUP_TECH_ADMIN, GROUP_COORDINATOR, GROUP_BUSINESS_OWNER, GROUP_READER]


def in_group(user, name: str) -> bool:
    return user.is_authenticated and user.groups.filter(name=name).exists()


def is_technical_admin(user) -> bool:
    return bool(user.is_authenticated and (user.is_superuser or in_group(user, GROUP_TECH_ADMIN)))


def is_coordinator(user) -> bool:
    return bool(is_technical_admin(user) or in_group(user, GROUP_COORDINATOR))


def is_business_owner(user) -> bool:
    return bool(is_coordinator(user) or in_group(user, GROUP_BUSINESS_OWNER))


def is_business_owner_or_coordinator(user) -> bool:
    return is_business_owner(user)


def is_reader(user) -> bool:
    return bool(user.is_authenticated)


def ensure_groups() -> None:
    for name in ALL_GROUPS:
        Group.objects.get_or_create(name=name)
