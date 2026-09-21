from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from ki_radar.accelerator import solution_generation_views
from ki_radar.accelerator.solution_generation_service import SolutionGenerationError
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Bedarf",
        outcome="Bestellung",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="Menschliche Freigabe",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
        description="Vergleich",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manuell",
        baseline_metrics="11 Minuten",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl dokumentiert",
        trigger="Frist endet",
        outcome="Auswahl",
        current_flow="Manueller Vergleich",
        roles="Einkauf",
        systems="ERP",
        data_objects="Angebote",
        bottlenecks="Übertragung",
        baseline_metrics="11 Minuten",
        analyzed_by=owner,
    )


@pytest.mark.django_db
def test_failure_feedback_is_local(client, owner, business_unit, monkeypatch):
    process = make_process(owner, business_unit)
    client.force_login(owner)

    def fail_generation(**kwargs):
        raise SolutionGenerationError("Providerantwort abgeschnitten.", code="output_truncated")

    monkeypatch.setattr(solution_generation_views, "generate_solution_preview", fail_generation)
    response = client.post(reverse("accelerator:solution_generation_start", args=[process.pk]))

    assert response.status_code == 302
    assert response["Location"] == f"{process.get_absolute_url()}#loesungsoptionen"
    assert "solution_option_compare" not in response["Location"]
    stored = list(get_messages(response.wsgi_request))
    assert len(stored) == 1
    assert "solution-generation-feedback" in stored[0].tags
    assert "KI-Antwort war unvollständig" in str(stored[0])


@pytest.mark.django_db
def test_success_targets_preview(client, owner, business_unit, monkeypatch):
    process = make_process(owner, business_unit)
    client.force_login(owner)
    run_id = uuid4()
    monkeypatch.setattr(
        solution_generation_views,
        "generate_solution_preview",
        lambda **kwargs: SimpleNamespace(pk=run_id),
    )

    response = client.post(reverse("accelerator:solution_generation_start", args=[process.pk]))

    expected = reverse("accelerator:solution_generation_preview", args=[run_id])
    assert response.status_code == 302
    assert response["Location"] == f"{expected}#solution-generation-result"


def test_feedback_script_moves_tagged_error():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "static" / "js" / "copilot-submit-guard.js"
    preview_path = root / "templates" / "accelerator" / "solution_generation_preview.html"
    script = script_path.read_text(encoding="utf-8")
    preview = preview_path.read_text(encoding="utf-8")

    assert ".alert-solution-generation-feedback" in script
    assert "#loesungsoptionen .card-body" in script
    assert "KI-Generierung fehlgeschlagen." in script
    assert "solution-generation-result" in preview
    assert "KI-Generierung erfolgreich" in preview
