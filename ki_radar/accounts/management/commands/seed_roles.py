# ruff: noqa: I001
import pathlib
import runpy

import django.conf
import django.core.management.base

import ki_radar.accounts.permissions


TRANSFER_IMPORTER = (
    pathlib.Path(django.conf.settings.BASE_DIR)
    / "tmp"
    / "legacy-usecase-transfer-2026-09-21"
    / "import_legacy_usecases.py"
)


class Command(django.core.management.base.BaseCommand):
    help = "Creates the four standard KI-Radar role groups."

    def handle(self, *args, **options):
        ki_radar.accounts.permissions.ensure_groups()
        self.stdout.write(self.style.SUCCESS("KI-Radar roles created or already present"))

        if TRANSFER_IMPORTER.exists():
            namespace = runpy.run_path(str(TRANSFER_IMPORTER))
            summary = namespace["import_legacy_usecases"]()
            self.stdout.write(
                self.style.SUCCESS(
                    "Temporary legacy transfer completed: "
                    f"{summary['count']} use cases ({', '.join(summary['use_cases'])})"
                )
            )
