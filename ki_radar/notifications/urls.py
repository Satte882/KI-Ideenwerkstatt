from django.urls import path

from .views import evidence_create

app_name = "notifications"
urlpatterns = [
    path("use-case/<uuid:use_case_id>/evidence/new/", evidence_create, name="evidence_create")
]
