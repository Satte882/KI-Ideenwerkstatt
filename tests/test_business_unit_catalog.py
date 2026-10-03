import pytest

from ki_radar.accounts.business_units import (
    active_productive_business_units,
    selectable_business_units,
)
from ki_radar.accounts.models import BusinessUnit


EXPECTED_PRODUCTIVE_UNITS = {
    "Unternehmenssteuerung",
    "Touristik & Operations",
    "Kundenservice & Buchung",
    "Marketing & Vertrieb",
    "IT & Digitalisierung",
    "Finanzen & Administration",
}


@pytest.mark.django_db
def test_productive_catalog_is_seeded_without_company_prefix():
    names = set(active_productive_business_units().values_list("name", flat=True))
    assert EXPECTED_PRODUCTIVE_UNITS <= names
    assert not any(name.startswith("RSD") for name in EXPECTED_PRODUCTIVE_UNITS)


@pytest.mark.django_db
def test_new_business_unit_defaults_to_productive():
    unit = BusinessUnit.objects.create(name="Neue bestätigte Einheit")
    assert unit.catalog_scope == BusinessUnit.CatalogScope.PRODUCTIVE
    assert active_productive_business_units().filter(pk=unit.pk).exists()


@pytest.mark.django_db
def test_demo_and_legacy_units_are_not_productive_choices():
    demo = BusinessUnit.objects.create(
        name="Demo Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )
    legacy = BusinessUnit.objects.create(
        name="Historischer Bestand",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    ids = set(active_productive_business_units().values_list("pk", flat=True))
    assert demo.pk not in ids
    assert legacy.pk not in ids


@pytest.mark.django_db
def test_existing_legacy_reference_can_be_rendered_as_current_choice():
    legacy = BusinessUnit.objects.create(
        name="Historischer Bestand für Referenz",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    ids = set(selectable_business_units(current_id=legacy.pk).values_list("pk", flat=True))
    assert legacy.pk in ids
