import json
from types import SimpleNamespace

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
from ki_radar.architecture.process_decision_presentation import suggested_confirmed_cause
from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.ap2_decision_governance import GOVERNANCE_FIELDS
from ki_radar.use_cases.ap2_metric_pilot import AP2MetricPilotError
from ki_radar.use_cases.models import UseCase


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
def test_suggested_cause_falls_back_through_reviewed_evidence(owner, business_unit):
    process = make_process(owner, business_unit)
    process.confirmed_causes = ""
    process.save(update_fields=["confirmed_causes", "updated_at"])
    materialization = SimpleNamespace(
        brief_revision=SimpleNamespace(
            payload={
                "hypotheses": [
                    {
                        "status": "supported",
                        "statement": "Freitext erzeugt vermeidbaren manuellen Leseaufwand.",
                    }
                ]
            }
        ),
        run=SimpleNamespace(
            claim_register=[
                {
                    "area": "recommendation",
                    "claim_kind": "hypothesis",
                    "status": "supported",
                    "statement": "Dieser Claim gehört nicht zur Ursachenbestätigung.",
                }
            ]
        ),
    )

    assert (
        suggested_confirmed_cause(
            process_analysis=process,
            latest_materialization=materialization,
        )
        == "Freitext erzeugt vermeidbaren manuellen Leseaufwand."
    )

    materialization.brief_revision.payload = {"hypotheses": []}
    assert (
        suggested_confirmed_cause(
            process_analysis=process,
            latest_materialization=materialization,
        )
        == process.cause_hypotheses
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
            "process_version": process.version,
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
    use_case = UseCase.objects.get()

    content = client.get(url).content.decode()
    assert "Aktuell bevorzugt: KI-Assistenz" in content
    assert "Die Entscheidung ist in der Auswahlhistorie auditierbar." in content
    assert use_case.short_id in content
    assert "direkt aus der bestätigten Lösungsentscheidung erzeugt" in content
    selected_value = client.get(url).context["form"]["selected_option"].value()
    assert str(selected_value) == str(assistant.pk)


@pytest.mark.django_db
def test_failed_metric_draft_can_resume_without_second_solution_decision(
    client,
    owner,
    business_unit,
    monkeypatch,
):
    process = make_process(owner, business_unit)
    make_option(
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
    attempts = 0

    def draft(*, use_case, actor):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise AP2MetricPilotError("Provider vorübergehend nicht verfügbar.", code="provider")
        use_case.ap2_planning_provenance = {"generated_by": "system"}
        use_case.save(update_fields=["ap2_planning_provenance", "updated_at"])
        return SimpleNamespace(changed_fields=("metric_name",))

    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_and_apply_ap2_metric_pilot",
        draft,
    )
    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_ap2_architecture_inputs",
        lambda **_kwargs: None,
    )

    def governance_draft(*, use_case, actor):
        use_case.ap2_governance_draft = {"generated_by": "system", "facts": {}}
        use_case.save(update_fields=["ap2_governance_draft", "updated_at"])

    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_ap2_decision_governance",
        governance_draft,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    first = client.post(
        url,
        {
            "process_version": process.version,
            "selected_option": assistant.pk,
            "rationale": "Die Assistenz deckt den Engpass ab.",
        },
    )
    assert first.status_code == 302
    use_case = UseCase.objects.get()
    assert use_case.ap2_planning_provenance == {}
    assert process.solution_selection_decisions.count() == 1
    assert "Mit AI-Entscheidungsgrundlage fortfahren" in client.get(url).content.decode()

    retry = client.post(url, {"continue_ai_handoff": "1"})
    assert retry.status_code == 302
    use_case.refresh_from_db()
    assert use_case.ap2_planning_provenance["generated_by"] == "system"
    assert process.solution_selection_decisions.count() == 1
    assert UseCase.objects.count() == 1
    assert attempts == 2
    assert "Mit AI-Entscheidungsgrundlage fortfahren" in client.get(url).content.decode()


@pytest.mark.django_db
def test_selected_ai_solution_continues_to_architecture_assessment_and_decision_surface(
    client, owner, business_unit, monkeypatch
):
    process = make_process(owner, business_unit)
    make_option(
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

    def metric_draft(*, use_case, actor):
        use_case.ap2_planning_provenance = {"generated_by": "system"}
        use_case.save(update_fields=["ap2_planning_provenance", "updated_at"])
        return SimpleNamespace(changed_fields=())

    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_and_apply_ap2_metric_pilot",
        metric_draft,
    )
    architecture_answers = {
        name: {
            "value": value,
            "source_ids": ["SO.description"],
            "rationale": "Aus dem Lösungsfall abgeleitet.",
        }
        for name, value in {
            "simpler_solution_sufficient": "no",
            "semantic_reasoning_required": "yes",
            "multiple_known_ai_steps_required": "no",
            "dynamic_orchestration_required": "no",
        }.items()
    }
    monkeypatch.setattr(
        "ki_radar.architecture.ap2_architecture.request_llm_task_provider",
        lambda _prepared, **_kwargs: SimpleNamespace(content=json.dumps(architecture_answers)),
    )
    assessment_values = {
        "business_value": "medium",
        "strategic_fit": "medium",
        "technical_feasibility": "medium",
        "data_readiness": "medium",
        "risk_complexity": "medium",
        "evidence_recency": "limited",
        "evidence_coverage": "limited",
        "independent_review": "critical",
        "assumptions_resolved": "limited",
        "recommendation": "deferred",
        "rationale": "present",
    }
    decision_payload = {
        "assessment": {
            name: {
                "value": value,
                "source_ids": ["UC.problem"],
                "rationale": "Konservative Analyse des Falles.",
            }
            for name, value in assessment_values.items()
        },
        "governance": {
            name: {
                "value": "unknown",
                "source_ids": ["UC.problem"],
                "rationale": "Nicht sicher belegt.",
                "evidence_quote": "",
            }
            for name in GOVERNANCE_FIELDS
        },
    }
    monkeypatch.setattr(
        "ki_radar.use_cases.ap2_decision_governance.request_llm_task_provider",
        lambda _prepared, **_kwargs: SimpleNamespace(content=json.dumps(decision_payload)),
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    selected = client.post(
        url,
        {
            "process_version": process.version,
            "selected_option": assistant.pk,
            "rationale": "Die Assistenz deckt den Engpass besser ab.",
        },
    )
    assert selected.status_code == 302
    continued = client.post(url, {"continue_ai_handoff": "1"})
    assert continued.status_code == 302
    use_case = UseCase.objects.get()
    assert assistant.architecture_assessment.architecture_mode == "controlled_llm"
    assert use_case.decision_assessments.count() == 1
    assert use_case.ap2_governance_draft["generated_by"] == "system"
    surface = client.get(reverse("use_cases:ap2_decision_surface", args=[use_case.pk]))
    assert surface.status_code == 200
    content = surface.content.decode()
    assert "Controlled LLM" in content
    assert "Systemgenerierte Analyse" in content
    assert "Governance-Entwurf vorhanden" in content


@pytest.mark.django_db
def test_missing_confirmed_cause_is_reviewed_in_same_solution_selection_submit(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    process.confirmed_causes = ""
    process.status = ProcessAnalysis.Status.REVIEW_REQUIRED
    process.save(update_fields=["confirmed_causes", "status", "updated_at"])
    reviewed_version = process.version
    organizational = make_option(
        process,
        owner,
        name="Organisation",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        assessed=True,
    )
    assistant = make_option(
        process,
        owner,
        name="Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
        assessed=True,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])

    response = client.get(url)
    content = response.content.decode()

    assert response.status_code == 200
    assert response.context["selection_blocked"] is False
    assert response.context["diagnosis_confirmation_required"] is True
    assert 'data-testid="combined-diagnosis-selection"' in content
    assert "Kernbefund fachlich bestätigen" in content
    assert "Diagnose bestätigen und bevorzugte Option auswählen" in content
    assert "data-submit-guard" in content
    assert reverse("architecture:process_analysis_update", args=[process.pk]) not in content

    invalid = client.post(
        url,
        {
            "process_version": reviewed_version,
            "selected_option": assistant.pk,
            "rationale": "Die Assistenz adressiert die verbleibende Extraktionsarbeit.",
        },
    )
    invalid_content = invalid.content.decode()
    assert invalid.status_code == 200
    assert "data-selection-error-summary" in invalid_content
    assert "Eingabe noch nicht gespeichert" in invalid_content
    assert "Kernbefund bestätigen oder korrigieren" in invalid_content
    assert not process.solution_selection_decisions.exists()

    response = client.post(
        url,
        {
            "process_version": reviewed_version,
            "confirmed_causes": (
                "Manuelle Übertragung entsteht durch unstrukturierte Eingangsdaten."
            ),
            "selected_option": assistant.pk,
            "rationale": "Die Assistenz adressiert die verbleibende Extraktionsarbeit.",
        },
    )

    assert response.status_code == 302
    process.refresh_from_db()
    organizational.refresh_from_db()
    assistant.refresh_from_db()
    assert process.confirmed_causes == (
        "Manuelle Übertragung entsteht durch unstrukturierte Eingangsdaten."
    )
    assert process.version == reviewed_version + 1
    assert process.validations.filter(process_version=process.version).exists()
    assert organizational.recommendation == SolutionOption.Recommendation.REJECTED
    assert assistant.recommendation == SolutionOption.Recommendation.PREFERRED
    selected_content = client.get(url).content.decode()
    assert "Mit AI-Entscheidungsgrundlage fortfahren" in selected_content
    assert "Bestehende Auswahl ändern" in selected_content
    assert "Geänderte Auswahl verbindlich speichern" in selected_content


@pytest.mark.django_db
def test_non_ai_preferred_selection_is_visible_end_state_without_use_case(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    organizational = make_option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        assessed=True,
    )
    make_option(
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
            "process_version": process.version,
            "selected_option": organizational.pk,
            "rationale": "Die organisatorische Lösung reicht fachlich aus.",
        },
    )

    assert response.status_code == 302
    assert not UseCase.objects.exists()
    content = client.get(url).content.decode()
    assert "gültiger Non-AI-Endzustand" in content
    assert "kein KI-Use-Case erzeugt" in content


@pytest.mark.django_db
def test_selection_rejects_stale_process_after_page_was_opened(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    organizational = make_option(
        process,
        owner,
        name="Vorlage standardisieren",
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        assessed=True,
    )
    make_option(
        process,
        owner,
        name="KI-Assistenz",
        option_type=SolutionOption.OptionType.ASSISTANT,
        assessed=True,
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    response = client.get(url)
    reviewed_version = response.context["form"]["process_version"].value()
    assert 'name="process_version"' in response.content.decode()

    ProcessAnalysis.objects.filter(pk=process.pk).update(
        version=process.version + 1,
        diagnostic_observations="Der fachliche Befund wurde inzwischen korrigiert.",
    )
    response = client.post(
        url,
        {
            "process_version": reviewed_version,
            "selected_option": organizational.pk,
            "rationale": "Die organisatorische Änderung deckt den Engpass ab.",
        },
    )

    assert response.status_code == 200
    assert not process.solution_selection_decisions.exists()
    organizational.refresh_from_db()
    assert organizational.recommendation == SolutionOption.Recommendation.CANDIDATE

    missing_version = client.post(
        url,
        {
            "selected_option": organizational.pk,
            "rationale": "Die organisatorische Änderung deckt den Engpass ab.",
        },
    )
    assert missing_version.status_code == 200
    assert not process.solution_selection_decisions.exists()


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
