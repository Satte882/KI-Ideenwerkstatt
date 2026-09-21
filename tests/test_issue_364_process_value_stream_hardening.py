from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROCESS_DETAIL = ROOT.joinpath(
    "templates", "architecture", "process_analysis_detail.html"
).read_text(encoding="utf-8")
VALUE_STREAM_DETAIL = ROOT.joinpath(
    "templates", "architecture", "value_stream_detail.html"
).read_text(encoding="utf-8")
PROCESS_FINDINGS_TEMPLATE = ROOT.joinpath(
    "templates", "architecture", "includes", "process_findings_summary.html"
).read_text(encoding="utf-8")
PROCESS_FINDINGS = ROOT.joinpath("ki_radar", "architecture", "process_findings.py").read_text(
    encoding="utf-8"
)
ANALYSIS_NAVIGATION_JS = ROOT.joinpath("static", "js", "analysis-navigation.js").read_text(
    encoding="utf-8"
)


def test_process_analysis_follows_source_diagnosis_validation_and_export():
    lifecycle = PROCESS_DETAIL.index("includes/lifecycle_rail.html")
    header = PROCESS_DETAIL.index('class="cr-page-header cr-work-header"')
    local_navigation = PROCESS_DETAIL.index("includes/local_work_status.html")
    next_action = PROCESS_DETAIL.index('id="next-action"')
    focus_source = PROCESS_DETAIL.index('data-testid="process-stage-focus-source"')
    process_frame = PROCESS_DETAIL.index('data-testid="process-frame"')
    diagnosis = PROCESS_DETAIL.index('id="prozessanalyse"')
    findings = PROCESS_DETAIL.index("process_findings_summary process_analysis")
    secondary = PROCESS_DETAIL.index('id="prozessdetails"')
    validation = PROCESS_DETAIL.index('id="process-validation"')
    work_design = PROCESS_DETAIL.index('id="arbeitsgestaltung"')
    solutions = PROCESS_DETAIL.index('id="loesungsoptionen"')
    export = PROCESS_DETAIL.index('data-testid="llm-review-export-notice"')

    assert lifecycle < header < local_navigation < next_action < focus_source
    assert focus_source < process_frame < diagnosis < findings < secondary
    assert secondary < validation < work_design < solutions < export


def test_process_validation_keeps_current_readiness_visible_and_metadata_secondary():
    assert PROCESS_DETAIL.count("{{ process_analysis.get_status_display }}") == 1
    assert 'data-testid="current-process-validation"' in PROCESS_DETAIL
    assert "Keine Validierung für Version v{{ process_analysis.version }}" in PROCESS_DETAIL
    validation_disclosure = (
        '<details class="architecture-disclosure" data-testid="process-validation-evidence">'
    )
    assert validation_disclosure in PROCESS_DETAIL
    assert "Validierungsnachweis und Historie" in PROCESS_DETAIL
    assert "Geprüfte Version" in PROCESS_DETAIL
    assert "Validiert durch" in PROCESS_DETAIL
    assert "Historische Validierungen" in PROCESS_DETAIL


def test_process_core_shows_one_finding_summary_and_groups_secondary_fields():
    core_start = PROCESS_DETAIL.index('data-testid="process-core-diagnosis"')
    core_end = PROCESS_DETAIL.index('id="prozessdetails"')
    core = PROCESS_DETAIL[core_start:core_end]

    for anchor in (
        "analysis-current-flow",
        "analysis-bottlenecks",
        "analysis-baseline-metrics",
        "analysis-roles",
    ):
        assert f'id="{anchor}"' in core
    assert core.count("process_findings_summary process_analysis") == 1
    assert 'data-testid="process-original-fields"' in core
    assert "architecture-artifact-grid" not in core

    for group_id in ("process-rules-collaboration", "process-systems-data"):
        assert (
            f'<details class="architecture-disclosure artifact-disclosure" id="{group_id}">'
            in PROCESS_DETAIL
        )
    for anchor in (
        "analysis-business-rules",
        "analysis-handoffs",
        "analysis-exceptions",
        "analysis-target-state-principles",
        "analysis-systems",
        "analysis-data-objects",
    ):
        assert f'id="{anchor}"' in PROCESS_DETAIL

    assert 'data-bs-toggle="collapse"' not in PROCESS_DETAIL


def test_process_finding_source_anchors_remain_reachable_after_disclosure_move():
    expected_anchors = (
        "analysis-bottlenecks",
        "analysis-baseline-metrics",
        "analysis-roles",
        "analysis-systems",
        "analysis-business-rules",
        "analysis-handoffs",
        "analysis-exceptions",
        "analysis-target-state-principles",
        "process-validation",
    )

    assert "field_name.replace('_', '-')" in PROCESS_FINDINGS
    for anchor in expected_anchors:
        assert f'id="{anchor}"' in PROCESS_DETAIL

    assert 'href="#{{ item.source_anchor }}"' in PROCESS_FINDINGS_TEMPLATE


def test_process_findings_are_flat_and_remain_before_solution_selection():
    assert "architecture-artifact-grid" not in PROCESS_FINDINGS_TEMPLATE
    assert "Kernbefund" in PROCESS_FINDINGS_TEMPLATE
    assert PROCESS_DETAIL.index("process_findings_summary process_analysis") < PROCESS_DETAIL.index(
        'id="loesungsoptionen"'
    )


def test_value_stream_prioritizes_trigger_outcome_and_focus_before_context():
    next_action = VALUE_STREAM_DETAIL.index('id="next-action"')
    core = VALUE_STREAM_DETAIL.index('data-testid="value-stream-core"')
    focus = VALUE_STREAM_DETAIL.index('id="fokus-priorisierung"')
    context = VALUE_STREAM_DETAIL.index('data-testid="value-stream-context"')
    phases = VALUE_STREAM_DETAIL.index('id="end-to-end-phasen"')

    assert next_action < core < focus < context < phases
    assert VALUE_STREAM_DETAIL.index("Auslöser", core) < VALUE_STREAM_DETAIL.index("Ergebnis", core)
    assert VALUE_STREAM_DETAIL.count("{{ value_stream.focus.get_status_display }}") == 1
    assert "Begründung der Fokusentscheidung" in VALUE_STREAM_DETAIL
    assert "Screening unvollständig:" in VALUE_STREAM_DETAIL


def test_value_stream_secondary_context_and_screening_use_native_disclosure():
    for summary in (
        "Screening- und Einordnungsdetails",
        "Rahmen, Scope und Leitplanken",
        "Entscheidungsnachweis und Phasenvergleich",
        "Phasendetails: Rollen, Systeme, Daten und Kennzahlen",
    ):
        assert summary in VALUE_STREAM_DETAIL

    assert VALUE_STREAM_DETAIL.count("<details") >= 4
    assert 'data-bs-toggle="collapse"' not in VALUE_STREAM_DETAIL


def test_native_stage_disclosure_is_not_wrapped_by_legacy_runtime_enhancement():
    assert 'data-testid="stage-details"' in VALUE_STREAM_DETAIL
    assert "details[data-testid='stage-details']" in ANALYSIS_NAVIGATION_JS
    guard = ANALYSIS_NAVIGATION_JS.index("details[data-testid='stage-details']")
    legacy_wrapper = ANALYSIS_NAVIGATION_JS.index('document.createElement("details")', guard)

    assert guard < legacy_wrapper


def test_focus_phase_keeps_selection_and_rationale_visible_before_evidence():
    focus_section = VALUE_STREAM_DETAIL.index('id="fokusphase"')
    selected = VALUE_STREAM_DETAIL.index("Ausgewählte Phase", focus_section)
    rationale = VALUE_STREAM_DETAIL.index("Begründung der Phasenentscheidung", focus_section)
    evidence = VALUE_STREAM_DETAIL.index("Entscheidungsnachweis und Phasenvergleich", focus_section)

    assert selected < evidence
    assert rationale < evidence
    assert "Kurzpfad begründet:" in VALUE_STREAM_DETAIL[:evidence]


def test_state_gated_stage_placeholders_are_status_copy_not_disabled_buttons():
    for label in (
        "Nicht als Fokusphase ausgewählt",
        "Erst Phasenerfassung abschließen",
        "Erst Fokusentscheidung abschließen",
    ):
        assert label in VALUE_STREAM_DETAIL
        assert f"disabled>{label}</button>" not in VALUE_STREAM_DETAIL

    assert 'data-testid="focus-stage-status"' in VALUE_STREAM_DETAIL
    assert "Prozess im Detail analysieren: zuerst Fokus auswählen" in VALUE_STREAM_DETAIL
    assert "Use Case direkt aus Phase ableiten" in VALUE_STREAM_DETAIL
