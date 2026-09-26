from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.investigation_models import InvestigationEvidenceCampaign
from ki_radar.accelerator.issue4_blind_review import (
    BlindReviewPackageError,
    build_blind_review_package,
)


class Command(BaseCommand):
    help = (
        "Build the anonymized reviewer package for the frozen Issue #4 "
        "adaptive scored sample. No provider calls and no database writes."
    )

    def add_arguments(self, parser):
        parser.add_argument("--campaign", required=True)
        parser.add_argument(
            "--output",
            default=str(Path(settings.BASE_DIR) / "output" / "issue4-blind-review"),
            help="Local output directory. Defaults to ignored output/issue4-blind-review.",
        )
        parser.add_argument(
            "--seed",
            required=False,
            help=(
                "Optional deterministic randomization seed. When omitted, a secure seed "
                "is generated and stored only in the curator key."
            ),
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Replace an existing local package intentionally.",
        )

    def handle(self, *args, **options):
        try:
            campaign = InvestigationEvidenceCampaign.objects.select_related(
                "authorized_by",
                "process_analysis",
            ).get(pk=options["campaign"])
        except (InvestigationEvidenceCampaign.DoesNotExist, ValueError) as exc:
            raise CommandError("Evidence campaign not found.") from exc

        try:
            package_path, curator_path = build_blind_review_package(
                campaign=campaign,
                output_dir=Path(options["output"]),
                seed=options.get("seed"),
                overwrite=bool(options["overwrite"]),
            )
        except (BlindReviewPackageError, OSError) as exc:
            raise CommandError(f"Blind-review package could not be built: {exc}") from exc

        self.stdout.write(self.style.SUCCESS(f"Reviewer package: {package_path}"))
        self.stdout.write(self.style.WARNING(f"Curator key (do not share): {curator_path}"))
        self.stdout.write(
            "No provider call was started and no investigation/evidence row was modified."
        )
