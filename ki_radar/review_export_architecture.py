from __future__ import annotations

from ki_radar.architecture.focus import ValueStreamFocus, get_value_stream_focus
from ki_radar.architecture.forms import (
    ProcessAnalysisForm,
    SolutionOptionForm,
    ValueStreamForm,
    ValueStreamStageForm,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.architecture.provenance import source_differences
from ki_radar.architecture.solution_selection import (
    comparison_blockers,
    diagnosis_readiness_blockers,
    ordered_solution_options,
)
from ki_radar.architecture.stage_focus import (
    CRITERIA_KEYS,
    EVIDENCE_BASIS_KEY,
    get_stage_focus_decision,
)
from ki_radar.architecture.stage_focus_forms import CRITERIA_LABELS
from ki_radar.review_export_core import (
    SHARING_APPROVED_TARGET,
    SHARING_UNCHANGED,
    ReviewContext,
    ReviewQuestion,
    answer_status,
    answer_value,
    compound_status,
    form_question,
    is_present,
    model_question,
    sharing_class,
    source_revision,
)
from ki_radar.use_cases.journey import PROCESS_REQUIRED_FIELDS


def _stage_ref(index: int) -> str:
    return f"stage-{index:02d}"


def _option_ref(index: int) -> str:
    return f"option-{index:02d}"


def build_value_stream_review_context(value_stream: ValueStream, actor) -> ReviewContext:
    del actor
    focus = get_value_stream_focus(value_stream)
    form = ValueStreamForm(instance=value_stream)
    context = ReviewContext(
        anchor="ValueStream",
        title=value_stream.name,
        reference="Value Stream",
        lifecycle=value_stream.get_status_display(),
        source_revision=source_revision(value_stream),
        traceability=[
            "ValueStreamForm liefert sichtbare Labels und Eingaben.",
            "ValueStreamFocus liefert Fokusentscheidung und Screening-Vollstaendigkeit.",
            "StageFocusDecision liefert Phasenvergleich oder begruendeten Kurzpfad.",
        ],
    )

    model_fields = set(ValueStreamForm._meta.fields)
    for field_name in form.fields:
        if field_name not in model_fields:
            continue
        context.questions.append(
            form_question(
                form=form,
                obj=value_stream,
                field_name=field_name,
                section="Value Stream",
                question_id=f"value_stream.{field_name}",
                canonical_source="architecture.ValueStream + ValueStreamForm",
            )
        )

    focus_status = focus.status if focus else ValueStreamFocus.Status.NOT_SCREENED
    for field_name in form.fields:
        if field_name in model_fields:
            continue
        focus_name = {"focus_status": "status", "focus_rationale": "rationale"}.get(
            field_name,
            field_name,
        )
        value = getattr(focus, focus_name, "") if focus else ""
        condition_applies = focus_status != ValueStreamFocus.Status.NOT_SCREENED
        always_required = field_name in {"business_domain", "focus_status"}
        applicable = always_required or condition_applies
        answer = answer_value(focus, focus_name) if focus is not None else ""
        context.questions.append(
            form_question(
                form=form,
                obj=value_stream,
                field_name=field_name,
                section="Fokus und Priorisierung",
                question_id=f"value_stream.focus.{focus_name}",
                canonical_source="architecture.ValueStreamFocus + ValueStreamForm.clean()",
                requirement="required" if always_required else "conditional",
                relevance="now" if applicable else "not_applicable",
                enforcement="validation" if applicable else "none",
                condition="-" if always_required else "Fokusentscheidung != not_screened",
                answer_source=f"ValueStreamFocus.{focus_name}",
                answer_override=answer,
                status_override=answer_status(value, applicable=applicable),
                sharing_override=sharing_class(focus_name),
            )
        )

    if focus is not None and focus.status != ValueStreamFocus.Status.NOT_SCREENED:
        for label in focus.missing_screening_fields:
            context.readiness_gaps.append(f"Value-Stream-Screening offen: {label}")

    stages = list(value_stream.stages.all().order_by("sequence", "created_at"))
    for index, stage in enumerate(stages, start=1):
        stage_form = ValueStreamStageForm(instance=stage)
        reference = _stage_ref(index)
        for field_name in stage_form.fields:
            context.questions.append(
                form_question(
                    form=stage_form,
                    obj=stage,
                    field_name=field_name,
                    section="Value-Stream-Phasen",
                    question_id=f"value_stream.stage.{field_name}",
                    canonical_source=("architecture.ValueStreamStage + ValueStreamStageForm"),
                    instance_ref=reference,
                )
            )

    _append_stage_focus(context, value_stream, stages, focus)
    return context


def _append_stage_focus(context, value_stream, stages, focus) -> None:
    decision = get_stage_focus_decision(value_stream)
    if decision is None:
        if focus is None or not focus.is_selected or not stages:
            return
        context.blockers.append(
            "Phasenentscheidung fehlt: Vor der Prozessanalyse muss eine Fokusphase "
            "oder ein begruendeter Kurzpfad gespeichert werden."
        )
        context.questions.append(
            ReviewQuestion(
                section="Fokusphase",
                question_id="value_stream.stage_focus.decision",
                label="Fokusphase ausgewaehlt und begruendet",
                purpose="Legt fest, welche Phase in die Prozessdetailanalyse uebergeht.",
                requirement="conditional",
                relevance="now",
                enforcement="blocker",
                condition="Value Stream ist fuer die Vertiefung ausgewaehlt",
                status="open",
                sharing_class=SHARING_UNCHANGED,
                canonical_source="architecture.StageFocusDecision",
                answer_source="StageFocusDecision",
                answer="",
            )
        )
        return

    context.questions.append(
        model_question(
            obj=decision,
            field_name="rationale",
            section="Fokusphase",
            question_id="value_stream.stage_focus.rationale",
            canonical_source="architecture.StageFocusDecision",
            requirement="required",
            sharing_override=SHARING_APPROVED_TARGET,
        )
    )
    if decision.is_short_path:
        context.questions.append(
            model_question(
                obj=decision,
                field_name="short_path_reason",
                section="Fokusphase",
                question_id="value_stream.stage_focus.short_path_reason",
                canonical_source="architecture.StageFocusDecision.clean()",
                requirement="conditional",
                condition="Bewusster Kurzpfad",
                enforcement="validation",
            )
        )

    snapshot = decision.criteria_snapshot or {}
    for index, stage in enumerate(stages, start=1):
        reference = _stage_ref(index)
        saved = snapshot.get(str(stage.pk), {})
        for criterion in (*CRITERIA_KEYS, EVIDENCE_BASIS_KEY):
            applicable = not decision.is_short_path
            answer = str(saved.get(criterion, "") or "")
            label = (
                "Evidenzbasis"
                if criterion == EVIDENCE_BASIS_KEY
                else CRITERIA_LABELS.get(criterion, criterion)
            )
            context.questions.append(
                ReviewQuestion(
                    section="Phasenvergleich",
                    question_id=f"value_stream.stage_focus.{criterion}",
                    label=label,
                    purpose="Kanonisches Kriterium des gespeicherten Phasenvergleichs.",
                    requirement="conditional",
                    relevance="now" if applicable else "not_applicable",
                    enforcement="validation" if applicable else "none",
                    condition=(
                        "vollstaendiger Phasenvergleich; entfaellt beim begruendeten Kurzpfad"
                    ),
                    status=answer_status(answer, applicable=applicable),
                    sharing_class=SHARING_UNCHANGED,
                    canonical_source="architecture.StageFocusDecision.criteria_snapshot",
                    answer_source=f"criteria_snapshot[{reference}].{criterion}",
                    instance_ref=reference,
                    answer=answer,
                )
            )


def build_process_review_context(process_analysis: ProcessAnalysis, actor) -> ReviewContext:
    del actor
    value_stream = process_analysis.stage.value_stream
    focus = get_value_stream_focus(value_stream)
    form = ProcessAnalysisForm(instance=process_analysis)
    options = ordered_solution_options(process_analysis)
    comparison_gaps = comparison_blockers(options)
    diagnosis_current = not comparison_gaps

    context = ReviewContext(
        anchor="ProcessAnalysis",
        title=process_analysis.name,
        reference=f"Prozessanalyse v{process_analysis.version}",
        lifecycle=process_analysis.get_status_display(),
        source_revision=(
            f"process-v{process_analysis.version}:{source_revision(process_analysis)}"
        ),
        upstream_context=[
            f"Value Stream: {value_stream.name}",
            f"Fokusphase: {process_analysis.stage.name}",
            (
                f"Fokusentscheidung: {focus.get_status_display()}"
                if focus is not None
                else "Fokusentscheidung: nicht gespeichert"
            ),
        ],
        traceability=[
            "Upstream wird ausschliesslich ueber ProcessAnalysis.stage abgeleitet.",
            "ProcessAnalysisForm liefert sichtbare Labels und Eingaben.",
            "PROCESS_REQUIRED_FIELDS liefert die bestehende Discovery-Readiness.",
            "ProcessValidation und source_differences liefern Validierung und Drift.",
            "Lösungsoptionen stammen aus ordered_solution_options (nur aktive Optionen).",
        ],
    )

    diagnosis_fields = {"diagnostic_observations", "confirmed_causes"}
    for field_name in form.fields:
        requirement = "required" if field_name in PROCESS_REQUIRED_FIELDS else "optional"
        enforcement = "readiness" if field_name in PROCESS_REQUIRED_FIELDS else "none"
        relevance = "now"
        condition = "-"
        if field_name in diagnosis_fields:
            requirement = "conditional"
            relevance = "now" if diagnosis_current else "later"
            enforcement = "blocker"
            condition = "fuer eine bindende Loesungswahl"
        context.questions.append(
            form_question(
                form=form,
                obj=process_analysis,
                field_name=field_name,
                section="Prozessanalyse und Diagnose",
                question_id=f"process.{field_name}",
                canonical_source=(
                    "architecture.ProcessAnalysis + ProcessAnalysisForm + PROCESS_REQUIRED_FIELDS"
                ),
                requirement=requirement,
                relevance=relevance,
                enforcement=enforcement,
                condition=condition,
            )
        )

    for field_name in PROCESS_REQUIRED_FIELDS:
        if is_present(getattr(process_analysis, field_name, None)):
            continue
        label = str(process_analysis._meta.get_field(field_name).verbose_name)
        context.readiness_gaps.append(f"Prozessanalyse offen: {label}")

    _append_process_validation(context, process_analysis)
    _append_process_drift(context, process_analysis)
    _append_solution_options(context, process_analysis, options)

    for blocker in comparison_gaps:
        context.readiness_gaps.append(f"Loesungsvergleich: {blocker}")
    if diagnosis_current:
        for blocker in diagnosis_readiness_blockers(process_analysis):
            context.blockers.append(f"Bindende Loesungswahl: {blocker} fehlt.")

    _append_solution_selection(
        context,
        process_analysis,
        options,
        comparison_gaps=comparison_gaps,
    )
    return context


def _append_process_validation(context, process_analysis) -> None:
    current_validation = process_analysis.validations.filter(
        process_version=process_analysis.version
    ).first()
    any_validation = process_analysis.validations.first()
    if current_validation:
        validation_status = "answered"
        validation_answer = (
            f"Version v{process_analysis.version} validiert; "
            f"Notiz: {current_validation.note or '[keine zusaetzliche Notiz]'}"
        )
    elif any_validation:
        validation_status = "partial"
        validation_answer = (
            f"Nur aeltere Validierung vorhanden (v{any_validation.process_version}); "
            f"aktuelle Version ist v{process_analysis.version}."
        )
    else:
        validation_status = "open"
        validation_answer = ""

    context.questions.append(
        ReviewQuestion(
            section="Validierung und Provenance",
            question_id="process.validation.current_version",
            label="Aktuelle Prozessversion validiert",
            purpose=("Unterscheidet aktuelle Validierung von veralteten Validierungsartefakten."),
            requirement="conditional",
            relevance="now",
            enforcement="validation",
            condition="belastbare Prozessanalyse vor nachgelagerter Entscheidung",
            status=validation_status,
            sharing_class=SHARING_APPROVED_TARGET,
            canonical_source="architecture.ProcessValidation",
            answer_source="ProcessAnalysis.validations",
            answer=validation_answer,
            evidence=(
                "Nachweislink vorhanden, aber aus Export entfernt."
                if current_validation and current_validation.evidence_url
                else "-"
            ),
        )
    )
    if validation_status != "answered":
        context.readiness_gaps.append(
            "Fuer die aktuelle Prozessversion fehlt eine aktuelle Validierung."
        )


def _append_process_drift(context, process_analysis) -> None:
    differences = source_differences(
        process_analysis.source_snapshot,
        stage=process_analysis.stage,
    )
    for item in differences:
        context.conflicts.append(
            f"Upstream-Drift: {item['source_label']} / {item['source_field']} wurde seit "
            "der Uebernahme geaendert."
        )


def _append_solution_options(context, process_analysis, options) -> None:
    detail_fields = (
        "description",
        "expected_value",
        "bottleneck_coverage",
        "data_requirements",
        "application_impact",
        "integration_impact",
        "risks",
        "architecture_fit",
        "feasibility",
        "integration_effort",
        "time_to_value",
    )
    for index, option in enumerate(options, start=1):
        reference = _option_ref(index)
        option_form = SolutionOptionForm(
            instance=option,
            process_analysis=process_analysis,
        )
        for field_name in option_form.fields:
            context.questions.append(
                form_question(
                    form=option_form,
                    obj=option,
                    field_name=field_name,
                    section="Loesungsoptionen",
                    question_id=f"solution_option.{field_name}",
                    canonical_source="architecture.SolutionOption + SolutionOptionForm",
                    instance_ref=reference,
                )
            )

        details = [getattr(option, name, None) for name in detail_fields]
        relevance = (
            "now" if option.evaluation_status == option.EvaluationStatus.ASSESSED else "later"
        )
        context.questions.append(
            ReviewQuestion(
                section="Loesungsoptionen",
                question_id="solution_option.comparison_complete",
                label="Vergleichsprofil vollstaendig",
                purpose="Verwendet die bestehende comparison_complete-Domainlogik.",
                requirement="conditional",
                relevance=relevance,
                enforcement="validation",
                condition="Option ist bewertet oder soll bindend verglichen werden",
                status=("answered" if option.comparison_complete else compound_status(details)),
                sharing_class=SHARING_UNCHANGED,
                canonical_source="architecture.SolutionOption.comparison_complete",
                answer_source=f"{reference}.comparison_complete",
                instance_ref=reference,
                answer="ja" if option.comparison_complete else "nein",
            )
        )


def _append_solution_selection(
    context,
    process_analysis,
    options,
    *,
    comparison_gaps,
) -> None:
    selection = process_analysis.solution_selection_decisions.order_by("-decided_at").first()
    if selection is not None:
        context.questions.extend(
            [
                ReviewQuestion(
                    section="Loesungsentscheidung",
                    question_id="solution_selection.selected_option",
                    label="Bevorzugte Loesungsoption",
                    answer=str(selection.selected_option.name),
                    status="answered",
                    requirement="required",
                    relevance="now",
                    enforcement="validation",
                    sharing_class=SHARING_APPROVED_TARGET,
                    canonical_source="architecture.SolutionSelectionDecision",
                    answer_source="SolutionSelectionDecision.selected_option",
                ),
                model_question(
                    obj=selection,
                    field_name="rationale",
                    section="Loesungsentscheidung",
                    question_id="solution_selection.rationale",
                    canonical_source="architecture.SolutionSelectionDecision",
                    requirement="required",
                    enforcement="validation",
                ),
            ]
        )
        return

    if len(options) < 2:
        return
    context.questions.append(
        ReviewQuestion(
            section="Loesungsentscheidung",
            question_id="solution_selection.decision",
            label="Bindende Loesungsentscheidung",
            answer="",
            status="open",
            requirement="conditional",
            relevance="later" if comparison_gaps else "now",
            enforcement="advisory",
            condition="wenn die Exploration in eine verbindliche Praeferenz uebergeht",
            sharing_class=SHARING_UNCHANGED,
            canonical_source="architecture.SolutionSelectionDecision",
            answer_source="SolutionSelectionDecision",
        )
    )
