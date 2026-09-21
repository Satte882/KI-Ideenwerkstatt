import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.intake_views import SESSION_KEY, _persist_optional_origin
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def architecture_context(owner, business_unit):
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
            "rationale": "Hoher fachlicher Hebel und belastbare Baseline.",
            "updated_by": owner,
        },
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote einholen und vergleichen.",
        actors="Einkauf und Fachbereich",
        systems="ERP, E-Mail und Dateiablage",
        documents="Angebote und Kriterienkatalog",
        pain_points=("Uneinheitliche Angebote verlängern den manuellen Vergleich erheblich."),
        baseline_metrics="Fünf Tage Durchlaufzeit",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        status=ProcessAnalysis.Status.VALIDATED,
        scope_start="Angebote sind eingegangen",
        scope_end="Lieferant ist ausgewählt",
        trigger="Ablauf der Angebotsfrist",
        outcome="Nachvollziehbare Lieferantenentscheidung",
        current_flow=("Angebote öffnen, Werte übertragen, fehlende Angaben nachfordern, bewerten."),
        roles="Einkauf erstellt Vergleich; Fachbereich bewertet Qualität.",
        systems="ERP, Shared Inbox, Dateiablage",
        data_objects="Angebote, Kriterien, Lieferantenstammdaten",
        business_rules=("Mindestens fünf Lieferanten; Muss-Kriterien müssen erfüllt sein."),
        handoffs="Einkauf übergibt Shortlist an Fachbereich.",
        bottlenecks="Manuelle Übertragung und Rückfragen verursachen Wartezeit.",
        exceptions="Fehlende Preise oder abweichende Mengeneinheiten.",
        baseline_metrics="Fünf Tage Durchlaufzeit, zwei Rückfragen je Angebot.",
        target_state_principles=(
            "Vergleichbare Struktur, nachvollziehbare Bewertung, Mensch entscheidet."
        ),
        analyzed_by=owner,
    )
    return stream, stage, process


@pytest.fixture
def preferred_option(owner, architecture_context):
    _stream, _stage, process = architecture_context
    return SolutionOption.objects.create(
        process_analysis=process,
        name="Assistierter Angebotsvergleich",
        option_type=SolutionOption.OptionType.ASSISTANT,
        recommendation=SolutionOption.Recommendation.PREFERRED,
        description=("Extrahiert Angebotsdaten und erstellt einen nachvollziehbaren Vergleich."),
        expected_value="Durchlaufzeit von fünf auf drei Tage reduzieren.",
        feasibility="high",
        data_requirements="PDF- und Word-Angebote sowie Kriterienkatalog",
        application_impact="Neue interne Webanwendung",
        integration_impact="Dateiablage; ERP zunächst über Export",
        technology_constraints="Menschliche Freigabe bleibt erforderlich",
        risks="Falsche Extraktion bei ungewöhnlichen Tabellen",
        architecture_fit="Passt zum bestehenden Dokumenten- und Review-Prozess.",
        created_by=owner,
    )


@pytest.mark.django_db
def test_owner_can_create_process_analysis_from_stage(
    client,
    owner,
    architecture_context,
):
    _stream, stage, _process = architecture_context
    client.force_login(owner)

    response = client.post(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": stage.pk}),
        {
            "name": "Zweite Prozessanalyse",
            "status": ProcessAnalysis.Status.DRAFT,
            "scope_start": "Start",
            "scope_end": "Ende",
            "trigger": "Auslöser",
            "outcome": "Ergebnis",
            "current_flow": "Schritt eins, Übergabe, Schritt zwei.",
            "roles": "Rolle A und Rolle B",
            "systems": "System A",
            "data_objects": "Dokument A",
            "business_rules": "Regel A",
            "handoffs": "Übergabe A zu B",
            "bottlenecks": "Wartezeit an Übergabe",
            "exceptions": "Fehlerfall A",
            "baseline_metrics": "Zehn Vorgänge pro Woche",
            "target_state_principles": "Medienbruch vermeiden",
        },
    )

    created = ProcessAnalysis.objects.get(name="Zweite Prozessanalyse")
    assert response.status_code == 302
    assert created.stage == stage
    assert created.analyzed_by == owner


@pytest.mark.django_db
def test_solution_options_allow_non_ai_alternatives_and_separate_selection(
    owner,
    architecture_context,
    preferred_option,
):
    _stream, _stage, process = architecture_context
    organizational = SolutionOption.objects.create(
        process_analysis=process,
        name="Kriterienkatalog vereinheitlichen",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        recommendation=SolutionOption.Recommendation.CANDIDATE,
        description="Verbindliche Angebotsvorlage und klarere Ausschreibung.",
        expected_value="Weniger Rückfragen ohne neue Software.",
        created_by=owner,
    )
    assert organizational.get_option_type_display() == "Organisatorische Änderung"

    form = SolutionOptionForm(process_analysis=process)
    assert "recommendation" not in form.fields
    assert "evaluation_status" in form.fields

    assessed = SolutionOptionForm(
        {
            "name": "Alternative KI-Lösung",
            "option_type": SolutionOption.OptionType.GENERATIVE_AI,
            "evaluation_status": SolutionOption.EvaluationStatus.ASSESSED,
            "description": "Alternative KI-Lösung",
            "expected_value": "Weitere Zeitersparnis",
            "bottleneck_coverage": "",
            "feasibility": "medium",
            "data_requirements": "Angebote",
            "application_impact": "Neue Anwendung",
            "integration_effort": "medium",
            "integration_impact": "Keine",
            "technology_constraints": "EU-Hosting",
            "risks": "Halluzinationen",
            "architecture_fit": "Noch zu prüfen",
        },
        process_analysis=process,
    )
    assert not assessed.is_valid()
    assert "bottleneck_coverage" in assessed.errors


@pytest.mark.django_db
def test_only_preferred_solution_prefills_governed_intake(
    client,
    owner,
    architecture_context,
    preferred_option,
):
    _stream, _stage, process = architecture_context
    candidate = SolutionOption.objects.create(
        process_analysis=process,
        name="Nur Kandidat",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        recommendation=SolutionOption.Recommendation.CANDIDATE,
        description="Regelbasierte Vorprüfung",
        expected_value="Weniger manuelle Schritte",
        created_by=owner,
    )
    client.force_login(owner)

    blocked = client.get(
        reverse(
            "architecture:solution_option_start_use_case",
            kwargs={"pk": candidate.pk},
        )
    )
    assert blocked.status_code == 302
    assert SESSION_KEY not in client.session

    response = client.get(
        reverse(
            "architecture:solution_option_start_use_case",
            kwargs={"pk": preferred_option.pk},
        )
    )
    stored = client.session[SESSION_KEY]
    assert response.status_code == 302
    assert response.url == reverse("use_cases:create")
    assert stored["title"] == preferred_option.name
    assert stored["problem_statement"] == process.bottlenecks
    assert stored["summary"] == preferred_option.description
    assert stored["solution_type"] == UseCase.SolutionType.ASSISTANT
    assert stored["source_process_analysis_id"] == str(process.pk)
    assert stored["source_solution_option_id"] == str(preferred_option.pk)


@pytest.mark.django_db
def test_preferred_non_ai_solution_does_not_start_use_case_intake(
    client,
    owner,
    architecture_context,
):
    _stream, _stage, process = architecture_context
    option = SolutionOption.objects.create(
        process_analysis=process,
        name="Regelbasierte Freigabe",
        option_type=SolutionOption.OptionType.RULE_AUTOMATION,
        recommendation=SolutionOption.Recommendation.PREFERRED,
        description="Eindeutige Regeln automatisieren Standardfälle.",
        expected_value="Wartezeit ohne KI reduzieren.",
        created_by=owner,
    )
    client.force_login(owner)

    detail_response = client.get(process.get_absolute_url())
    assert detail_response.status_code == 200
    assert "Bevorzugte Option als Use Case prüfen" not in detail_response.content.decode()

    response = client.get(
        reverse(
            "architecture:solution_option_start_use_case",
            kwargs={"pk": option.pk},
        )
    )
    assert response.status_code == 302
    assert response.url == option.process_analysis.get_absolute_url()
    assert SESSION_KEY not in client.session


@pytest.mark.django_db
def test_process_and_solution_origin_is_traceable(
    owner,
    business_unit,
    architecture_context,
    preferred_option,
):
    _stream, stage, process = architecture_context
    use_case = UseCase.objects.create(
        title="Assistierter Angebotsvergleich",
        problem_statement=("Uneinheitliche Angebote verlängern den Vergleich erheblich."),
        business_unit=business_unit,
        affected_process=process.name,
        business_owner=owner,
        submitter=owner,
        expected_benefit="Durchlaufzeit reduzieren",
    )

    _persist_optional_origin(
        candidate=use_case,
        stored={
            "source_stage_id": str(stage.pk),
            "source_process_analysis_id": str(process.pk),
            "source_solution_option_id": str(preferred_option.pk),
        },
    )

    origin = UseCaseOrigin.objects.get(use_case=use_case)
    assert origin.stage == stage
    assert origin.process_analysis == process
    assert origin.solution_option == preferred_option


@pytest.mark.django_db
def test_process_detail_renders_task_oriented_headings_and_methodology(
    client,
    owner,
    architecture_context,
    preferred_option,
):
    _stream, _stage, process = architecture_context
    client.force_login(owner)

    response = client.get(process.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ist-Prozess und Ursachen" in content
    assert "Methodik: Business Architecture (ADM Phase B)." in content
    assert "Vertiefende Analyseinformationen" in content
    assert "Methodik: Information Systems &amp; Technology (ADM Phasen C/D)." in content
    assert "Lösungsoptionen vergleichen" in content
    assert "Methodik: Opportunities &amp; Solutions (ADM Phase E)." in content
    assert preferred_option.name in content
    assert "Bevorzugte Option als Use Case prüfen" in content
