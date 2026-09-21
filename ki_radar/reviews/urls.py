from django.urls import path

from . import views

app_name = "reviews"
urlpatterns = [
    path("monthly/", views.monthly_review, name="monthly"),
    path(
        "use-case/<uuid:use_case_id>/scale-readiness-preview/",
        views.scale_readiness_preview,
        name="scale_readiness_preview",
    ),
    path("use-case/<uuid:use_case_id>/new/", views.review_create, name="create"),
]
