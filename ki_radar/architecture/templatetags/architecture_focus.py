from django import template

from ki_radar.accelerator.solution_generation_entry import (
    build_solution_generation_entry_context,
)
from ki_radar.core.taxonomy import ScreeningLevel

from ..models import EvidenceBasis, TimeToValue
from ..process_findings import build_process_findings
from ..stage_focus import get_stage_focus_decision

register = template.Library()
SCREENING_LABELS = dict(ScreeningLevel.choices)
TIME_TO_VALUE_LABELS = dict(TimeToValue.choices)
EVIDENCE_BASIS_LABELS = dict(EvidenceBasis.choices)


@register.simple_tag
def stage_focus_item(decision, stage):
    if decision is None:
        return {}
    return decision.criteria_for(stage)


@register.filter
def screening_label(value):
    return SCREENING_LABELS.get(value, "-")


@register.filter
def time_to_value_label(value):
    return TIME_TO_VALUE_LABELS.get(value, "-")


@register.filter
def evidence_basis_label(value):
    return EVIDENCE_BASIS_LABELS.get(value, "-")


@register.filter
def is_selected_focus_stage(stage):
    decision = get_stage_focus_decision(stage.value_stream)
    return bool(decision and decision.selected_stage_id == stage.pk)


@register.inclusion_tag("architecture/includes/process_findings_summary.html")
def process_findings_summary(process_analysis):
    return {
        "process_analysis": process_analysis,
        "finding_groups": build_process_findings(process_analysis),
    }


@register.simple_tag
def solution_generation_entry(process_analysis):
    return build_solution_generation_entry_context(process_analysis)
