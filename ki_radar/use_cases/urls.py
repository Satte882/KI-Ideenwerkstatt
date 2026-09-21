from django.urls import path

from . import (
    decision_views,
    idea_views,
    intake_views,
    lean_decision_views,
    origin_consistency_views,
    views,
)

app_name = "use_cases"
urlpatterns = [
    path("", views.use_case_list, name="list"),
    path("ideas/", idea_views.idea_list, name="idea_list"),
    path("ideas/new/", idea_views.idea_create, name="idea_create"),
    path("ideas/<uuid:pk>/", idea_views.idea_detail, name="idea_detail"),
    path("ideas/<uuid:pk>/edit/", idea_views.idea_edit, name="idea_edit"),
    path("ideas/<uuid:pk>/triage/", idea_views.idea_triage, name="idea_triage"),
    path("ideas/<uuid:pk>/dismiss/", idea_views.idea_dismiss, name="idea_dismiss"),
    path("ideas/<uuid:pk>/promote/", idea_views.idea_promote, name="idea_promote"),
    path("new/", intake_views.use_case_intake, {"step": 1}, name="create"),
    path("new/discard/", intake_views.discard_use_case_intake, name="intake_discard"),
    path("new/step/<int:step>/", intake_views.use_case_intake, name="intake_step"),
    path("export.csv", views.export_csv, name="export_csv"),
    path("<uuid:pk>/", views.use_case_detail, name="detail"),
    path("<uuid:pk>/edit/", views.use_case_edit, name="edit"),
    path("<uuid:pk>/assessment/new/", decision_views.assessment_create, name="assessment_create"),
    path(
        "<uuid:pk>/decision/new/",
        lean_decision_views.approval_decision_create,
        name="approval_decision_create",
    ),
    path(
        "decision/<int:decision_id>/second-approval/",
        decision_views.second_approval_review,
        name="second_approval_review",
    ),
    path(
        "<uuid:pk>/origin-consistency/",
        origin_consistency_views.origin_consistency_review,
        name="origin_consistency_review",
    ),
    path(
        "<uuid:pk>/origin-consistency/feedback/",
        origin_consistency_views.origin_consistency_feedback,
        name="origin_consistency_feedback",
    ),
    path("<uuid:pk>/copilot/", views.use_case_copilot, name="copilot"),
]
