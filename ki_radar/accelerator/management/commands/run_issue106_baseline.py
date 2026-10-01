from __future__ import annotations

import json
import os
import re
import shutil
import subprocess  # nosec B404 -- fixed local git executable, shell=False
import uuid
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from ki_radar.accelerator.investigation_evidence import (
    create_evidence_campaign,
    mark_provider_attempt_uncertain,
)
from ki_radar.accelerator.investigation_loop import run_until_boundary
from ki_radar.accelerator.investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationProviderReservation,
    InvestigationRun,
)
from ki_radar.accelerator.investigation_runtime import (
    DEFAULT_BUDGET,
    InvestigationRunError,
    StartInvestigationRequest,
    start_investigation,
)
from ki_radar.accelerator.issue106_baseline import (
    EXPERIMENT_ID,
    GOLDEN_CASE_IDS,
    REPETITIONS,
    baseline_runs,
    baseline_slots,
    build_baseline_record,
    consumed_or_reserved_cost_microunits,
    golden_case_specs,
    performance_contract,
    slot_campaign_key,
    slot_process_name,
)
from ki_radar.architecture.models import ProcessAnalysis

HEX40 = re.compile(r"^[0-9a-f]{40}$")
AP1_LOCK_NAMESPACE = 106
AP1_LOCK_KEY = 111


@contextmanager
def baseline_execution_lock():
    """Serialize all real-provider AP1 slots across command processes."""
    if connection.vendor != "postgresql":
        raise CommandError(
            "Real AP1 baseline execution requires PostgreSQL so the project-wide "
            "advisory lock can protect the shared provider-cost budget."
        )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_try_advisory_lock(%s, %s)",
            [AP1_LOCK_NAMESPACE, AP1_LOCK_KEY],
        )
        row = cursor.fetchone()
    if not row or not bool(row[0]):
        raise CommandError(
            "Another Issue #106 AP1 baseline command currently owns the project lock."
        )
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_unlock(%s, %s)",
                [AP1_LOCK_NAMESPACE, AP1_LOCK_KEY],
            )


class Command(BaseCommand):
    help = "Run one or all controlled real-provider #106/AP1 baseline slots."

    def add_arguments(self, parser):
        parser.add_argument("--case", choices=GOLDEN_CASE_IDS)
        parser.add_argument("--repeat", type=int)
        parser.add_argument(
            "--all",
            action="store_true",
            dest="run_all",
            help="Run all still-empty 5x5 baseline slots serially.",
        )
        parser.add_argument(
            "--confirm-real-provider",
            action="store_true",
            help="Required acknowledgement that real provider calls and cost are allowed.",
        )

    def handle(self, *args, **options):
        if not options["confirm_real_provider"]:
            raise CommandError("--confirm-real-provider is required.")
        run_all = bool(options["run_all"])
        case_id = options.get("case")
        repetition = options.get("repeat")
        if run_all and (case_id or repetition is not None):
            raise CommandError("--all cannot be combined with --case/--repeat.")
        if not run_all and (not case_id or repetition not in REPETITIONS):
            raise CommandError("Use --all or provide --case and --repeat 1..5.")

        tested_commit = self._tested_commit()
        self._assert_environment()
        slots = baseline_slots() if run_all else ((case_id, int(repetition)),)

        with baseline_execution_lock():
            self._assert_existing_commit_binding(tested_commit)
            for slot_case, slot_repeat in slots:
                self._run_slot(
                    case_id=slot_case,
                    repetition=slot_repeat,
                    tested_commit=tested_commit,
                )

    def _assert_existing_commit_binding(self, tested_commit: str) -> None:
        metadata_rows = list(baseline_runs().values_list("evidence_metadata", flat=True))
        if not metadata_rows:
            return
        commits = [str((item or {}).get("tested_commit") or "").lower() for item in metadata_rows]
        if any(not HEX40.fullmatch(value) for value in commits):
            raise CommandError(
                "Existing AP1 baseline population contains a missing or invalid tested_commit."
            )
        if set(commits) != {tested_commit}:
            raise CommandError(
                "Existing AP1 baseline runs use a different tested commit: "
                + ", ".join(sorted(set(commits)))
            )

    def _run_slot(self, *, case_id: str, repetition: int, tested_commit: str) -> None:
        existing = list(
            baseline_runs()
            .select_related("evidence_campaign__authorized_by")
            .filter(
                evidence_metadata__case_id=case_id,
                evidence_metadata__repetition=repetition,
            )
        )
        if len(existing) > 1:
            raise CommandError(f"{case_id} R{repetition}: duplicate baseline runs exist.")
        if existing:
            self._handle_existing_run(
                run=existing[0],
                case_id=case_id,
                repetition=repetition,
            )
            return

        if baseline_runs().filter(status=InvestigationRun.Status.RUNNING).exists():
            raise CommandError(
                "Another Issue #106 AP1 run is currently RUNNING; baseline execution is serial."
            )

        process_name = slot_process_name(case_id, repetition)
        matches = list(
            ProcessAnalysis.objects.select_related("stage__value_stream").filter(name=process_name)
        )
        if len(matches) != 1:
            raise CommandError(
                f"{case_id} R{repetition}: prepared ProcessAnalysis missing; "
                "run prepare_issue106_baseline first."
            )
        process = matches[0]
        snapshots = list(
            process.investigation_source_snapshots.filter(process_version=process.version).order_by(
                "-revision"
            )
        )
        if len(snapshots) != 1:
            raise CommandError(
                f"{case_id} R{repetition}: expected exactly one prepared current snapshot."
            )
        snapshot = snapshots[0]
        self._assert_source_pack(case_id=case_id)

        contract = performance_contract()
        baseline_cap_usd = Decimal(
            str(contract["experiment_budget"]["baseline_provider_cost_cap_usd"])
        )
        project_cap_microunits = int(baseline_cap_usd * Decimal("1000000"))
        consumed = consumed_or_reserved_cost_microunits()
        remaining = project_cap_microunits - consumed
        if remaining <= 0:
            raise CommandError("Issue #106 AP1 provider-cost budget is exhausted.")

        campaign = self._campaign(
            process=process,
            case_id=case_id,
            repetition=repetition,
            remaining_cost_microunits=remaining,
        )
        metadata = {
            "provider_mode": "real",
            "phase": "baseline",
            "variant": "baseline",
            "experiment_id": EXPERIMENT_ID,
            "contract_version": contract["contract_version"],
            "case_id": case_id,
            "repetition": repetition,
            "tested_commit": tested_commit,
        }
        idempotency_key = f"i106-{case_id.lower()}-r{repetition}-base-v1"

        try:
            handle = start_investigation(
                actor=campaign.authorized_by,
                request=StartInvestigationRequest(
                    snapshot_id=snapshot.pk,
                    idempotency_key=idempotency_key,
                    evidence_campaign_id=campaign.pk,
                    execution_mode="adaptive",
                    evidence_metadata=metadata,
                    decision_brief_required=True,
                ),
            )
        except InvestigationRunError as exc:
            raise CommandError(f"{case_id} R{repetition}: run could not start: {exc}") from exc

        if handle.reused:
            reused = InvestigationRun.objects.select_related(
                "evidence_campaign__authorized_by"
            ).get(pk=handle.run_id)
            self._handle_existing_run(run=reused, case_id=case_id, repetition=repetition)
            return

        self._execute_run(
            run_id=handle.run_id,
            actor=campaign.authorized_by,
            executor_token=handle.executor_token,
            case_id=case_id,
            repetition=repetition,
        )

    def _handle_existing_run(
        self,
        *,
        run: InvestigationRun,
        case_id: str,
        repetition: int,
    ) -> None:
        if run.status != InvestigationRun.Status.RUNNING:
            record = build_baseline_record(run)
            self.stdout.write(
                self.style.WARNING(
                    "ISSUE106_AP1_SLOT_REUSED "
                    + json.dumps(
                        {
                            "case_id": case_id,
                            "repetition": repetition,
                            "run_id": record["run_id"],
                            "status": record["status"],
                            "cost_usd": record["performance"]["cost_usd"],
                        },
                        separators=(",", ":"),
                    )
                )
            )
            return

        if run.evidence_campaign is None:
            raise CommandError(
                f"{case_id} R{repetition}: RUNNING baseline run has no evidence campaign."
            )

        open_reservation_ids = list(
            run.provider_reservations.filter(
                status=InvestigationProviderReservation.Status.OPEN
            ).values_list("pk", flat=True)
        )
        has_inflight_state = bool(
            open_reservation_ids
            or run.model_calls.filter(status="running").exists()
            or run.steps.filter(status="running").exists()
        )
        if has_inflight_state:
            self._fence_interrupted_run(
                run=run,
                open_reservation_ids=open_reservation_ids,
            )
            self.stdout.write(
                self.style.WARNING(
                    f"{case_id} R{repetition}: interrupted in-flight provider state was "
                    f"preserved as FAILED on existing run {run.pk}; no replacement run started."
                )
            )
            return

        self.stdout.write(
            self.style.WARNING(
                f"{case_id} R{repetition}: resuming existing RUNNING baseline run {run.pk}."
            )
        )
        self._execute_run(
            run_id=run.pk,
            actor=run.evidence_campaign.authorized_by,
            executor_token=run.executor_token,
            case_id=case_id,
            repetition=repetition,
        )

    def _fence_interrupted_run(
        self,
        *,
        run: InvestigationRun,
        open_reservation_ids,
    ) -> None:
        for reservation_id in open_reservation_ids:
            mark_provider_attempt_uncertain(
                reservation_id=reservation_id,
                reason="baseline_execution_interrupted",
            )

        with transaction.atomic():
            current = InvestigationRun.objects.select_for_update().get(pk=run.pk)
            if current.status != InvestigationRun.Status.RUNNING:
                return
            now = timezone.now()
            current.model_calls.filter(status="running").update(
                status="discarded",
                finished_at=now,
                error_code="execution_interrupted",
            )
            current.steps.filter(status="running").update(
                status="discarded",
                finished_at=now,
                error_code="execution_interrupted",
            )
            current.status = InvestigationRun.Status.FAILED
            current.finished_at = now
            current.clarification_reason = "technical_failure"
            current.clarification_payload = {
                "error_code": "execution_interrupted",
                "impact": (
                    "Die AP1-Ausführung wurde mit offenem Provider-/Schrittzustand "
                    "unterbrochen; der tatsächliche Providerverbrauch kann teilweise "
                    "unklar sein."
                ),
                "required_action": (
                    "Run als fehlgeschlagene Baseline-Evidence behalten; keinen "
                    "Ersatzlauf für denselben Slot starten."
                ),
            }
            current.executor_generation += 1
            current.executor_token = uuid.uuid4()
            current.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "clarification_reason",
                    "clarification_payload",
                    "executor_generation",
                    "executor_token",
                    "updated_at",
                ]
            )

    def _execute_run(
        self,
        *,
        run_id,
        actor,
        executor_token,
        case_id: str,
        repetition: int,
    ) -> None:
        try:
            result = run_until_boundary(
                actor=actor,
                run_id=run_id,
                executor_token=executor_token,
            )
        except InvestigationRunError as exc:
            raise CommandError(f"{case_id} R{repetition}: investigation failed: {exc}") from exc

        run = InvestigationRun.objects.get(pk=result.run_id)
        record = build_baseline_record(run)
        contract = performance_contract()
        baseline_cap_usd = Decimal(
            str(contract["experiment_budget"]["baseline_provider_cost_cap_usd"])
        )
        project_cap_microunits = int(baseline_cap_usd * Decimal("1000000"))
        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE106_AP1_SLOT_FINISHED "
                + json.dumps(
                    {
                        "case_id": case_id,
                        "repetition": repetition,
                        "run_id": str(result.run_id),
                        "status": result.status,
                        "run_seconds": record["performance"]["run_seconds"],
                        "cost_usd": record["performance"]["cost_usd"],
                        "remaining_project_cost_usd": round(
                            (project_cap_microunits - consumed_or_reserved_cost_microunits())
                            / 1_000_000,
                            6,
                        ),
                    },
                    separators=(",", ":"),
                )
            )
        )

    def _campaign(
        self,
        *,
        process,
        case_id: str,
        repetition: int,
        remaining_cost_microunits: int,
    ) -> InvestigationEvidenceCampaign:
        key = slot_campaign_key(case_id, repetition)
        existing = InvestigationEvidenceCampaign.objects.filter(campaign_key=key).first()
        pricing = self._pricing_from_env()
        currency = os.getenv("ISSUE106_PRICING_CURRENCY", "USD").strip().upper()
        pricing_version = os.getenv("ISSUE106_PRICING_VERSION", "").strip()
        if currency != "USD" or not pricing_version:
            raise CommandError("Issue #106 pricing requires USD and ISSUE106_PRICING_VERSION.")
        if existing is not None:
            if existing.process_analysis_id != process.pk:
                raise CommandError(f"{case_id} R{repetition}: campaign belongs to another slot.")
            if existing.pricing != pricing or existing.pricing_version != pricing_version:
                raise CommandError(f"{case_id} R{repetition}: campaign pricing differs.")
            if not existing.investigation_runs.exists():
                cap = int(existing.limits.get("max_cost_microunits", 0))
                if cap > remaining_cost_microunits:
                    raise CommandError(
                        f"{case_id} R{repetition}: stale empty campaign exceeds remaining "
                        "project budget; inspect before retrying."
                    )
            return existing

        limits = {
            "max_provider_calls": int(DEFAULT_BUDGET["max_model_calls"]),
            "max_input_tokens": int(DEFAULT_BUDGET["max_input_tokens"]),
            "max_output_tokens": int(DEFAULT_BUDGET["max_output_tokens"]),
            "max_cost_microunits": int(remaining_cost_microunits),
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

    def _assert_environment(self) -> None:
        contract = performance_contract()["execution_contract"]
        configured_model = str(getattr(settings, "OPENROUTER_MODEL", "") or "").strip()
        api_key = str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
        if not api_key:
            raise CommandError("OPENROUTER_API_KEY is not configured.")
        if configured_model != contract["model"]:
            raise CommandError(
                f"OPENROUTER_MODEL must match the frozen AP0 contract exactly: {contract['model']}"
            )

    def _pricing_from_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for env_name, key in (
            ("ISSUE106_PRICE_INPUT_PER_MILLION", "input_per_million"),
            ("ISSUE106_PRICE_OUTPUT_PER_MILLION", "output_per_million"),
        ):
            raw = os.getenv(env_name, "").strip()
            try:
                value = Decimal(raw)
            except (InvalidOperation, ValueError) as exc:
                raise CommandError(f"{env_name} must be a non-negative decimal.") from exc
            if value < 0:
                raise CommandError(f"{env_name} must be a non-negative decimal.")
            values[key] = str(value)
        return values

    def _tested_commit(self) -> str:
        base = Path(settings.BASE_DIR)
        git = shutil.which("git")
        if not git:
            raise CommandError(
                "Git executable unavailable; AP1 requires a verifiable checkout/HEAD binding."
            )
        try:
            status = subprocess.run(  # noqa: S603  # nosec B603 -- fixed git argv
                [git, "status", "--porcelain"],
                cwd=base,
                check=True,
                capture_output=True,
                text=True,
            )
            if status.stdout.strip():
                raise CommandError(
                    "Baseline runs require a clean worktree; commit local changes first."
                )
            head = (
                subprocess.run(  # noqa: S603  # nosec B603 -- fixed git argv
                    [git, "rev-parse", "HEAD"],
                    cwd=base,
                    check=True,
                    capture_output=True,
                    text=True,
                )
                .stdout.strip()
                .lower()
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise CommandError(
                "Git revision unavailable; AP1 refuses an unverifiable tested_commit."
            ) from exc

        if not HEX40.fullmatch(head):
            raise CommandError("Could not resolve a valid tested commit.")

        explicit = os.getenv("ISSUE106_TESTED_COMMIT", "").strip().lower()
        if explicit:
            if not HEX40.fullmatch(explicit):
                raise CommandError("ISSUE106_TESTED_COMMIT must be a 40-character SHA.")
            if explicit != head:
                raise CommandError(
                    "ISSUE106_TESTED_COMMIT must exactly match the verified checkout HEAD."
                )

        os.environ["GIT_COMMIT"] = head
        return head

    def _assert_source_pack(self, *, case_id: str) -> None:
        spec = golden_case_specs()[case_id]
        contract_case = spec["quality_contract"]
        root = (Path(settings.BASE_DIR) / str(spec["source_pack"])).resolve()
        from ki_radar.accelerator.ap4_evidence import source_pack_hash

        current_hash = source_pack_hash(root, tuple(spec["files"]))
        if current_hash not in set(contract_case["source_pack_hashes"]):
            raise CommandError(
                f"{case_id}: current source pack hash differs from the frozen AP0 contract."
            )
