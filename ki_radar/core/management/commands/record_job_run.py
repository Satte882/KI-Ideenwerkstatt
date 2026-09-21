import json
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ki_radar.core.models import SystemJobRun


class Command(BaseCommand):
    help = "Records a completed operational job run for monitoring."

    def add_arguments(self, parser):
        parser.add_argument("job_name")
        parser.add_argument("--status", choices=["success", "failed"], required=True)
        parser.add_argument("--started-at")
        parser.add_argument("--exit-code", type=int, default=0)
        parser.add_argument("--details", default="{}")
        parser.add_argument("--error", default="")

    def handle(self, *args, **options):
        try:
            details = json.loads(options["details"])
        except json.JSONDecodeError as exc:
            raise CommandError("--details must be valid JSON") from exc
        started_at = (
            datetime.fromisoformat(options["started_at"])
            if options["started_at"]
            else timezone.now()
        )
        if timezone.is_naive(started_at):
            started_at = timezone.make_aware(started_at)
        run = SystemJobRun.objects.create(
            job_name=options["job_name"],
            status=options["status"],
            started_at=started_at,
            finished_at=timezone.now(),
            exit_code=options["exit_code"],
            details=details,
            error_message=options["error"],
        )
        self.stdout.write(self.style.SUCCESS(f"Recorded job run {run.pk}"))
