from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import ApprovalDecision, DecisionAssessment, UseCase


@admin.register(UseCase)
class UseCaseAdmin(SimpleHistoryAdmin):
    list_display = (
        "short_id",
        "title",
        "status",
        "decision_status",
        "business_unit",
        "business_owner",
        "next_review_date",
        "updated_at",
    )
    list_filter = (
        "status",
        "decision_status",
        "priority",
        "business_unit",
        "business_value",
        "risk_complexity",
    )
    search_fields = ("short_id", "title", "problem_statement", "expected_benefit")
    readonly_fields = ("short_id", "decision_status", "created_at", "updated_at")


class AuditOnlyDecisionAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DecisionAssessment)
class DecisionAssessmentAdmin(AuditOnlyDecisionAdmin):
    list_display = (
        "use_case",
        "version",
        "assessment_date",
        "assessed_by",
        "recommendation",
    )
    list_filter = ("recommendation", "assessment_date")
    search_fields = ("use_case__short_id", "use_case__title", "rationale")


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(AuditOnlyDecisionAdmin):
    list_display = (
        "use_case",
        "decision_status",
        "decided_by",
        "second_approved_by",
        "finalized_at",
    )
    list_filter = ("decision_status", "governance_confirmed")
    search_fields = ("use_case__short_id", "use_case__title", "rationale")
