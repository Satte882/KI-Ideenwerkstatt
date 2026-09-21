import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ProcessAnalysisForm
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Validierbarer Wertstrom",
        business_unit=business_unit,
        owner=owner,
        trigger="Start",
        outcome="Ergebnis",
        scope_in="Prüfung",
        status=ValueStream.Status.ACTIVE,
    )
    ValueStreamFocus.objects.create(
        value_stream=stream,
        business_domain=BusinessDomain.OTHER,
        capability="Anfragen prüfen",
        strategic_impact=ScreeningLevel.MEDIUM,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.MEDIUM,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Deep Dive ausgewählt.",
        updated_by=owner,
    )
    stage = ValueStreamStage.objects.create(value_stream=stream, sequence=1, name="Prüfen")
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Ist-Prozess prüfen",
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Anfrage liegt vor",
        scope_end="Entscheidung ist dokumentiert",
        trigger="Neue Anfrage",
        outcome="Nachvollziehbare Entscheidung",
        current_flow="Anfrage lesen und manuell prüfen",
        roles="Fachbereich prüft",
        systems="Fachanwendung",
        data_objects="Anfrage und Stammdaten",
        business_rules="Vier-Augen-Prinzip bei Sonderfällen",
        handoffs="Übergabe an Freigabe",
        bottlenecks="Manuelle Suche",
        exceptions="Unvollständige Anfrage",
        baseline_metrics="20 Minuten je Anfrage",
        analyzed_by=owner,
    )


def process_form_data(process, **overrides):
    data = {
        "name": process.name,
        "status": process.status,
        "scope_start": process.scope_start,
        "scope_end": process.scope_end,
        "trigger": process.trigger,
        "outcome": process.outcome,
        "current_flow": process.current_flow,
        "roles": process.roles,
        "systems": process.systems,
        "data_objects": process.data_objects,
        "business_rules": process.business_rules,
        "handoffs": process.handoffs,
        "bottlenecks": process.bottlenecks,
        "exceptions": process.exceptions,
        "baseline_metrics": process.baseline_metrics,
        "target_state_principles": process.target_state_principles,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_validated_status_cannot_be_set_in_general_process_form(owner, business_unit):
    process = make_process(owner, business_unit)
    form = ProcessAnalysisForm(
        data=process_form_data(process, status=ProcessAnalysis.Status.VALIDATED),
        instance=process,
    )

    assert form.is_valid() is False
    assert "eigenständige Validierungsaktion" in form.errors["status"][0]


@pytest.mark.django_db
def test_dedicated_validation_records_person_role_version_and_optional_evidence(
    client, owner, business_unit
):
    process = make_process(owner, business_unit)
    client.force_login(owner)

    response = client.post(
        reverse("architecture:process_analysis_validate", args=[process.pk]),
        {
            "note": "Ist-Ablauf im Fachworkshop bestätigt.",
            "evidence_url": "https://example.com/process-workshop",
        },
    )

    assert response.status_code == 302
    process.refresh_from_db()
    validation = ProcessValidation.objects.get(process_analysis=process)
    assert process.status == ProcessAnalysis.Status.VALIDATED
    assert validation.process_version == 1
    assert validation.validated_by == owner
    assert validation.validator_role == "Business Owner"
    assert validation.note == "Ist-Ablauf im Fachworkshop bestätigt."
    assert validation.validated_at is not None


@pytest.mark.django_db
def test_essential_change_creates_new_version_and_requires_revalidation(
    client, owner, business_unit
):
    process = make_process(owner, business_unit)
    ProcessValidation.objects.create(
        process_analysis=process,
        process_version=1,
        validated_by=owner,
        validator_role="Business Owner",
    )
    process.status = ProcessAnalysis.Status.VALIDATED
    process.save(update_fields=["status", "updated_at"])
    client.force_login(owner)

    response = client.post(
        reverse("architecture:process_analysis_update", args=[process.pk]),
        process_form_data(process, current_flow="Geänderter Ist-Ablauf mit zusätzlicher Prüfung"),
    )

    assert response.status_code == 302
    process.refresh_from_db()
    assert process.version == 2
    assert process.status == ProcessAnalysis.Status.REVIEW_REQUIRED
    assert process.validations.count() == 1
    assert process.validations.get().process_version == 1


@pytest.mark.django_db
def test_nonessential_status_change_does_not_invalidate_process_version(
    client, owner, business_unit
):
    process = make_process(owner, business_unit)
    client.force_login(owner)

    response = client.post(
        reverse("architecture:process_analysis_update", args=[process.pk]),
        process_form_data(process, status=ProcessAnalysis.Status.TARGET_DEFINED),
    )

    assert response.status_code == 302
    process.refresh_from_db()
    assert process.version == 1
    assert process.status == ProcessAnalysis.Status.TARGET_DEFINED


@pytest.mark.django_db
def test_detail_displays_current_and_historical_validation_data(client, owner, business_unit):
    process = make_process(owner, business_unit)
    ProcessValidation.objects.create(
        process_analysis=process,
        process_version=1,
        validated_by=owner,
        validator_role="Business Owner",
        note="Workshop bestätigt.",
        evidence_url="https://example.com/evidence",
    )
    process.status = ProcessAnalysis.Status.VALIDATED
    process.save(update_fields=["status", "updated_at"])
    client.force_login(owner)

    response = client.get(process.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Validierung des Ist-Prozesses" in content
    assert "Geprüfte Version" in content
    assert "Business Owner" in content
    assert "Workshop bestätigt." in content
    assert "Validierungsnachweis öffnen" in content
