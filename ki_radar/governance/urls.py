from django.urls import path

from .views import assessment_create, review_create

app_name = "governance"
urlpatterns = [
    path("use-case/<uuid:use_case_id>/new/", assessment_create, name="create"),
    path(
        "use-case/<uuid:use_case_id>/review/<str:review_type>/",
        review_create,
        name="review",
    ),
]
