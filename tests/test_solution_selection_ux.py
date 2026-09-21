import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Angebotsvergleich",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.HIGH,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Deep Dive ausgewählt.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP",
        data_objects="Angebote und Kriterien",
        bottlenecks="Manuelle Übertragung.",
        diagnostic_observations="Der manuelle Vergleich benötigt fünf Tage.",
        cause_hypotheses="Uneinheitliche Angebotsformate erhöhen den Übertragungsaufwand.",
        confirmed_causes="Fehlende strukturierte Angebotsdaten erzwingen manuelle Übertragung.",
        baseline_metrics="Fünf Tage",
        analyzed_by=owner,
    )


def make_option(process, owner, *, name, option_type, assessed):
    status = (
        SolutionOption.EvaluationStatus.ASSESSED
        if assessed
        else SolutionOption.EvaluationStatus.DRAFT
    )
    feasibility = SolutionOption.Effort.HIGH if assessed else SolutionOption.Effort.NOT_ASSESSED
    integration = SolutionOption.Effort.MEDIUM if assessed else SolutionOption.Effort.NOT_ASSESSED
    time_to_value = TimeToValue.UNKNOWN if assessed else TimeToValue.NOT_ASSESSED
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=option_type,
        evaluation_status=status,
        description=f"Beschreibung {name}",
        expected_value=f"Nutzen {name}",
        bottleneck_coverage="Reduziert manuelle Übertragung.",
        feasibility=feasibility,
        data_requirements="Angebote und Kriterien",
        application_impact="Ergänzung der Fachanwendung",
        integration_effort=integration,
        integration_impact="ERP-Export",
        technology_constraints="Nachvollziehbare Verarbeitung",
        risks="Fehlerhafte Eingaben",
        architecture_fit="Passt zur bestehenden Architektur",
        time_to_value=time_to_value,
        created_by=owner,
    )


@pytest.mark.django_db
def test_incomplete_options_make_preferred_selection_gate_actionable(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    first = make_option(
        process,
        owner,
        name="Organisatorischer Entwurf",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        assessed=False,
    )
    second = make_option(
        process,
        owner,
        name="Assistenzentwurf",
        option_type=SolutionOption.OptionType.ASSISTANT,
        assessed=False,
    )
    client.force_login(owner)

    url = reverse("architecture:solution_option_compare", args=[process.pk])
    content = client.get(url).content.decode()

    assert "Auswahl noch gesperrt" in content
    assert "KI-Entwürfe werden absichtlich" in content
    assert "Noch nicht bewertet" in content
    assert content.count("Option vollständig bewerten") == 2
    assert reverse("architecture:solution_option_update", args=[first.pk]) in content
    assert reverse("architecture:solution_option_update", args=[second.pk]) in content


@pytest.mark.django_db
def test_preferred_selection_returns_to_visible_result(client, owner, business_unit):
    process = make_process(owner, business_unit)
    organizational = make_option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        assessed=True,
    )
    assistant = make_option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
        assessed=True,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])

    response = client.post(
        url,
        {
            "selected_option": assistant.pk,
            "rationale": "Die Assistenz deckt den Engpass besser ab.",
        },
    )

    assert response.status_code == 302
    assert response.url == f"{url}#selection-result"
    organizational.refresh_from_db()
    assistant.refresh_from_db()
    assert organizational.recommendation == SolutionOption.Recommendation.REJECTED
    assert assistant.recommendation == SolutionOption.Recommendation.PREFERRED

    content = client.get(url).content.decode()
    assert "Aktuell bevorzugt: KI-Assistenz" in content
    assert "Die Entscheidung ist in der Auswahlhistorie auditierbar." in content
    selected_value = client.get(url).context["form"]["selected_option"].value()
    assert str(selected_value) == str(assistant.pk)
