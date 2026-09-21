from django.contrib import admin

from .models import DeliveryPackage


@admin.register(DeliveryPackage)
class DeliveryPackageAdmin(admin.ModelAdmin):
    list_display = (
        "use_case",
        "version",
        "status",
        "created_by",
        "handed_over_by",
        "updated_at",
    )
    list_filter = ("status", "use_case__business_unit")
    search_fields = ("use_case__short_id", "use_case__title", "problem_context")
    readonly_fields = (
        "use_case",
        "version",
        "generated_from_decision",
        "created_by",
        "handed_over_by",
        "handed_over_at",
        "created_at",
        "updated_at",
    )
