import json
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from ki_radar.accounts.services import apply_anonymized_identity


class Command(BaseCommand):
    help = "Reapplies anonymizations from the external append-only ledger after a restore."

    def add_arguments(self, parser):
        parser.add_argument("--ledger", default=str(settings.ANONYMIZATION_LEDGER_PATH))
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        path = Path(options["ledger"])
        if not path.exists():
            self.stdout.write(self.style.WARNING("No anonymization ledger found"))
            return

        user_model = get_user_model()
        count = 0
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                user_id = record["user_id"]
                anonymized_username = record["anonymized_username"]
                anonymized_at = datetime.fromisoformat(record["anonymized_at"])
            except (KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Invalid anonymization ledger entry at line {line_number}"
                ) from exc

            user = user_model.objects.filter(pk=user_id).first()
            if not user or user.is_anonymized:
                continue
            count += 1
            if options["dry_run"]:
                continue
            with transaction.atomic():
                apply_anonymized_identity(
                    user=user,
                    anonymized_username=anonymized_username,
                    anonymized_at=anonymized_at,
                )

        action = "Would reapply" if options["dry_run"] else "Reapplied"
        self.stdout.write(self.style.SUCCESS(f"{action} {count} anonymizations"))
