from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import BusinessUnit, PrivacyRequest, User


@admin.register(User)
class RadarUserAdmin(UserAdmin):
    fieldsets = (
        *UserAdmin.fieldsets,
        (
            "KI-Radar",
            {
                "fields": (
                    "business_unit",
                    "job_function",
                    "external_identity_id",
                    "is_anonymized",
                    "anonymized_at",
                )
            },
        ),
    )
    readonly_fields = ("is_anonymized", "anonymized_at")
    list_display = ("username", "email", "business_unit", "is_active", "is_anonymized", "is_staff")
    list_filter = (*UserAdmin.list_filter, "is_anonymized", "business_unit")


@admin.register(BusinessUnit)
class BusinessUnitAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "subject_user", "status", "request_received_at", "completed_at")
    list_filter = ("status",)
    search_fields = ("reference",)
