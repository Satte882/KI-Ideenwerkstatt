import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    EvidenceBasis,
    ProcessAnalysis,
    SolutionOption,
    TimeToValue,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
    WorkDesignAssessment,
    WorkDesignTask,
)
from ki_radar.architecture.work_design import (
    METHOD_VERSION,
    score_task,
    validate_task,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.intake_views import SESSION_KEY, _persist_optional_origin
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def work_design_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Kundenanfrage bis Angebot",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Kundenanfrage",
        outcome="Freigegebenes Angebot",
        scope_in="Anfrage bis Angebot",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.SALES,
        capability="Account Management",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.HIGH,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Rollen- und Handoff-Frage soll vertieft werden.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebot vorbereiten",
        description="Account-Kontext aufbereiten und Angebot erstellen.",
        actors="Account Manager, Sales Operations und Legal",
        systems="CRM, ERP",
        documents="Kundenakte, Vertrag, Preislisten",
        pain_points="Rückfragen und Wartezeiten an Übergaben.",
        baseline_metrics="Drei Tage Durchlaufzeit",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvorbereitung",
        status=ProcessAnalysis.Status.VALIDATED,
        scope_start="Kundenanfrage ist qualifiziert",
        scope_end="Angebot ist freigegeben",
        trigger="Qualifizierte Anfrage",
        outcome="Schnelleres belastbares Angebot",
        current_flow="Account Manager sammelt Kontext und übergibt Sonderfälle.",
        roles="Account Manager arbeitet mit Sales Operations und Legal.",
        systems="CRM, ERP",
        data_objects="Kundenakte, Verträge, Preislisten",
        business_rules="Sonderkonditionen benötigen Freigabe.",
        handoffs="Account Manager übergibt Vertragsabweichungen an Legal.",
        bottlenecks="Wartezeit bei Rückfragen und Vertragsprüfung.",
        exceptions="Sonderkonditionen",
        baseline_metrics="Drei Tage Durchlaufzeit",
        target_state_principles="Klare Freigabegrenzen",
        analyzed_by=owner,
    )


def complete_criteria(**overrides):
    criteria = {
        "business_value": 4,
        "handoff_friction": 4,
        "recurrence": 4,
        "context_proximity": 4,
        "ai_leverage": 4,
        "data_readiness": 4,
        "judgment_stakes": 1,
        "specialist_accountability": 1,
    }
    criteria.update(overrides)
    return criteria


def test_taskshift_v17_regression_vectors_match_standalone_contract():
    own = score_task(complete_criteria())
    assert own.potential_score == 100
    assert own.boundary_score == 25
    assert own.recommendation == "own"
    assert own.approval_required is False

    contract_review = score_task(
        complete_criteria(
            data_readiness=3,
            judgment_stakes=3,
            specialist_accountability=4,
        )
    )
    assert contract_review.potential_score == 98
    assert contract_review.boundary_score == 86
    assert contract_review.recommendation == "prepare-only"
    assert contract_review.approval_required is True
    assert contract_review.design_pattern == "AI-Powered Process Redesign"

    with_approval = score_task(
        complete_criteria(
            judgment_stakes=2,
            specialist_accountability=2,
        )
    )
    assert with_approval.boundary_score == 50
    assert with_approval.recommendation == "own-with-approval"
    assert with_approval.approval_required is True

    explore = score_task({key: 2 for key in complete_criteria()})
    assert explore.potential_score == 50
    assert explore.boundary_score == 50
    assert explore.recommendation == "explore"


def test_incomplete_or_invalid_assessment_has_no_score():
    incomplete = complete_criteria()
    incomplete["ai_leverage"] = None
    validation = validate_task(incomplete)
    assert validation.complete is False
    assert validation.missing == ("ai_leverage",)

    invalid = complete_criteria(ai_leverage=5)
    validation = validate_task(invalid)
    assert validation.complete is False
    assert validation.invalid == ("ai_leverage",)


@pytest.mark.django_db
def test_work_design_assessment_keeps_confirmed_role_separate_from_process_roles(
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        method_version=METHOD_VERSION,
        created_by=owner,
    )

    assert assessment.role_name == "Account Manager"
    assert "Legal" in work_design_process.roles
    assert assessment.is_stale is False

    work_design_process.version += 1
    work_design_process.save(update_fields=["version", "updated_at"])
    assessment.refresh_from_db()
    assert assessment.is_stale is True


@pytest.mark.django_db
def test_work_design_task_persists_deterministic_scores(owner, work_design_process):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Vertragsabweichungen vorprüfen",
        source_area="Legal",
        target_work_split=(
            "Account Manager bereitet Abweichungen mit KI vor; Legal entscheidet final."
        ),
        approval_role="Legal",
        **complete_criteria(
            data_readiness=3,
            judgment_stakes=3,
            specialist_accountability=4,
        ),
    )

    assert task.potential_score == 98
    assert task.boundary_score == 86
    assert task.recommendation == WorkDesignTask.Recommendation.PREPARE_ONLY
    assert task.approval_required is True


@pytest.mark.django_db
def test_work_design_task_requires_approval_role_when_recommendation_requires_it(
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )

    with pytest.raises(ValidationError) as exc:
        WorkDesignTask.objects.create(
            assessment=assessment,
            name="Vertragsabweichungen vorprüfen",
            approval_role="",
            **complete_criteria(
                judgment_stakes=2,
                specialist_accountability=2,
            ),
        )

    assert "approval_role" in exc.value.message_dict


@pytest.mark.django_db
def test_work_design_task_allows_draft_without_complete_criteria(
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Meeting vorbereiten",
        business_value=4,
    )

    assert task.potential_score is None
    assert task.boundary_score is None
    assert task.recommendation == ""
    assert task.approval_required is False


def task_form_payload(**overrides):
    payload = {
        "name": "Kundenmeeting vorbereiten",
        "source_area": "Sales",
        "target_work_split": (
            "Account Manager erstellt Briefing und Potenzialanalyse mit KI selbst."
        ),
        "approval_role": "",
        "business_value": "4",
        "handoff_friction": "3",
        "recurrence": "4",
        "context_proximity": "4",
        "ai_leverage": "4",
        "data_readiness": "3",
        "judgment_stakes": "1",
        "specialist_accountability": "1",
    }
    for field_name in (
        "business_value",
        "handoff_friction",
        "recurrence",
        "context_proximity",
        "ai_leverage",
        "data_readiness",
        "judgment_stakes",
        "specialist_accountability",
    ):
        payload[f"{field_name}_touched"] = "1"
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_process_detail_exposes_optional_work_design_entry(
    client,
    owner,
    work_design_process,
):
    client.force_login(owner)

    response = client.get(work_design_process.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Arbeitsgestaltung" in content
    assert "Rollenbetrachtung starten" in content
    create_url = reverse(
        "architecture:work_design_assessment_create",
        kwargs={"process_pk": work_design_process.pk},
    )
    assert create_url in content


@pytest.mark.django_db
def test_work_design_create_prefills_outcome_but_not_primary_role(
    client,
    owner,
    work_design_process,
):
    client.force_login(owner)
    url = reverse(
        "architecture:work_design_assessment_create",
        kwargs={"process_pk": work_design_process.pk},
    )

    response = client.get(url)

    assert response.status_code == 200
    form = response.context["form"]
    assert form.initial["business_outcome"] == work_design_process.outcome
    assert not form.initial.get("role_name")
    assert work_design_process.roles in response.content.decode()

    response = client.post(
        url,
        {
            "role_name": "Account Manager",
            "business_outcome": work_design_process.outcome,
        },
    )
    assessment = WorkDesignAssessment.objects.get(
        process_analysis=work_design_process,
        role_name="Account Manager",
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "architecture:work_design_assessment_detail",
        kwargs={"pk": assessment.pk},
    )
    assert assessment.process_version == work_design_process.version
    assert assessment.version == 1


@pytest.mark.django_db
def test_new_task_requires_each_slider_to_be_deliberately_touched(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    client.force_login(owner)
    url = reverse(
        "architecture:work_design_task_create",
        kwargs={"assessment_pk": assessment.pk},
    )

    payload = task_form_payload()
    payload["ai_leverage_touched"] = ""
    response = client.post(url, payload)

    assert response.status_code == 200
    assert not assessment.tasks.exists()
    assert "Bitte diesen Regler einmal bewusst setzen" in response.content.decode()


@pytest.mark.django_db
def test_task_rating_is_added_to_workspace_and_marks_assessment_assessed(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    client.force_login(owner)
    create_url = reverse(
        "architecture:work_design_task_create",
        kwargs={"assessment_pk": assessment.pk},
    )

    response = client.post(create_url, task_form_payload())
    task = WorkDesignTask.objects.get(assessment=assessment)

    assert response.status_code == 302
    assessment.refresh_from_db()
    assert assessment.status == WorkDesignAssessment.Status.ASSESSED
    assert task.potential_score is not None
    assert task.boundary_score is not None
    assert not SolutionOption.objects.filter(process_analysis=work_design_process).exists()

    workspace_url = reverse(
        "architecture:work_design_assessment_detail",
        kwargs={"pk": assessment.pk},
    )
    workspace = client.get(workspace_url)
    content = workspace.content.decode()
    assert workspace.status_code == 200
    assert "Kundenmeeting vorbereiten" in content
    assert task.get_recommendation_display() in content
    assert f"{task.potential_score}/100" in content
    assert work_design_process.roles in content
    assert work_design_process.handoffs in content


@pytest.mark.django_db
def test_task_edit_recalculates_scores_and_enforces_approval_role(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Kundenmeeting vorbereiten",
        source_area="Sales",
        **complete_criteria(),
    )
    client.force_login(owner)
    url = reverse("architecture:work_design_task_update", kwargs={"pk": task.pk})

    response = client.post(
        url,
        task_form_payload(
            name=task.name,
            source_area=task.source_area,
            approval_role="Legal",
            judgment_stakes="3",
            specialist_accountability="4",
        ),
    )

    assert response.status_code == 302
    task.refresh_from_db()
    assert task.recommendation == WorkDesignTask.Recommendation.PREPARE_ONLY
    assert task.approval_required is True
    assert task.approval_role == "Legal"
    assert not SolutionOption.objects.filter(process_analysis=work_design_process).exists()


@pytest.mark.django_db
def test_workspace_warns_when_process_context_has_changed(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    work_design_process.version += 1
    work_design_process.save(update_fields=["version", "updated_at"])
    client.force_login(owner)

    workspace_url = reverse(
        "architecture:work_design_assessment_detail",
        kwargs={"pk": assessment.pk},
    )
    response = client.get(workspace_url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Prozesskontext wurde seit dieser Arbeitsgestaltung geändert" in content


def solution_option_payload(**overrides):
    payload = {
        "name": "KI-gestützte Meetingvorbereitung",
        "option_type": SolutionOption.OptionType.ASSISTANT,
        "evaluation_status": SolutionOption.EvaluationStatus.DRAFT,
        "evidence_basis": EvidenceBasis.HYPOTHESIS,
        "description": "Account Manager erstellt Briefing und Potenzialanalyse mit KI selbst.",
        "expected_value": "Schnelleres belastbares Angebot",
        "time_to_value": TimeToValue.NOT_ASSESSED,
        "bottleneck_coverage": "",
        "feasibility": SolutionOption.Effort.NOT_ASSESSED,
        "data_requirements": "",
        "application_impact": "",
        "integration_effort": SolutionOption.Effort.NOT_ASSESSED,
        "integration_impact": "",
        "technology_constraints": "",
        "risks": "",
        "architecture_fit": "",
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_work_design_task_selection_opens_solution_design_context_without_creating_option(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Kundenmeeting vorbereiten",
        source_area="Sales",
        target_work_split="Account Manager erstellt Briefing und Potenzialanalyse mit KI selbst.",
        **complete_criteria(),
    )
    client.force_login(owner)

    url = reverse(
        "architecture:work_design_task_select_solution_design",
        kwargs={"pk": task.pk},
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == (
        f"{work_design_process.get_absolute_url()}?design_task={task.pk}#loesungsoptionen"
    )
    assert not SolutionOption.objects.filter(source_work_design_task=task).exists()

    landing = client.get(f"{work_design_process.get_absolute_url()}?design_task={task.pk}")
    content = landing.content.decode()
    assert landing.status_code == 200
    assert 'data-testid="solution-design-task-context"' in content
    assert task.name in content
    assert "Lösungsoption für diese Aufgabe ergänzen" in content
    assert "Die Aufgabe bleibt Ergebnis der TASKSHIFT-Arbeitsgestaltung" in content


@pytest.mark.django_db
def test_selected_task_can_source_multiple_real_solution_options_with_frozen_snapshot(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Vertragsabweichungen vorprüfen",
        source_area="Legal",
        target_work_split=(
            "Account Manager bereitet Abweichungen mit KI vor; Legal entscheidet final."
        ),
        approval_role="Legal",
        **complete_criteria(
            data_readiness=3,
            judgment_stakes=3,
            specialist_accountability=4,
        ),
    )
    client.force_login(owner)
    base_url = reverse(
        "architecture:solution_option_create",
        kwargs={"process_analysis_id": work_design_process.pk},
    )
    url = f"{base_url}?work_design_task={task.pk}"

    get_response = client.get(url)
    form = get_response.context["form"]
    assert get_response.status_code == 200
    assert not form.initial.get("name")
    assert not form.initial.get("description")
    assert form.initial["expected_value"] == assessment.business_outcome
    assert "Lösungsdesign-Kontext aus der Arbeitsgestaltung" in get_response.content.decode()

    response = client.post(
        url,
        solution_option_payload(
            name="KI-Assistent für Vertragsvorprüfung",
            option_type=SolutionOption.OptionType.ASSISTANT,
            description=(
                "Ein Assistenzsystem analysiert Vertragsabweichungen und bereitet "
                "eine strukturierte Vorlage für Legal vor."
            ),
            expected_value=assessment.business_outcome,
        ),
    )

    assert response.status_code == 302
    option = SolutionOption.objects.get(
        source_work_design_task=task,
        name="KI-Assistent für Vertragsvorprüfung",
    )
    assert response.url == (
        f"{work_design_process.get_absolute_url()}?"
        f"design_task={task.pk}&highlight={option.pk}#loesungsoptionen"
    )
    assert option.recommendation == SolutionOption.Recommendation.CANDIDATE
    assert option.source_work_design_snapshot["schema"] == "taskshift.solution_origin.v1"
    assert option.source_work_design_snapshot["role_name"] == "Account Manager"
    assert option.source_work_design_snapshot["task_name"] == task.name
    assert option.source_work_design_snapshot["approval_role"] == "Legal"
    assert option.source_work_design_snapshot["approval_required"] is True
    assert option.source_work_design_snapshot["criteria"] == task.criteria

    second_response = client.post(
        url,
        solution_option_payload(
            name="Regelbasierte Vertragsvorprüfung",
            option_type=SolutionOption.OptionType.RULE_AUTOMATION,
            description=(
                "Eindeutige Vertragsabweichungen werden regelbasiert markiert; "
                "Legal prüft die markierten Fälle."
            ),
            expected_value=assessment.business_outcome,
        ),
    )
    assert second_response.status_code == 302
    assert SolutionOption.objects.filter(source_work_design_task=task).count() == 2

    frozen_snapshot = dict(option.source_work_design_snapshot)
    task.name = "Nachträglich geänderte Aufgabe"
    task.business_value = 0
    task.save()
    option.refresh_from_db()
    assert option.source_work_design_snapshot == frozen_snapshot


@pytest.mark.django_db
def test_incomplete_work_design_task_cannot_be_selected_for_solution_design(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Noch offene Aufgabe",
        business_value=4,
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:work_design_task_select_solution_design",
            kwargs={"pk": task.pk},
        )
    )

    assert response.status_code == 302
    assert response.url == reverse(
        "architecture:work_design_assessment_detail",
        kwargs={"pk": assessment.pk},
    )
    assert not SolutionOption.objects.filter(source_work_design_task=task).exists()


@pytest.mark.django_db
def test_taskshift_e2e_selects_task_then_compares_real_solution_options(
    client,
    owner,
    work_design_process,
):
    process = work_design_process
    process.diagnostic_observations = (
        "Vertragsabweichungen erzeugen Rückfragen und verlängern die Angebotsvorbereitung."
    )
    process.confirmed_causes = (
        "Account Manager müssen Vertragsabweichungen heute vollständig an Legal übergeben."
    )
    process.save(update_fields=["diagnostic_observations", "confirmed_causes", "updated_at"])

    assessment = WorkDesignAssessment.objects.create(
        process_analysis=process,
        process_version=process.version,
        role_name="Account Manager",
        business_outcome=process.outcome,
        created_by=owner,
    )
    selected_task = WorkDesignTask.objects.create(
        assessment=assessment,
        sequence=1,
        name="Vertragsabweichungen vorprüfen",
        source_area="Legal",
        target_work_split=(
            "Account Manager bereitet Vertragsabweichungen mit KI vor; "
            "Legal entscheidet und gibt kritische Fälle frei."
        ),
        approval_role="Legal",
        **complete_criteria(
            data_readiness=3,
            judgment_stakes=3,
            specialist_accountability=4,
        ),
    )
    other_task = WorkDesignTask.objects.create(
        assessment=assessment,
        sequence=2,
        name="Kundenmeeting vorbereiten",
        source_area="Sales",
        target_work_split="Account Manager erstellt das Briefing selbst mit KI-Unterstützung.",
        **complete_criteria(),
    )

    client.force_login(owner)
    workspace = client.get(
        reverse(
            "architecture:work_design_assessment_detail",
            kwargs={"pk": assessment.pk},
        )
    )
    workspace_content = workspace.content.decode()
    assert workspace.status_code == 200
    assert selected_task.name in workspace_content
    assert other_task.name in workspace_content
    assert "Für Lösungsdesign auswählen" in workspace_content

    select_url = reverse(
        "architecture:work_design_task_select_solution_design",
        kwargs={"pk": selected_task.pk},
    )
    response = client.get(select_url)
    assert response.status_code == 302
    assert not SolutionOption.objects.filter(source_work_design_task=selected_task).exists()

    create_option_url = reverse(
        "architecture:solution_option_create",
        kwargs={"process_analysis_id": process.pk},
    )
    task_option_url = f"{create_option_url}?work_design_task={selected_task.pk}"

    response = client.post(
        task_option_url,
        solution_option_payload(
            name="KI-Assistent für Vertragsvorprüfung",
            option_type=SolutionOption.OptionType.ASSISTANT,
            evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
            description=(
                "KI analysiert Vertragsabweichungen und erstellt eine prüffähige Vorlage "
                "für Legal; die Freigabe bleibt bei Legal."
            ),
            expected_value=assessment.business_outcome,
            time_to_value=TimeToValue.MEDIUM,
            bottleneck_coverage="Reduziert den vollständigen Handoff an Legal.",
            feasibility=SolutionOption.Effort.MEDIUM,
            data_requirements="Verträge, Kundenakte und Freigaberegeln",
            application_impact="Assistenzfunktion in der bestehenden Arbeitsoberfläche",
            integration_effort=SolutionOption.Effort.MEDIUM,
            integration_impact="CRM- und Dokumentenzugriff",
            technology_constraints="Legal-Freigabe bleibt verpflichtend.",
            risks="Fehlerhafte Vorprüfung darf keine automatische Freigabe auslösen.",
            architecture_fit="Unterstützt die neue Aufgabenteilung mit klarer Freigabegrenze.",
        ),
    )
    assert response.status_code == 302
    assistant_option = SolutionOption.objects.get(
        source_work_design_task=selected_task,
        name="KI-Assistent für Vertragsvorprüfung",
    )

    response = client.post(
        task_option_url,
        solution_option_payload(
            name="Regelbasierte Vertragsvorprüfung",
            option_type=SolutionOption.OptionType.RULE_AUTOMATION,
            evaluation_status=SolutionOption.EvaluationStatus.ASSESSED,
            description=(
                "Deterministische Regeln markieren bekannte Vertragsabweichungen und "
                "erstellen eine strukturierte Prüfliste."
            ),
            expected_value=assessment.business_outcome,
            time_to_value=TimeToValue.SHORT,
            bottleneck_coverage="Reduziert Rückfragen bei bekannten Standardabweichungen.",
            feasibility=SolutionOption.Effort.HIGH,
            data_requirements="Verträge und verbindliche Freigaberegeln",
            application_impact="Regelprüfung in der bestehenden Arbeitsoberfläche",
            integration_effort=SolutionOption.Effort.LOW,
            integration_impact="Dokumentenzugriff",
            technology_constraints="Nur eindeutig kodifizierbare Regeln.",
            risks="Neue oder mehrdeutige Sonderfälle werden nicht erkannt.",
            architecture_fit="Deterministische Alternative für bekannte Abweichungen.",
        ),
    )
    assert response.status_code == 302
    rule_option = SolutionOption.objects.get(
        source_work_design_task=selected_task,
        name="Regelbasierte Vertragsvorprüfung",
    )

    assert assistant_option.source_work_design_snapshot["approval_role"] == "Legal"
    assert rule_option.source_work_design_snapshot["criteria"] == selected_task.criteria

    compare_url = reverse(
        "architecture:solution_option_compare",
        kwargs={"pk": process.pk},
    )
    comparison = client.get(compare_url)
    comparison_content = comparison.content.decode()
    assert comparison.status_code == 200
    assert assistant_option.name in comparison_content
    assert rule_option.name in comparison_content

    response = client.post(
        compare_url,
        {
            "selected_option": assistant_option.pk,
            "rationale": (
                "Die Assistenzoption deckt auch nicht vollständig kodifizierbare "
                "Vertragsabweichungen ab, während die formale Legal-Freigabe erhalten bleibt."
            ),
        },
    )
    assert response.status_code == 302
    assistant_option.refresh_from_db()
    rule_option.refresh_from_db()
    assert assistant_option.recommendation == SolutionOption.Recommendation.PREFERRED
    assert rule_option.recommendation == SolutionOption.Recommendation.REJECTED

    response = client.get(
        reverse(
            "architecture:solution_option_start_use_case",
            kwargs={"pk": assistant_option.pk},
        )
    )
    assert response.status_code == 302
    assert response.url == reverse("use_cases:create")
    stored = client.session[SESSION_KEY]
    assert stored["source_process_analysis_id"] == str(process.pk)
    assert stored["source_solution_option_id"] == str(assistant_option.pk)

    use_case = UseCase.objects.create(
        title=assistant_option.name,
        problem_statement=process.bottlenecks,
        business_unit=process.stage.value_stream.business_unit,
        affected_process=process.name,
        business_owner=owner,
        submitter=owner,
        expected_benefit=assistant_option.expected_value,
    )
    _persist_optional_origin(candidate=use_case, stored=stored)

    origin = UseCaseOrigin.objects.get(use_case=use_case)
    assert origin.process_analysis == process
    assert origin.solution_option == assistant_option
    assert origin.solution_option.source_work_design_snapshot["approval_role"] == "Legal"
    assert origin.solution_option.source_work_design_snapshot["approval_required"] is True
    assert origin.solution_option.source_work_design_snapshot["criteria"] == selected_task.criteria


@pytest.mark.django_db
def test_work_design_empty_state_has_single_task_entry_action(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:work_design_assessment_detail",
            kwargs={"pk": assessment.pk},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Erste Aufgabe bewerten" in content
    assert "Weitere Aufgabe bewerten" not in content
    task_url = reverse(
        "architecture:work_design_task_create",
        kwargs={"assessment_pk": assessment.pk},
    )
    assert content.count(task_url) == 1


@pytest.mark.django_db
def test_work_design_workspace_shows_matrix_and_solution_design_action(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Vertragsabweichungen vorprüfen",
        source_area="Legal",
        target_work_split="Account Manager bereitet vor; Legal entscheidet final.",
        approval_role="Legal",
        **complete_criteria(
            data_readiness=3,
            judgment_stakes=3,
            specialist_accountability=4,
        ),
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:work_design_assessment_detail",
            kwargs={"pk": assessment.pk},
        )
    )
    content = response.content.decode()

    expected_x = int(round(task.potential_score / 5) * 5)
    expected_y = int(round(task.boundary_score / 5) * 5)

    assert response.status_code == 200
    assert 'data-testid="work-design-matrix"' in content
    assert "Übernahmepotenzial" in content
    assert "Verantwortungsgrenze" in content
    assert f"matrix-x-{expected_x}" in content
    assert f"matrix-y-{expected_y}" in content
    assert 'style="left:' not in content
    assert "work-design-task-actions" in content
    assert "Für Lösungsdesign auswählen" in content
    assert (
        reverse(
            "architecture:work_design_task_select_solution_design",
            kwargs={"pk": task.pk},
        )
        in content
    )


@pytest.mark.django_db
def test_work_design_solution_design_gate_is_visible_when_focus_is_not_selected(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    WorkDesignTask.objects.create(
        assessment=assessment,
        name="Kundenmeeting vorbereiten",
        source_area="Sales",
        **complete_criteria(),
    )
    focus = work_design_process.stage.value_stream.focus
    focus.status = ValueStreamFocus.Status.NOT_SELECTED
    focus.save(update_fields=["status", "updated_at"])
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:work_design_assessment_detail",
            kwargs={"pk": assessment.pk},
        )
    )
    content = response.content.decode()

    assert response.status_code == 200
    assert "Für Lösungsdesign auswählen" in content
    assert "Lösungsdesign noch gesperrt" in content
    assert "Fokusentscheidung öffnen" in content
    assert "disabled" in content


@pytest.mark.django_db
def test_task_rating_form_uses_german_labels_and_fails_closed_without_js(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:work_design_task_create",
            kwargs={"assessment_pk": assessment.pk},
        )
    )
    form = response.context["form"]
    content = response.content.decode()

    assert response.status_code == 200
    assert form.fields["business_value"].label == "Geschäftswert"
    assert form.fields["handoff_friction"].label == "Übergabereibung"
    assert form.fields["context_proximity"].label == "Kontextnähe"
    assert form.fields["ai_leverage"].label == "KI-Hebel"
    assert form.fields["data_readiness"].label == "Datenreife"
    assert form.fields["judgment_stakes"].label == "Entscheidungsrisiko"
    assert form.fields["specialist_accountability"].label == "Fachverantwortung"
    assert form.fields["business_value"].widget.attrs["disabled"] == "disabled"
    assert "Nicht bewertet" in content
    assert "Aufgabenbewertung benötigt JavaScript" in content


@pytest.mark.django_db
def test_work_design_assessment_form_uses_mode_specific_submit_labels(
    client,
    owner,
    work_design_process,
):
    client.force_login(owner)
    create_url = reverse(
        "architecture:work_design_assessment_create",
        kwargs={"process_pk": work_design_process.pk},
    )
    create_response = client.get(create_url)
    assert "Rollenbetrachtung anlegen" in create_response.content.decode()

    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    update_response = client.get(
        reverse(
            "architecture:work_design_assessment_update",
            kwargs={"pk": assessment.pk},
        )
    )
    assert "Änderungen speichern" in update_response.content.decode()
    assert "Rollen im Prozess" in update_response.content.decode()
    assert "(nur Kontext)" in update_response.content.decode()


@pytest.mark.django_db
def test_task_sourced_solution_lands_highlighted_with_design_context(
    client,
    owner,
    work_design_process,
):
    assessment = WorkDesignAssessment.objects.create(
        process_analysis=work_design_process,
        process_version=work_design_process.version,
        role_name="Account Manager",
        business_outcome=work_design_process.outcome,
        created_by=owner,
    )
    task = WorkDesignTask.objects.create(
        assessment=assessment,
        name="Kundenmeeting vorbereiten",
        source_area="Sales",
        target_work_split="Account Manager erstellt das Briefing mit KI selbst.",
        **complete_criteria(),
    )
    client.force_login(owner)

    create_url = reverse(
        "architecture:solution_option_create",
        kwargs={"process_analysis_id": work_design_process.pk},
    )
    response = client.post(
        f"{create_url}?work_design_task={task.pk}",
        solution_option_payload(
            name="Beratungsassistent",
            option_type=SolutionOption.OptionType.ASSISTANT,
            description="KI bereitet Beratungskontext und nächste Schritte vor.",
            expected_value=assessment.business_outcome,
        ),
    )
    option = SolutionOption.objects.get(
        source_work_design_task=task,
        name="Beratungsassistent",
    )

    assert response.status_code == 302
    assert response.url.endswith(f"design_task={task.pk}&highlight={option.pk}#loesungsoptionen")

    landing = client.get(
        f"{work_design_process.get_absolute_url()}?design_task={task.pk}&highlight={option.pk}"
    )
    content = landing.content.decode()
    assert landing.status_code == 200
    assert 'data-testid="solution-design-task-context"' in content
    assert 'data-testid="newly-added-solution-option"' in content
    assert "Neue Lösungsoption für eine TASKSHIFT-Aufgabe" in content
    assert f'id="solution-option-{option.pk}"' in content


@pytest.mark.django_db
def test_process_detail_marks_work_design_as_visible_optional_step(
    client,
    owner,
    work_design_process,
):
    client.force_login(owner)

    response = client.get(work_design_process.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert 'data-testid="work-design-entry"' in content
    assert 'data-work-target="arbeitsgestaltung" data-work-state="optional"' in content
    assert "Lösungsoptionen bleiben unabhängig davon nutzbar." in content
    assert [step.key for step in response.context["journey"].steps].count("work_design") == 0

    create_option = client.get(
        reverse(
            "architecture:solution_option_create",
            kwargs={"process_pk": work_design_process.pk},
        )
    )
    assert create_option.status_code == 200
