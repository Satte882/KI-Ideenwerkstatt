from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed local git executable, shell=False
from dataclasses import replace
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ki_radar.accelerator.investigation_evidence import create_evidence_campaign
from ki_radar.accelerator.investigation_llm import (
    PlannerAction,
    request_planner_action,
    request_synthesis_package,
)
from ki_radar.accelerator.investigation_loop import run_until_boundary
from ki_radar.accelerator.investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationProviderReservation,
    InvestigationRun,
)
from ki_radar.accelerator.investigation_runtime import (
    DEFAULT_BUDGET,
    ENDPOINT_CAPABILITY,
    InvestigationRunError,
    StartInvestigationRequest,
    brief_hash,
    content_hash,
    normalize_decision_brief_payload,
    start_investigation,
)
from ki_radar.accelerator.issue118_experiment import pricing_from_env
from ki_radar.architecture.models import ProcessAnalysis

CONTRACT_PATH = "tests/fixtures/issue117_package3_contract_v1.json"
EXPERIMENT_ID = "issue117-package3-v1"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
REPLACEABLE_RUN_ID = "d6469021-d878-43de-9471-db97310edaf1"
REPLACEABLE_SLOT = "p3-c-ap4-02-missing-repair"


def _contract() -> dict[str, object]:
    path = Path(settings.BASE_DIR) / CONTRACT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandError(f"Could not load {CONTRACT_PATH}: {exc}") from exc
    if payload.get("schema_version") != "issue117-package3-contract-v1":
        raise CommandError("Unexpected Issue #117 Package 3 contract version.")
    return payload


def _process_name(slot_id: str) -> str:
    return f"Issue #117 Package 3 {slot_id}"


def _package_provider_usage() -> tuple[int, int]:
    reservations = InvestigationProviderReservation.objects.filter(
        run__evidence_metadata__experiment_id=EXPERIMENT_ID
    )
    calls = reservations.count()
    cost = 0
    for item in reservations:
        if item.actual_cost_microunits is not None:
            cost += int(item.actual_cost_microunits)
        elif item.reserved_cost_microunits is not None:
            cost += int(item.reserved_cost_microunits)
    return calls, cost


class Command(BaseCommand):
    help = "Run exactly one predeclared real-provider Issue #117 Package 3 slot."

    def add_arguments(self, parser):
        slot_ids = tuple(str(item["slot_id"]) for item in _contract()["slots"])
        parser.add_argument("--slot", choices=slot_ids, required=True)
        parser.add_argument(
            "--replace-run",
            help="Explicitly replace the single documented P3-C harness-control failure once.",
        )
        parser.add_argument(
            "--confirm-real-provider",
            action="store_true",
            help="Required acknowledgement that real provider calls and cost are allowed.",
        )

    def handle(self, *args, **options):
        if not options["confirm_real_provider"]:
            raise CommandError("--confirm-real-provider is required.")

        contract = _contract()
        slot = next(item for item in contract["slots"] if item["slot_id"] == options["slot"])
        tested_commit = self._tested_commit()
        self._assert_environment()
        self._assert_package_budget(contract)

        process = self._prepared_process(str(slot["slot_id"]))
        snapshots = list(
            process.investigation_source_snapshots.filter(process_version=process.version).order_by(
                "-revision"
            )
        )
        if len(snapshots) != 1:
            raise CommandError(
                f"{slot['slot_id']}: expected exactly one prepared current snapshot; "
                "run prepare_issue117_package3 first."
            )
        snapshot = snapshots[0]
        self._assert_snapshot_contract(snapshot, slot)

        handle, campaign = self._start_slot(
            process=process,
            snapshot=snapshot,
            slot=slot,
            contract=contract,
            tested_commit=tested_commit,
            replace_run=options.get("replace_run"),
        )

        mutation = slot.get("mutation")
        mutation_audit = {
            "declared": dict(mutation) if isinstance(mutation, dict) else None,
            "applied": False,
            "original_mapping": None,
            "mutated_mapping": None,
            "mutated_brief_hash": None,
            "model_call_id": None,
        }
        planner = request_planner_action
        synthesizer = request_synthesis_package
        if isinstance(mutation, dict):
            synthesizer = self._controlled_synthesizer(slot, mutation_audit)
            planner = self._controlled_synthesizer(
                slot, mutation_audit, requester=request_planner_action
            )

        try:
            result = run_until_boundary(
                actor=campaign.authorized_by,
                run_id=handle.run_id,
                executor_token=handle.executor_token,
                planner=planner,
                synthesizer=synthesizer,
            )
        except InvestigationRunError as exc:
            run = InvestigationRun.objects.get(pk=handle.run_id)
            self.stdout.write(
                "ISSUE117_P3_EVIDENCE "
                + json.dumps(
                    self._summary(run, slot, mutation_audit=mutation_audit),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
            raise CommandError(
                f"{slot['slot_id']}: investigation stopped with {exc.code}: {exc}"
            ) from exc

        run = InvestigationRun.objects.get(pk=result.run_id)
        summary = self._summary(run, slot, mutation_audit=mutation_audit)
        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE117_P3_EVIDENCE "
                + json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
            )
        )
        self._assert_mechanical_expectation(run, slot, mutation_audit)

    @transaction.atomic
    def _start_slot(self, *, process, snapshot, slot, contract, tested_commit, replace_run):
        # Serialize duplicate/replacement checks with creation, before any provider call.
        ProcessAnalysis.objects.select_for_update().get(pk=process.pk)
        self._assert_package_budget(contract)
        existing = list(
            InvestigationRun.objects.filter(
                evidence_metadata__experiment_id=EXPERIMENT_ID,
                evidence_metadata__slot_id=slot["slot_id"],
            )
        )
        replaced = self._replacement_target(slot, existing, replace_run)
        if replaced is not None and (
            replaced.process_analysis_id != process.pk or replaced.source_snapshot_id != snapshot.pk
        ):
            raise CommandError(
                "Replacement must reuse the original P3-C process and source snapshot."
            )
        if existing and replaced is None:
            if len(existing) > 1:
                raise CommandError(f"{slot['slot_id']}: duplicate Package 3 runs exist.")
            self.stdout.write(
                self.style.WARNING(
                    "ISSUE117_P3_EXISTING "
                    + json.dumps(self._summary(existing[0], slot, mutation_audit=None))
                )
            )
            raise CommandError(
                f"{slot['slot_id']}: a Package 3 run already exists; "
                "no automatic replacement or retry is allowed."
            )

        campaign = self._campaign(
            process=process, slot=slot, contract=contract, replacement=replaced is not None
        )
        mutation = slot.get("mutation")
        metadata = {
            "provider_mode": "real",
            "phase": "package3",
            "experiment_id": EXPERIMENT_ID,
            "slot_id": slot["slot_id"],
            "case_id": slot["case_id"],
            "test_type": slot["test_type"],
            "tested_commit": tested_commit,
            "control_mutation": dict(mutation) if isinstance(mutation, dict) else None,
            "contract_schema_version": contract["schema_version"],
        }
        suffix = "-replacement-1" if replaced is not None else ""
        if replaced is not None:
            metadata.update(
                replaces_run_id=str(replaced.pk),
                replacement_reason="package3_control_initial_synthesis_bypass",
            )

        try:
            handle = start_investigation(
                actor=campaign.authorized_by,
                request=StartInvestigationRequest(
                    snapshot_id=snapshot.pk,
                    idempotency_key=f"i117-{slot['slot_id']}-v1{suffix}",
                    evidence_campaign_id=campaign.pk,
                    execution_mode="adaptive",
                    evidence_metadata=metadata,
                    decision_brief_required=True,
                ),
            )
        except InvestigationRunError as exc:
            raise CommandError(f"{slot['slot_id']}: run could not start: {exc}") from exc

        if handle.reused:
            raise CommandError(
                f"{slot['slot_id']}: start unexpectedly reused an existing run; inspect manually."
            )

        return handle, campaign

    def _replacement_target(self, slot, existing, requested):
        if not requested:
            return None
        if slot["slot_id"] != REPLACEABLE_SLOT or str(requested) != REPLACEABLE_RUN_ID:
            raise CommandError("Replacement is restricted to the documented P3-C control failure.")
        if len(existing) != 1 or str(existing[0].pk) != REPLACEABLE_RUN_ID:
            raise CommandError(
                "Original P3-C run is missing or its one replacement already exists."
            )
        original = existing[0]
        if original.status != InvestigationRun.Status.FAILED:
            raise CommandError("Only the documented FAILED P3-C run may be replaced.")
        if original.evidence_metadata.get("replaces_run_id"):
            raise CommandError("A replacement cannot itself be replaced.")
        return original

    def _controlled_synthesizer(self, slot, mutation_audit, *, requester=None):
        requester = requester or request_synthesis_package
        mutation = dict(slot["mutation"])
        expected_keys = {str(item) for item in slot["case_keys"]}
        target_key = str(mutation["case_key"])

        def controlled(*, actor, run, executor_token) -> PlannerAction:
            action = requester(
                actor=actor,
                run=run,
                executor_token=executor_token,
            )
            if mutation_audit["applied"] or action.action != "synthesize":
                return action
            if not isinstance(action.brief_payload, dict):
                raise InvestigationRunError(
                    "Package 3 control requires a concrete brief payload.",
                    code="package3_control_precondition",
                )

            payload = json.loads(json.dumps(action.brief_payload))
            mappings = payload.get("structured_mappings")
            if not isinstance(mappings, list) or len(mappings) != 1:
                raise InvestigationRunError(
                    "Package 3 control requires exactly one structured mapping.",
                    code="package3_control_precondition",
                )
            assignments = mappings[0].get("assignments")
            if not isinstance(assignments, list):
                raise InvestigationRunError(
                    "Package 3 control requires a structured assignment list.",
                    code="package3_control_precondition",
                )
            by_key = {
                str(item.get("case_key") or ""): item
                for item in assignments
                if isinstance(item, dict)
            }
            if set(by_key) != expected_keys or len(assignments) != len(expected_keys):
                raise InvestigationRunError(
                    "Package 3 control mutation requires a complete first mapping.",
                    code="package3_control_precondition",
                )
            if target_key not in by_key:
                raise InvestigationRunError(
                    "Package 3 mutation target is missing from first mapping.",
                    code="package3_control_precondition",
                )

            mutation_audit["original_mapping"] = json.loads(json.dumps(mappings[0]))
            latest_call = run.model_calls.filter(role="synthesizer").order_by("-started_at").first()
            mutation_audit["model_call_id"] = (
                str(latest_call.pk) if latest_call is not None else None
            )

            if mutation["type"] == "drop_assignment":
                mappings[0]["assignments"] = [
                    item for item in assignments if str(item.get("case_key") or "") != target_key
                ]
            elif mutation["type"] == "replace_value":
                expected_value = str(slot["expected_assignments"][target_key])
                observed_value = str(by_key[target_key].get("value") or "")
                if observed_value != expected_value:
                    raise InvestigationRunError(
                        "Semantic negative control requires the original target value "
                        "to match the frozen human-review label.",
                        code="package3_control_precondition",
                    )
                wrong_value = str(mutation["value"])
                if wrong_value == expected_value:
                    raise InvestigationRunError(
                        "Semantic negative mutation must materially change the value.",
                        code="package3_control_precondition",
                    )
                by_key[target_key]["value"] = wrong_value
            else:
                raise InvestigationRunError(
                    "Unknown Package 3 control mutation.",
                    code="package3_control_precondition",
                )

            mutation_audit["applied"] = True
            mutation_audit["mutated_mapping"] = json.loads(json.dumps(mappings[0]))
            normalized_payload = normalize_decision_brief_payload(run, payload)
            mutation_audit["mutated_brief_hash"] = brief_hash(normalized_payload)
            return replace(action, brief_payload=payload)

        return controlled

    def _assert_mechanical_expectation(self, run, slot, mutation_audit) -> None:
        test_type = str(slot["test_type"])
        if test_type == "positive":
            if run.status != InvestigationRun.Status.READY:
                raise CommandError(
                    f"{slot['slot_id']}: positive run did not reach READY; keep as evidence."
                )
            return

        if not mutation_audit["applied"]:
            raise CommandError(f"{slot['slot_id']}: declared control mutation was never applied.")

        mutated_brief_hash = str(mutation_audit.get("mutated_brief_hash") or "")
        if not mutated_brief_hash:
            raise CommandError(f"{slot['slot_id']}: injected brief hash is missing from the audit.")

        if test_type == "controlled_missing_assignment_repair":
            repair_calls = list(
                run.model_calls.filter(
                    role="synthesizer",
                    context_refs__synthesis_mode="pre_verifier_repair",
                    status="success",
                ).order_by("started_at", "id")
            )
            if not repair_calls:
                raise CommandError(
                    f"{slot['slot_id']}: no successful real pre-verifier repair was observed."
                )
            if not any(
                str((call.context_refs or {}).get("brief_hash") or "") == mutated_brief_hash
                for call in repair_calls
            ):
                raise CommandError(
                    f"{slot['slot_id']}: repair was not bound to the injected incomplete brief."
                )
            if run.status != InvestigationRun.Status.READY:
                raise CommandError(
                    f"{slot['slot_id']}: real repair did not return the run to READY; "
                    "keep the run as evidence but do not claim repair success."
                )

            final_mappings = (
                run.brief_payload.get("structured_mappings")
                if isinstance(run.brief_payload, dict)
                else None
            )
            if not isinstance(final_mappings, list) or len(final_mappings) != 1:
                raise CommandError(
                    f"{slot['slot_id']}: repaired READY brief has no single structured mapping."
                )
            final_assignments = final_mappings[0].get("assignments")
            if not isinstance(final_assignments, list):
                raise CommandError(
                    f"{slot['slot_id']}: repaired READY brief has no assignment list."
                )
            final_by_key = {
                str(item.get("case_key") or ""): item
                for item in final_assignments
                if isinstance(item, dict)
            }
            expected_keys = {str(item) for item in slot["case_keys"]}
            if set(final_by_key) != expected_keys or len(final_assignments) != len(expected_keys):
                raise CommandError(
                    f"{slot['slot_id']}: repair did not restore the exact required case set."
                )

            original = mutation_audit.get("original_mapping") or {}
            original_assignments = original.get("assignments")
            if not isinstance(original_assignments, list):
                raise CommandError(
                    f"{slot['slot_id']}: original control mapping is unavailable for audit."
                )
            original_by_key = {
                str(item.get("case_key") or ""): item
                for item in original_assignments
                if isinstance(item, dict)
            }
            target_key = str(slot["mutation"]["case_key"])
            for case_key in sorted(expected_keys - {target_key}):
                if str(final_by_key[case_key].get("value") or "") != str(
                    original_by_key[case_key].get("value") or ""
                ):
                    raise CommandError(
                        f"{slot['slot_id']}: repair changed previously retained assignment "
                        f"{case_key}."
                    )
            if not str(final_by_key[target_key].get("value") or "").strip():
                raise CommandError(f"{slot['slot_id']}: repaired target assignment is still empty.")

            final_reports = list(run.verifier_reports.order_by("revision"))
            if not self._has_final_verifier(run, final_reports):
                raise CommandError(
                    f"{slot['slot_id']}: repaired READY brief lacks a fresh successful verifier."
                )
            return

        if test_type == "semantic_verifier_negative":
            reports = list(run.verifier_reports.order_by("revision"))
            reported_rejection = any(
                report.critical_findings > 0
                and str((report.bound_hashes or {}).get("brief") or "") == mutated_brief_hash
                for report in reports
            )
            if not reported_rejection and not self._negative_verifier_calls(
                run, mutated_brief_hash
            ):
                raise CommandError(
                    f"{slot['slot_id']}: no accepted real verifier critical finding "
                    "bound to the semantic negative-control brief."
                )

            if run.status == InvestigationRun.Status.READY:
                final_mappings = (
                    run.brief_payload.get("structured_mappings")
                    if isinstance(run.brief_payload, dict)
                    else None
                )
                if not isinstance(final_mappings, list) or len(final_mappings) != 1:
                    raise CommandError(
                        f"{slot['slot_id']}: final READY brief has no single structured mapping."
                    )
                final_assignments = final_mappings[0].get("assignments")
                if not isinstance(final_assignments, list):
                    raise CommandError(
                        f"{slot['slot_id']}: final READY brief has no assignment list."
                    )
                target_key = str(slot["mutation"]["case_key"])
                final_by_key = {
                    str(item.get("case_key") or ""): item
                    for item in final_assignments
                    if isinstance(item, dict)
                }
                expected_keys = {str(item) for item in slot["case_keys"]}
                if set(final_by_key) != expected_keys or len(final_assignments) != len(
                    expected_keys
                ):
                    raise CommandError(
                        f"{slot['slot_id']}: final READY brief lacks the exact required case set."
                    )
                # Frozen labels belong to this evidence harness, never to the product guard.
                if str(final_by_key[target_key].get("value") or "") != str(
                    slot["expected_assignments"][target_key]
                ):
                    raise CommandError(
                        f"{slot['slot_id']}: final READY brief has not restored the frozen "
                        "expected semantic value."
                    )
                if not self._has_final_verifier(run, reports):
                    raise CommandError(
                        f"{slot['slot_id']}: corrected READY brief lacks a fresh verifier."
                    )
            return

        raise CommandError(f"{slot['slot_id']}: unknown Package 3 test type.")

    @staticmethod
    def _negative_verifier_calls(run, mutated_brief_hash):
        # A validated critical response already proves rejection, even if it also
        # requests more evidence. It cannot authorize READY: that still requires
        # a completed successful report bound to the corrected final brief.
        calls = run.model_calls.filter(
            role="verifier", status="success", context_refs__brief_hash=mutated_brief_hash
        )
        return [
            call
            for call in calls
            if isinstance(call.accepted_payload, dict)
            and call.accepted_payload_hash == content_hash(call.accepted_payload)
            and any(
                isinstance(finding, dict) and finding.get("severity") == "critical"
                for finding in call.accepted_payload.get("findings", [])
            )
        ]

    @staticmethod
    def _has_final_verifier(run, reports) -> bool:
        if not reports or not run.brief_hash:
            return False
        latest = reports[-1]
        return (
            latest.success
            and latest.critical_findings == 0
            and str((latest.bound_hashes or {}).get("brief") or "") == run.brief_hash
        )

    def _prepared_process(self, slot_id: str) -> ProcessAnalysis:
        matches = list(
            ProcessAnalysis.objects.select_related("stage__value_stream").filter(
                name=_process_name(slot_id)
            )
        )
        if len(matches) != 1:
            raise CommandError(
                f"{slot_id}: prepared ProcessAnalysis missing; run prepare_issue117_package3 first."
            )
        return matches[0]

    def _assert_snapshot_contract(self, snapshot, slot) -> None:
        specs = snapshot.process_context.get("structured_mapping_specs")
        if not isinstance(specs, list) or len(specs) != 1:
            raise CommandError(f"{slot['slot_id']}: snapshot mapping spec is missing.")
        spec = specs[0]
        expected = {
            "source_filename": slot["source_filename"],
            "case_key_column": slot["case_key_column"],
            "case_keys": slot["case_keys"],
            "mapping_dimension": slot["mapping_dimension"],
            "exhaustive": True,
        }
        for key, value in expected.items():
            if spec.get(key) != value:
                raise CommandError(
                    f"{slot['slot_id']}: snapshot mapping contract differs in {key}."
                )
        source = snapshot.sources.filter(filename=slot["source_filename"]).first()
        if source is None or spec.get("source_content_sha256") != source.content_sha256:
            raise CommandError(f"{slot['slot_id']}: mapping source binding is invalid.")

    def _campaign(
        self, *, process, slot, contract, replacement=False
    ) -> InvestigationEvidenceCampaign:
        budget = contract["provider_budget"]
        max_cost = int(Decimal(str(budget["max_cost_usd"])) * Decimal("1000000"))
        used_calls, used_cost = _package_provider_usage()
        remaining_calls = int(budget["max_provider_calls_total"]) - used_calls
        remaining_cost = max_cost - used_cost
        if remaining_calls <= 0 or remaining_cost <= 0:
            raise CommandError("Issue #117 Package 3 provider budget is exhausted.")

        key = f"i117-p3-{slot['slot_id']}-v1"
        if replacement:
            key += "-replacement-1"
        existing = InvestigationEvidenceCampaign.objects.filter(campaign_key=key).first()
        pricing_data = pricing_from_env()
        pricing = pricing_data["rates"]
        currency = pricing_data["currency"]
        pricing_version = pricing_data["version"]
        if existing is not None:
            if existing.process_analysis_id != process.pk:
                raise CommandError(f"{slot['slot_id']}: campaign belongs to another process.")
            if existing.investigation_runs.exists():
                raise CommandError(f"{slot['slot_id']}: campaign already has a run.")
            return existing

        limits = {
            "max_provider_calls": min(10, remaining_calls),
            "max_input_tokens": int(DEFAULT_BUDGET["max_input_tokens"]),
            "max_output_tokens": int(DEFAULT_BUDGET["max_output_tokens"]),
            "max_cost_microunits": remaining_cost,
        }
        return create_evidence_campaign(
            actor=process.analyzed_by,
            process_analysis_id=process.pk,
            campaign_key=key,
            limits=limits,
            pricing=pricing,
            currency=currency,
            pricing_version=pricing_version,
        )

    def _assert_package_budget(self, contract) -> None:
        budget = contract["provider_budget"]
        runs = InvestigationRun.objects.filter(
            evidence_metadata__experiment_id=EXPERIMENT_ID
        ).count()
        calls, cost = _package_provider_usage()
        if runs >= int(budget["max_investigation_runs"]):
            raise CommandError("Issue #117 Package 3 run budget is exhausted.")
        if calls >= int(budget["max_provider_calls_total"]):
            raise CommandError("Issue #117 Package 3 provider-call budget is exhausted.")
        cap = int(Decimal(str(budget["max_cost_usd"])) * Decimal("1000000"))
        if cost >= cap:
            raise CommandError("Issue #117 Package 3 provider-cost budget is exhausted.")

    def _assert_environment(self) -> None:
        api_key = str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
        model = str(getattr(settings, "OPENROUTER_MODEL", "") or "").strip()
        if not api_key:
            raise CommandError("OPENROUTER_API_KEY is not configured.")
        if model != ENDPOINT_CAPABILITY["model"]:
            raise CommandError(
                "OPENROUTER_MODEL must match the frozen #117 execution contract exactly: "
                f"{ENDPOINT_CAPABILITY['model']}"
            )

    def _tested_commit(self) -> str:
        root = Path(settings.BASE_DIR)
        git = shutil.which("git")
        if not git:
            raise CommandError("Git is required for Package 3 commit binding.")
        try:
            status = subprocess.run(  # noqa: S603  # nosec B603 -- fixed argv
                [git, "status", "--porcelain", "--untracked-files=all"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                raise CommandError("Package 3 real runs require a clean worktree.")
            head = (
                subprocess.run(  # noqa: S603  # nosec B603 -- fixed argv
                    [git, "rev-parse", "HEAD"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                .stdout.strip()
                .lower()
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CommandError("Could not verify the Package 3 checkout.") from exc
        if not HEX40.fullmatch(head):
            raise CommandError("Could not resolve a valid Package 3 commit SHA.")
        explicit = os.getenv("ISSUE117_TESTED_COMMIT", "").strip().lower()
        if explicit and explicit != head:
            raise CommandError("ISSUE117_TESTED_COMMIT must exactly match checkout HEAD.")
        os.environ["GIT_COMMIT"] = head
        return head

    def _summary(self, run, slot, *, mutation_audit):
        run.refresh_from_db()
        verifier_reports = [
            {
                "revision": report.revision,
                "success": report.success,
                "critical_findings": report.critical_findings,
                "findings": report.findings,
                "bound_hashes": report.bound_hashes,
                "model_call_id": str(report.model_call_id),
            }
            for report in run.verifier_reports.order_by("revision")
        ]
        model_calls = [
            {
                "id": str(call.pk),
                "role": call.role,
                "status": call.status,
                "prompt_version": call.prompt_version,
                "schema_version": call.schema_version,
                "synthesis_trigger": str((call.context_refs or {}).get("synthesis_mode") or ""),
                "accepted_payload_hash": call.accepted_payload_hash,
                "context_refs": call.context_refs,
                "error_code": call.error_code,
            }
            for call in run.model_calls.order_by("started_at", "id")
        ]
        mappings = []
        if isinstance(run.brief_payload, dict):
            raw = run.brief_payload.get("structured_mappings")
            if isinstance(raw, list):
                mappings = raw
        return {
            "experiment_id": EXPERIMENT_ID,
            "slot_id": slot["slot_id"],
            "case_id": slot["case_id"],
            "test_type": slot["test_type"],
            "run_id": str(run.pk),
            "status": run.status,
            "tested_commit": run.evidence_metadata.get("tested_commit"),
            "replaces_run_id": run.evidence_metadata.get("replaces_run_id"),
            "replacement_reason": run.evidence_metadata.get("replacement_reason"),
            "contract_hash": run.contract_hash,
            "manifest_hash": run.manifest_hash,
            "final_brief_hash": run.brief_hash,
            "structured_mapping_obligations": run.execution_snapshot.get(
                "structured_mapping_obligations"
            ),
            "final_structured_mappings": mappings,
            "mutation_audit": mutation_audit,
            "verifier_reports": verifier_reports,
            "negative_verifier_responses": [
                {
                    "model_call_id": str(call.pk),
                    "brief_hash": call.context_refs["brief_hash"],
                    "accepted_payload_hash": call.accepted_payload_hash,
                    "findings": call.accepted_payload.get("findings", []),
                    "read_requests": call.accepted_payload.get("read_requests", []),
                    "completed_report": run.verifier_reports.filter(model_call_id=call.pk).exists(),
                }
                for call in self._negative_verifier_calls(
                    run, str((mutation_audit or {}).get("mutated_brief_hash") or "")
                )
            ]
            if slot["test_type"] == "semantic_verifier_negative"
            else [],
            "model_calls": model_calls,
            "usage": run.usage,
        }
