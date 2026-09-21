import pytest
from django.urls import reverse

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.forms import CaptureSectionForm
from ki_radar.accelerator.methodology_views import (
    METHODOLOGY_DOWNLOAD_NAME,
    METHODOLOGY_PATH,
)
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_capture_session
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.forms import ValueStreamStageForm
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_selected_stream(*, owner, business_unit):
    value_stream = ValueStream.objects.create(
        name="Beschaffungsbedarf bis Bestellung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bestätigter Bedarf liegt vor.",
        outcome="Freigegebene Bestellung wurde ausgelöst.",
        scope_in="Bedarf bis Bestellung.",
        scope_out="Wareneingang und Zahlung.",
        status=ValueStream.Status.ACTIVE,
        created_by=owner,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Beschaffung steuern",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Relevanter Wertstrom mit nachvollziehbarem Transformationsbedarf.",
        updated_by=owner,
    )
    return value_stream


@pytest.mark.django_db
def test_value_stream_capture_exposes_methodology_help_but_use_case_capture_does_not(
    client,
    owner,
):
    client.force_login(owner)

    value_stream_response = client.get(reverse("accelerator:value_stream_start"))
    value_stream_body = value_stream_response.content.decode()
    use_case_response = client.get(reverse("accelerator:use_case_start"))
    use_case_body = use_case_response.content.decode()

    assert value_stream_response.status_code == 200
    assert "value-stream-methodology-modal" in value_stream_body
    assert "Methodik &amp; Beispiel" in value_stream_body
    assert "Capability" in value_stream_body
    assert "Trigger" in value_stream_body
    assert "Scope-In" in value_stream_body
    assert "Business Importance \u00d7 Transformation Need" in value_stream_body
    assert "Wertfortschritt" in value_stream_body
    assert "Methodik herunterladen" in value_stream_body

    assert use_case_response.status_code == 200
    assert "value-stream-methodology-modal" not in use_case_body
    assert "Methodik &amp; Beispiel" not in use_case_body


@pytest.mark.django_db
def test_value_stream_wizard_keeps_methodology_help_available(client, owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung",
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "accelerator:capture_step",
            kwargs={"session_id": session.pk, "step": 1},
        )
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert "value-stream-methodology-modal" in body
    assert "Methodik &amp; Beispiel" in body
    assert "Entwurf prüfen" in body


@pytest.mark.django_db
def test_methodology_download_serves_canonical_repository_markdown(client, owner):
    client.force_login(owner)

    response = client.get(reverse("accelerator:value_stream_methodology_download"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/markdown")
    assert METHODOLOGY_DOWNLOAD_NAME in response["Content-Disposition"]
    assert response.content.decode() == METHODOLOGY_PATH.read_text(encoding="utf-8")
    assert "**Version:** 1.2" in response.content.decode()


@pytest.mark.django_db
def test_methodology_download_requires_login(client):
    response = client.get(reverse("accelerator:value_stream_methodology_download"))

    assert response.status_code == 302
    assert "/login/" in response.url


def test_guided_stage_capture_explains_value_progress_without_new_capture_fields():
    catalog = get_capture_catalog(CaptureSession.CaptureType.VALUE_STREAM)
    stage_section = next(section for section in catalog.sections if section.key == "stages")
    form = CaptureSectionForm(section=stage_section)

    assert "Wertfortschritt" in form.fields["vs_stages"].help_text
    assert "Was liegt vorher vor" in form.fields["vs_stages"].help_text
    assert "welcher relevante Zustand" in form.fields["vs_stages"].help_text
    assert "entrance" not in form.fields
    assert "transformation" not in form.fields
    assert "value_item" not in form.fields
    assert "exit" not in form.fields


def test_existing_screening_level_semantics_remain_unchanged():
    assert list(ScreeningLevel.choices) == [
        ("low", "Niedrig"),
        ("medium", "Mittel"),
        ("high", "Hoch"),
    ]


@pytest.mark.django_db
def test_regular_stage_form_explains_value_progress_without_new_required_fields(
    client,
    owner,
    business_unit,
):
    value_stream = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf",
        outcome="Bestellung",
        scope_in="Beschaffung",
        created_by=owner,
    )
    client.force_login(owner)

    response = client.get(
        reverse(
            "architecture:stage_create",
            kwargs={"value_stream_id": value_stream.pk},
        )
    )
    body = response.content.decode()
    form = ValueStreamStageForm()

    assert response.status_code == 200
    assert "Wertfortschritt" in body
    assert "Was liegt vorher vor" in body
    assert form.fields["description"].required is False
    assert set(form.fields) == {
        "sequence",
        "name",
        "description",
        "actors",
        "systems",
        "documents",
        "pain_points",
        "baseline_metrics",
    }


@pytest.mark.django_db
def test_value_stream_and_stage_focus_show_criterion_specific_screening_anchors(
    client,
    owner,
    business_unit,
):
    client.force_login(owner)

    value_stream_form_response = client.get(reverse("architecture:value_stream_create"))
    value_stream_body = value_stream_form_response.content.decode()
    assert value_stream_form_response.status_code == 200
    assert "Skalenanker Niedrig · Mittel · Hoch" in value_stream_body
    assert "Wirtschaftliches Potenzial" in value_stream_body
    assert "Veränderungsaufwand" in value_stream_body
    assert "hohen Aufwand" in value_stream_body

    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Angebote vergleichbar machen",
        description="Aus Angeboten entsteht eine vergleichbare Entscheidungsgrundlage.",
    )
    stage_focus_response = client.get(
        reverse("architecture:stage_focus_select", kwargs={"pk": value_stream.pk})
    )
    stage_focus_body = stage_focus_response.content.decode()

    assert stage_focus_response.status_code == 200
    assert "Skalenanker Niedrig · Mittel · Hoch" in stage_focus_body
    assert "Datenlage" in stage_focus_body
    assert "Problemintensität" in stage_focus_body
    assert "Veränderungsaufwand" in stage_focus_body
