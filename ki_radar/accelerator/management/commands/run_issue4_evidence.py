from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.investigation_benchmark import run_fixed_route_until_boundary
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
        parser.add_argument("--phase", required=True, choices=("calibration", "scored"))
        parser.add_argument("--attempt", required=True, type=int)

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

        process = campaign.process_analysis
        snapshot = (
            process.investigation_source_snapshots.select_related("folder")
            .filter(
                process_version=process.version,
                folder__is_active=True,
            )
            .order_by("-revision")
            .first()
        )
        if snapshot is None:
            raise CommandError(
                "No active source snapshot exists for the current ProcessAnalysis version."
            )

        variant = options["variant"]
        mode = options["mode"]
        phase = options["phase"]
        idempotency_key = (
            f"i4-{campaign.pk.hex[:12]}-{variant.lower()}-"
            f"{mode[0]}-{phase[0]}-{attempt}"
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
                ),
            )
        except InvestigationRunError as exc:
            raise CommandError(f"Evidence run could not start: {exc}") from exc

        if handle.reused:
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
