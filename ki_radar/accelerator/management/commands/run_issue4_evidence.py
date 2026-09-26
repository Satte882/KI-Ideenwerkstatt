from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.investigation_benchmark import (
    resolve_benchmark_snapshot,
    run_fixed_route_until_boundary,
    validate_evidence_attempt,
)
from ki_radar.accelerator.investigation_loop import run_until_boundary
from ki_radar.accelerator.investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationRun,
)
from ki_radar.accelerator.investigation_runtime import (
    InvestigationRunError,
    StartInvestigationRequest,
    start_investigation,
)


class Command(BaseCommand):
    help = "Run one controlled real-provider VS1/3 evidence attempt for Issue #4."

    def add_arguments(self, parser):
        parser.add_argument("--campaign", required=True)
        parser.add_argument("--variant", required=True, choices=("A", "B", "C"))
        parser.add_argument("--mode", required=True, choices=("adaptive", "fixed"))
        parser.add_argument(
            "--phase",
            required=True,
            choices=("calibration", "scored", "post_fix"),
        )
        parser.add_argument("--attempt", required=True, type=int)
        parser.add_argument(
            "--snapshot",
            required=False,
            help=(
                "Explicit Source-Snapshot UUID. Required only for the first calibration "
                "run of each A/B/C variant; scored and post_fix runs reuse the frozen binding."
            ),
        )

    def handle(self, *args, **options):
        attempt = int(options["attempt"])
        if attempt < 1:
            raise CommandError("--attempt must be a positive integer.")

        try:
            campaign = InvestigationEvidenceCampaign.objects.select_related(
                "process_analysis__stage__value_stream",
                "authorized_by",
            ).get(pk=options["campaign"])
        except (InvestigationEvidenceCampaign.DoesNotExist, ValueError) as exc:
            raise CommandError("Evidence campaign not found.") from exc

        variant = options["variant"]
        mode = options["mode"]
        phase = options["phase"]
        try:
            validate_evidence_attempt(
                campaign=campaign,
                variant=variant,
                mode=mode,
                phase=phase,
                attempt=attempt,
            )
            snapshot = resolve_benchmark_snapshot(
                campaign=campaign,
                variant=variant,
                phase=phase,
                requested_snapshot_id=options.get("snapshot"),
            )
        except InvestigationRunError as exc:
            raise CommandError(f"Evidence attempt contract invalid: {exc}") from exc
        idempotency_key = "-".join(
            (
                "i4",
                campaign.pk.hex[:12],
                variant.lower(),
                mode[0],
                phase[0],
                str(attempt),
            )
        )

        try:
            handle = start_investigation(
                actor=campaign.authorized_by,
                request=StartInvestigationRequest(
                    snapshot_id=snapshot.pk,
                    idempotency_key=idempotency_key,
                    evidence_campaign_id=campaign.pk,
                    execution_mode=mode,
                    evidence_metadata={
                        "provider_mode": "real",
                        "phase": phase,
                        "variant": variant,
                        "attempt": attempt,
                    },
                    decision_brief_required=True,
                    allow_historical_snapshot_replay=phase == "post_fix",
                ),
            )
        except InvestigationRunError as exc:
            raise CommandError(f"Evidence run could not start: {exc}") from exc

        if handle.reused:
            if phase == "post_fix" and handle.status == InvestigationRun.Status.RUNNING:
                self.stdout.write(
                    self.style.WARNING(
                        f"Existing running post-fix attempt resumed: {handle.run_id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Existing attempt reused; no provider call started: {handle.run_id}"
                    )
                )
                return

        if handle.status != InvestigationRun.Status.RUNNING:
            self.stdout.write(
                self.style.WARNING(
                    f"Run is not executable in status {handle.status}: {handle.run_id}"
                )
            )
            return

        runner = run_fixed_route_until_boundary if mode == "fixed" else run_until_boundary
        try:
            result = runner(
                actor=campaign.authorized_by,
                run_id=handle.run_id,
                executor_token=handle.executor_token,
            )
        except InvestigationRunError as exc:
            raise CommandError(f"Evidence run failed: {exc}") from exc

        self.stdout.write(
            self.style.SUCCESS(
                f"Issue #4 evidence attempt finished at boundary: "
                f"{result.run_id} status={result.status}"
            )
        )
