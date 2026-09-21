from django.core.management.base import BaseCommand
from django.utils import timezone

from ki_radar.core.models import LLMTaskRun


class Command(BaseCommand):
    help = "Löscht abgelaufene technische LLM-Task-Run-Metadaten."

    def handle(self, *args, **options):
        deleted, _details = LLMTaskRun.objects.filter(expires_at__lte=timezone.now()).delete()
        self.stdout.write(self.style.SUCCESS(f"{deleted} abgelaufene LLM-Task-Runs gelöscht."))
