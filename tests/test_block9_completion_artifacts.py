import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTERACTIVE_PATH = ROOT / "artifacts" / "block9" / "raw-interactive.jsonl"
TECHNICAL_PATH = ROOT / "artifacts" / "block9" / "raw-technical.jsonl"
SUMMARY_PATH = ROOT / "artifacts" / "block9" / "ap10-summary.json"

EXPECTED_SEQUENCE = [
    "manual-A-1",
    "accelerator-A-1",
    "accelerator-A-2",
    "manual-A-2",
    "manual-A-3",
    "accelerator-A-3",
    "accelerator-B-1",
]


def _jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_block9_interactive_records_preserve_frozen_order_and_first_attempt_failures():
    records = _jsonl(INTERACTIVE_PATH)

    assert [record["run_id"] for record in records] == EXPECTED_SEQUENCE
    assert all(record["benchmark_version"] == "block9-v2" for record in records)
    assert records[2]["status"] == "failed"
    assert records[6]["status"] == "failed"
    assert all(record["times"]["end_to_end_seconds"] > 0 for record in records)


def test_block9_technical_records_remain_v1_and_are_not_relabeled():
    records = _jsonl(TECHNICAL_PATH)

    assert [record["run_id"] for record in records] == [
        "blueprint-A-control-1",
        "delivery-A-1",
        "delivery-A-2",
        "delivery-A-3",
    ]
    assert all(record["benchmark_version"] == "block9-v1" for record in records)


def test_ap10_summary_matches_primary_outcome():
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

    assert summary["scored_sequence"] == EXPECTED_SEQUENCE
    assert summary["case_a"]["manual"]["completed"] == 3
    assert summary["case_a"]["accelerator_primary_slots"]["completed"] == 2
    assert summary["case_a"]["accelerator_primary_slots"]["failed"] == 1
    assert summary["case_b"]["status"] == "failed"
    assert summary["all_scored_accelerator_slots"]["cost_usd"] == "0.051802"
