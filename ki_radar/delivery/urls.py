from django.urls import path

from . import ai_views, lean_views, residual_views, views

app_name = "delivery"
urlpatterns = [
    path("", views.package_list, name="package_list"),
    path("methodology/", views.methodology_reference, name="methodology_reference"),
    path("methodology/download/", views.methodology_download, name="methodology_download"),
    path("use-cases/<uuid:use_case_id>/new/", views.package_create, name="package_create"),
    path("<uuid:pk>/", views.package_detail, name="package_detail"),
    path("<uuid:pk>/edit/", views.package_update, name="package_update"),
    path(
        "<uuid:pk>/ai/mvp-scope/generate/",
        ai_views.generate_mvp_scope_draft_view,
        name="mvp_scope_ai_generate",
    ),
    path(
        "<uuid:pk>/ai/mvp-scope/event/",
        ai_views.mvp_scope_draft_event,
        name="mvp_scope_ai_event",
    ),
    path(
        "<uuid:pk>/mapping/<str:target_field>/refine/",
        residual_views.refine_mapping_text,
        name="refine_mapping_text",
    ),
    path(
        "<uuid:pk>/sections/<str:section_key>/review/",
        views.package_section_review,
        name="package_section_review",
    ),
    path(
        "<uuid:pk>/sources/technical-owner/resolve/",
        views.package_resolve_technical_owner_source,
        name="package_resolve_technical_owner_source",
    ),
    path("<uuid:pk>/ready/", lean_views.package_mark_ready, name="package_mark_ready"),
    path("<uuid:pk>/handover/", lean_views.package_handover, name="package_handover"),
    path("<uuid:pk>/export.md", views.package_export_markdown, name="package_export_markdown"),
]
