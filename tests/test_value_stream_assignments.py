import pytest
from django.contrib.auth.models import Group

from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import (
    GROUP_BUSINESS_OWNER,
    GROUP_COORDINATOR,
    GROUP_READER,
    GROUP_TECH_ADMIN,
)
from ki_radar.architecture.forms import ValueStreamForm
from ki_radar.architecture.models import ValueStream


def add_group(user, group_name):
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)


def form_data(business_unit, owner):
    return {
        "name": "Auftrag bis Zahlung",
        "business_unit": business_unit.pk,
        "owner": owner.pk if owner else "",
        "status": ValueStream.Status.DRAFT,
        "description": "End-to-End-Ablauf",
        "trigger": "Kundenauftrag geht ein",
        "outcome": "Zahlung ist verbucht",
        "scope_in": "Vom Auftragseingang bis zum Zahlungseingang",
        "strategic_objective": "Durchlaufzeit reduzieren",
        "stakeholders": "Vertrieb und Finance",
        "constraints": "Bestehendes ERP",
        "business_domain": "other",
        "capability": "",
        "strategic_impact": "",
        "economic_potential": "",
        "pain_intensity": "",
        "data_accessibility": "",
        "change_effort": "",
        "focus_status": "not_screened",
        "focus_rationale": "",
    }


@pytest.mark.django_db
def test_value_stream_form_filters_active_units_and_eligible_owners(business_unit):
    inactive_unit = BusinessUnit.objects.create(name="Stillgelegte Einheit", is_active=False)
    business_owner = User.objects.create_user(username="vs-owner", password="x")
    coordinator = User.objects.create_user(username="vs-coordinator", password="x")
    tech_admin = User.objects.create_user(username="vs-admin", password="x")
    reader = User.objects.create_user(username="vs-reader", password="x")
    inactive_owner = User.objects.create_user(username="vs-inactive", password="x", is_active=False)
    anonymized_owner = User.objects.create_user(
        username="vs-anonymized", password="x", is_anonymized=True
    )
    superuser = User.objects.create_superuser(
        username="vs-superuser", email="root@example.invalid", password="x"
    )
    add_group(business_owner, GROUP_BUSINESS_OWNER)
    add_group(coordinator, GROUP_COORDINATOR)
    add_group(tech_admin, GROUP_TECH_ADMIN)
    add_group(reader, GROUP_READER)
    add_group(inactive_owner, GROUP_BUSINESS_OWNER)
    add_group(anonymized_owner, GROUP_BUSINESS_OWNER)

    form = ValueStreamForm()

    assert list(form.fields["business_unit"].queryset) == [business_unit]
    owner_ids = set(form.fields["owner"].queryset.values_list("pk", flat=True))
    assert {business_owner.pk, coordinator.pk, tech_admin.pk, superuser.pk} <= owner_ids
    assert reader.pk not in owner_ids
    assert inactive_owner.pk not in owner_ids
    assert anonymized_owner.pk not in owner_ids
    assert inactive_unit.pk not in form.fields["business_unit"].queryset.values_list(
        "pk", flat=True
    )
    assert form.fields["owner"].label == "Value-Stream-Owner"
    assert form.fields["business_unit"].label == "Organisationseinheit"


@pytest.mark.django_db
def test_value_stream_form_rejects_manipulated_inactive_unit_and_ineligible_owner():
    inactive_unit = BusinessUnit.objects.create(name="Inaktive Einheit", is_active=False)
    reader = User.objects.create_user(username="only-reader", password="x")
    add_group(reader, GROUP_READER)

    form = ValueStreamForm(data=form_data(inactive_unit, reader))

    assert form.is_valid() is False
    assert "business_unit" in form.errors
    assert "owner" in form.errors


@pytest.mark.django_db
def test_legacy_assignments_remain_visible_and_are_flagged():
    inactive_unit = BusinessUnit.objects.create(name="Historische Einheit", is_active=False)
    legacy_owner = User.objects.create_user(username="legacy-reader", password="x")
    add_group(legacy_owner, GROUP_READER)
    value_stream = ValueStream.objects.create(
        name="Historischer Value Stream",
        business_unit=inactive_unit,
        owner=legacy_owner,
        trigger="Alt",
        outcome="Alt",
        scope_in="Alt",
    )

    form = ValueStreamForm(instance=value_stream)

    assert inactive_unit.pk in form.fields["business_unit"].queryset.values_list("pk", flat=True)
    assert legacy_owner.pk in form.fields["owner"].queryset.values_list("pk", flat=True)
    assert len(form.assignment_warnings) == 2
    assert "inaktiv" in form.assignment_warnings[0]
    assert "nicht mehr" in form.assignment_warnings[1]


@pytest.mark.django_db
def test_active_business_owner_can_be_saved_as_value_stream_owner(business_unit):
    owner = User.objects.create_user(username="valid-vs-owner", password="x")
    add_group(owner, GROUP_BUSINESS_OWNER)

    form = ValueStreamForm(data=form_data(business_unit, owner))

    assert form.is_valid(), form.errors
