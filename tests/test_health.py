from datetime import timedelta

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.core.models import SystemJobRun


@pytest.mark.django_db
def test_readiness(client):
    assert client.get(reverse("health-ready")).status_code == 200


@pytest.mark.django_db
def test_operations_requires_token(client):
    assert client.get(reverse("health-operations")).status_code == 404


@pytest.mark.django_db
@override_settings(MONITORING_TOKEN="secret", JOB_FRESHNESS_HOURS=26)
def test_operations_healthy(client):
    now = timezone.now()
    for name in ["database_backup", "review_scan"]:
        SystemJobRun.objects.create(
            job_name=name,
            status=SystemJobRun.Status.SUCCESS,
            started_at=now - timedelta(minutes=1),
            finished_at=now,
            exit_code=0,
        )
    response = client.get(reverse("health-operations"), HTTP_X_MONITORING_TOKEN="secret")
    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(MONITORING_TOKEN="secret", JOB_FRESHNESS_HOURS=26)
def test_operations_degraded_when_latest_backup_failed(client):
    now = timezone.now()
    for name in ["database_backup", "review_scan"]:
        SystemJobRun.objects.create(
            job_name=name,
            status=SystemJobRun.Status.SUCCESS,
            started_at=now - timedelta(minutes=5),
            finished_at=now - timedelta(minutes=4),
            exit_code=0,
        )
    SystemJobRun.objects.create(
        job_name="database_backup",
        status=SystemJobRun.Status.FAILED,
        started_at=now - timedelta(minutes=1),
        finished_at=now,
        exit_code=1,
        error_message="Backup failed",
    )

    response = client.get(reverse("health-operations"), HTTP_X_MONITORING_TOKEN="secret")
    payload = response.json()
    assert response.status_code == 503
    assert payload["jobs"]["database_backup"]["last_run_status"] == "failed"
    assert payload["jobs"]["database_backup"]["last_success"] is not None
