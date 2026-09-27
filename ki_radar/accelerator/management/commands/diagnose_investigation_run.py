from __future__ import annotations

import json

from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.investigation_diagnostics import (
    build_investigation_diagnostic,
    render_investigation_diagnostic_markdown,
)
from ki_radar.accelerator.investigation_models import InvestigationRun


class Command(BaseCommand):
    help = "Read-only diagnosis of one persisted investigation run."

    def add_arguments(self, parser):
        parser.add_argument("run_id")
        parser.add_argument(
            "--json",
            action="store_true",
            dest="as_json",
            help="Emit machine-readable JSON instead of Markdown.",
        )

    def handle(self, *args, **options):
        try:
            run = InvestigationRun.objects.get(pk=options["run_id"])
        except (InvestigationRun.DoesNotExist, ValueError) as exc:
            raise CommandError("Investigation-Run wurde nicht gefunden.") from exc

        report = build_investigation_diagnostic(run)
        if options["as_json"]:
            self.stdout.write(
                json.dumps(report, ensure_ascii=False, indent=2, default=str)
            )
            return
        self.stdout.write(render_investigation_diagnostic_markdown(report))
