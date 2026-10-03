import pytest

from ki_radar.accounts import business_units
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
    names = set(business_units.active_productive_business_units().values_list("name", flat=True))
    assert names >= EXPECTED_PRODUCTIVE_UNITS
    assert not any(name.startswith("RSD") for name in EXPECTED_PRODUCTIVE_UNITS)


@pytest.mark.django_db
def test_new_business_unit_defaults_to_productive():
    unit = BusinessUnit.objects.create(name="Neue bestätigte Einheit")
    assert unit.catalog_scope == BusinessUnit.CatalogScope.PRODUCTIVE
    assert business_units.active_productive_business_units().filter(pk=unit.pk).exists()


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
    ids = set(business_units.active_productive_business_units().values_list("pk", flat=True))
    assert demo.pk not in ids
    assert legacy.pk not in ids


@pytest.mark.django_db
def test_existing_legacy_reference_can_be_rendered_as_current_choice():
    legacy = BusinessUnit.objects.create(
        name="Historischer Bestand für Referenz",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    ids = set(
        business_units.selectable_business_units(current_id=legacy.pk).values_list(
            "pk", flat=True
        )
    )
    assert legacy.pk in ids


@pytest.mark.django_db
def test_all_productive_business_unit_forms_hide_demo_and_legacy_units():
    from ki_radar.accelerator.architect_forms import AutonomousDiscoveryStartForm
    from ki_radar.architecture.forms import ValueStreamForm
    from ki_radar.use_cases.forms import UseCaseForm
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.intake import ProblemStepForm

    demo = BusinessUnit.objects.create(
        name="Nicht auswählbare Demo-Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )
    legacy = BusinessUnit.objects.create(
        name="Nicht auswählbarer Bestand",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )

    forms = [
        AutonomousDiscoveryStartForm(),
        IdeaCandidateForm(),
        ProblemStepForm(),
        UseCaseForm(),
        ValueStreamForm(),
    ]

    for form in forms:
        ids = set(form.fields["business_unit"].queryset.values_list("pk", flat=True))
        assert demo.pk not in ids
        assert legacy.pk not in ids


@pytest.mark.django_db
def test_discovery_service_rejects_demo_unit_when_form_is_bypassed(owner):
    from django.core.exceptions import ValidationError

    from ki_radar.accelerator.services import create_autonomous_capture_session

    demo = BusinessUnit.objects.create(
        name="Manipulierte Demo-Einheit",
        catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
    )

    with pytest.raises(ValidationError, match="freigegebenen Organisationskatalog"):
        create_autonomous_capture_session(
            actor=owner,
            problem_statement="Kundenanfragen benötigen zu viele manuelle Schritte.",
            business_unit_id=demo.pk,
        )


@pytest.mark.django_db
def test_existing_legacy_assignment_remains_selectable_only_on_its_own_edit_form():
    from ki_radar.use_cases.idea_forms import IdeaCandidateForm
    from ki_radar.use_cases.idea_models import IdeaCandidate

    legacy = BusinessUnit.objects.create(
        name="Historische Zuordnung",
        catalog_scope=BusinessUnit.CatalogScope.LEGACY,
    )
    idea = IdeaCandidate.objects.create(
        title="Historischer Eintrag",
        description="Bestehende Zuordnung darf nicht still verschwinden.",
        business_unit=legacy,
    )

    form = IdeaCandidateForm(instance=idea)
    ids = set(form.fields["business_unit"].queryset.values_list("pk", flat=True))
    assert legacy.pk in ids

    create_form = IdeaCandidateForm()
    create_ids = set(create_form.fields["business_unit"].queryset.values_list("pk", flat=True))
    assert legacy.pk not in create_ids
