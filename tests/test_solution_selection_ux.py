import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import select_preferred_solution
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


@pytest.mark.django_db
def test_all_blockers_are_visible_without_misleading_edit_links(client, owner, business_unit):
    process = make_process(owner, business_unit)
    process.stage.value_stream.focus.delete()
    process.confirmed_causes = ""
    process.save()
    option = make_option(
        process, owner, name="Entwurf", option_type="organizational", assessed=False
    )
    client.force_login(owner)
    response = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))
    content = response.content.decode()
    assert response.context["selection_blocked"]
    assert "Fokusfreigabe fehlt" in content
    assert "Mindestens zwei aktive Optionen erforderlich" in content
    assert "Noch vollständig zu bewerten" in content
    assert "bestätigte Ursache" in content
    assert "Bewertungsstatus: Bewertet" in content
    assert (
        reverse("architecture:value_stream_update", args=[process.stage.value_stream_id]) in content
    )
    assert reverse("architecture:solution_option_update", args=[option.pk]) not in content
    assert reverse("architecture:process_analysis_update", args=[process.pk]) not in content


@pytest.mark.django_db
def test_focus_alone_blocks_ui_and_server_selection(client, owner, business_unit):
    process = make_process(owner, business_unit)
    process.stage.value_stream.focus.delete()
    option = make_option(
        process, owner, name="Organisation", option_type="organizational", assessed=True
    )
    make_option(process, owner, name="Assistenz", option_type="assistant", assessed=True)
    client.force_login(owner)
    response = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))
    assert response.context["selection_blocked"]
    assert 'name="selected_option"' not in response.content.decode()
    with pytest.raises(ValidationError, match="Fokusentscheidung"):
        select_preferred_solution(
            process_analysis=process, selected_option=option, rationale="Vergleich", actor=owner
        )
    assert not process.solution_selection_decisions.exists()


@pytest.mark.django_db
def test_assessment_link_opens_fields_and_saves_back_to_comparison(client, owner, business_unit):
    process = make_process(owner, business_unit)
    option = make_option(
        process, owner, name="Organisation", option_type="organizational", assessed=False
    )
    client.force_login(owner)
    compare_url = reverse("architecture:solution_option_compare", args=[process.pk])
    edit_url = (
        reverse("architecture:solution_option_update", args=[option.pk]) + "?return_to=comparison"
    )
    assert edit_url in client.get(compare_url).content.decode()
    response = client.get(edit_url)
    assert response.status_code == 200
    assert "Noch offene Bewertungsangaben" in response.content.decode()
    assert 'name="feasibility"' in response.content.decode()
    assessed = make_option(
        process, owner, name="Vollständig", option_type="organizational", assessed=True
    )
    payload = {field: getattr(assessed, field) for field in SolutionOptionForm.Meta.fields}
    payload["name"] = option.name
    response = client.post(edit_url, payload)
    assert response.status_code == 302
    assert response.url == compare_url
    option.refresh_from_db()
    assert option.comparison_complete
    assert not client.get(compare_url).context["selection_blocked"]


@pytest.mark.django_db
def test_incomplete_assessment_cannot_be_marked_complete(client, owner, business_unit):
    process = make_process(owner, business_unit)
    option = make_option(
        process, owner, name="Entwurf", option_type="organizational", assessed=False
    )
    client.force_login(owner)
    payload = {field: getattr(option, field) for field in SolutionOptionForm.Meta.fields}
    payload["evaluation_status"] = "assessed"
    url = reverse("architecture:solution_option_update", args=[option.pk]) + "?return_to=comparison"
    response = client.post(url, payload)
    assert response.status_code == 200
    assert response.context["form"].errors
    option.refresh_from_db()
    assert not option.comparison_complete


@pytest.mark.django_db
def test_retired_option_is_explained_and_does_not_count(client, owner, business_unit):
    from ki_radar.architecture.solution_retirement import retire_solution_option

    process = make_process(owner, business_unit)
    make_option(process, owner, name="Organisation", option_type="organizational", assessed=True)
    retired = make_option(process, owner, name="Alt", option_type="assistant", assessed=True)
    retire_solution_option(option=retired, actor=owner)
    client.force_login(owner)
    response = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))
    assert response.context["needs_more_options"]
    assert "zählen aber nicht für die Auswahl" in response.content.decode()
