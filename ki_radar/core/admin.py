from django.contrib import admin

from .models import SystemJobRun


@admin.register(SystemJobRun)
class SystemJobRunAdmin(admin.ModelAdmin):
    list_display = ("job_name", "status", "started_at", "finished_at", "exit_code")
    list_filter = ("status", "job_name")
    search_fields = ("job_name", "error_message")
    readonly_fields = [field.name for field in SystemJobRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
