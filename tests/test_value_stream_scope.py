import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ValueStreamForm
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def form_data(business_unit, owner, **overrides):
    data = {
        "name": "Anfrage bis Abschluss",
        "business_unit": business_unit.pk,
        "owner": owner.pk,
        "status": ValueStream.Status.DRAFT,
        "description": "Kundenanfragen bearbeiten.",
        "trigger": "Anfrage geht ein",
        "outcome": "Anfrage ist abgeschlossen",
        "scope_in": "Annahme, Bearbeitung und Abschluss der Anfrage",
        "scope_out": "Vertragsänderungen und Abrechnung",
        "strategic_objective": "Durchlaufzeit reduzieren",
        "stakeholders": "Kundenservice",
        "constraints": "Bestehendes CRM",
        "business_domain": "other",
        "capability": "",
        "strategic_impact": "",
        "economic_potential": "",
        "pain_intensity": "",
        "data_accessibility": "",
        "change_effort": "",
        "focus_status": "not_screened",
        "focus_rationale": "",
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_scope_in_is_required_and_scope_out_is_optional(business_unit, owner):
    missing_scope = ValueStreamForm(data=form_data(business_unit, owner, scope_in="", scope_out=""))
    optional_exclusion = ValueStreamForm(data=form_data(business_unit, owner, scope_out=""))

    assert missing_scope.is_valid() is False
    assert "scope_in" in missing_scope.errors
    assert optional_exclusion.is_valid(), optional_exclusion.errors


@pytest.mark.django_db
def test_value_stream_detail_displays_scope_and_exclusion_separately(client, business_unit, owner):
    value_stream = ValueStream.objects.create(
        name="Getrennter Scope",
        business_unit=business_unit,
        owner=owner,
        trigger="Start",
        outcome="Ergebnis",
        scope_in="Anfrage bis Entscheidung",
        scope_out="Vertragsabschluss",
    )
    client.force_login(owner)

    response = client.get(value_stream.get_absolute_url())

    content = response.content.decode()
    assert response.status_code == 200
    assert "Im Scope" in content
    assert "Anfrage bis Entscheidung" in content
    assert "Nicht im Scope" in content
    assert "Vertragsabschluss" in content


@pytest.mark.django_db
def test_process_analysis_references_value_stream_scope_without_copying(
    client, business_unit, owner
):
    value_stream = ValueStream.objects.create(
        name="Referenzierter Scope",
        business_unit=business_unit,
        owner=owner,
        trigger="Start",
        outcome="Ergebnis",
        scope_in="Prüfung und Entscheidung",
        scope_out="Operative Ausführung",
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.OTHER,
        capability="Anfragen bearbeiten",
        strategic_impact=ScreeningLevel.MEDIUM,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.MEDIUM,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Für den Deep Dive ausgewählt.",
        updated_by=owner,
    )
    value_stream.status = ValueStream.Status.ACTIVE
    value_stream.save(update_fields=["status", "updated_at"])
    stage = ValueStreamStage.objects.create(value_stream=value_stream, sequence=1, name="Prüfen")
    client.force_login(owner)

    response = client.get(reverse("architecture:process_analysis_create", args=[stage.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert "Quellkontext aus dem Value Stream" in content
    assert "Prüfung und Entscheidung" in content
    assert "Operative Ausführung" in content
    assert not hasattr(stage, "scope_in")
