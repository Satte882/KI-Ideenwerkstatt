from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.retention import (
    CAPTURE_PURGE_GRACE_DAYS,
    expire_due_capture_sessions,
    purge_terminal_capture_sessions,
)


class Command(BaseCommand):
    help = "Lässt überfällige Capture Sessions ablaufen und bereinigt terminale Sessions."

    def add_arguments(self, parser):
        parser.add_argument(
            "--grace-days",
            type=int,
            default=CAPTURE_PURGE_GRACE_DAYS,
            help="Karenz zwischen Terminalzustand und physischer Löschung.",
        )

    def handle(self, *args, **options):
        grace_days = options["grace_days"]
        if grace_days < 0:
            raise CommandError("Die Karenzzeit darf nicht negativ sein.")

        expired_count = expire_due_capture_sessions()
        deleted_count = purge_terminal_capture_sessions(grace_days=grace_days)
        self.stdout.write(
            self.style.SUCCESS(
                f"Capture-Retention abgeschlossen: {expired_count} abgelaufen, "
                f"{deleted_count} physisch gelöscht."
            )
        )
