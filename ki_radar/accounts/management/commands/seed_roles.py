from pathlib import Path
from runpy import run_path

from django.conf import settings
from django.core.management.base import BaseCommand

from ki_radar.accounts.permissions import ensure_groups


TRANSFER_IMPORTER = (
    Path(settings.BASE_DIR)
    / "tmp"
    / "legacy-usecase-transfer-2026-09-21"
    / "import_legacy_usecases.py"
)


class Command(BaseCommand):
    help = "Creates the four standard KI-Radar role groups."

    def handle(self, *args, **options):
        ensure_groups()
        self.stdout.write(self.style.SUCCESS("KI-Radar roles created or already present"))

        if TRANSFER_IMPORTER.exists():
            namespace = run_path(str(TRANSFER_IMPORTER))
            summary = namespace["import_legacy_usecases"]()
            self.stdout.write(
                self.style.SUCCESS(
                    "Temporary legacy transfer completed: "
                    f"{summary['count']} use cases ({', '.join(summary['use_cases'])})"
                )
            )
