from django.urls import path

from . import adoption_views, methodology_views, solution_generation_views, structured_views, views
from .models import CaptureSession

app_name = "accelerator"

urlpatterns = [
    path("my-captures/", views.capture_session_list, name="capture_list"),
    path(
        "value-stream/start/",
        views.start_capture,
        {"capture_type": CaptureSession.CaptureType.VALUE_STREAM},
        name="value_stream_start",
    ),
    path(
        "value-stream/methodology/download/",
        methodology_views.value_stream_methodology_download,
        name="value_stream_methodology_download",
    ),
    path(
        "use-case/start/",
        views.start_capture,
        {"capture_type": CaptureSession.CaptureType.USE_CASE},
        name="use_case_start",
    ),
    path(
        "<uuid:session_id>/step/<int:step>/",
        views.capture_step,
        name="capture_step",
    ),
    path(
        "<uuid:session_id>/review/",
        views.capture_review,
        name="capture_review",
    ),
    path(
        "<uuid:session_id>/analyze/",
        views.capture_analyze,
        name="capture_analyze",
    ),
    path(
        "analyses/<uuid:analysis_id>/",
        views.analysis_detail,
        name="analysis_detail",
    ),
    path(
        "analyses/<uuid:analysis_id>/candidates/<uuid:candidate_id>/adopt/",
        adoption_views.candidate_adopt,
        name="candidate_adopt",
    ),
    path(
        "analyses/<uuid:analysis_id>/candidates/<uuid:candidate_id>/reject/",
        adoption_views.candidate_reject,
        name="candidate_reject",
    ),
    path(
        "<uuid:session_id>/discard/",
        views.capture_discard,
        name="capture_discard",
    ),
    path(
        "analyses/<uuid:analysis_id>/structured-review/",
        structured_views.structured_review,
        name="structured_review",
    ),
    path(
        "analyses/<uuid:analysis_id>/structured-review/<uuid:batch_id>/items/<uuid:item_id>/decide/",
        structured_views.structured_review_decide,
        name="structured_review_decide",
    ),
    path(
        "analyses/<uuid:analysis_id>/structured-review/<uuid:batch_id>/commit/",
        structured_views.structured_review_commit,
        name="structured_review_commit",
    ),
    path(
        "processes/<uuid:process_pk>/solution-generation/start/",
        solution_generation_views.solution_generation_start,
        name="solution_generation_start",
    ),
    path(
        "solution-generations/<uuid:run_id>/preview/",
        solution_generation_views.solution_generation_preview,
        name="solution_generation_preview",
    ),
    path(
        "solution-generations/<uuid:run_id>/repair/",
        solution_generation_views.solution_generation_repair,
        name="solution_generation_repair",
    ),
    path(
        "solution-generations/<uuid:run_id>/adopt/",
        solution_generation_views.solution_generation_adopt,
        name="solution_generation_adopt",
    ),
]
