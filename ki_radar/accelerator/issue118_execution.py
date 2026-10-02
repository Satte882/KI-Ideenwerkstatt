"""Isolated experiment orchestration around the unchanged investigation runtime."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, transaction

from .ap4_evidence import source_pack_hash
from .investigation_evidence import create_evidence_campaign
from .investigation_loop import run_until_boundary
from .investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationProviderReservation,
    InvestigationRun,
)
from .investigation_runtime import (
    DEFAULT_BUDGET,
    StartInvestigationRequest,
    base_execution_snapshot,
    start_investigation,
)
from .issue106_baseline import build_baseline_record, golden_case_specs
from .issue118_experiment import (
    ARMS,
    CONTROL_COMMIT,
    EXPERIMENT_ID,
    LOOPS,
    digest,
    git_output,
    historical_reference,
    pricing_from_env,
    process_name,
    read_plan,
    slot_key,
    slots,
    technical_contract,
    validate_record,
    verify_checkout,
)
from .management.commands.run_issue106_baseline import (
    Command as AP1Runner,
)
from .management.commands.run_issue106_baseline import baseline_execution_lock


def database_binding():
    if connection.vendor != "postgresql":
        raise CommandError("#118 execution/preparation requires PostgreSQL")
    config = settings.DATABASES["default"]
    return digest(
        {key: str(config.get(key, "")) for key in ("ENGINE", "NAME", "HOST", "PORT", "USER")}
    )


def experiment_runs():
    # Include malformed phases as well, so an accidental metadata edit cannot hide a slot.
    return InvestigationRun.objects.filter(evidence_metadata__experiment_id=EXPERIMENT_ID)


def ledger_cost(query):
    total = 0
    for row in query:
        amount = row.actual_cost_microunits
        if amount is None:
            amount = row.reserved_cost_microunits
        if amount is None:
            raise CommandError("Unpriced #106 reservation: cannot prove remaining budget")
        total += int(amount)
    return total


def remaining_budget():
    experiment = ledger_cost(
        InvestigationProviderReservation.objects.filter(
            run__evidence_metadata__experiment_id=EXPERIMENT_ID,
        )
    )
    project = ledger_cost(
        InvestigationProviderReservation.objects.filter(
            run__evidence_metadata__experiment_id__startswith="issue106-",
        )
    )
    # AP1 remains charged globally even if only its versioned archive is present
    # in a restored database. Take the larger live/archive amount, never both.
    ap1_live = ledger_cost(
        InvestigationProviderReservation.objects.filter(
            run__evidence_metadata__experiment_id="issue106-ap1-baseline-v1",
        )
    )
    archive = historical_reference(Path(__file__).resolve().parents[2])
    ap1_archive = round(archive["summary"]["total_budget_accounted_cost_usd"] * 1_000_000)
    project += max(0, ap1_archive - ap1_live)
    return min(20_000_000 - experiment, 60_000_000 - project)


def assert_schema_compatible(variant_root, control_root):
    # ORM dependencies and all migrations, not only the accelerator app.
    changed = git_output(
        variant_root,
        "diff",
        "--name-only",
        CONTROL_COMMIT,
        "HEAD",
        "--",
        "ki_radar",
        "config",
        "pyproject.toml",
        "uv.lock",
    )
    forbidden = [
        name
        for name in changed.splitlines()
        if (
            "/migrations/" in name
            or name.endswith("models.py")
            or name.startswith("config/")
            or name in {"pyproject.toml", "uv.lock"}
        )
    ]
    if forbidden:
        raise CommandError("Shared DB/runtime compatibility unproven: " + ", ".join(forbidden))
    verify_checkout(control_root, CONTROL_COMMIT)


def source_hash(root, case):
    spec = golden_case_specs()[case]
    folder = Path(root) / spec["source_pack"]
    actual_files = sorted(p.name for p in folder.iterdir() if p.is_file())
    if actual_files != sorted(spec["files"]):
        raise CommandError("Wrong frozen source-pack file set")
    result = source_pack_hash(folder, spec["files"])
    if result not in spec["quality_contract"]["source_pack_hashes"]:
        raise CommandError("Wrong AP0 source-pack hash")
    return result


def assert_snapshot(snapshot, root, case, binding):
    spec = golden_case_specs()[case]
    if (
        str(snapshot.pk) != binding["snapshot_id"]
        or snapshot.manifest_hash != binding["manifest_hash"]
        or snapshot.process_version != snapshot.process_analysis.version
        or snapshot.decision_question != spec["problem_statement"]
        or snapshot.run_limits != {}
    ):
        raise CommandError("Prepared source snapshot/decision question changed")
    sources = {s.filename: s for s in snapshot.sources.all()}
    if set(sources) != set(spec["files"]):
        raise CommandError("Snapshot source file set changed")
    for filename, source in sources.items():
        file = Path(root) / spec["source_pack"] / filename
        if source.content_sha256 != hashlib.sha256(file.read_bytes()).hexdigest():
            raise CommandError("Snapshot content differs from frozen source pack")


def build_record(run):
    record = build_baseline_record(run)
    metadata = run.evidence_metadata or {}
    for key in ("arm", "phase", "plan_hash", "source_pack_hash"):
        record[key] = metadata.get(key)
    record["execution_contract"] = technical_contract(run.execution_snapshot)
    record["source_file_hashes"] = {
        source.filename: source.content_sha256 for source in run.source_snapshot.sources.all()
    }
    record["domain_input_hash"] = digest(run.execution_snapshot.get("domain_materialization_base"))
    record["failure_codes"] = {}
    codes = list(run.model_calls.exclude(error_code="").values_list("error_code", flat=True))
    codes += list(run.steps.exclude(error_code="").values_list("error_code", flat=True))
    terminal_code = (run.clarification_payload or {}).get("error_code")
    if terminal_code and terminal_code not in codes:
        codes.append(terminal_code)
    for code in codes:
        if code:
            record["failure_codes"][code] = record["failure_codes"].get(code, 0) + 1
    tools = record["performance"]["tool_steps"]
    for role in ("planner", "synthesizer", "verifier"):
        record["performance"]["role_totals"].setdefault(role, {"calls": 0, "seconds": 0})
    record["tool_totals"] = {
        "calls": len(tools),
        "seconds": sum(step["duration_seconds"] or 0 for step in tools),
    }
    record["events"] = {
        name: bool(record["recovery"].get(f"has_{name}"))
        for name in ("timeout", "retry", "repair", "invalid_response")
    }
    record["events"].update(
        no_progress=bool(record["failure_codes"].get("no_progress_loop")),
        contract_error=bool(record["failure_codes"].get("structured_contract_error")),
    )
    record["deterministic_checks"] = {
        "terminal_state": record["terminal_state_check"],
        "source_manifest_hash": run.manifest_hash,
        "source_file_hashes": record["source_file_hashes"],
        "execution_contract_hash": digest(record["execution_contract"]),
    }
    return record


def assert_population_order(records, requested):
    by_slot = {}
    order = slots()
    for record in records:
        slot = {key: record[key] for key in ("arm", "case_id", "repetition")}
        key = slot_key(slot)
        if key in by_slot:
            raise CommandError("Duplicate experiment slot")
        by_slot[key] = record
    # Existing runs must form an authoritative prefix in actual start order.
    observed = sorted(records, key=lambda r: r["performance"]["started_at"])
    observed_keys = [
        slot_key({k: r[k] for k in ("arm", "case_id", "repetition")}) for r in observed
    ]
    if observed_keys != [slot_key(s) for s in order[: len(observed)]]:
        raise CommandError("Stored run start order differs from frozen sequence")
    running = [r for r in records if not r["terminal_state_check"]["system_boundary_reached"]]
    key = slot_key(requested)
    if running and (len(running) != 1 or running[0] != by_slot.get(key)):
        raise CommandError("Recover the existing RUNNING slot before starting another")
    if key not in by_slot and (len(records) >= 25 or requested != order[len(records)]):
        raise CommandError("Wrong next slot; frozen sequence cannot be skipped")


class ExperimentRunner(AP1Runner):
    arm = "variant"
    help = "Run/check one frozen #118 slot, preserving every authoritative attempt."

    def add_arguments(self, parser):
        parser.add_argument("--plan", required=True)
        parser.add_argument("--case", required=True)
        parser.add_argument("--repeat", type=int, required=True)
        parser.add_argument("--check-only", action="store_true")
        parser.add_argument("--confirm-real-provider", action="store_true")

    def handle(self, *args, **options):
        plan = read_plan(options["plan"])
        slot = {"arm": self.arm, "case_id": options["case"], "repetition": options["repeat"]}
        try:
            slot_key(slot)
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        if not options["check_only"] and not options["confirm_real_provider"]:
            raise CommandError("--confirm-real-provider is required for execution")
        self.plan = plan
        self.slot = slot
        for arm in ARMS:
            verify_checkout(plan[f"{arm}_root"], plan[f"{arm}_commit"])
            for case in golden_case_specs():
                if source_hash(plan[f"{arm}_root"], case) != plan["source_hashes"][case]:
                    raise CommandError("Source packs differ between frozen arms")
        if Path(settings.BASE_DIR).resolve() != Path(plan[f"{self.arm}_root"]).resolve():
            raise CommandError("Command loaded in the wrong runtime checkout")
        from . import investigation_runtime

        if LOOPS[self.arm] != investigation_runtime.LOOP_VERSION:
            raise CommandError("Wrong arm runtime; controls require the historical bridge")
        if database_binding() != plan["database_binding"]:
            raise CommandError("Wrong experiment database")
        if pricing_from_env() != plan["pricing"]:
            raise CommandError("Pricing changed after preparation")
        if historical_reference(plan["variant_root"])["hashes"] != plan["ap1_hashes"]:
            raise CommandError("AP1 reference changed")
        os.environ["GIT_COMMIT"] = plan[f"{self.arm}_commit"]
        for name in ("RENDER_GIT_COMMIT", "SOURCE_VERSION", "ISSUE106_TESTED_COMMIT"):
            if os.environ.get(name) and os.environ[name] != plan[f"{self.arm}_commit"]:
                raise CommandError(f"{name} conflicts with the verified runtime checkout")
        # AP1's project lock is also held: an old AP1 command cannot spend against
        # the global #106 cap concurrently. Same lock serializes both #118 arms.
        with baseline_execution_lock():
            with transaction.atomic():
                self._preflight()
            if options["check_only"]:
                self.stdout.write("ISSUE118_CHECK_OK " + json.dumps(slot))
                return
            self._run_experiment_slot()

    def _preflight(self):
        records = [build_record(run) for run in experiment_runs()]
        for record in records:
            try:
                validate_record(record, self.plan)
            except ValueError as exc:
                raise CommandError(str(exc)) from exc
        for run in experiment_runs().select_related("evidence_campaign"):
            campaign = run.evidence_campaign
            pricing = self.plan["pricing"]
            slot = {key: run.evidence_metadata[key] for key in ("arm", "case_id", "repetition")}
            if (
                campaign is None
                or campaign.campaign_key != slot_key(slot)
                or campaign.process_analysis_id != run.process_analysis_id
                or campaign.revision != 1
                or campaign.pricing != pricing["rates"]
                or campaign.currency != pricing["currency"]
                or campaign.pricing_version != pricing["version"]
            ):
                raise CommandError("Existing authoritative slot campaign binding changed")
        assert_population_order(records, self.slot)
        key = slot_key(self.slot)
        binding = self.plan["prepared"][key]
        from ki_radar.architecture.models import ProcessAnalysis

        try:
            process = ProcessAnalysis.objects.get(
                pk=binding["process_id"], name=process_name(self.slot)
            )
            snapshot = process.investigation_source_snapshots.get(pk=binding["snapshot_id"])
        except (ProcessAnalysis.DoesNotExist, KeyError) as exc:
            raise CommandError("Prepared slot missing") from exc
        if (
            process.status != ProcessAnalysis.Status.DRAFT
            or process.solution_options.exists()
            or process.validations.exists()
        ):
            raise CommandError("Prepared process is no longer neutral DRAFT")
        assert_snapshot(snapshot, self.plan[f"{self.arm}_root"], self.slot["case_id"], binding)
        current = base_execution_snapshot(
            snapshot, DEFAULT_BUDGET, process=process, decision_brief_required=True
        )
        if technical_contract(current) != self.plan["contracts"][self.arm]:
            raise CommandError("Live execution contract differs from frozen plan")
        if digest(current.get("domain_materialization_base")) != binding["domain_input_hash"]:
            raise CommandError("Neutral domain inputs changed after preparation")
        self.process, self.snapshot = process, snapshot
        process_runs = list(process.investigation_runs.values_list("pk", flat=True))
        expected_ids = {str(run.pk) for run in experiment_runs().filter(process_analysis=process)}
        if len(process_runs) > 1 or {str(pk) for pk in process_runs} != expected_ids:
            raise CommandError("Foreign/duplicate run occupies the authoritative process slot")
        # Terminal reuse/recovery must remain available after budget exhaustion.
        if (
            remaining_budget() <= 0
            and not experiment_runs()
            .filter(
                evidence_metadata__arm=self.arm,
                evidence_metadata__case_id=self.slot["case_id"],
                evidence_metadata__repetition=self.slot["repetition"],
            )
            .exists()
        ):
            raise CommandError("Shared experiment/global #106 budget exhausted")

    def _run_experiment_slot(self):
        case, repeat = self.slot["case_id"], self.slot["repetition"]
        existing = (
            experiment_runs()
            .select_related("evidence_campaign__authorized_by")
            .filter(
                evidence_metadata__arm=self.arm,
                evidence_metadata__case_id=case,
                evidence_metadata__repetition=repeat,
            )
            .first()
        )
        if existing:
            self._handle_existing_run(run=existing, case_id=case, repetition=repeat)
            return
        self._assert_environment()
        key = slot_key(self.slot)
        pricing = self.plan["pricing"]
        limits = {
            "max_provider_calls": DEFAULT_BUDGET["max_model_calls"],
            "max_input_tokens": DEFAULT_BUDGET["max_input_tokens"],
            "max_output_tokens": DEFAULT_BUDGET["max_output_tokens"],
            "max_cost_microunits": remaining_budget(),
        }
        campaign = InvestigationEvidenceCampaign.objects.filter(campaign_key=key).first()
        if campaign:
            if (
                campaign.process_analysis_id != self.process.pk
                or campaign.pricing != pricing["rates"]
                or campaign.pricing_version != pricing["version"]
                or campaign.currency != "USD"
                or campaign.revision != 1
                or campaign.investigation_runs.exists()
                or any(campaign.limits.get(k) != v for k, v in limits.items())
            ):
                raise CommandError("Stale/conflicting slot campaign; refusing new attempt")
        else:
            campaign = create_evidence_campaign(
                actor=self.process.analyzed_by,
                process_analysis_id=self.process.pk,
                campaign_key=key,
                limits=limits,
                pricing=pricing["rates"],
                currency=pricing["currency"],
                pricing_version=pricing["version"],
            )
        metadata = {
            "provider_mode": "real",
            "phase": "experiment",
            "variant": self.arm,
            "experiment_id": EXPERIMENT_ID,
            **self.slot,
            "tested_commit": self.plan[f"{self.arm}_commit"],
            "plan_hash": self.plan["plan_hash"],
            "source_pack_hash": self.plan["source_hashes"][case],
            "execution_contract": self.plan["contracts"][self.arm],
        }
        handle = start_investigation(
            actor=campaign.authorized_by,
            request=StartInvestigationRequest(
                snapshot_id=self.snapshot.pk,
                idempotency_key=key,
                evidence_campaign_id=campaign.pk,
                execution_mode="adaptive",
                evidence_metadata=metadata,
                decision_brief_required=True,
            ),
        )
        self._execute_run(
            run_id=handle.run_id,
            actor=campaign.authorized_by,
            executor_token=handle.executor_token,
            case_id=case,
            repetition=repeat,
        )

    def _execute_run(self, *, run_id, actor, executor_token, case_id, repetition):
        # Existing campaign cap bounds every reservation; no cap expansion on resume.
        self._assert_environment()
        run = InvestigationRun.objects.select_related("evidence_campaign").get(pk=run_id)
        campaign_headroom = run.evidence_campaign.limits["max_cost_microunits"] - ledger_cost(
            run.evidence_campaign.provider_reservations.all()
        )
        if campaign_headroom > remaining_budget():
            raise CommandError(
                "Shared budget changed during interruption; resume requires parent re-gate"
            )
        result = run_until_boundary(actor=actor, run_id=run_id, executor_token=executor_token)
        record = build_record(InvestigationRun.objects.get(pk=result.run_id))
        self.stdout.write(
            "ISSUE118_SLOT_FINISHED "
            + json.dumps(
                {
                    "arm": self.arm,
                    "case_id": case_id,
                    "repetition": repetition,
                    "run_id": record["run_id"],
                    "status": record["status"],
                }
            )
        )

    def _handle_existing_run(self, *, run, case_id, repetition):
        if run.status != InvestigationRun.Status.RUNNING:
            self.stdout.write(f"ISSUE118_SLOT_REUSED {run.pk} {run.status}")
            return
        # AP1's proven fencing/resume implementation operates on this exact run,
        # never looks up an AP1 slot and never starts a replacement investigation.
        super()._handle_existing_run(run=run, case_id=case_id, repetition=repetition)
