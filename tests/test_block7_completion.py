from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accelerator import block7_demo
from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accounts.models import User
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "accelerator"
FIXTURE_PATH = FIXTURE_DIR / "block7_real_demo.v1.json"
CHECKSUM_PATH = FIXTURE_DIR / "block7_real_demo.v1.sha256"


def _expected_report() -> dict:
    content = FIXTURE_PATH.read_text(encoding="utf-8")
    return json.loads(content)


def test_block7_real_demo_fixture_checksum_prevents_silent_drift():
    checksum_text = CHECKSUM_PATH.read_text(encoding="utf-8")
    expected = checksum_text.split()[0]
    actual = hashlib.sha256(FIXTURE_PATH.read_bytes()).hexdigest()
    report = _expected_report()

    assert actual == expected
    assert report["path"] == "solution_generation"
    assert report["generation"]["provider_calls"] == 1


@pytest.mark.django_db
def test_block7_real_demo_matches_governed_reference():
    report = block7_demo.run_block7_real_demo()

    assert report == _expected_report()
    assert report["adoption"]["option_count"] == 3
    assert report["rollback"] == {
        "error": "simulated_persistence_failure",
        "option_count": 0,
        "adoption_recorded": False,
    }
    assert all(report["gates"].values())


@pytest.mark.django_db
def test_block7_real_demo_management_command_is_reproducible(tmp_path):
    output_path = tmp_path / "block7-real-demo.json"

    call_command("run_block7_real_demo", output=output_path)
    first_text = output_path.read_text(encoding="utf-8")
    first = json.loads(first_text)

    call_command("run_block7_real_demo", output=output_path)
    second_text = output_path.read_text(encoding="utf-8")
    second = json.loads(second_text)

    assert first == second
    assert second == _expected_report()


@pytest.mark.django_db
def test_block7_real_demo_preview_and_comparison_preserve_review_contract(client):
    report = block7_demo.run_block7_real_demo()
    actor = User.objects.get(username=block7_demo.block6_demo.DEMO_USERNAME)
    process = ProcessAnalysis.objects.get(
        stage__value_stream__demo_key=block7_demo.block6_demo.VALUE_STREAM_DEMO_KEY,
        name=block7_demo.PROCESS_NAME,
    )
    run = SolutionGenerationRun.objects.get(
        process_analysis=process,
        status=SolutionGenerationRun.Status.SUCCESS,
    )
    client.force_login(actor)

    preview_url = reverse("accelerator:solution_generation_preview", args=[run.pk])
    preview_response = client.get(preview_url)
    preview_page = preview_response.content.decode()

    assert preview_response.status_code == 200
    assert "Gemeinsame Ausgangslage" in preview_page
    assert "Einkauf vergleicht Angebote manuell." in preview_page
    assert "Quellen" in preview_page
    assert "Annahmen" in preview_page
    assert "Offene Evidenz" in preview_page
    assert "Unsicherheit" in preview_page
    assert "Organisatorische Änderung" in preview_page
    assert "Regelbasierte Automatisierung" in preview_page
    assert "KI-/Assistenzlösung" in preview_page
    assert "Bereits übernommen" in preview_page
    assert "col-12 col-xl-4" in preview_page
    assert "<table" not in preview_page
    assert "min-width" not in preview_page

    compare_url = reverse("architecture:solution_option_compare", args=[process.pk])
    compare_response = client.get(compare_url)
    compare_page = compare_response.content.decode()
    assert compare_response.status_code == 200
    for option in report["adoption"]["options"]:
        assert option["name"] in compare_page

    options = list(SolutionOption.objects.filter(process_analysis=process))
    assert len(options) == 3
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()
    for option in options:
        assert option.recommendation == SolutionOption.Recommendation.CANDIDATE
        assert option.evaluation_status == SolutionOption.EvaluationStatus.DRAFT
        assert option.feasibility == SolutionOption.Effort.NOT_ASSESSED
        assert option.integration_effort == SolutionOption.Effort.NOT_ASSESSED
