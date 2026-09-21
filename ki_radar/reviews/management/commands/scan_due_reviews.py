from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from ki_radar.core.models import SystemJobRun
from ki_radar.use_cases.models import UseCase


class Command(BaseCommand):
    help = "Scans due and overdue reviews and records operational job health; no e-mail is sent."

    def handle(self, *args, **options):
        started = timezone.now()
        today = timezone.localdate()
        try:
            active = UseCase.objects.filter(is_archived=False).exclude(status=UseCase.Status.ENDED)
            overdue = active.filter(next_review_date__lt=today).count()
            due_soon = active.filter(
                next_review_date__gte=today, next_review_date__lte=today + timedelta(days=30)
            ).count()
            missing = active.filter(next_review_date__isnull=True).count()
            details = {
                "overdue": overdue,
                "due_within_30_days": due_soon,
                "missing_review_date": missing,
            }
            SystemJobRun.objects.create(
                job_name="review_scan",
                status=SystemJobRun.Status.SUCCESS,
                started_at=started,
                finished_at=timezone.now(),
                exit_code=0,
                details=details,
            )
        except Exception as exc:
            SystemJobRun.objects.create(
                job_name="review_scan",
                status=SystemJobRun.Status.FAILED,
                started_at=started,
                finished_at=timezone.now(),
                exit_code=1,
                error_message=str(exc)[:1000],
            )
            raise
        self.stdout.write(self.style.SUCCESS(f"Review scan complete: {details}"))
