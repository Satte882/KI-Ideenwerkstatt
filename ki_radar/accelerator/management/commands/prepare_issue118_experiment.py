from __future__ import annotations

import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import CommandError
from django.db import transaction

from ki_radar.accelerator.investigation_models import InvestigationSourceFolder
from ki_radar.accelerator.investigation_runtime import DEFAULT_BUDGET, base_execution_snapshot
from ki_radar.accelerator.investigation_tools import SnapshotRequest, create_source_snapshot
from ki_radar.accelerator.issue106_baseline import golden_case_specs
from ki_radar.accelerator.issue118_execution import (
    assert_schema_compatible,
    database_binding,
    source_hash,
)
from ki_radar.accelerator.issue118_experiment import (
    CONTROL_COMMIT,
    EXPERIMENT_ID,
    LOOPS,
    digest,
    historical_reference,
    pricing_from_env,
    process_name,
    read_plan,
    slot_key,
    slots,
    technical_contract,
    verify_checkout,
)
from ki_radar.accelerator.issue118_fixtures import fixture_evidence
from ki_radar.accelerator.management.commands.prepare_issue106_baseline import Command as AP1Prepare
from ki_radar.accelerator.management.commands.run_issue106_baseline import baseline_execution_lock
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage


class Command(AP1Prepare):
    help = (
        "Prepare isolated #118 source snapshots and freeze one immutable 25-slot plan; no provider."
    )

    def add_arguments(self, parser):
        parser.add_argument("--expected-variant-commit", required=True)
        parser.add_argument("--control-checkout", required=True)
        parser.add_argument("--fixture-evidence", required=True)
        parser.add_argument("--plan", required=True)

    def handle(self, *args, **options):
        variant_root = Path(settings.BASE_DIR).resolve()
        control_root = Path(options["control_checkout"]).resolve()
        commit = verify_checkout(variant_root, options["expected_variant_commit"])
        assert_schema_compatible(variant_root, control_root)
        if variant_root == control_root or commit == CONTROL_COMMIT:
            raise CommandError("Two distinct v20/v19 checkouts required")
        pricing = pricing_from_env()
        reference = historical_reference()
        fixtures = fixture_evidence(options["fixture_evidence"], variant_root, commit)
        roots = {"variant": variant_root, "control": control_root}
        hashes = {}
        specs = golden_case_specs()
        for case in specs:
            values = {source_hash(root, case) for root in roots.values()}
            if len(values) != 1:
                raise CommandError("Arm source packs differ")
            hashes[case] = values.pop()
        path = Path(options["plan"]).resolve()
        if path.is_relative_to(variant_root) or path.is_relative_to(control_root):
            raise CommandError("Keep the plan/evidence outside both verified checkouts")
        owner_name = os.environ.get("ISSUE106_OWNER_USERNAME", "").strip() or "Satinder"
        try:
            owner = get_user_model().objects.get(username=owner_name, is_active=True)
        except get_user_model().DoesNotExist as exc:
            raise CommandError("Active experiment owner missing") from exc
        os.environ["GIT_COMMIT"] = commit
        # Reuse is allowed only when every frozen field and DB snapshot still matches.
        with baseline_execution_lock(), transaction.atomic():
            _stream, stage = self._ensure_stream(owner)
            prepared = {}
            contract = None
            for slot in slots():
                self.preparing_slot = slot
                case, repeat = slot["case_id"], slot["repetition"]
                spec = specs[case]
                process = self._ensure_process(
                    owner=owner,
                    stage=stage,
                    case_id=case,
                    repetition=repeat,
                    problem_statement=spec["problem_statement"],
                )
                root = roots[slot["arm"]] / spec["source_pack"]
                folder, _created = InvestigationSourceFolder.objects.get_or_create(
                    process_analysis=process,
                    root_path=str(root),
                    defaults={"name": process_name(slot), "registered_by": owner},
                )
                if not folder.is_active:
                    raise CommandError("Experiment source folder inactive")
                snapshot = self._matching_snapshot(
                    folder=folder,
                    process=process,
                    root=root,
                    filenames=tuple(spec["files"]),
                    decision_question=spec["problem_statement"],
                )
                if snapshot is None:
                    if process.investigation_runs.exists():
                        raise CommandError("Sources changed after an authoritative slot exists")
                    result = create_source_snapshot(
                        actor=owner,
                        request=SnapshotRequest(
                            process_analysis_id=process.pk,
                            folder_id=folder.pk,
                            decision_question=spec["problem_statement"],
                            run_limits={},
                        ),
                    )
                    snapshot = folder.snapshots.get(pk=result.snapshot_id)
                prepared[slot_key(slot)] = {
                    "process_id": str(process.pk),
                    "snapshot_id": str(snapshot.pk),
                    "manifest_hash": snapshot.manifest_hash,
                    "source_file_hashes": {
                        source.filename: source.content_sha256 for source in snapshot.sources.all()
                    },
                }
                raw = base_execution_snapshot(
                    snapshot, DEFAULT_BUDGET, process=process, decision_brief_required=True
                )
                current = technical_contract(raw)
                prepared[slot_key(slot)]["domain_input_hash"] = digest(
                    raw.get("domain_materialization_base")
                )
                if current["loop_version"] != LOOPS["variant"]:
                    raise CommandError("Preparation requires v20")
                if contract is not None and contract != current:
                    raise CommandError("Slot execution contracts differ")
                contract = current
            # All frozen prompt/transport/policy values must still match AP1.
            reference_contract = technical_contract(
                {**reference["runs"][0]["execution_contract"], "tools": contract["tools"]}
            )
            reference_contract["loop_version"] = LOOPS["variant"]
            if contract != reference_contract:
                raise CommandError(
                    "AP1 execution environment/contract changed; comparison requires re-gate"
                )
            control_contract = {**contract, "loop_version": LOOPS["control"]}
            plan = {
                "schema_version": EXPERIMENT_ID,
                "experiment_id": EXPERIMENT_ID,
                "variant_root": str(variant_root),
                "control_root": str(control_root),
                "variant_commit": commit,
                "control_commit": CONTROL_COMMIT,
                "database_binding": database_binding(),
                "pricing": pricing,
                "source_hashes": hashes,
                "ap1_hashes": reference["hashes"],
                "fixture_evidence": fixtures,
                "slots": slots(),
                "prepared": prepared,
                "contracts": {"variant": contract, "control": control_contract},
            }
            plan["plan_hash"] = digest(plan)
            if path.exists():
                if read_plan(path) != plan:
                    raise CommandError(
                        "Frozen plan already exists with different bindings; never overwrite"
                    )
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open("x", encoding="utf-8") as output:
                    output.write(json.dumps(plan, indent=2) + "\n")
        self.stdout.write("ISSUE118_PREPARED " + str(path))

    def _ensure_stream(self, owner):
        unit = owner.business_unit
        if unit is None or not unit.is_active:
            unit, _ = BusinessUnit.objects.get_or_create(
                name="Issue #106 Evidence", defaults={"is_active": True}
            )
        if not unit.is_active:
            raise CommandError("Experiment business unit inactive")
        stream, _ = ValueStream.objects.get_or_create(
            name="Issue #118 Experiment",
            defaults={
                "business_unit": unit,
                "owner": owner,
                "created_by": owner,
                "status": ValueStream.Status.ACTIVE,
            },
        )
        if (
            stream.owner_id != owner.pk
            or stream.business_unit_id != unit.pk
            or stream.status != ValueStream.Status.ACTIVE
        ):
            raise CommandError("Experiment stream owner/status conflict")
        stage, _ = ValueStreamStage.objects.get_or_create(
            value_stream=stream, sequence=1, defaults={"name": "Investigation Experiment"}
        )
        if stage.name != "Investigation Experiment":
            raise CommandError("Experiment stage conflict")
        return stream, stage

    def _ensure_process(
        self,
        *,
        owner,
        stage,
        case_id: str,
        repetition: int,
        problem_statement: str,
    ):
        name = process_name(self.preparing_slot)
        expected = {
            "scope_start": "Ein eingefrorener Fall liegt zur Investigation vor.",
            "scope_end": "Ein fachlich korrekter Investigation-Endzustand ist erreicht.",
            "trigger": "Der Baseline-Slot wird explizit gestartet.",
            "outcome": "READY, WAITING_HUMAN oder fachlich korrektes FAILED.",
            "current_flow": (
                "Evidenz untersuchen und Decision Brief bis zur fachlichen Grenze erzeugen."
            ),
            "roles": "Benchmark-Operator; fachliche Entscheidungen bleiben Human Authority.",
            "systems": "KI-Ideenwerkstatt Investigation",
            "data_objects": "Eingefrorener Source-Snapshot und persistierter Investigation-State.",
            "business_rules": "Keine Performance-Optimierung; aktueller #106-Contract ist bindend.",
            "handoffs": "",
            "bottlenecks": "Werden durch die Baseline nicht vorweggenommen.",
            "diagnostic_observations": problem_statement,
            "cause_hypotheses": "",
            "confirmed_causes": "",
            "constraints": "Nur die eingefrorenen Quellen und der aktuelle Execution Contract.",
            "exceptions": "",
            "baseline_metrics": "Noch nicht gemessen.",
        }
        matches = list(ProcessAnalysis.objects.select_for_update().filter(stage=stage, name=name))
        if len(matches) > 1:
            raise CommandError(f"{name}: multiple ProcessAnalysis records exist.")
        if matches:
            process = matches[0]
            if process.status != ProcessAnalysis.Status.DRAFT:
                raise CommandError(f"{name}: existing ProcessAnalysis is not DRAFT.")
            if process.analyzed_by_id != owner.pk:
                raise CommandError(f"{name}: existing ProcessAnalysis has a different owner.")
            for field, value in expected.items():
                if getattr(process, field) != value:
                    raise CommandError(
                        f"{name}: existing ProcessAnalysis differs in {field}; refusing overwrite."
                    )
            if process.solution_options.exists() or process.validations.exists():
                raise CommandError(f"{name}: benchmark ProcessAnalysis is no longer neutral.")
            return process
        return ProcessAnalysis.objects.create(
            stage=stage,
            name=name,
            status=ProcessAnalysis.Status.DRAFT,
            analyzed_by=owner,
            **expected,
        )
