import json
from pathlib import Path

from django.conf import settings

from ki_radar.accelerator.catalogs import (
    CATALOGS,
    get_capture_catalog,
    validate_answer_document,
)

REAL_DEMO_PATH = (
    Path(settings.BASE_DIR) / "ki_radar" / "core" / "scenario_blueprints" / "real_demo.v1.json"
)
SYSTEM_MANAGED_PATHS = {
    "value_stream.key",
    "value_stream.status",
    "value_stream.focus.status",
    "value_stream.stages[].key",
    "process_analysis.key",
    "process_analysis.stage_key",
    "process_analysis.status",
    "solution_options[].key",
    "solution_options[].recommendation",
    "solution_options[].evaluation_status",
    "use_case.key",
    "use_case.status",
    "use_case.decision_status",
}
CAPTURE_ROOT_PREFIXES = (
    "value_stream.",
    "process_analysis.",
    "solution_options[].",
    "use_case.",
)


def _leaf_paths(value, prefix=""):
    if isinstance(value, dict):
        for key, child in value.items():
            child_prefix = f"{prefix}.{key}" if prefix else key
            yield from _leaf_paths(child, child_prefix)
        return
    if isinstance(value, list):
        array_prefix = f"{prefix}[]"
        for child in value:
            yield from _leaf_paths(child, array_prefix)
        return
    yield prefix


def _path_values(document, target_path):
    nodes = [document]
    for segment in target_path.split("."):
        is_array = segment.endswith("[]")
        key = segment[:-2] if is_array else segment
        next_nodes = []
        for node in nodes:
            child = node[key]
            if is_array:
                next_nodes.extend(child)
            else:
                next_nodes.append(child)
        nodes = next_nodes
    return nodes


def _render_value(value):
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _real_demo_blueprint():
    return json.loads(REAL_DEMO_PATH.read_text(encoding="utf-8"))


def test_real_demo_narrative_fields_are_covered_by_the_two_capture_catalogs():
    blueprint = _real_demo_blueprint()
    real_demo_narrative_paths = {
        path
        for path in _leaf_paths(blueprint)
        if path.startswith(CAPTURE_ROOT_PREFIXES) and path not in SYSTEM_MANAGED_PATHS
    }
    configured_target_paths = {
        target_path
        for catalog in CATALOGS.values()
        for question in catalog.questions
        for target_path in question.target_paths
    }

    assert configured_target_paths == real_demo_narrative_paths
    assert configured_target_paths.isdisjoint(SYSTEM_MANAGED_PATHS)


def test_real_demo_can_be_expressed_as_complete_value_stream_and_use_case_answers():
    blueprint = _real_demo_blueprint()
    normalized_answers = {}

    for capture_type in ("value_stream", "use_case"):
        catalog = get_capture_catalog(capture_type)
        answers = {}
        for question in catalog.questions:
            values = [
                value
                for target_path in question.target_paths
                for value in _path_values(blueprint, target_path)
                if value not in (None, "")
            ]
            if values:
                answers[question.key] = "\n".join(_render_value(value) for value in values)
            elif question.required:
                raise AssertionError(
                    f"[Real-DEMO] liefert keine narrative Grundlage für {question.key}."
                )

        normalized_answers[capture_type] = validate_answer_document(
            catalog,
            answers,
            require_complete=True,
        )

    value_stream_answers = normalized_answers["value_stream"]
    use_case_answers = normalized_answers["use_case"]
    assert "Vertragsverhandlung" in value_stream_answers["vs_scope_out"]
    assert "Median elf Minuten" in value_stream_answers["vs_stage_pain_metrics"]
    assert "Assistierter Angebotsvergleich" in value_stream_answers["solution_candidates"]
    assert "Bearbeitungszeit je Angebotsvergleich" in use_case_answers["uc_metric"]
    assert "8.25" in use_case_answers["uc_metric"]
    assert "finale Lieferantenauswahl" in use_case_answers["uc_oversight_support"]
