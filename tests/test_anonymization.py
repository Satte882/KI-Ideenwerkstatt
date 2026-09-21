import json
from pathlib import Path

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accounts.models import PrivacyRequest
from ki_radar.accounts.services import anonymize_user
from ki_radar.notifications.models import NotificationLog


@pytest.mark.django_db
def test_anonymization_removes_personal_fields(owner, technical_admin, tmp_path):
    owner.first_name = "Max"
    owner.last_name = "Muster"
    owner.email = "max@example.com"
    owner.job_function = "Leitung"
    owner.external_identity_id = "entra-123"
    owner.save()
    notification = NotificationLog.objects.create(
        recipient_user=owner,
        recipient_label="Max Muster",
        recipient_email=owner.email,
        notification_type="review_due",
        idempotency_key="anonymization-test",
    )
    request = PrivacyRequest.objects.create(
        reference="DS-1",
        subject_user=owner,
        status=PrivacyRequest.Status.APPROVED,
        request_received_at=timezone.now(),
    )
    ledger = tmp_path / "ledger.jsonl"

    with override_settings(ANONYMIZATION_LEDGER_PATH=ledger):
        anonymize_user(user=owner, privacy_request=request, actor=technical_admin)

    owner.refresh_from_db()
    notification.refresh_from_db()
    request.refresh_from_db()
    assert owner.is_anonymized and not owner.is_active
    assert owner.first_name == "" and owner.last_name == ""
    assert owner.email.endswith("@example.invalid")
    assert owner.business_unit is None
    assert notification.recipient_email == ""
    assert notification.recipient_label == "Anonymisierter Benutzer"
    assert request.status == PrivacyRequest.Status.COMPLETED
    assert Path(ledger).exists()
    record = json.loads(ledger.read_text(encoding="utf-8").strip())
    assert record["user_id"] == owner.pk
    assert record["request_reference"] == "DS-1"
    assert record["anonymized_username"] == owner.username
