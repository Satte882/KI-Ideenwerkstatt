from django.urls import path

from ki_radar import review_export_views

app_name = "review_export"

urlpatterns = [
    path(
        "value-stream/<uuid:pk>.md",
        review_export_views.value_stream_review_export,
        name="value_stream",
    ),
    path(
        "process/<uuid:pk>.md",
        review_export_views.process_review_export,
        name="process",
    ),
    path(
        "use-case/<uuid:pk>.md",
        review_export_views.use_case_review_export,
        name="use_case",
    ),
]
