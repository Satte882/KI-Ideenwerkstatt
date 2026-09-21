from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from django.core.management import call_command
from django.test import override_settings

from ki_radar.architecture.focus import ValueStreamFocus, get_value_stream_focus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.scenario_blueprint import blueprint_checksum, load_blueprint_json
from ki_radar.core.scenario_blueprint_apply import BlueprintApplyError
from ki_radar.core.scenario_blueprint_run import run_blueprint
from ki_radar.use_cases.models import UseCase

BLUEPRINT_DIRECTORY = (
    Path(__file__).resolve().parents[1] / "ki_radar" / "core" / "scenario_blueprints"
)
BLUEPRINT_PATH = BLUEPRINT_DIRECTORY / "real_demo.v1.json"
CHECKSUM_PATH = BLUEPRINT_DIRECTORY / "real_demo.v1.sha256"
EXPECTED_CHECKSUM = "a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5"
STREAM_KEY = "real-demo-procurement-order"
USE_CASE_KEY = "real-demo-assisted-offer-comparison"


@pytest.fixture
def real_demo_payload(db):
    with override_settings(DEBUG=True):
        call_command("seed_demo_data", verbosity=0)
    return load_blueprint_json(BLUEPRINT_PATH)


def _target_counts() -> dict[str, int]:
    stream = ValueStream.objects.filter(demo_key=STREAM_KEY).first()
    return {
        "value_streams": ValueStream.objects.filter(demo_key=STREAM_KEY).count(),
        "stages": ValueStreamStage.objects.filter(value_stream=stream).count() if stream else 0,
        "process_analyses": ProcessAnalysis.objects.filter(stage__value_stream=stream).count()
        if stream
        else 0,
        "solution_options": SolutionOption.objects.filter(
            process_analysis__stage__value_stream=stream
        ).count()
        if stream
        else 0,
        "use_cases": UseCase.objects.filter(demo_key=USE_CASE_KEY).count(),
        "origins": UseCaseOrigin.objects.filter(use_case__demo_key=USE_CASE_KEY).count(),
    }


def test_real_demo_repository_file_matches_governed_checksum():
    payload = load_blueprint_json(BLUEPRINT_PATH)
    checksum_line = CHECKSUM_PATH.read_text(encoding="utf-8").strip()

    assert checksum_line == f"{EXPECTED_CHECKSUM}  real_demo.v1.json"
    assert blueprint_checksum(payload) == EXPECTED_CHECKSUM

    changed = deepcopy(payload)
    changed["use_case"]["summary"] += " Manipuliert."
    assert blueprint_checksum(changed) != EXPECTED_CHECKSUM


@pytest.mark.django_db
def test_real_demo_dry_run_apply_and_repeat_are_reproducible(real_demo_payload):
    first_dry_run = run_blueprint(real_demo_payload)
    assert first_dry_run.summary["graph_status"] == "CREATE"
    assert first_dry_run.summary["checksum"] == EXPECTED_CHECKSUM
    assert _target_counts() == {
        "value_streams": 0,
        "stages": 0,
        "process_analyses": 0,
        "solution_options": 0,
        "use_cases": 0,
        "origins": 0,
    }

    applied = run_blueprint(real_demo_payload, apply=True)
    assert applied.summary["result"] == "CREATE"
    assert applied.summary["created_counts"] == {
        "value_streams": 1,
        "stages": 3,
        "process_analyses": 1,
        "solution_options": 3,
        "use_cases": 1,
        "origins": 1,
    }
    assert _target_counts() == applied.summary["created_counts"]

    stream = ValueStream.objects.get(demo_key=STREAM_KEY)
    use_case = UseCase.objects.get(demo_key=USE_CASE_KEY)
    process = ProcessAnalysis.objects.get(stage__value_stream=stream)
    options = SolutionOption.objects.filter(process_analysis=process)
    origin = UseCaseOrigin.objects.get(use_case=use_case)
    focus = get_value_stream_focus(stream)

    assert stream.status == ValueStream.Status.DRAFT
    assert focus.status == ValueStreamFocus.Status.NOT_SCREENED
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert options.count() == 3
    assert set(options.values_list("recommendation", flat=True)) == {
        SolutionOption.Recommendation.CANDIDATE
    }
    assert set(options.values_list("evaluation_status", flat=True)) == {
        SolutionOption.EvaluationStatus.DRAFT
    }
    assert use_case.status == UseCase.Status.IDEA
    assert use_case.decision_status == UseCase.DecisionStatus.CLARIFICATION
    assert process.source_snapshot["_blueprint"]["checksum"] == EXPECTED_CHECKSUM
    assert origin.source_snapshot["_blueprint"]["checksum"] == EXPECTED_CHECKSUM

    counts_after_first_apply = _target_counts()
    repeated = run_blueprint(real_demo_payload, apply=True)
    assert repeated.summary["result"] == "NO_CHANGE"
    assert repeated.summary["created_counts"] == {}
    assert _target_counts() == counts_after_first_apply

    final_dry_run = run_blueprint(real_demo_payload)
    assert final_dry_run.summary["graph_status"] == "NO_CHANGE"


@pytest.mark.django_db
def test_real_demo_apply_rolls_back_complete_graph_on_error(real_demo_payload, monkeypatch):
    def fail_options(*args, **kwargs):
        raise BlueprintApplyError("Erzwungener Regressionstestfehler")

    monkeypatch.setattr(
        "ki_radar.core.scenario_blueprint_apply._save_options",
        fail_options,
    )

    with pytest.raises(BlueprintApplyError, match="Erzwungener Regressionstestfehler"):
        run_blueprint(real_demo_payload, apply=True)

    assert _target_counts() == {
        "value_streams": 0,
        "stages": 0,
        "process_analyses": 0,
        "solution_options": 0,
        "use_cases": 0,
        "origins": 0,
    }
