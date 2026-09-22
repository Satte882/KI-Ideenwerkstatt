import os

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


def maybe_prepare_issue4() -> None:
    mode = os.getenv("ISSUE4_PREPARE_CAMPAIGN", "").strip().casefold()
    if not mode:
        return
    if mode not in {"inspect", "apply"}:
        raise CommandError("ISSUE4_PREPARE_CAMPAIGN must be empty, 'inspect', or 'apply'.")
    call_command("prepare_issue4_campaign", inspect_only=(mode == "inspect"))


class Command(BaseCommand):
    help = "Create or update a superuser from temporary environment variables."

    def handle(self, *args, **options):
        username = os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
        password = os.getenv("DJANGO_SUPERUSER_PASSWORD", "")
        email = os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()

        if not username and not password:
            maybe_prepare_issue4()
            return
        if not username or not password:
            raise CommandError(
                "DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD must be set together."
            )

        user_model = get_user_model()
        user, created = user_model.objects.get_or_create(username=username)
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        if email:
            user.email = email
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(self.style.SUCCESS(f"Superuser {username!r} {action}."))
        maybe_prepare_issue4()
