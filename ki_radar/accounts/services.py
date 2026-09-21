from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from ki_radar.notifications.models import NotificationLog

from .models import PrivacyRequest, User


def _delete_user_sessions(user: User) -> None:
    for session in Session.objects.all().iterator():
        data = session.get_decoded()
        if str(data.get("_auth_user_id")) == str(user.pk):
            session.delete()


def _clear_notification_data(user: User, original_email: str) -> None:
    NotificationLog.objects.filter(recipient_user=user).update(
        recipient_email="", recipient_label="Anonymisierter Benutzer"
    )
    if original_email:
        NotificationLog.objects.filter(recipient_email__iexact=original_email).update(
            recipient_email="", recipient_label="Anonymisierter Benutzer"
        )


def _append_ledger(
    user_id: int,
    anonymized_username: str,
    request_reference: str,
    anonymized_at: datetime,
) -> None:
    path: Path = settings.ANONYMIZATION_LEDGER_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "user_id": user_id,
        "anonymized_username": anonymized_username,
        "request_reference": request_reference,
        "anonymized_at": anonymized_at.isoformat(),
    }
    with path.open("a", encoding="utf-8") as ledger:
        ledger.write(json.dumps(record, ensure_ascii=False) + "\n")


def apply_anonymized_identity(
    *,
    user: User,
    anonymized_username: str,
    anonymized_at: datetime | None = None,
) -> User:
    original_email = user.email
    user.username = anonymized_username
    user.first_name = ""
    user.last_name = ""
    user.email = f"{anonymized_username}@example.invalid"
    user.external_identity_id = ""
    user.job_function = ""
    user.business_unit = None
    user.is_active = False
    user.is_staff = False
    user.is_superuser = False
    user.is_anonymized = True
    user.anonymized_at = anonymized_at or timezone.now()
    user.set_unusable_password()
    user.save()
    user.groups.clear()
    user.user_permissions.clear()
    _clear_notification_data(user, original_email)
    _delete_user_sessions(user)
    return user


@transaction.atomic
def anonymize_user(*, user: User, privacy_request: PrivacyRequest, actor: User) -> User:
    if (
        not actor.is_superuser
        and not actor.groups.filter(name="Technischer Administrator").exists()
    ):
        raise PermissionError("Only technical administrators may anonymize users")
    if privacy_request.status != PrivacyRequest.Status.APPROVED:
        raise ValueError("Privacy request must be approved before anonymization")
    if user.is_anonymized:
        return user

    anonymized_username = f"deleted-user-{secrets.token_hex(6)}"
    anonymized_at = timezone.now()
    apply_anonymized_identity(
        user=user,
        anonymized_username=anonymized_username,
        anonymized_at=anonymized_at,
    )
    _append_ledger(
        user.pk,
        anonymized_username,
        privacy_request.reference,
        anonymized_at,
    )

    privacy_request.status = PrivacyRequest.Status.COMPLETED
    privacy_request.completed_at = timezone.now()
    privacy_request.save(update_fields=["status", "completed_at", "updated_at"])
    return user
