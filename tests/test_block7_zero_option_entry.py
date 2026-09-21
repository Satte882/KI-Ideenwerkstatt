import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import comparison_blockers
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_ready_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="EU-Datenhaltung und menschliche Freigabe",
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Supplier Sourcing und Angebotsvergleich",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Angebotsvergleich vertiefen.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=2,
        name="Angebote vergleichen",
        description="Angebote fachlich vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manueller Vergleich",
        baseline_metrics="11 Minuten pro Vergleich",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell gegenübergestellt.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterienkatalog",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        baseline_metrics="11 Minuten pro Vergleich",
        analyzed_by=owner,
    )


def add_option(process, owner):
    SolutionOption.objects.create(
        process_analysis=process,
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        name="Bestehende Option",
        description="Rollen werden geklärt.",
        expected_value="Weniger Rückfragen.",
        created_by=owner,
    )


@pytest.mark.django_db
@pytest.mark.parametrize("existing_options", [0, 1])
def test_ai_generation_entry_is_available_with_zero_or_one_existing_option(
    client, owner, business_unit, existing_options
):
    process = make_ready_process(owner, business_unit)
    if existing_options:
        add_option(process, owner)
    client.force_login(owner)

    response = client.get(reverse("architecture:process_analysis_detail", args=[process.pk]))

    assert response.status_code == 200
    content = response.content.decode()
    start_url = reverse("accelerator:solution_generation_start", args=[process.pk])
    assert f'action="{start_url}"' in content
    assert "3 Lösungsentwürfe mit KI erstellen" in content


def test_comparison_blocker_is_explicitly_about_later_selection_not_generation():
    blockers = comparison_blockers([])

    assert blockers == [
        "Für die spätere Auswahl sind mindestens zwei unterschiedliche, gespeicherte "
        "Lösungsoptionen erforderlich."
    ]
