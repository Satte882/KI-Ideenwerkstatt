from __future__ import annotations

from ki_radar.architecture.models import ProcessAnalysis

from .models import SolutionGenerationRun
from .solution_generation_forms import READINESS_FIELD_LABELS, VALIDATION_LABELS
from .solution_generation_preview import build_solution_generation_preview_state
from .solution_generation_sources import build_solution_generation_source_context


def build_solution_generation_entry_context(
    process_analysis: ProcessAnalysis,
) -> dict[str, object]:
    """Build the shared presentation state for every Block-7 generation entry surface."""
    generation_context = build_solution_generation_source_context(process_analysis)
    latest_generation_run = (
        SolutionGenerationRun.objects.filter(
            process_analysis=process_analysis,
            status=SolutionGenerationRun.Status.SUCCESS,
        )
        .order_by("-created_at")
        .first()
    )
    latest_generation_state = (
        build_solution_generation_preview_state(latest_generation_run)
        if latest_generation_run is not None
        else None
    )
    return {
        "generation_ready": generation_context.is_ready,
        "generation_missing_labels": [
            READINESS_FIELD_LABELS.get(field_name, field_name)
            for field_name in generation_context.missing_required
        ],
        "generation_validation_label": VALIDATION_LABELS.get(
            generation_context.validation_state,
            generation_context.validation_state,
        ),
        "latest_generation_run": latest_generation_run,
        "latest_generation_state": latest_generation_state,
    }
