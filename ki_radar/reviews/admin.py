from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Review


@admin.register(Review)
class ReviewAdmin(SimpleHistoryAdmin):
    list_display = (
        "use_case",
        "review_date",
        "reviewer",
        "decision",
        "previous_status",
        "new_status",
        "next_review_date",
    )
    list_filter = ("decision", "new_status")
    search_fields = ("use_case__short_id", "use_case__title", "rationale", "open_actions")

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields] if obj else ()

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
