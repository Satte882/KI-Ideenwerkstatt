from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from ki_radar.accelerator.ap4_evidence import (
    AP4EvidenceError,
    append_record,
    load_records,
    normalize_record,
    summarize_records,
    validate_frozen_manifest,
)


MANIFEST = Path(settings.BASE_DIR) / "tests/fixtures/ap4_case_manifest_v1.json"


def _validation():
    return validate_frozen_manifest(MANIFEST, repo_root=settings.BASE_DIR)


def _case(validation, case_id):
    return next(case for case in validation.manifest.cases if case.case_id == case_id)


def _record(
    validation,
    *,
    case_id,
    path,
    record_id,
    phase="scored",
    pre_fix_record_id="",
    active_input_seconds=100,
    navigation_seconds=50,
    authority_decision_seconds=50,
    post_draft_review_seconds=25,
    post_draft_correction_seconds=25,
    system_wait_seconds=100,
    manual_fields_changed=5,
    post_draft_fields_changed=1,
    avoidable_questions=2,
    authority_questions=1,
    source_derived_claims=10,
    provenance_resolved_claims=10,
    hallucinated_facts=0,
    cross_domain_consistent=True,
    expected_outcome_pass=True,
):
    case = _case(validation, case_id)
    if phase == "scored" and path == "autonomous":
        run_slot = case.run_slot
    elif phase == "scored":
        run_slot = f"{case_id}-B0"
    else:
        run_slot = f"{case_id}-PF-{record_id}"

    return {
        "record_id": record_id,
        "case_id": case_id,
        "run_slot": run_slot,
        "phase": phase,
        "path": path,
        "status": "completed",
        "source_pack_hash": validation.source_hashes[case_id],
        "times": {
            "active_input_seconds": active_input_seconds,
            "navigation_seconds": navigation_seconds,
            "authority_decision_seconds": authority_decision_seconds,
            "post_draft_review_seconds": post_draft_review_seconds,
            "post_draft_correction_seconds": post_draft_correction_seconds,
            "system_wait_seconds": system_wait_seconds,
        },
        "manual_fields_changed": manual_fields_changed,
        "post_draft_fields_changed": post_draft_fields_changed,
        "avoidable_questions": avoidable_questions,
        "authority_questions": authority_questions,
        "quality": {
            "source_derived_claims": source_derived_claims,
            "provenance_resolved_claims": provenance_resolved_claims,
            "hallucinated_facts": hallucinated_facts,
            "cross_domain_consistent": cross_domain_consistent,
            "expected_outcome_pass": expected_outcome_pass,
        },
        "pre_fix_record_id": pre_fix_record_id,
        "notes": "",
    }


def test_ap4_manifest_freezes_exactly_eight_distinct_cases_and_versions():
    validation = _validation()

    assert len(validation.manifest.cases) == 8
    assert len(validation.source_hashes) == 8
    assert len(set(validation.source_hashes.values())) == 8
    assert validation.manifest.baseline_case_ids == (
        "AP4-01",
        "AP4-02",
        "AP4-03",
        "AP4-04",
    )


def test_ap4_append_only_rejects_second_scored_slot(tmp_path):
    validation = _validation()
    evidence_path = tmp_path / "evidence.jsonl"

    first = _record(
        validation,
        case_id="AP4-03",
        path="autonomous",
        record_id="AP4-03-scored",
    )
    append_record(evidence_path, first, validation=validation)

    replacement = _record(
        validation,
        case_id="AP4-03",
        path="autonomous",
        record_id="AP4-03-better",
    )
    with pytest.raises(AP4EvidenceError, match="success sampling forbidden"):
        append_record(evidence_path, replacement, validation=validation)

    loaded = load_records(evidence_path, validation=validation)
    assert [item["record_id"] for item in loaded] == ["AP4-03-scored"]


def test_ap4_post_fix_must_preserve_pref_fix_record_and_does_not_replace_score(tmp_path):
    validation = _validation()
    evidence_path = tmp_path / "evidence.jsonl"

    scored = _record(
        validation,
        case_id="AP4-03",
        path="autonomous",
        record_id="AP4-03-scored",
        active_input_seconds=1400,
        hallucinated_facts=1,
        cross_domain_consistent=False,
        expected_outcome_pass=False,
    )
    append_record(evidence_path, scored, validation=validation)

    post_fix = _record(
        validation,
        case_id="AP4-03",
        path="autonomous",
        record_id="AP4-03-post-fix",
        phase="post_fix",
        pre_fix_record_id="AP4-03-scored",
        active_input_seconds=100,
        hallucinated_facts=0,
        cross_domain_consistent=True,
        expected_outcome_pass=True,
    )
    append_record(evidence_path, post_fix, validation=validation)

    summary = summarize_records(
        load_records(evidence_path, validation=validation),
        validation=validation,
    )

    assert summary["population"]["post_fix_runs"] == 1
    assert summary["metrics"]["hallucinated_facts"] == 1
    assert summary["pass"]["hallucinations"] is False
    assert summary["pass"]["cross_domain_consistency"] is False


def test_ap4_summary_uses_fresh_paired_baseline_and_frozen_targets():
    validation = _validation()
    records = []

    for case_id in validation.manifest.baseline_case_ids:
        records.append(
            normalize_record(
                _record(
                    validation,
                    case_id=case_id,
                    path="manual",
                    record_id=f"{case_id}-manual",
                    active_input_seconds=500,
                    navigation_seconds=100,
                    authority_decision_seconds=100,
                    post_draft_review_seconds=200,
                    post_draft_correction_seconds=100,
                    manual_fields_changed=100,
                    post_draft_fields_changed=20,
                    avoidable_questions=0,
                    source_derived_claims=0,
                    provenance_resolved_claims=0,
                ),
                validation=validation,
            )
        )

    for case in validation.manifest.cases:
        records.append(
            normalize_record(
                _record(
                    validation,
                    case_id=case.case_id,
                    path="autonomous",
                    record_id=f"{case.case_id}-auto",
                    active_input_seconds=120,
                    navigation_seconds=60,
                    authority_decision_seconds=60,
                    post_draft_review_seconds=50,
                    post_draft_correction_seconds=50,
                    manual_fields_changed=5,
                    post_draft_fields_changed=1,
                    avoidable_questions=2,
                    source_derived_claims=10,
                    provenance_resolved_claims=10,
                    hallucinated_facts=0,
                    cross_domain_consistent=True,
                    expected_outcome_pass=True,
                ),
                validation=validation,
            )
        )

    summary = summarize_records(records, validation=validation)

    assert summary["population"]["scored_autonomous_cases"] == 8
    assert summary["population"]["missing_scored_cases"] == []
    assert summary["metrics"]["manual_field_reduction"] == pytest.approx(0.95)
    assert summary["metrics"]["human_rework_ratio"] == pytest.approx(0.10)
    assert summary["metrics"]["provenance_ratio"] == pytest.approx(1.0)
    assert summary["metrics"]["hallucinated_facts"] == 0
    assert summary["pass"] == {
        "active_human_work": True,
        "manual_field_reduction": True,
        "avoidable_questions": True,
        "provenance": True,
        "hallucinations": True,
        "cross_domain_consistency": True,
        "human_rework": True,
    }


def test_ap4_source_pack_hash_rejects_unfrozen_file(tmp_path):
    validation = _validation()
    case = _case(validation, "AP4-01")
    source_root = Path(settings.BASE_DIR) / case.source_pack

    copied = tmp_path / "pack"
    copied.mkdir()
    for relative in case.files:
        (copied / relative).write_bytes((source_root / relative).read_bytes())
    (copied / "unexpected.md").write_text("not frozen", encoding="utf-8")

    from ki_radar.accelerator.ap4_evidence import source_pack_hash

    with pytest.raises(AP4EvidenceError, match="source pack file set changed"):
        source_pack_hash(copied, case.files)


def test_ap4_hardening_map_references_existing_tests():
    path = Path(settings.BASE_DIR) / "tests/fixtures/ap4_hardening_evidence_v1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert len(payload["scenarios"]) == 12
    partial = {
        item["scenario"] for item in payload["scenarios"] if item["coverage"] == "partial"
    }
    assert partial == {"concurrent_runs", "irrelevant_source"}

    for item in payload["scenarios"]:
        assert item["coverage"] in {"covered", "partial"}
        assert item["evidence"]
        for reference in item["evidence"]:
            relative, test_name = reference.split("::", 1)
            source = (Path(settings.BASE_DIR) / relative).read_text(encoding="utf-8")
            assert f"def {test_name}(" in source


def test_ap4_management_command_validates_contract_without_records(tmp_path):
    output = io.StringIO()

    call_command(
        "ap4_evidence",
        records=str(tmp_path / "ap4-evidence-does-not-exist.jsonl"),
        stdout=output,
    )

    rendered = output.getvalue()
    assert "AP4 contract valid: 8 cases, 0 evidence records." in rendered
    assert "Fehlende gewertete Slots" in rendered
