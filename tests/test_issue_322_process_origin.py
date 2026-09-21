import pytest
from django.core.exceptions import FieldDoesNotExist, ValidationError
from django.db.models.deletion import ProtectedError
from django.urls import reverse

from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel
from ki_radar.use_cases.classification import UseCaseClassification
from ki_radar.use_cases.intake import ProcessStepForm
from ki_radar.use_cases.intake_views import SESSION_KEY, _persist_optional_origin
from ki_radar.use_cases.models import UseCase


def make_value_stream(*, business_unit, owner, name="Beschaffung bis Zahlung"):
    stream = ValueStream.objects.create(
        name=name,
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
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Source-to-Pay",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.HIGH,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Hoher fachlicher Hebel und belastbare Baseline.",
        updated_by=owner,
    )
    return stream


def make_process(*, stream, owner, name="Angebote vergleichbar machen", sequence=1):
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=sequence,
        name=f"Phase {sequence}",
        description="Angebote vergleichen und Entscheidung vorbereiten.",
        actors="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        documents="Angebote und Kriterienkatalog",
        pain_points="Der Vergleich dauert zu lange.",
        baseline_metrics="Fünf Tage Durchlaufzeit",
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name=name,
        scope_start="Angebote liegen vor",
        scope_end="Entscheidung ist dokumentiert",
        trigger="Angebote eingegangen",
        outcome="Vergleichbare Entscheidungsgrundlage",
        current_flow="Angebote werden manuell verglichen.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote",
        bottlenecks="Manueller Abgleich",
        baseline_metrics="Fünf Tage Durchlaufzeit",
        analyzed_by=owner,
    )
    return stage, process


def make_use_case(*, business_unit, owner, affected_process):
    return UseCase.objects.create(
        title="Angebotsvergleich unterstützen",
        problem_statement="Uneinheitliche Angebote erschweren eine schnelle Auswahl.",
        business_unit=business_unit,
        affected_process=affected_process,
        business_owner=owner,
        submitter=owner,
        expected_benefit="Durchlaufzeit reduzieren",
    )


def process_step_data(*, process_analysis="", affected_process="Direkter Prozess"):
    return {
        "process_analysis": process_analysis,
        "business_domain": BusinessDomain.PROCUREMENT,
        "business_capability": "Source-to-Pay",
        "affected_process": affected_process,
        "summary": "Angebote werden heute manuell verglichen.",
        "target_users": "Einkauf und Fachbereich",
        "source_systems": "ERP und Dateiablage",
    }


@pytest.mark.django_db
def test_direct_process_selection_is_filtered_by_business_unit_and_derives_process_name(
    owner,
    business_unit,
):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    _, process = make_process(stream=stream, owner=owner)
    other_business_unit = BusinessUnit.objects.create(name="Organisationseinheit B")
    other_stream = make_value_stream(
        business_unit=other_business_unit,
        owner=owner,
        name="Order to Cash",
    )
    _, other_process = make_process(
        stream=other_stream,
        owner=owner,
        name="Kundenauftrag bearbeiten",
    )

    valid_form = ProcessStepForm(
        data=process_step_data(process_analysis=str(process.pk), affected_process=""),
        business_unit=business_unit,
    )
    invalid_form = ProcessStepForm(
        data=process_step_data(process_analysis=str(other_process.pk), affected_process=""),
        business_unit=business_unit,
    )

    assert valid_form.is_valid(), valid_form.errors
    assert valid_form.cleaned_data["affected_process"] == process.name
    assert not invalid_form.is_valid()
    assert "process_analysis" in invalid_form.errors


@pytest.mark.django_db
def test_discovery_process_is_locked_and_cannot_be_overwritten_in_process_step(
    owner,
    business_unit,
):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    stage, process = make_process(stream=stream, owner=owner)
    other_process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Alternativer Prozess",
        scope_start="Start",
        scope_end="Ende",
        trigger="Trigger",
        outcome="Outcome",
        current_flow="Anderer Ablauf",
        roles="Einkauf",
        systems="ERP",
        data_objects="Daten",
        bottlenecks="Engpass",
        baseline_metrics="Baseline",
        analyzed_by=owner,
    )

    form = ProcessStepForm(
        data=process_step_data(process_analysis=str(other_process.pk), affected_process=""),
        business_unit=business_unit,
        source_stage_id=str(stage.pk),
        source_process_analysis_id=str(process.pk),
    )

    assert form.is_valid(), form.errors
    assert form.fields["process_analysis"].disabled
    assert form.cleaned_data["process_analysis"] == process
    assert form.cleaned_data["affected_process"] == process.name


@pytest.mark.django_db
def test_direct_intake_persists_process_origin_end_to_end(client, owner, business_unit):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    _, process = make_process(stream=stream, owner=owner)
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:create"),
        {
            "title": "Angebotsvergleich beschleunigen",
            "business_unit": business_unit.pk,
            "business_owner": owner.pk,
            "problem_statement": (
                "Mitarbeitende benötigen heute deutlich zu viel Zeit für den manuellen "
                "Vergleich eingehender Lieferantenangebote."
            ),
        },
    )
    assert response.status_code == 302

    response = client.post(
        reverse("use_cases:intake_step", args=[2]),
        process_step_data(process_analysis=str(process.pk), affected_process=""),
    )
    assert response.status_code == 302
    stored = client.session[SESSION_KEY]
    assert stored["process_analysis"] == str(process.pk)
    assert stored["affected_process"] == process.name

    client.post(
        reverse("use_cases:intake_step", args=[3]),
        {
            "intended_users": "Einkauf und Fachbereich",
            "intended_purpose": "Angebote strukturiert vergleichen und Abweichungen hervorheben",
        },
    )
    client.post(
        reverse("use_cases:intake_step", args=[4]),
        {
            "expected_benefit": "Durchlaufzeit des Angebotsvergleichs reduzieren",
            "metric_name": "Bearbeitungszeit je Vergleich",
            "metric_type": UseCase.MetricType.DURATION,
            "metric_direction": UseCase.MetricDirection.LOWER,
            "metric_unit": "Minuten",
            "metric_baseline": "60",
            "metric_target": "30",
            "metric_measurement_method": "Vierwöchige Stichprobe über alle Vergleiche",
        },
    )
    client.post(
        reverse("use_cases:intake_step", args=[5]),
        {
            "data_sources": "Angebote und Kriterienkatalog",
            "solution_type": UseCase.SolutionType.ASSISTANT,
            "hosting_type": UseCase.HostingType.INTERNAL,
        },
    )
    response = client.post(reverse("use_cases:intake_step", args=[6]))

    use_case = UseCase.objects.get(title="Angebotsvergleich beschleunigen")
    origin = UseCaseOrigin.objects.get(use_case=use_case)
    use_case.refresh_from_db()

    assert response.status_code == 302
    assert use_case.affected_process == process.name
    assert origin.process_analysis == process
    assert origin.stage == process.stage
    assert origin.stage.value_stream == stream
    assert origin.source_snapshot["affected_process"]["value"] == process.name
    assert use_case.classification.business_domain == BusinessDomain.PROCUREMENT
    assert use_case.classification.capability == "Source-to-Pay"
    assert use_case.classification.process_area == process.name


@pytest.mark.django_db
def test_discovery_origin_has_precedence_over_manual_session_value(owner, business_unit):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    stage, process = make_process(stream=stream, owner=owner)
    other_process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Anderer Prozess",
        scope_start="Start",
        scope_end="Ende",
        trigger="Trigger",
        outcome="Outcome",
        current_flow="Anderer Ablauf",
        roles="Einkauf",
        systems="ERP",
        data_objects="Daten",
        bottlenecks="Engpass",
        baseline_metrics="Baseline",
        analyzed_by=owner,
    )
    use_case = make_use_case(
        business_unit=business_unit,
        owner=owner,
        affected_process=process.name,
    )

    _persist_optional_origin(
        candidate=use_case,
        stored={
            "source_stage_id": str(stage.pk),
            "source_process_analysis_id": str(process.pk),
            "process_analysis": str(other_process.pk),
        },
    )

    assert use_case.architecture_origin.process_analysis == process


@pytest.mark.django_db
def test_origin_rejects_business_unit_changed_after_process_selection(owner, business_unit):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    _, process = make_process(stream=stream, owner=owner)
    other_business_unit = BusinessUnit.objects.create(name="Organisationseinheit B")
    use_case = make_use_case(
        business_unit=other_business_unit,
        owner=owner,
        affected_process=process.name,
    )

    with pytest.raises(ValidationError, match="Organisationseinheit"):
        _persist_optional_origin(
            candidate=use_case,
            stored={"process_analysis": str(process.pk)},
        )

    assert not UseCaseOrigin.objects.filter(use_case=use_case).exists()


@pytest.mark.django_db
def test_origin_derives_strategy_in_detail_without_redundant_use_case_fields(
    client,
    owner,
    business_unit,
):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    _, process = make_process(stream=stream, owner=owner)
    use_case = make_use_case(
        business_unit=business_unit,
        owner=owner,
        affected_process=process.name,
    )
    _persist_optional_origin(
        candidate=use_case,
        stored={"process_analysis": str(process.pk)},
    )
    client.force_login(owner)

    response = client.get(use_case.get_absolute_url())
    content = response.content.decode()

    assert response.status_code == 200
    assert "Ursprung & strategischer Kontext" in content
    assert stream.strategic_objective in content
    assert "Einkauf" in content
    assert "Source-to-Pay" in content
    assert "Hoch" in content
    with pytest.raises(FieldDoesNotExist):
        UseCase._meta.get_field("process_analysis")
    with pytest.raises(FieldDoesNotExist):
        UseCase._meta.get_field("strategic_objective")


@pytest.mark.django_db
def test_origin_protects_linked_process_from_deletion(owner, business_unit):
    stream = make_value_stream(business_unit=business_unit, owner=owner)
    _, process = make_process(stream=stream, owner=owner)
    use_case = make_use_case(
        business_unit=business_unit,
        owner=owner,
        affected_process=process.name,
    )
    _persist_optional_origin(
        candidate=use_case,
        stored={"process_analysis": str(process.pk)},
    )

    with pytest.raises(ProtectedError):
        process.delete()

    assert UseCaseClassification.objects.filter(use_case=use_case).exists()
