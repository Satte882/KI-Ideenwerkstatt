import pytest
from django.core.management import call_command
from django.utils import timezone

from ki_radar.core.models import SystemJobRun
from ki_radar.use_cases.models import UseCase


@pytest.mark.django_db
def test_review_scan_records_job(owner, business_unit):
    UseCase.objects.create(
        title="Überfällig",
        problem_statement="Problem",
        business_unit=business_unit,
        affected_process="Prozess",
        business_owner=owner,
        expected_benefit="Nutzen",
        next_review_date=timezone.localdate() - timezone.timedelta(days=1),
    )
    call_command("scan_due_reviews")
    run = SystemJobRun.objects.get(job_name="review_scan")
    assert run.status == SystemJobRun.Status.SUCCESS
    assert run.details["overdue"] == 1
