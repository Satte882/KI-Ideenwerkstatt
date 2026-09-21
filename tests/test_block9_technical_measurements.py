# fmt: off
import json

import pytest
from django.core.management import call_command

REFERENCE_SHA256 = "a910863c3f677eb95b593e8031f48e54f811c5bb55295b4e601ae6f13a0b70d5"
EXPECTED_TECHNICAL_RUNS = (
    "blueprint-A-control-1",
    "delivery-A-1",
    "delivery-A-2",
    "delivery-A-3",
)
EXPECTED_INTERACTIVE_RUNS = (
    "manual-A-1",
    "accelerator-A-1",
    "accelerator-A-2",
    "manual-A-2",
    "manual-A-3",
    "accelerator-A-3",
)

pytestmark = pytest.mark.django_db(transaction=True)


def test_block9_technical_runner_records_only_real_technical_controls(tmp_path):
    raw_path = tmp_path / "raw-technical.jsonl"
    interactive_path = tmp_path / "interactive-status.json"

    call_command(
        "run_block9_technical_measurements",
        output=str(raw_path),
        interactive_manifest=str(interactive_path),
        verbosity=0,
    )

    rows = [
        json.loads(line)
        for line in raw_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert tuple(row["run_id"] for row in rows) == EXPECTED_TECHNICAL_RUNS
    assert all(row["status"] == "completed" for row in rows)

    blueprint = rows[0]
    assert blueprint["technical_control"]["result"] == "CREATE"
    assert blueprint["technical_control"]["checksum"] == REFERENCE_SHA256
    assert blueprint["times"]["end_to_end_seconds"] > 0

    for row in rows[1:]:
        assert row["path"] == "delivery"
        assert row["times"]["end_to_end_seconds"] > 0
        assert row["delivery"]["llm_fields"] == 0
        assert row["delivery"]["deterministic_fields"] > 0

    manifest = json.loads(interactive_path.read_text(encoding="utf-8"))
    assert manifest["status"] == "operator_measurement_required"
    assert tuple(item["run_id"] for item in manifest["runs"]) == EXPECTED_INTERACTIVE_RUNS
    assert all(item["status"] == "not_executed" for item in manifest["runs"])
    assert manifest["quality_case_B"]["status"] == "not_executed"
# fmt: on
