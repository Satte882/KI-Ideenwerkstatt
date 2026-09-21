from django.urls import path

from . import (
    architecture_assessment_views,
    gated_views,
    solution_views,
    stage_focus_views,
    views,
)

app_name = "architecture"


def _stage_create_from_journey(request, stream_pk):
    return views.stage_create(request, value_stream_id=stream_pk)


def _process_create_from_journey(request, stage_pk):
    return gated_views.process_analysis_create(request, stage_id=stage_pk)


def _option_create_from_journey(request, process_pk):
    return views.solution_option_create(request, process_analysis_id=process_pk)


urlpatterns = [
    path("", views.value_stream_list, name="value_stream_list"),
    path("new/", views.value_stream_create, name="value_stream_create"),
    path("<uuid:pk>/", views.value_stream_detail, name="value_stream_detail"),
    path("<uuid:pk>/edit/", views.value_stream_update, name="value_stream_update"),
    path(
        "<uuid:pk>/stages/focus/",
        stage_focus_views.stage_focus_select,
        name="stage_focus_select",
    ),
    path(
        "<uuid:value_stream_id>/stages/new/",
        views.stage_create,
        name="stage_create",
    ),
    path(
        "<uuid:stream_pk>/stages/new/",
        _stage_create_from_journey,
        name="stage_create",
    ),
    path("stages/<uuid:pk>/edit/", views.stage_update, name="stage_update"),
    path(
        "stages/<uuid:pk>/start-use-case/",
        gated_views.stage_start_use_case,
        name="stage_start_use_case",
    ),
    path(
        "stages/<uuid:stage_id>/processes/new/",
        gated_views.process_analysis_create,
        name="process_analysis_create",
    ),
    path(
        "stages/<uuid:stage_pk>/processes/new/",
        _process_create_from_journey,
        name="process_analysis_create",
    ),
    path(
        "processes/<uuid:pk>/",
        views.process_analysis_detail,
        name="process_analysis_detail",
    ),
    path(
        "processes/<uuid:pk>/edit/",
        views.process_analysis_update,
        name="process_analysis_update",
    ),
    path(
        "processes/<uuid:pk>/validate/",
        views.process_analysis_validate,
        name="process_analysis_validate",
    ),
    path(
        "processes/<uuid:process_pk>/work-design/new/",
        views.work_design_assessment_create,
        name="work_design_assessment_create",
    ),
    path(
        "work-design/<uuid:pk>/",
        views.work_design_assessment_detail,
        name="work_design_assessment_detail",
    ),
    path(
        "work-design/<uuid:pk>/edit/",
        views.work_design_assessment_update,
        name="work_design_assessment_update",
    ),
    path(
        "work-design/<uuid:assessment_pk>/tasks/new/",
        views.work_design_task_create,
        name="work_design_task_create",
    ),
    path(
        "work-design/tasks/<uuid:pk>/edit/",
        views.work_design_task_update,
        name="work_design_task_update",
    ),
    path(
        "work-design/tasks/<uuid:pk>/solution-design/",
        views.work_design_task_select_solution_design,
        name="work_design_task_select_solution_design",
    ),
    path(
        "processes/<uuid:pk>/options/compare/",
        solution_views.solution_option_compare,
        name="solution_option_compare",
    ),
    path(
        "processes/<uuid:process_analysis_id>/options/new/",
        views.solution_option_create,
        name="solution_option_create",
    ),
    path(
        "processes/<uuid:process_pk>/options/new/",
        _option_create_from_journey,
        name="solution_option_create",
    ),
    path(
        "options/<uuid:pk>/edit/",
        views.solution_option_update,
        name="solution_option_update",
    ),
    path(
        "options/<uuid:pk>/architecture-assessment/",
        architecture_assessment_views.solution_architecture_assessment_update,
        name="solution_architecture_assessment_update",
    ),
    path(
        "options/<uuid:pk>/retire/",
        solution_views.solution_option_retire,
        name="solution_option_retire",
    ),
    path(
        "options/<uuid:pk>/start-use-case/",
        views.solution_option_start_use_case,
        name="solution_option_start_use_case",
    ),
]
