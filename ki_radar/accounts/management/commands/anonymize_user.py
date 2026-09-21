from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ki_radar.accounts.models import PrivacyRequest
from ki_radar.accounts.services import anonymize_user


class Command(BaseCommand):
    help = "Anonymizes a user after an approved privacy request."

    def add_arguments(self, parser):
        parser.add_argument("user_id", type=int)
        parser.add_argument("privacy_request_reference")
        parser.add_argument("--actor-id", type=int, required=True)

    def handle(self, *args, **options):
        User = get_user_model()
        try:
            user = User.objects.get(pk=options["user_id"])
            actor = User.objects.get(pk=options["actor_id"])
            privacy_request = PrivacyRequest.objects.get(
                reference=options["privacy_request_reference"]
            )
        except (User.DoesNotExist, PrivacyRequest.DoesNotExist) as exc:
            raise CommandError(str(exc)) from exc
        anonymize_user(user=user, privacy_request=privacy_request, actor=actor)
        self.stdout.write(self.style.SUCCESS(f"User {user.pk} anonymized"))
