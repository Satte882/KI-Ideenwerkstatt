from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from django.core.management import call_command
from django.urls import reverse

from ki_radar.accelerator import block6_demo
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accounts.models import User
from ki_radar.core import scenario_blueprint_apply, scenario_blueprint_run

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "accelerator" / "block6_real_demo.v1.json"
CHECKSUM_PATH = FIXTURE_PATH.with_suffix(".sha256")


def _expected_report() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_block6_real_demo_fixture_checksum_prevents_silent_drift():
    expected = CHECKSUM_PATH.read_text(encoding="utf-8").split()[0]
    normalized = FIXTURE_PATH.read_bytes().replace(b"\r\n", b"\n")
    actual = hashlib.sha256(normalized).hexdigest()

    assert actual == expected
    assert _expected_report()["path"] == "structured_adoption"
    assert _expected_report()["legacy_blueprint_importer_used"] is False


@pytest.mark.django_db
def test_block6_real_demo_matches_governed_reference():
    assert block6_demo.run_block6_real_demo() == _expected_report()


@pytest.mark.django_db
def test_block6_real_demo_never_uses_legacy_blueprint_importer(monkeypatch):
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("Der Block-6-Real-DEMO darf den Blueprint-Importer nicht verwenden.")

    monkeypatch.setattr(scenario_blueprint_apply, "apply_blueprint", forbidden)
    monkeypatch.setattr(scenario_blueprint_run, "apply_blueprint", forbidden)
    monkeypatch.setattr(scenario_blueprint_run, "run_blueprint", forbidden)

    report = block6_demo.run_block6_real_demo()

    assert calls == []
    assert report["path"] == "structured_adoption"
    assert report["legacy_blueprint_importer_used"] is False


@pytest.mark.django_db
def test_block6_real_demo_management_command_is_reproducible(tmp_path):
    output_path = tmp_path / "block6-real-demo.json"

    call_command("run_block6_real_demo", output=output_path)
    first = json.loads(output_path.read_text(encoding="utf-8"))
    call_command("run_block6_real_demo", output=output_path)
    second = json.loads(output_path.read_text(encoding="utf-8"))

    assert first == second == _expected_report()


@pytest.mark.django_db
def test_block6_real_demo_review_page_preserves_responsive_contract(client):
    block6_demo.run_block6_real_demo()
    actor = User.objects.get(username=block6_demo.DEMO_USERNAME)
    session = CaptureSession.objects.get(
        owner=actor,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        target_value_stream__demo_key=block6_demo.VALUE_STREAM_DEMO_KEY,
    )
    analysis = CaptureAnalysis.objects.get(session=session)
    client.force_login(actor)

    response = client.get(reverse("accelerator:structured_review", args=[analysis.id]))
    page = response.content.decode()

    assert response.status_code == 200
    assert "Bedarf klären" in page
    assert "Angebote vergleichen" in page
    assert "Bestellung auslösen" in page
    assert "Angebotsvergleich" in page
    assert "<table" not in page
    assert "overflow-x" not in page
    assert "white-space: nowrap" not in page
    assert "min-width:" not in page
    assert "flex-wrap" in page
    assert "text-break" in page
