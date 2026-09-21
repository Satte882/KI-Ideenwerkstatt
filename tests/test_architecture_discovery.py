import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
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
def value_stream(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        description="End-to-End-Wertschöpfung des Einkaufs.",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bezahlte und verbuchte Leistung",
        scope_in="Vom Bedarf bis zur Zahlung",
        strategic_objective="Durchlaufzeit und Transparenz verbessern",
        stakeholders="Einkauf, Fachbereich, Finanzen",
        constraints="Bestehendes ERP bleibt führend",
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
    return stream


@pytest.fixture
def value_stream_stage(value_stream):
    return ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote einholen, vergleichen und Entscheidung vorbereiten.",
        actors="Einkauf und Fachbereich",
        systems="ERP, E-Mail, Dateiablage",
        documents="Angebote und Kriterienkatalog",
        pain_points="Angebote sind uneinheitlich und der Vergleich dauert zu lange.",
        baseline_metrics="Durchlaufzeit heute fünf Tage",
    )


@pytest.mark.django_db
def test_value_stream_is_optional_and_visible_to_authenticated_users(client, reader):
    client.force_login(reader)

    response = client.get(reverse("architecture:value_stream_list"))
    create_response = client.get(reverse("architecture:value_stream_create"))

    assert response.status_code == 200
    assert "Optionaler Discovery-Pfad" in response.content.decode()
    assert create_response.status_code == 403


@pytest.mark.django_db
def test_business_owner_can_create_value_stream(client, owner, business_unit):
    client.force_login(owner)

    response = client.post(
        reverse("architecture:value_stream_create"),
        {
            "name": "Order to Cash",
            "business_unit": business_unit.pk,
            "owner": "",
            "status": ValueStream.Status.DRAFT,
            "description": "Auftrag bis Zahlung",
            "trigger": "Kundenauftrag",
            "outcome": "Zahlungseingang",
            "scope_in": "Von Auftragseingang bis Zahlung",
            "strategic_objective": "Cash Conversion verbessern",
            "stakeholders": "Vertrieb, Operations, Finance",
            "constraints": "ERP bleibt führend",
            "business_domain": BusinessDomain.PROCUREMENT,
            "focus_status": ValueStreamFocus.Status.NOT_SCREENED,
        },
    )

    stream = ValueStream.objects.get(name="Order to Cash")
    assert response.status_code == 302
    assert stream.owner == owner
    assert stream.created_by == owner


@pytest.mark.django_db
def test_stage_can_prefill_existing_intake_without_bypassing_it(
    client,
    owner,
    value_stream_stage,
):
    client.force_login(owner)

    response = client.get(
        reverse("architecture:stage_start_use_case", kwargs={"pk": value_stream_stage.pk})
    )

    assert response.status_code == 302
    assert response.url == reverse("use_cases:create")
    stored = client.session[SESSION_KEY]
    assert stored["business_unit"] == value_stream_stage.value_stream.business_unit_id
    assert stored["affected_process"] == value_stream_stage.name
    assert stored["problem_statement"] == value_stream_stage.pain_points
    assert stored["source_stage_id"] == str(value_stream_stage.pk)


@pytest.mark.django_db
def test_optional_origin_is_persisted_only_for_valid_stage(
    owner,
    business_unit,
    value_stream_stage,
):
    use_case = UseCase.objects.create(
        title="Angebote vergleichbar machen",
        problem_statement="Uneinheitliche Angebote erschweren die Auswahl.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Durchlaufzeit reduzieren",
    )

    _persist_optional_origin(
        candidate=use_case,
        stored={"source_stage_id": str(value_stream_stage.pk)},
    )

    origin = UseCaseOrigin.objects.get(use_case=use_case)
    assert origin.stage == value_stream_stage

    direct_use_case = UseCase.objects.create(
        title="Direkt erfasster Use Case",
        problem_statement="Ein anderer fachlicher Bedarf.",
        business_unit=business_unit,
        affected_process="Direkter Prozess",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Qualität verbessern",
    )
    _persist_optional_origin(candidate=direct_use_case, stored={})
    with pytest.raises(ObjectDoesNotExist):
        _ = direct_use_case.architecture_origin


@pytest.mark.django_db
def test_value_stream_detail_shows_traceable_use_case_origin(
    client,
    owner,
    business_unit,
    value_stream,
    value_stream_stage,
):
    use_case = UseCase.objects.create(
        title="Angebotsvergleich unterstützen",
        problem_statement="Vergleich ist manuell und langsam.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Bearbeitungszeit reduzieren",
    )
    UseCaseOrigin.objects.create(use_case=use_case, stage=value_stream_stage)
    client.force_login(owner)

    response = client.get(value_stream.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "End-to-End-Phasen" in content
    assert use_case.short_id in content
    assert "Use Case direkt aus Phase ableiten" in content


@pytest.mark.django_db
def test_use_case_detail_shows_complete_architecture_origin_chain(
    client,
    owner,
    business_unit,
    value_stream,
    value_stream_stage,
):
    process_analysis = ProcessAnalysis.objects.create(
        stage=value_stream_stage,
        name="Eingangsrechnungsprüfung",
        status=ProcessAnalysis.Status.VALIDATED,
        scope_start="Rechnungseingang",
        scope_end="Buchungsfreigabe",
        trigger="Eingegangene Rechnung",
        outcome="Geprüfte Rechnung",
        current_flow="Manuelle Prüfung",
        roles="Buchhaltung",
        systems="ERP",
        data_objects="Rechnung",
        bottlenecks="Manueller Abgleich",
        baseline_metrics="Elf Minuten je Rechnung",
        analyzed_by=owner,
    )
    solution_option = SolutionOption.objects.create(
        process_analysis=process_analysis,
        name="Regel- und KI-gestützte Rechnungsprüfung",
        option_type=SolutionOption.OptionType.GENERATIVE_AI,
        recommendation=SolutionOption.Recommendation.PREFERRED,
        description="Vorprüfung automatisieren.",
        expected_value="Weniger manuelle Prüfzeit.",
        feasibility="high",
        created_by=owner,
    )
    use_case = UseCase.objects.create(
        title="Automatische Rechnungspruefung",
        problem_statement="Rechnungen werden manuell geprüft.",
        business_unit=business_unit,
        affected_process="Eingangsrechnungsverarbeitung",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Schnellere Vorprüfung.",
    )
    UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=value_stream_stage,
        process_analysis=process_analysis,
        solution_option=solution_option,
    )
    client.force_login(owner)

    response = client.get(use_case.get_absolute_url())

    assert response.status_code == 200
    content = response.content.decode()
    assert "Herkunft aus Discovery" in content
    assert value_stream.name in content
    assert value_stream_stage.name in content
    assert process_analysis.name in content
    assert solution_option.name in content
    assert use_case.title in content


@pytest.mark.django_db
def test_process_analysis_stores_field_level_source_snapshot(client, owner, value_stream_stage):
    client.force_login(owner)
    response = client.post(
        reverse("architecture:process_analysis_create", args=[value_stream_stage.pk]),
        {
            "name": value_stream_stage.name,
            "status": ProcessAnalysis.Status.DRAFT,
            "scope_start": "Angebote liegen vor",
            "scope_end": "Entscheidung ist dokumentiert",
            "trigger": value_stream_stage.value_stream.trigger,
            "outcome": value_stream_stage.description,
            "current_flow": "Angebote werden manuell verglichen.",
            "roles": value_stream_stage.actors,
            "systems": value_stream_stage.systems,
            "data_objects": value_stream_stage.documents,
            "business_rules": "",
            "handoffs": "",
            "bottlenecks": value_stream_stage.pain_points,
            "exceptions": "",
            "baseline_metrics": value_stream_stage.baseline_metrics,
            "target_state_principles": "",
        },
    )

    process = ProcessAnalysis.objects.get(stage=value_stream_stage)
    assert response.status_code == 302
    assert process.source_snapshot["roles"]["label"] == "Value-Stream-Phase"
    assert process.source_snapshot["roles"]["value"] == value_stream_stage.actors

    value_stream_stage.actors = "Einkauf, Fachbereich und Controlling"
    value_stream_stage.save(update_fields=["actors", "updated_at"])
    detail = client.get(process.get_absolute_url()).content.decode()

    assert "Quellenänderungen" in detail
    assert "Einkauf, Fachbereich und Controlling" in detail


@pytest.mark.django_db
def test_use_case_origin_stores_snapshot_and_shows_later_source_diff(
    client,
    owner,
    business_unit,
    value_stream_stage,
):
    use_case = UseCase.objects.create(
        title=value_stream_stage.name,
        problem_statement=value_stream_stage.pain_points,
        business_unit=business_unit,
        affected_process=value_stream_stage.name,
        business_owner=owner,
        submitter=owner,
        expected_benefit="Auswahl beschleunigen",
    )
    _persist_optional_origin(
        candidate=use_case,
        stored={"source_stage_id": str(value_stream_stage.pk)},
    )
    origin = UseCaseOrigin.objects.get(use_case=use_case)
    assert origin.source_snapshot["affected_process"]["value"] == value_stream_stage.name

    value_stream_stage.name = "Lieferantenentscheidung"
    value_stream_stage.save(update_fields=["name", "updated_at"])
    client.force_login(owner)
    content = client.get(use_case.get_absolute_url()).content.decode()

    assert "Quellenänderungen seit der Übernahme" in content
    assert "Lieferantenentscheidung" in content
