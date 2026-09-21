import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import (
    EvidenceBasis,
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.solution_selection import (
    comparison_blockers,
    ordered_solution_options,
    select_preferred_solution,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


@pytest.fixture
def comparison_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bezahlte Leistung",
        scope_in="Bedarf bis Zahlung",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.update_or_create(
        value_stream=stream,
        defaults={
            "business_domain": BusinessDomain.PROCUREMENT,
            "capability": "Source-to-Pay",
            "strategic_impact": ScreeningLevel.HIGH,
            "economic_potential": ScreeningLevel.HIGH,
            "pain_intensity": ScreeningLevel.HIGH,
            "data_accessibility": ScreeningLevel.MEDIUM,
            "change_effort": ScreeningLevel.MEDIUM,
            "status": ValueStreamFocus.Status.SELECTED,
            "rationale": "Der Value Stream ist für den Deep Dive ausgewählt.",
            "updated_by": owner,
        },
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        description="Alternativen vergleichen.",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manuelle Übertragung",
        baseline_metrics="Fünf Tage",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        status=ProcessAnalysis.Status.TARGET_DEFINED,
        scope_start="Angebote liegen vor",
        scope_end="Lieferant ist gewählt",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote manuell vergleichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterien",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        diagnostic_observations="Der Angebotsvergleich benötigt fünf Tage und viele Rückfragen.",
        cause_hypotheses="Uneinheitliche Formate verursachen zusätzliche Übertragungsschritte.",
        confirmed_causes=(
            "Angebotsdaten liegen nicht strukturiert vor und werden manuell übertragen."
        ),
        baseline_metrics="Fünf Tage",
        analyzed_by=owner,
    )


def make_option(process, owner, *, name, option_type, status="assessed", **overrides):
    data = {
        "process_analysis": process,
        "name": name,
        "option_type": option_type,
        "evaluation_status": status,
        "evidence_basis": EvidenceBasis.HYPOTHESIS,
        "description": f"Beschreibung {name}",
        "expected_value": f"Nutzen {name}",
        "time_to_value": TimeToValue.UNKNOWN,
        "bottleneck_coverage": "Reduziert manuelle Übertragung.",
        "feasibility": SolutionOption.Effort.HIGH,
        "data_requirements": "Angebote und Kriterien",
        "application_impact": "Ergänzung der Fachanwendung",
        "integration_effort": SolutionOption.Effort.MEDIUM,
        "integration_impact": "ERP-Export",
        "technology_constraints": "Nachvollziehbare Verarbeitung",
        "risks": "Fehlerhafte Eingaben",
        "architecture_fit": "Passt zur bestehenden Architektur",
        "created_by": owner,
    }
    data.update(overrides)
    return SolutionOption.objects.create(**data)


def assessed_form_data(**overrides):
    data = {
        "name": "Regelprüfung",
        "option_type": SolutionOption.OptionType.RULE_AUTOMATION,
        "evaluation_status": SolutionOption.EvaluationStatus.ASSESSED,
        "evidence_basis": EvidenceBasis.HYPOTHESIS,
        "description": "Beschreibung Regelprüfung",
        "expected_value": "Nutzen Regelprüfung",
        "time_to_value": TimeToValue.UNKNOWN,
        "bottleneck_coverage": "Reduziert manuelle Übertragung.",
        "feasibility": SolutionOption.Effort.HIGH,
        "data_requirements": "Angebote und Kriterien",
        "application_impact": "Ergänzung der Fachanwendung",
        "integration_effort": SolutionOption.Effort.MEDIUM,
        "integration_impact": "ERP-Export",
        "technology_constraints": "Nachvollziehbare Verarbeitung",
        "risks": "Fehlerhafte Eingaben",
        "architecture_fit": "Passt zur bestehenden Architektur",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_new_solution_option_defaults_are_not_assessed(comparison_process, owner):
    option = SolutionOption.objects.create(
        process_analysis=comparison_process,
        name="Neuer Entwurf",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Beschreibung",
        expected_value="Erwarteter Beitrag",
        created_by=owner,
    )

    assert option.feasibility == SolutionOption.Effort.NOT_ASSESSED
    assert option.integration_effort == SolutionOption.Effort.NOT_ASSESSED
    assert option.time_to_value == TimeToValue.NOT_ASSESSED
    assert option.evidence_basis == EvidenceBasis.HYPOTHESIS
    assert option.get_feasibility_display() == "Noch nicht bewertet"
    assert option.get_integration_effort_display() == "Noch nicht bewertet"
    assert option.comparison_complete is False


@pytest.mark.django_db
def test_explicit_existing_assessments_remain_unchanged(comparison_process, owner):
    option = make_option(
        comparison_process,
        owner,
        name="Bestehende Bewertung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
    )
    option.refresh_from_db()

    assert option.feasibility == SolutionOption.Effort.HIGH
    assert option.integration_effort == SolutionOption.Effort.MEDIUM
    assert option.time_to_value == TimeToValue.UNKNOWN
    assert option.comparison_complete is True


@pytest.mark.django_db
@pytest.mark.parametrize("field_name", ["feasibility", "integration_effort"])
def test_assessed_form_rejects_unassessed_effort(comparison_process, field_name):
    form = SolutionOptionForm(
        data=assessed_form_data(**{field_name: SolutionOption.Effort.NOT_ASSESSED}),
        process_analysis=comparison_process,
    )

    assert not form.is_valid()
    assert field_name in form.errors
    assert "muss für den Status 'Bewertet' bewertet sein" in form.errors[field_name][0]


@pytest.mark.django_db
def test_assessed_form_requires_time_to_value_tradeoff(comparison_process):
    form = SolutionOptionForm(
        data=assessed_form_data(time_to_value=TimeToValue.NOT_ASSESSED),
        process_analysis=comparison_process,
    )

    assert not form.is_valid()
    assert "time_to_value" in form.errors
    assert "Time-to-Value muss" in form.errors["time_to_value"][0]


@pytest.mark.django_db
def test_comparison_complete_rejects_unassessed_effort(comparison_process, owner):
    option = make_option(
        comparison_process,
        owner,
        name="Unvollständige Bewertung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
    )
    option.feasibility = SolutionOption.Effort.NOT_ASSESSED

    assert option.comparison_complete is False


@pytest.mark.django_db
def test_options_are_sorted_solution_open(comparison_process, owner):
    ai = make_option(
        comparison_process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )
    rule = make_option(
        comparison_process,
        owner,
        name="Regelprüfung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
    )
    organizational = make_option(
        comparison_process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )

    assert ordered_solution_options(comparison_process) == [organizational, rule, ai]


@pytest.mark.django_db
def test_hybrid_and_ambiguous_types_require_explicit_ai_component(comparison_process, owner):
    custom = make_option(
        comparison_process,
        owner,
        name="Individuelle Fachlogik",
        option_type=SolutionOption.OptionType.CUSTOM_SOFTWARE,
    )
    other = make_option(
        comparison_process,
        owner,
        name="Sonstige Lösung",
        option_type=SolutionOption.OptionType.OTHER,
    )
    hybrid_non_ai = make_option(
        comparison_process,
        owner,
        name="Hybrid ohne KI",
        option_type=SolutionOption.OptionType.HYBRID,
    )
    hybrid_ai = make_option(
        comparison_process,
        owner,
        name="Hybrid mit KI",
        option_type=SolutionOption.OptionType.HYBRID,
        contains_ai_component=True,
    )
    assistant = make_option(
        comparison_process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )

    assert custom.starts_ai_use_case is False
    assert other.starts_ai_use_case is False
    assert hybrid_non_ai.starts_ai_use_case is False
    assert hybrid_ai.starts_ai_use_case is True
    assert assistant.starts_ai_use_case is True


@pytest.mark.django_db
def test_comparison_requires_two_complete_options(comparison_process, owner):
    first = make_option(
        comparison_process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    assert comparison_blockers([first]) == [
        "Für die spätere Auswahl sind mindestens zwei unterschiedliche, gespeicherte "
        "Lösungsoptionen erforderlich."
    ]

    second = make_option(
        comparison_process,
        owner,
        name="Regelprüfung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        status=SolutionOption.EvaluationStatus.DRAFT,
    )
    blockers = comparison_blockers([first, second])
    assert "Regelprüfung" in blockers[0]


@pytest.mark.django_db
def test_selection_is_auditable_and_updates_statuses(comparison_process, owner):
    organizational = make_option(
        comparison_process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        evidence_basis=EvidenceBasis.MEASURED,
        time_to_value=TimeToValue.SHORT,
    )
    assistant = make_option(
        comparison_process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
        evidence_basis=EvidenceBasis.INDICATIVE,
        time_to_value=TimeToValue.MEDIUM,
    )

    decision = select_preferred_solution(
        process_analysis=comparison_process,
        selected_option=assistant,
        rationale="Die organisatorische Option reduziert nicht die verbleibende Extraktionsarbeit.",
        actor=owner,
    )

    organizational.refresh_from_db()
    assistant.refresh_from_db()
    assert organizational.recommendation == SolutionOption.Recommendation.REJECTED
    assert assistant.recommendation == SolutionOption.Recommendation.PREFERRED
    assert decision.decided_by == owner
    assert decision.process_version == comparison_process.version
    assert decision.diagnosis_snapshot["diagnostic_observations"] == (
        comparison_process.diagnostic_observations
    )
    assert decision.diagnosis_snapshot["confirmed_causes"] == comparison_process.confirmed_causes
    assert decision.diagnosis_snapshot["validation"] is None
    assert decision.comparison_snapshot[0]["name"] == organizational.name
    assert decision.comparison_snapshot[0]["time_to_value"] == TimeToValue.SHORT
    assert decision.comparison_snapshot[0]["evidence_basis"] == EvidenceBasis.MEASURED
    assert decision.comparison_snapshot[0]["contains_ai_component"] is False
    assert decision.comparison_snapshot[1]["contains_ai_component"] is True
    assert len(decision.comparison_snapshot) == 2

    decision.rationale = "Nachträglich geändert"
    with pytest.raises(ValidationError):
        decision.save()
    with pytest.raises(ValidationError):
        decision.delete()


@pytest.mark.django_db
def test_selection_rejects_unauthorized_reader(comparison_process, owner, reader):
    first = make_option(
        comparison_process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    make_option(
        comparison_process,
        owner,
        name="Regelprüfung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
    )

    with pytest.raises(ValidationError, match="Berechtigung"):
        select_preferred_solution(
            process_analysis=comparison_process,
            selected_option=first,
            rationale="Nicht berechtigt.",
            actor=reader,
        )


@pytest.mark.django_db
def test_comparison_page_selects_and_shows_history(client, comparison_process, owner):
    organizational = make_option(
        comparison_process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
    )
    assistant = make_option(
        comparison_process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", kwargs={"pk": comparison_process.pk})

    response = client.get(url)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Vergleichsmatrix" in content
    assert content.index(organizational.name) < content.index(assistant.name)
    assert "Bottleneck-Abdeckung" in content
    assert "Integrationsaufwand" in content
    assert "Technologieleitplanken" in content
    assert "Time-to-Value" in content
    assert "Evidenzbasis" in content

    response = client.post(
        url,
        {
            "selected_option": assistant.pk,
            "rationale": "Die organisatorische Alternative deckt die Extraktionsarbeit nicht ab.",
        },
    )
    assert response.status_code == 302
    decision = SolutionSelectionDecision.objects.get(process_analysis=comparison_process)
    assert decision.selected_option == assistant

    history = client.get(url).content.decode()
    assert "Auswahlhistorie" in history
    assert "Die organisatorische Alternative" in history
    assert f"Prozessversion v{comparison_process.version}" in history
    assert "Diagnose- und Evidenzstand der Entscheidung" in history
    assert "KI-Use-Case kann regulär weitergeführt werden" in history


def test_solution_option_form_uses_german_option_type_label():
    form = SolutionOptionForm()

    assert form.fields["option_type"].label == "Lösungstyp"


@pytest.mark.django_db
def test_comparison_page_handles_unassessed_and_empty_technology_constraints(
    client,
    comparison_process,
    owner,
):
    option = SolutionOption.objects.create(
        process_analysis=comparison_process,
        name="Ältere manuelle Option",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Beschreibung",
        expected_value="Nutzen",
        feasibility=SolutionOption.Effort.MEDIUM,
        integration_effort=SolutionOption.Effort.MEDIUM,
        technology_constraints="",
        created_by=owner,
    )
    new_option = SolutionOption.objects.create(
        process_analysis=comparison_process,
        name="Neutraler Entwurf",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        description="Beschreibung",
        expected_value="Nutzen",
        created_by=owner,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", kwargs={"pk": comparison_process.pk})

    content = client.get(url).content.decode()

    assert option.name in content
    assert new_option.name in content
    assert "Noch nicht bewertet" in content
    assert "Technologieleitplanken" in content
    assert "\u2013" in content


@pytest.mark.django_db
def test_selection_audit_rejects_bulk_changes_and_inconsistent_option(
    comparison_process,
    owner,
    business_unit,
):
    from django.db.models.deletion import ProtectedError

    selected = make_option(
        comparison_process,
        owner,
        name="Regelprüfung",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
    )
    alternative = make_option(
        comparison_process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
    )
    decision = select_preferred_solution(
        process_analysis=comparison_process,
        selected_option=selected,
        rationale="Die Regelprüfung deckt den Engpass mit geringerer Komplexität ab.",
        actor=owner,
    )

    with pytest.raises(ValidationError, match="unveränderlich"):
        SolutionSelectionDecision.objects.filter(pk=decision.pk).update(rationale="Manipuliert")
    with pytest.raises(ValidationError, match="unveränderlich"):
        SolutionSelectionDecision.objects.filter(pk=decision.pk).delete()
    with pytest.raises(ProtectedError):
        selected.delete()

    other_stream = ValueStream.objects.create(
        name="Anderer Wertstrom",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Start",
        outcome="Ergebnis",
        scope_in="Scope",
    )
    other_stage = ValueStreamStage.objects.create(
        value_stream=other_stream,
        sequence=1,
        name="Andere Phase",
    )
    other_process = ProcessAnalysis.objects.create(
        stage=other_stage,
        name="Anderer Prozess",
        scope_start="Start",
        scope_end="Ende",
        trigger="Start",
        outcome="Ergebnis",
        current_flow="Ablauf",
        roles="Rolle",
        systems="System",
        data_objects="Daten",
        bottlenecks="Engpass",
        baseline_metrics="Baseline",
        analyzed_by=owner,
    )
    with pytest.raises(ValidationError, match="gehört nicht"):
        SolutionSelectionDecision.objects.create(
            process_analysis=other_process,
            selected_option=alternative,
            rationale="Inkonsistente Zuordnung",
            comparison_snapshot=[],
            decided_by=owner,
        )
