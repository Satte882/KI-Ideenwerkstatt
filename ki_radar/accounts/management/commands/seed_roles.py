from django.core.management.base import BaseCommand

from ki_radar.accounts.permissions import ensure_groups


class Command(BaseCommand):
    help = "Creates the four standard KI-Radar role groups."

    def handle(self, *args, **options):
        ensure_groups()
        self.stdout.write(self.style.SUCCESS("KI-Radar roles created or already present"))
