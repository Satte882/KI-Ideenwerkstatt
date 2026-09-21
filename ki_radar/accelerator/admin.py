from django.contrib import admin

from ki_radar.accounts.permissions import is_technical_admin

from .investigation_models import (
    InvestigationSource,
    InvestigationSourceFolder,
    InvestigationSourceSnapshot,
    InvestigationToolResult,
)


class TechnicalAdminOnlyMixin:
    def has_module_permission(self, request):
        return is_technical_admin(request.user)

    def has_view_permission(self, request, obj=None):
        return is_technical_admin(request.user)

    def has_add_permission(self, request):
        return is_technical_admin(request.user)

    def has_change_permission(self, request, obj=None):
        return is_technical_admin(request.user)

    def has_delete_permission(self, request, obj=None):
        return is_technical_admin(request.user)


@admin.register(InvestigationSourceFolder)
class InvestigationSourceFolderAdmin(TechnicalAdminOnlyMixin, admin.ModelAdmin):
    list_display = ("name", "process_analysis", "is_active", "registered_by", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "process_analysis__name", "root_path")
    fields = ("process_analysis", "name", "root_path", "is_active", "registered_by")

    def save_model(self, request, obj, form, change):
        if obj.registered_by_id is None:
            obj.registered_by = request.user
        super().save_model(request, obj, form, change)


class ReadOnlyEvidenceAdmin(TechnicalAdminOnlyMixin, admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(InvestigationSourceSnapshot)
class InvestigationSourceSnapshotAdmin(ReadOnlyEvidenceAdmin):
    list_display = (
        "process_analysis",
        "revision",
        "folder",
        "manifest_hash",
        "captured_by",
        "captured_at",
    )
    search_fields = ("process_analysis__name", "manifest_hash", "decision_question")


@admin.register(InvestigationSource)
class InvestigationSourceAdmin(ReadOnlyEvidenceAdmin):
    list_display = ("filename", "snapshot", "source_type", "size_bytes", "content_sha256")
    search_fields = ("filename", "content_sha256")
    exclude = ("content",)


@admin.register(InvestigationToolResult)
class InvestigationToolResultAdmin(ReadOnlyEvidenceAdmin):
    list_display = ("tool_name", "snapshot", "source", "tool_version", "created_at")
    list_filter = ("tool_name", "tool_version")
    search_fields = ("source_hash",)
