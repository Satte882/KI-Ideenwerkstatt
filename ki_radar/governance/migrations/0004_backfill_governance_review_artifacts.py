from django.db import migrations
from django.utils import timezone


REVIEW_DEFINITIONS = {
    "privacy": (
        "privacy_review_required",
        "privacy_review_rationale",
        "Datenschutzverantwortliche Rolle",
    ),
    "security": (
        "security_review_required",
        "security_review_rationale",
        "Informationssicherheitsverantwortliche Rolle",
    ),
    "legal": (
        "legal_review_required",
        "legal_review_rationale",
        "Rechtsverantwortliche Rolle",
    ),
}


def _screening_for_review(Assessment, review):
    screenings = Assessment.objects.filter(use_case_id=review.use_case_id)
    screening = (
        screenings.filter(assessment_date__lte=review.reviewed_at)
        .order_by("-assessment_date", "-created_at")
        .first()
    )
    return screening or screenings.order_by("-assessment_date", "-created_at").first()


def _history_kwargs(HistoricalReview, review):
    values = {}
    for field in HistoricalReview._meta.concrete_fields:
        if field.primary_key:
            continue
        attname = field.attname
        if attname == "history_date":
            values[attname] = review.updated_at or timezone.now()
        elif attname == "history_type":
            values[attname] = "+"
        elif attname == "history_change_reason":
            values[attname] = "Bestandsdaten-Backfill für Issue #46"
        elif attname == "history_user_id":
            values[attname] = review.reviewer_id
        elif hasattr(review, attname):
            values[attname] = getattr(review, attname)
    return values


def forwards(apps, schema_editor):
    Assessment = apps.get_model("governance", "GovernanceAssessment")
    Review = apps.get_model("governance", "GovernanceReview")
    HistoricalReview = apps.get_model("governance", "HistoricalGovernanceReview")

    for review in Review.objects.all().iterator():
        review.screening = _screening_for_review(Assessment, review)
        review.status = "completed"
        review.responsible_role = REVIEW_DEFINITIONS[review.review_type][2]
        if review.result == "passed_with_conditions" and not review.conditions:
            review.conditions = review.rationale
        if review.result == "failed":
            review.risks = review.risks or review.rationale
            review.measures = review.measures or review.rationale
        review.save(
            update_fields=[
                "screening",
                "status",
                "responsible_role",
                "conditions",
                "risks",
                "measures",
            ]
        )

    for screening in Assessment.objects.all().iterator():
        for review_type, definition in REVIEW_DEFINITIONS.items():
            required_field, rationale_field, responsible_role = definition
            if Review.objects.filter(
                screening_id=screening.pk,
                review_type=review_type,
            ).exists():
                continue
            required = getattr(screening, required_field)
            rationale = getattr(screening, rationale_field) or screening.rationale
            Review.objects.create(
                use_case_id=screening.use_case_id,
                screening_id=screening.pk,
                review_type=review_type,
                status="open" if required else "not_relevant",
                reviewed_at=screening.assessment_date,
                reviewer_id=screening.reviewer_id,
                responsible_role=responsible_role,
                result="",
                rationale=rationale,
            )

    for review in Review.objects.all().iterator():
        if HistoricalReview.objects.filter(id=review.pk).exists():
            continue
        HistoricalReview.objects.create(**_history_kwargs(HistoricalReview, review))


def backwards(apps, schema_editor):
    Review = apps.get_model("governance", "GovernanceReview")
    HistoricalReview = apps.get_model("governance", "HistoricalGovernanceReview")
    HistoricalReview.objects.filter(
        history_change_reason="Bestandsdaten-Backfill für Issue #46"
    ).delete()
    Review.objects.filter(result="").delete()


class Migration(migrations.Migration):
    dependencies = [("governance", "0003_governance_review_artifacts")]

    operations = [migrations.RunPython(forwards, backwards)]
