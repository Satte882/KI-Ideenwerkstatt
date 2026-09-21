import pytest
from django.contrib.auth.models import Group

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_READER,
    GROUP_TECH_ADMIN,
)


@pytest.fixture
def business_unit(db):
    return BusinessUnit.objects.create(name="Organisationseinheit A")


def make_user(username, group_name, business_unit):
    user = User.objects.create_user(
        username=username, password="VerySecureTestPassword!123", business_unit=business_unit
    )
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


@pytest.fixture
def owner(db, business_unit):
    return make_user("owner", GROUP_BUSINESS_OWNER, business_unit)


@pytest.fixture
def other_owner(db, business_unit):
    return make_user("other", GROUP_BUSINESS_OWNER, business_unit)


@pytest.fixture
def coordinator(db, business_unit):
    return make_user("coordinator", GROUP_COORDINATOR, business_unit)


@pytest.fixture
def reader(db, business_unit):
    return make_user("reader", GROUP_READER, business_unit)


@pytest.fixture
def technical_admin(db, business_unit):
    user = make_user("admin", GROUP_TECH_ADMIN, business_unit)
    user.is_staff = True
    user.save(update_fields=["is_staff"])
    return user
