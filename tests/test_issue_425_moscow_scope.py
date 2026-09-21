import importlib
from decimal import Decimal

import pytest
from django.apps import apps
from django.utils import timezone

from ki_radar.delivery.ai_draft import EDITABLE_CONTEXT_FIELDS, TARGET_FIELD
from ki_radar.delivery.evidence_mapping_contract import (
    FORBIDDEN_AUTOMATED_DELIVERY_FIELDS,
    V1_DELIVERY_FIELD_MAPPINGS,
    mapping_spec,
)
from ki_radar.delivery.exports import render_delivery_markdown
from ki_radar.delivery.forms import SECTION_FIELDS, DeliveryPackageForm
from ki_radar.delivery.models import (
    DELIVERY_SECTION_DEFINITIONS,
    SECTION_REVIEW_REQUIREMENTS,
    DeliveryPackage,
    DeliverySectionReview,
)
from ki_radar.delivery.readiness import READY_REQUIRED_FIELDS, evaluate_delivery_readiness
from ki_radar.delivery.services import create_delivery_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase


def make_approved_use_case(*, owner, technical_owner, coordinator, business_unit):
    use_case = UseCase.objects.create(
        title="MoSCoW Scope Test",
        summary="Angebote strukturiert vergleichen.",
        problem_statement="Uneinheitliche Angebote erzeugen Rückfragen.",
        business_unit=business_unit,
        affected_process="Lieferantenauswahl",
        target_users="Einkauf",
        submitter=owner,
        business_owner=owner,
        technical_owner=technical_owner,
        source_systems="ERP, Shared Inbox",
        data_sources="Angebote und Kriterienkatalog",
        interface_description="Dateiimport und ERP-Export",
        intended_users="Strategischer Einkauf",
        intended_purpose="Angebote extrahieren und vergleichbar darstellen.",
        expected_benefit="Durchlaufzeit reduzieren.",
        metric_name="Durchlaufzeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="Tage",
        metric_baseline=Decimal("5"),
        metric_target=Decimal("3"),
        metric_measurement_method="Median über zehn Vorgänge.",
        metric_measurement_period="Vier Wochen.",
        human_oversight="Einkauf prüft und entscheidet.",
        support_responsibility="Application Management",
        decision_status=UseCase.DecisionStatus.APPROVED,
    )
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=coordinator,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_url="https://example.com/evidence",
        rationale="Repräsentative Messung und technische Vorprüfung liegen vor.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Freigabe für Delivery.",
        decided_by=coordinator,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return use_case


@pytest.fixture
def moscow_package(owner, other_owner, coordinator, business_unit):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=False,
    )
    DeliveryPackage.objects.filter(pk=package.pk).update(
        in_scope="Angebote vergleichen",
        out_of_scope="Vertragsabschluss",
        users_and_scenarios="Einkauf vergleicht eingehende Angebote",
        mvp_scope="Ein Angebot Ende-zu-Ende einlesen und vergleichen",
    )
    package.refresh_from_db()
    return package


def test_moscow_stays_inside_existing_scope_section():
    assert len(DELIVERY_SECTION_DEFINITIONS) == 7
    assert "scope_prioritization" not in dict(DELIVERY_SECTION_DEFINITIONS)
    assert SECTION_FIELDS["scope_and_users"] == [
        "in_scope",
        "out_of_scope",
        "users_and_scenarios",
        "mvp_scope",
        "should_scope",
        "could_scope",
        "wont_this_time",
    ]
    assert SECTION_REVIEW_REQUIREMENTS["scope_and_users"] == frozenset({"business"})


def test_optional_priorities_do_not_extend_readiness_requirements():
    required = READY_REQUIRED_FIELDS["scope_and_users"]
    assert "mvp_scope" in required
    assert "should_scope" not in required
    assert "could_scope" not in required
    assert "wont_this_time" not in required


def test_new_priorities_fail_closed_for_evidence_mapping_and_ai():
    for field_name in ("should_scope", "could_scope", "wont_this_time"):
        assert field_name in FORBIDDEN_AUTOMATED_DELIVERY_FIELDS
        assert field_name not in V1_DELIVERY_FIELD_MAPPINGS
        assert field_name not in EDITABLE_CONTEXT_FIELDS
        with pytest.raises(ValueError):
            mapping_spec(field_name)
    assert TARGET_FIELD == "mvp_scope"


@pytest.mark.django_db
def test_new_package_uses_mixed_scope_origin_and_empty_optional_priorities(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    use_case = make_approved_use_case(
        owner=owner,
        technical_owner=other_owner,
        coordinator=coordinator,
        business_unit=business_unit,
    )
    package = create_delivery_package(
        use_case=use_case,
        actor=coordinator,
        use_evidence_mapper=False,
    )
    review = package.section_reviews.get(section_key="scope_and_users")

    assert package.should_scope == ""
    assert package.could_scope == ""
    assert package.wont_this_time == ""
    assert review.content_origin == DeliverySectionReview.ContentOrigin.MIXED


@pytest.mark.django_db
def test_empty_optional_priorities_create_no_readiness_blockers(moscow_package):
    findings = evaluate_delivery_readiness(moscow_package)
    codes = {finding.code for finding in findings}

    assert "SHOULD_SCOPE_MISSING" not in codes
    assert "COULD_SCOPE_MISSING" not in codes
    assert "WONT_THIS_TIME_MISSING" not in codes


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field_name", "new_value"),
    [
        ("mvp_scope", "Must neu priorisiert"),
        ("should_scope", "Sollte im nächsten Schritt folgen"),
        ("could_scope", "Optional bei verfügbarer Kapazität"),
        ("wont_this_time", "Bewusst erst in einer späteren Delivery-Version"),
    ],
)
def test_priority_edit_reopens_scope_review_and_ready_package(
    moscow_package,
    owner,
    field_name,
    new_value,
):
    package = moscow_package
    review = package.section_reviews.get(section_key="scope_and_users")
    DeliverySectionReview.objects.filter(pk=review.pk).update(
        content_origin=DeliverySectionReview.ContentOrigin.MIXED,
        review_status=DeliverySectionReview.ReviewStatus.CONFIRMED,
        reviewed_by=owner,
        reviewed_at=timezone.now(),
        business_confirmed_by=owner,
        business_confirmed_at=timezone.now(),
        business_confirmation_role="Business Owner",
    )
    DeliveryPackage.objects.filter(pk=package.pk).update(status=DeliveryPackage.Status.READY)
    package.refresh_from_db()

    data = {
        "in_scope": package.in_scope,
        "out_of_scope": package.out_of_scope,
        "users_and_scenarios": package.users_and_scenarios,
        "mvp_scope": package.mvp_scope,
        "should_scope": package.should_scope,
        "could_scope": package.could_scope,
        "wont_this_time": package.wont_this_time,
    }
    data[field_name] = new_value
    form = DeliveryPackageForm(
        data=data,
        instance=package,
        actor=owner,
        active_section="scope_and_users",
    )

    assert form.is_valid(), form.errors
    form.save()

    package.refresh_from_db()
    review.refresh_from_db()
    assert getattr(package, field_name) == new_value
    assert package.status == DeliveryPackage.Status.DRAFT
    assert review.review_status == DeliverySectionReview.ReviewStatus.NEEDS_REVIEW
    assert review.business_confirmed_by is None
    assert review.business_confirmed_at is None


@pytest.mark.django_db
def test_markdown_export_has_one_must_block_and_distinguishes_wont_from_out_of_scope(
    moscow_package,
):
    package = moscow_package
    DeliveryPackage.objects.filter(pk=package.pk).update(
        should_scope="Mehrere Angebote stapelweise vergleichen",
        could_scope="Zusätzliche Visualisierung",
        wont_this_time="Automatische Lieferantenauswahl",
    )
    package.refresh_from_db()

    exported = render_delivery_markdown(package)

    assert "## Scope-Grenzen" in exported
    assert "### Nicht im Scope\nVertragsabschluss" in exported
    assert "## Priorisierung für diese Delivery-Version (MoSCoW)" in exported
    assert exported.count("### Must / MVP-Scope") == 1
    assert "### Should\nMehrere Angebote stapelweise vergleichen" in exported
    assert "### Could\nZusätzliche Visualisierung" in exported
    assert "### Won't this time\nAutomatische Lieferantenauswahl" in exported
    assert "nicht mit 'Nicht im Scope' gleichzusetzen" in exported


@pytest.mark.django_db
def test_scope_origin_backfill_skips_handed_over_snapshots(
    owner,
    other_owner,
    coordinator,
    business_unit,
):
    active = create_delivery_package(
        use_case=make_approved_use_case(
            owner=owner,
            technical_owner=other_owner,
            coordinator=coordinator,
            business_unit=business_unit,
        ),
        actor=coordinator,
        use_evidence_mapper=False,
    )
    handed_over = create_delivery_package(
        use_case=make_approved_use_case(
            owner=owner,
            technical_owner=other_owner,
            coordinator=coordinator,
            business_unit=business_unit,
        ),
        actor=coordinator,
        use_evidence_mapper=False,
    )
    active_review = active.section_reviews.get(section_key="scope_and_users")
    handed_over_review = handed_over.section_reviews.get(section_key="scope_and_users")
    DeliverySectionReview.objects.filter(pk__in=[active_review.pk, handed_over_review.pk]).update(
        content_origin=DeliverySectionReview.ContentOrigin.INHERITED
    )
    DeliveryPackage.objects.filter(pk=handed_over.pk).update(
        status=DeliveryPackage.Status.HANDED_OVER,
        handed_over_at=timezone.now(),
    )

    migration = importlib.import_module(
        "ki_radar.delivery.migrations.0007_moscow_scope_prioritization"
    )
    migration.set_active_scope_origin_mixed(apps, None)

    active_review.refresh_from_db()
    handed_over_review.refresh_from_db()
    assert active_review.content_origin == DeliverySectionReview.ContentOrigin.MIXED
    assert handed_over_review.content_origin == DeliverySectionReview.ContentOrigin.INHERITED
