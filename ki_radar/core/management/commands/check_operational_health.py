from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ki_radar.core.models import SystemJobRun


class Command(BaseCommand):
    help = "Fails when required operational jobs are stale or failed."

    def handle(self, *args, **options):
        threshold = timezone.now() - timedelta(hours=settings.JOB_FRESHNESS_HOURS)
        failures = []
        for job_name in ("database_backup", "review_scan"):
            latest = SystemJobRun.objects.filter(job_name=job_name).order_by("-started_at").first()
            if (
                not latest
                or latest.status != SystemJobRun.Status.SUCCESS
                or not latest.finished_at
                or latest.finished_at < threshold
            ):
                failures.append(job_name)
        if failures:
            raise CommandError(f"Operational jobs unhealthy: {', '.join(failures)}")
        self.stdout.write(self.style.SUCCESS("Operational jobs are healthy"))
