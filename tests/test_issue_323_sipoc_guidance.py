import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ProcessAnalysisForm
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


@pytest.fixture
def sipoc_stage(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffungsbedarf bis Bestellung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Beschaffungsbedarf",
        outcome="Bestellung wurde ausgelöst",
        scope_in="Bedarf konkretisieren bis Bestellung",
        scope_out="Wareneingang, Rechnungsprüfung und Zahlung",
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
        rationale="Lieferantenauswahl für den Deep Dive ausgewählt.",
        updated_by=owner,
    )
    return ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote vergleichen und Lieferantenentscheidung vorbereiten.",
        actors="Einkauf und Fachbereich",
        systems="ERP, E-Mail und Dateiablage",
        documents="Angebote und Kriterienkatalog",
        pain_points="Uneinheitliche Angebote verursachen Rückfragen.",
        baseline_metrics="Fünf Tage Durchlaufzeit",
    )


@pytest.mark.django_db
def test_process_analysis_form_shows_sipoc_guidance(client, owner, sipoc_stage):
    client.force_login(owner)

    response = client.get(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": sipoc_stage.pk})
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert 'data-testid="sipoc-guidance"' in content
    assert "SIPOC" in content
    assert "Prozesskontext prüfen" in content
    assert "Supplier → Input → Process → Output → Customer" in content
    assert "Welche fachlichen Inputs, Daten oder Dokumente gelangen in den Prozess?" in content
    assert "Welches fachliche Ergebnis verlässt den Prozess?" in content
    assert "Von wem bzw. aus welcher Quelle kommen relevante Inputs" in content
    assert "wer übernimmt, verwendet oder erhält das Prozessergebnis?" in content
    assert "Es entsteht kein separates SIPOC-Artefakt." in content


def test_sipoc_guidance_reuses_existing_process_analysis_fields():
    form = ProcessAnalysisForm()

    assert form.fields["data_objects"].required is True
    assert form.fields["outcome"].required is True
    assert form.fields["handoffs"].required is False
    assert {"supplier", "input", "output", "customer"}.isdisjoint(form.fields)
