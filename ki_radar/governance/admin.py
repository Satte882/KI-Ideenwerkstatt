from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import GovernanceAssessment, GovernanceReview


@admin.register(GovernanceAssessment)
class GovernanceAssessmentAdmin(SimpleHistoryAdmin):
    list_display = ("use_case", "assessment_date", "reviewer", "result", "next_assessment_date")
    list_filter = (
        "result",
        "privacy_review_required",
        "security_review_required",
        "legal_review_required",
    )
    search_fields = ("use_case__short_id", "use_case__title", "rationale")


@admin.register(GovernanceReview)
class GovernanceReviewAdmin(SimpleHistoryAdmin):
    list_display = (
        "use_case",
        "review_type",
        "status",
        "result",
        "reviewer",
        "created_at",
    )
    list_filter = ("review_type", "status", "result")
    search_fields = (
        "use_case__short_id",
        "use_case__title",
        "responsible_role",
        "rationale",
        "risks",
        "measures",
        "conditions",
    )
