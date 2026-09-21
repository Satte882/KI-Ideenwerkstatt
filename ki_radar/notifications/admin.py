from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import EvidenceLink, NotificationLog


@admin.register(EvidenceLink)
class EvidenceLinkAdmin(SimpleHistoryAdmin):
    list_display = ("use_case", "label", "document_type", "created_by", "created_at")
    list_filter = ("document_type",)
    search_fields = ("label", "use_case__short_id", "use_case__title")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        "notification_type",
        "use_case",
        "recipient_label",
        "status",
        "sent_at",
        "created_at",
    )
    list_filter = ("status", "notification_type")
    search_fields = ("recipient_label", "recipient_email", "idempotency_key")
    readonly_fields = [field.name for field in NotificationLog._meta.fields]

    def has_add_permission(self, request):
        return False
