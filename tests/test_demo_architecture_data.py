import pytest

from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, ValueStream
from ki_radar.core.demo_architecture_data import (
    INVOICE_STREAM_NAME,
    INVOICE_USE_CASE_TITLE,
    clear_demo_architecture_data,
    seed_demo_architecture_data,
)
from ki_radar.core.demo_data import clear_demo_data, seed_demo_data
from ki_radar.core.demo_decision_data import enrich_demo_metrics
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.use_cases.models import UseCase


@pytest.mark.django_db
def test_architecture_demo_seed_is_idempotent_and_clearable():
    seed_demo_data(demo_user_password="Demo-Test-2026!")
    enrich_demo_metrics()

    first = seed_demo_architecture_data()
    second = seed_demo_architecture_data()

    assert first == second
    assert ValueStream.objects.filter(name=INVOICE_STREAM_NAME).count() == 1
    assert (
        ProcessAnalysis.objects.filter(stage__value_stream__name=INVOICE_STREAM_NAME).count() == 1
    )
    assert (
        SolutionOption.objects.filter(
            process_analysis__stage__value_stream__name=INVOICE_STREAM_NAME
        ).count()
        == 1
    )
    use_case = UseCase.objects.get(title=INVOICE_USE_CASE_TITLE)
    package = DeliveryPackage.objects.get(use_case=use_case, version=1)
    assert package.status == DeliveryPackage.Status.READY

    package.status = DeliveryPackage.Status.HANDED_OVER
    package.save(update_fields=["status", "updated_at"])
    seed_demo_architecture_data()
    package.refresh_from_db()
    assert package.status == DeliveryPackage.Status.HANDED_OVER

    clear_demo_architecture_data()
    counts = clear_demo_data()

    assert counts["use_cases"] > 0
    assert ValueStream.objects.filter(name=INVOICE_STREAM_NAME).exists() is False
    assert UseCase.objects.filter(title=INVOICE_USE_CASE_TITLE).exists() is False
