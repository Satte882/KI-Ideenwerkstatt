from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.utils import timezone

MIN_COMPLETED_RETENTION_DAYS = 30
MAX_COMPLETED_RETENTION_DAYS = 365
DEFAULT_COMPLETED_RETENTION_DAYS = 90


class CaptureRetentionConfigurationError(RuntimeError):
    pass


def get_completed_capture_retention_days() -> int:
    value = getattr(
        settings,
        "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS",
        DEFAULT_COMPLETED_RETENTION_DAYS,
    )
    if isinstance(value, bool):
        raise CaptureRetentionConfigurationError(
            "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS muss eine ganze Zahl sein."
        )
    try:
        days = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise CaptureRetentionConfigurationError(
            "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS muss eine ganze Zahl sein."
        ) from exc
    if not MIN_COMPLETED_RETENTION_DAYS <= days <= MAX_COMPLETED_RETENTION_DAYS:
        raise CaptureRetentionConfigurationError(
            "ACCELERATOR_CAPTURE_COMPLETED_RETENTION_DAYS muss zwischen "
            f"{MIN_COMPLETED_RETENTION_DAYS} und {MAX_COMPLETED_RETENTION_DAYS} liegen."
        )
    return days


def completed_capture_expiry(*, now=None):
    return (now or timezone.now()) + timedelta(days=get_completed_capture_retention_days())
