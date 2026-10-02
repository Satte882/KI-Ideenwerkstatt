from __future__ import annotations

import hashlib
import json
import shutil
from contextlib import nullcontext
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import CommandError

from ki_radar.accelerator import investigation_llm, issue118_execution, issue118_experiment
from ki_radar.accelerator.investigation_models import InvestigationRun
from ki_radar.accelerator.issue106_baseline import golden_case_specs
from ki_radar.accelerator.issue118_execution import (
    ExperimentRunner,
    assert_population_order,
    ledger_cost,
)
from ki_radar.accelerator.issue118_experiment import (
    AFFECTED_CASES,
    CONTROL_COMMIT,
    EXPERIMENT_ID,
    FIXTURE_TEST,
    LOOPS,
    aggregate_experiment,
    digest,
    experiment_review_template,
    experiment_reviews,
    historical_reference,
    pricing_from_env,
    read_plan,
    slot_key,
    slots,
    technical_contract,
    validate_record,
    verify_checkout,
)
from ki_radar.accelerator.issue118_fixtures import ARCHIVED_SOURCE, fixture_evidence
from ki_radar.accelerator.management.commands import prepare_issue118_experiment
from tests.test_issue_111_baseline import _complete_review, _record


@pytest.fixture(autouse=True)
def block_real_provider(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("C2a must never invoke a real provider")

    monkeypatch.setattr(investigation_llm, "request_openrouter", forbidden)


@pytest.fixture
def reference():
    return historical_reference()


@pytest.fixture
def plan(reference):
    contract = technical_contract({**reference["runs"][0]["execution_contract"], "tools": {}})
    variant = {**contract, "loop_version": LOOPS["variant"]}
    return {
        "experiment_id": EXPERIMENT_ID,
        "variant_commit": "a" * 40,
        "control_commit": CONTROL_COMMIT,
        "plan_hash": "frozen-plan",
        "contracts": {"control": contract, "variant": variant},
        "source_hashes": {case: f"hash-{case}" for case in issue118_experiment.GOLDEN_CASE_IDS},
        "prepared": {
            slot_key(slot): {
                "manifest_hash": slot_key(slot),
                "source_file_hashes": {},
                "domain_input_hash": digest(None),
            }
            for slot in slots()
        },
        "fixture_evidence": {"tested_commit": "a" * 40, "passed_cases": list(AFFECTED_CASES)},
        "slots": slots(),
    }


@pytest.fixture
def records(plan, reference):
    result = []
    for index, slot in enumerate(slots()):
        arm, case, repetition = slot["arm"], slot["case_id"], slot["repetition"]
        runtime = reference["summary"]["by_case"][case]["runtime"]["median_seconds"]
        row = _record(
            case,
            repetition,
            runtime,
            0.005,
            tested_commit=plan[f"{arm}_commit"],
            status="waiting_human" if case == "AP4-05" else "ready",
        )
        row.update(
            slot,
            run_id=f"{arm}-{case}-{repetition}",
            experiment_id=EXPERIMENT_ID,
            phase="experiment",
            plan_hash=plan["plan_hash"],
            execution_contract=plan["contracts"][arm],
            source_pack_hash=plan["source_hashes"][case],
            manifest_hash=plan["prepared"][slot_key(slot)]["manifest_hash"],
            source_file_hashes={},
            domain_input_hash=digest(None),
            failure_codes={},
        )
        row["performance"]["started_at"] = f"2026-10-02T12:{index:02}:00+00:00"
        result.append(row)
    return result


def reviews_for(records, plan):
    template = experiment_review_template(records, plan)
    _complete_review(template)
    return experiment_reviews(template, records, plan)


def test_population_and_alternating_order():
    ordered = slots()
    assert len(ordered) == 25
    assert sum(s["arm"] == "variant" for s in ordered) == 20
    assert sum(s["arm"] == "control" for s in ordered) == 5
    assert len({slot_key(s) for s in ordered}) == 25
    assert [ordered[i]["arm"] for i in (0, 5, 10, 15, 20)] == [
        "variant",
        "control",
        "variant",
        "control",
        "variant",
    ]


def test_ap1_reference_is_validated_not_hardcoded(reference):
    assert reference["summary"]["total_budget_accounted_cost_usd"] == 0.184652
    assert reference["summary"]["quality_statuses"]["pass"] == 16
    assert reference["summary"]["by_case"]["AP4-02"]["runtime"]["median_seconds"] == 249.280


@pytest.mark.parametrize("outside", [0, 1, 2])
def test_control_drift_zero_one_two(outside, records, plan, reference):
    controls = [r for r in records if r["arm"] == "control"]
    for record in controls[:outside]:
        noise = reference["summary"]["by_case"][record["case_id"]]["runtime"][
            "noise_floor_2x_mad_seconds"
        ]
        record["performance"]["run_seconds"] += noise + 1
    report = aggregate_experiment(records, plan, reference)
    assert report["controls_outside_noise_count"] == outside
    assert report["comparison_status"] == (
        "not_sufficiently_proven" if outside >= 2 else "comparable"
    )


def test_missing_slot_is_incomplete(records, plan, reference):
    result = aggregate_experiment(records[:-1], plan, reference)
    assert not result["population_complete"]
    assert not result["adoption_eligible"]
    assert len(result["missing_slots"]) == 1


def test_duplicate_slot_rejected(records, plan, reference):
    with pytest.raises(ValueError, match="Duplicate"):
        aggregate_experiment([*records, records[0]], plan, reference)


@pytest.mark.parametrize(
    "field,value",
    [
        ("tested_commit", "b" * 40),
        ("plan_hash", "changed"),
        ("experiment_id", "issue106-ap1-baseline-v1"),
        ("phase", "baseline"),
        ("source_pack_hash", "changed"),
        ("manifest_hash", "changed"),
        ("arm", "unknown"),
        ("repetition", 5),
    ],
)
def test_bad_bindings_fail_closed(field, value, records, plan):
    records[0][field] = value
    with pytest.raises(ValueError):
        validate_record(records[0], plan)


def test_wrong_control_commit_rejected(records, plan):
    record = next(r for r in records if r["arm"] == "control")
    record["tested_commit"] = plan["variant_commit"]
    with pytest.raises(ValueError, match="commit"):
        validate_record(record, plan)


@pytest.mark.parametrize("arm", ["variant", "control"])
def test_swapped_loop_contract_rejected(arm, records, plan):
    record = next(r for r in records if r["arm"] == arm)
    record["execution_contract"] = plan["contracts"]["control" if arm == "variant" else "variant"]
    with pytest.raises(ValueError, match="contract"):
        validate_record(record, plan)


@pytest.mark.parametrize("loops", [0, 1])
def test_g03_zero_or_one_no_progress(loops, records, plan, reference):
    row = next(r for r in records if r["arm"] == "variant" and r["case_id"] == "AP4-02")
    if loops:
        row["failure_codes"]["no_progress_loop"] = 1
    report = aggregate_experiment(records, plan, reference)
    assert report["g03"]["affected_variant_run_count"] == 8
    assert report["g03"]["no_progress_loop_count"] == loops
    assert report["g03"]["gate_pass"] is (loops == 0)


def test_new_failure_type_blocks_reliability(records, plan, reference):
    records[0]["failure_codes"]["novel_transport_failure"] = 1
    report = aggregate_experiment(records, plan, reference)
    assert report["by_arm"]["variant"]["new_failure_types"] == ["novel_transport_failure"]
    assert not report["g03"]["gate_pass"]


def test_state_fixture_absence_blocks_reliability(records, plan, reference):
    plan["fixture_evidence"]["passed_cases"] = []
    assert not aggregate_experiment(records, plan, reference)["g03"]["gate_pass"]


@pytest.mark.parametrize("reduction,passes", [(29, False), (95, False), (96, True)])
def test_runtime_gate_requires_contract_threshold_and_noise(
    reduction, passes, records, plan, reference
):
    # Synthetic homogeneous workload isolates the AP0 formula from status changes.
    for row in reference["runs"]:
        if row["case_id"] in AFFECTED_CASES:
            row["status"] = "ready"
    for row in records:
        if row["arm"] == "variant" and row["case_id"] in AFFECTED_CASES:
            row["performance"]["run_seconds"] -= reduction
    result = aggregate_experiment(records, plan, reference)
    assert result["runtime_effect"]["aggregate_effect_seconds"] == pytest.approx(reduction)
    assert result["runtime_effect"]["gate_pass"] is passes


def test_noncritical_quality_regression_blocks_adoption(records, plan, reference):
    payload = experiment_review_template(records, plan)
    _complete_review(payload)
    for row in payload["reviews"]:
        if row["arm"] == "variant" and row["case_id"] == "AP4-01":
            row["semantic_rubric"]["facts_hypotheses_and_unknowns_separated"] = "fail"
    report = aggregate_experiment(
        records, plan, reference, experiment_reviews(payload, records, plan)
    )
    assert report["observed_hard_fail_count"] == 0
    assert not report["by_arm"]["variant"]["by_case"]["AP4-01"]["quality_rate_guard_pass"]
    assert not report["adoption_eligible"]


def test_complete_review_reliability_path_is_eligible(records, plan, reference):
    report = aggregate_experiment(records, plan, reference, reviews_for(records, plan))
    assert report["population_complete"] and report["quality_complete"]
    assert report["g03"]["gate_pass"]
    assert not report["runtime_effect"]["gate_pass"]
    assert report["adoption_eligible"]
    assert report["ap1_reference"]["quality_pass_count"] == 16
    assert report["ap1_reference"]["by_case"]["AP4-04"]["runtime"]["median_seconds"] == 266.381


def test_failed_runtime_is_stratified_not_speed_comparison(records, plan, reference):
    record = next(r for r in records if r["arm"] == "variant" and r["case_id"] == "AP4-02")
    record["status"] = "failed"
    record["performance"]["run_seconds"] = 999
    result = aggregate_experiment(records, plan, reference)
    case = result["by_arm"]["variant"]["by_case"]["AP4-02"]
    assert case["runtime_by_terminal_state"]["failed"]["median_seconds"] == 999
    assert case["runtime_by_terminal_state"]["ready"]["sample_size"] == 3
    assert not result["runtime_effect"]["status_comparable"]
    assert not result["runtime_effect"]["gate_pass"]


def test_unassessed_blocks_adoption(records, plan, reference):
    reviews = experiment_reviews(experiment_review_template(records, plan), records, plan)
    report = aggregate_experiment(records, plan, reference, reviews)
    assert not report["quality_complete"]
    assert not report["adoption_eligible"]
    assert report["by_arm"]["variant"]["cost_per_quality_pass_usd"] is None
    assert report["by_arm"]["variant"]["cost_metric_status"] == "undefined"


def test_hard_fail_blocks_adoption(records, plan, reference):
    payload = experiment_review_template(records, plan)
    _complete_review(payload)
    payload["reviews"][0]["hard_fail_checks"][0]["status"] = "fail"
    report = aggregate_experiment(
        records, plan, reference, experiment_reviews(payload, records, plan)
    )
    assert report["observed_hard_fail_count"] == 1
    assert not report["adoption_eligible"]


@pytest.mark.parametrize("rate,passes", [(1.05, True), (1.05001, False)])
def test_cost_guard_five_percent(rate, passes, records, plan, reference):
    cost = float(
        Decimal(str(reference["summary"]["total_budget_accounted_cost_usd"]))
        / 16
        * Decimal(str(rate))
    )
    for row in records:
        row["performance"]["budget_accounted_cost_usd"] = cost if row["arm"] == "variant" else 1
    report = aggregate_experiment(records, plan, reference, reviews_for(records, plan))
    variant = report["by_arm"]["variant"]
    assert variant["quality_pass_count"] == 20
    assert variant["cost_guard_pass"] is passes
    assert variant["cost_per_quality_pass_usd"] == pytest.approx(cost)


def test_uncertain_cost_kept_and_budget_combines_arms(records, plan, reference):
    for row in records:
        row["performance"]["budget_accounted_cost_usd"] = 1
        row["performance"]["cost_usd"] = 0
        row["performance"]["uncertain_provider_attempts"] = 1
    report = aggregate_experiment(records, plan, reference)
    assert report["experiment_budget_accounted_cost_usd"] == 25
    assert not report["experiment_budget_guard_pass"]
    assert report["by_arm"]["variant"]["uncertain_attempts"] == 20


def test_event_denominator_includes_failed(records, plan, reference):
    records[0]["status"] = "failed"
    records[0]["recovery"]["has_timeout"] = True
    result = aggregate_experiment(records, plan, reference)
    assert result["by_arm"]["variant"]["event_rates_percent"]["timeout"] == 5
    assert result["by_arm"]["control"]["event_rates_percent"]["timeout"] == 0


@pytest.mark.parametrize(
    "field,value", [("arm", "control"), ("tested_commit", "b" * 40), ("record_hash", "forged")]
)
def test_review_binds_arm_commit_context(field, value, records, plan):
    payload = experiment_review_template(records, plan)
    payload["reviews"][0][field] = value
    with pytest.raises(ValueError):
        experiment_reviews(payload, records, plan)


def test_authoritative_prefix_and_reuse(records):
    assert_population_order(records[:2], slots()[2])
    assert_population_order(records[:2], slots()[0])
    with pytest.raises(CommandError, match="next slot"):
        assert_population_order(records[:2], slots()[3])
    with pytest.raises(CommandError, match="start order"):
        assert_population_order([records[1]], slots()[2])
    records[1]["terminal_state_check"]["system_boundary_reached"] = False
    with pytest.raises(CommandError, match="Recover"):
        assert_population_order(records[:2], slots()[2])
    assert_population_order(records[:2], slots()[1])


@pytest.mark.parametrize("dirty,head", [(" M changed.py", "a" * 40), ("", "b" * 40)])
def test_git_fail_closed(monkeypatch, tmp_path, dirty, head):
    def output(root, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return str(tmp_path)
        return dirty if args[0] == "status" else head

    monkeypatch.setattr(issue118_experiment, "git_output", output)
    with pytest.raises(CommandError):
        verify_checkout(tmp_path, "a" * 40)


@pytest.mark.parametrize("price", ["", "-1", "NaN", "Infinity", "-Infinity"])
def test_invalid_pricing_rejected(price, monkeypatch):
    monkeypatch.setenv("ISSUE106_PRICE_INPUT_PER_MILLION", price)
    with pytest.raises(CommandError):
        pricing_from_env()


def test_explicit_pricing_frozen(monkeypatch):
    monkeypatch.setenv("ISSUE106_PRICE_INPUT_PER_MILLION", "1.20")
    monkeypatch.setenv("ISSUE106_PRICE_OUTPUT_PER_MILLION", "2.50")
    monkeypatch.setenv("ISSUE106_PRICING_CURRENCY", "USD")
    monkeypatch.setenv("ISSUE106_PRICING_VERSION", "synthetic-only")
    assert pricing_from_env()["rates"] == {"input_per_million": "1.2", "output_per_million": "2.5"}


def test_ledger_keeps_uncertain_and_rejects_unpriced():
    assert (
        ledger_cost([SimpleNamespace(actual_cost_microunits=None, reserved_cost_microunits=42)])
        == 42
    )
    with pytest.raises(CommandError, match="Unpriced"):
        ledger_cost([SimpleNamespace(actual_cost_microunits=None, reserved_cost_microunits=None)])


@pytest.mark.parametrize(
    "experiment,project,ap1,expected",
    [
        (19_000_000, 59_500_000, 184_652, 500_000),
        (19_900_000, 40_000_000, 184_652, 100_000),
        (0, 59_900_000, 0, -84_652),
    ],
)
def test_shared_twenty_and_global_sixty_cap(experiment, project, ap1, expected, monkeypatch):
    class Manager:
        def filter(self, **kwargs):
            if "run__evidence_metadata__experiment_id__startswith" in kwargs:
                value = project
            elif kwargs["run__evidence_metadata__experiment_id"] == EXPERIMENT_ID:
                value = experiment
            else:
                value = ap1
            return [SimpleNamespace(actual_cost_microunits=None, reserved_cost_microunits=value)]

    monkeypatch.setattr(
        issue118_execution, "InvestigationProviderReservation", SimpleNamespace(objects=Manager())
    )
    assert issue118_execution.remaining_budget() == expected


def test_plan_order_is_versioned_and_hash_protected(plan, tmp_path):
    path = tmp_path / "plan.json"
    plan["plan_hash"] = digest({k: v for k, v in plan.items() if k != "plan_hash"})
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert read_plan(path)["slots"] == slots()
    plan["slots"].reverse()
    plan["plan_hash"] = digest({k: v for k, v in plan.items() if k != "plan_hash"})
    path.write_text(json.dumps(plan), encoding="utf-8")
    with pytest.raises(CommandError, match="order"):
        read_plan(path)


def test_fixture_proof_requires_both_exact_passed_tests(tmp_path):
    path = tmp_path / "fixtures.json"
    payload = {
        "tested_commit": "b7c7832f6436a487b4921fad68baa7a33466ef79",
        "test_selector": FIXTURE_TEST,
        "test_source_sha256": hashlib.sha256(
            (Path(settings.BASE_DIR) / ARCHIVED_SOURCE).read_bytes()
        ).hexdigest(),
        "passed_cases": list(AFFECTED_CASES),
        "junit_xml": (
            '<testsuite><testcase name="test_historical_early_read_survives_six_later_steps'
            '[AP4-02-R4-state-pattern]"/><testcase name="test_historical_early_read_survives_'
            'six_later_steps[AP4-04-R5-state-pattern]"/></testsuite>'
        ),
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert fixture_evidence(path, settings.BASE_DIR, payload["tested_commit"]) == payload
    payload["junit_xml"] = payload["junit_xml"].replace(
        "/></testsuite>", "><failure/></testcase></testsuite>"
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(CommandError, match="passed"):
        fixture_evidence(path, settings.BASE_DIR, payload["tested_commit"])


@pytest.fixture
def prepared(owner, business_unit, monkeypatch, tmp_path, plan):
    owner.business_unit = business_unit
    owner.save()
    control = tmp_path / "control"
    for spec in golden_case_specs().values():
        shutil.copytree(
            Path(settings.BASE_DIR) / spec["source_pack"], control / spec["source_pack"]
        )
    monkeypatch.setenv("ISSUE106_OWNER_USERNAME", owner.username)
    monkeypatch.setenv("ISSUE106_PRICE_INPUT_PER_MILLION", "1")
    monkeypatch.setenv("ISSUE106_PRICE_OUTPUT_PER_MILLION", "2")
    monkeypatch.setenv("ISSUE106_PRICING_CURRENCY", "USD")
    monkeypatch.setenv("ISSUE106_PRICING_VERSION", "synthetic")
    monkeypatch.setattr(prepare_issue118_experiment, "verify_checkout", lambda *a: "a" * 40)
    monkeypatch.setattr(prepare_issue118_experiment, "assert_schema_compatible", lambda *a: None)
    monkeypatch.setattr(prepare_issue118_experiment, "database_binding", lambda: "test-db")
    monkeypatch.setattr(prepare_issue118_experiment, "baseline_execution_lock", nullcontext)
    monkeypatch.setattr(
        prepare_issue118_experiment, "fixture_evidence", lambda *a: plan["fixture_evidence"]
    )
    snapshot_contract = {
        **plan["contracts"]["variant"],
        "runtime": {**plan["contracts"]["variant"]["runtime"], "code_revision": "a" * 40},
    }
    monkeypatch.setattr(
        prepare_issue118_experiment, "base_execution_snapshot", lambda *a, **kw: snapshot_contract
    )
    path = tmp_path / "plan.json"
    call_command(
        "prepare_issue118_experiment",
        expected_variant_commit="a" * 40,
        control_checkout=str(control),
        fixture_evidence="synthetic",
        plan=str(path),
    )
    frozen = read_plan(path)
    return frozen, path


@pytest.mark.django_db
def test_prepare_isolated_idempotent_without_ap1_changes(prepared, owner):
    from ki_radar.architecture.models import ProcessAnalysis

    plan, path = prepared
    assert ProcessAnalysis.objects.filter(name__startswith="Issue #118").count() == 25
    assert not ProcessAnalysis.objects.filter(name__startswith="Issue #106 AP1").exists()
    call_command(
        "prepare_issue118_experiment",
        expected_variant_commit="a" * 40,
        control_checkout=plan["control_root"],
        fixture_evidence="synthetic",
        plan=str(path),
    )
    assert ProcessAnalysis.objects.filter(name__startswith="Issue #118").count() == 25
    assert not InvestigationRun.objects.exists()


@pytest.mark.django_db
def test_real_start_requires_explicit_flag(prepared):
    _, path = prepared
    with pytest.raises(CommandError, match="confirm-real-provider"):
        call_command("run_issue118_variant", plan=str(path), case="AP4-01", repeat=1)


@pytest.mark.django_db
def test_control_direct_command_refuses_current_checkout(prepared, monkeypatch):
    _frozen, path = prepared
    monkeypatch.setattr(issue118_execution, "verify_checkout", lambda *a: "a" * 40)
    with pytest.raises(CommandError, match="wrong runtime checkout"):
        call_command(
            "run_issue118_control", plan=str(path), case="AP4-01", repeat=1, check_only=True
        )


@pytest.mark.django_db
def test_check_only_never_starts_provider_or_run(prepared, monkeypatch):
    frozen, path = prepared
    monkeypatch.setattr(issue118_execution, "verify_checkout", lambda *a: "a" * 40)
    monkeypatch.setattr(issue118_execution, "database_binding", lambda: "test-db")
    monkeypatch.setattr(issue118_execution, "baseline_execution_lock", nullcontext)
    monkeypatch.setattr(
        issue118_execution,
        "base_execution_snapshot",
        lambda *a, **kw: frozen["contracts"]["variant"],
    )
    # Simulate the historical v20 checkout for the historical harness success path.
    monkeypatch.setattr(
        "ki_radar.accelerator.investigation_runtime.LOOP_VERSION", "vs1-agent-loop-v20"
    )
    call_command("run_issue118_variant", plan=str(path), case="AP4-01", repeat=1, check_only=True)
    assert not InvestigationRun.objects.exists()
    with pytest.raises(CommandError, match="next slot"):
        call_command(
            "run_issue118_variant", plan=str(path), case="AP4-01", repeat=2, check_only=True
        )


@pytest.mark.django_db
def test_partial_export_shows_all_slots_and_preserves_review(prepared, monkeypatch, tmp_path):
    from ki_radar.accelerator.management.commands import export_issue118_experiment

    _frozen, path = prepared
    monkeypatch.setattr(export_issue118_experiment, "fixture_evidence", lambda *a: {})
    output = tmp_path / "experiment.json"
    review = tmp_path / "review.json"
    review.write_text('{"human_work":"preserve"}', encoding="utf-8")
    call_command(
        "export_issue118_experiment",
        plan=str(path),
        output=str(output),
        review_template=str(review),
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert len(payload["slots"]) == 25
    assert not payload["runs"]
    assert not payload["summary"]["population_complete"]
    assert review.read_text(encoding="utf-8") == '{"human_work":"preserve"}'
    with pytest.raises(CommandError, match="Incomplete"):
        call_command(
            "export_issue118_experiment",
            plan=str(path),
            output=str(output),
            review_template=str(review),
            require_complete=True,
        )


@pytest.mark.django_db
def test_export_cannot_overwrite_ap1(prepared, monkeypatch, tmp_path):
    from ki_radar.accelerator.management.commands import export_issue118_experiment

    _frozen, path = prepared
    monkeypatch.setattr(export_issue118_experiment, "fixture_evidence", lambda *a: {})
    with pytest.raises(CommandError, match="AP1"):
        call_command(
            "export_issue118_experiment",
            plan=str(path),
            output="artifacts/issue106/ap1/baseline.json",
            review_template=str(tmp_path / "review.json"),
        )


@pytest.mark.django_db
def test_interrupted_existing_run_fenced_no_replacement(
    owner, business_unit, tmp_path, monkeypatch
):
    from ki_radar.accelerator.investigation_models import (
        InvestigationEvidenceCampaign,
        InvestigationModelCall,
        InvestigationProviderReservation,
    )
    from tests.test_issue_3_investigation_hardening import start_csv_run

    process, _snapshot, handle, _source = start_csv_run(
        owner=owner, business_unit=business_unit, tmp_path=tmp_path
    )
    run = InvestigationRun.objects.get(pk=handle.run_id)
    campaign = InvestigationEvidenceCampaign.objects.create(
        process_analysis=process,
        campaign_key="issue118-test-interrupted",
        limits={"max_cost_microunits": 100},
        pricing={},
        currency="USD",
        pricing_version="synthetic",
        authorized_by=owner,
    )
    run.evidence_campaign = campaign
    # Evidence fields are immutable after start; test setup uses queryset update only.
    InvestigationRun.objects.filter(pk=run.pk).update(evidence_campaign=campaign)
    run.refresh_from_db()
    call = InvestigationModelCall.objects.create(
        run=run,
        role="planner",
        status="running",
        executor_generation=run.executor_generation,
        requested_model="test",
        prompt_version="test",
        prompt_hash="a" * 64,
        instruction_template="test",
        schema_version="test",
    )
    reservation = InvestigationProviderReservation.objects.create(
        campaign=campaign,
        run=run,
        model_call=call,
        reserved_input_tokens=1,
        reserved_output_tokens=1,
        reserved_cost_microunits=9,
    )
    runner = ExperimentRunner()
    monkeypatch.setattr(
        runner, "_execute_run", lambda **kw: pytest.fail("Interrupted slot must never rerun")
    )
    runner._handle_existing_run(run=run, case_id="AP4-01", repetition=1)
    run.refresh_from_db()
    reservation.refresh_from_db()
    assert run.status == "failed"
    assert run.clarification_payload["error_code"] == "execution_interrupted"
    assert reservation.status == "uncertain"
    assert ledger_cost([reservation]) == 9
    assert InvestigationRun.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize("check_only", [True, False])
def test_variant_execution_fails_closed_on_restored_v19(prepared, monkeypatch, check_only):
    _, path = prepared
    # Even if checkout verification were satisfied, a v19 runtime cannot run v20 slots.
    monkeypatch.setattr(issue118_execution, "verify_checkout", lambda *a: "a" * 40)
    with pytest.raises(CommandError, match="Wrong arm runtime"):
        call_command(
            "run_issue118_variant",
            plan=str(path),
            case="AP4-01",
            repeat=1,
            check_only=check_only,
            confirm_real_provider=True,
        )
    assert not InvestigationRun.objects.exists()
