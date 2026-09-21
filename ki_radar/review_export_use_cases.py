from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist

from ki_radar.architecture.provenance import source_differences
from ki_radar.delivery.readiness import READY_REQUIRED_FIELDS, evaluate_delivery_readiness
from ki_radar.review_export_core import (
    SHARING_APPROVED_TARGET,
    SHARING_OMIT,
    SHARING_UNCHANGED,
    ReviewContext,
    ReviewQuestion,
    answer_status,
    answer_value,
    compound_status,
    form_question,
    model_question,
    sharing_class,
    source_revision,
)
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.governance_status import build_governance_statuses
from ki_radar.use_cases.lean_decision_forms import DecisionAssessmentForm
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.services import (
    APPROVAL_METRIC_REQUIREMENTS,
    BASE_REQUIREMENTS,
    GO_LIVE_CORE_REQUIREMENTS,
    INTAKE_REQUIREMENTS,
    PILOT_METRIC_REQUIREMENTS,
    POSITIVE_APPROVAL_CORE_REQUIREMENTS,
    current_decision_check,
)

CLASSIFICATION_FIELDS = {
    "business_domain": "business_domain",
    "business_capability": "capability",
    "process_area": "process_area",
}


def _use_case_requirement_metadata(
    *,
    use_case: UseCase,
    field_name: str,
    label: str,
    blockers: list[str],
    warnings: list[str],
) -> tuple[str, str, str, str]:
    rank = {
        UseCase.Status.IDEA: 0,
        UseCase.Status.REVIEW: 1,
        UseCase.Status.PILOT: 2,
        UseCase.Status.OPERATION: 3,
        UseCase.Status.ENDED: 4,
    }[use_case.status]

    if field_name in INTAKE_REQUIREMENTS:
        requirement, target_rank, condition = "required", 0, "-"
    elif (
        field_name in POSITIVE_APPROVAL_CORE_REQUIREMENTS
        or field_name in APPROVAL_METRIC_REQUIREMENTS
    ):
        requirement, target_rank, condition = "conditional", 1, "bei positiver Freigabe"
    elif (
        field_name in BASE_REQUIREMENTS[UseCase.Status.PILOT]
        or field_name in PILOT_METRIC_REQUIREMENTS
    ):
        requirement, target_rank, condition = "conditional", 1, "fuer Pilotstart"
    elif field_name in GO_LIVE_CORE_REQUIREMENTS:
        requirement, target_rank, condition = "conditional", 2, "fuer Produktivsetzung"
    else:
        requirement, target_rank, condition = "optional", rank, "-"

    relevance = "later" if requirement == "conditional" and rank < target_rank else "now"
    enforcement = "none"
    if label in blockers:
        enforcement = "blocker"
        relevance = "now"
        if requirement == "optional":
            requirement = "conditional"
            condition = "fuer das aktuelle Gate"
    elif f"Readiness offen: {label}" in warnings:
        enforcement = "readiness"
        relevance = "now"
        if requirement == "optional":
            requirement = "conditional"
            condition = "fuer das aktuelle Gate"
    return requirement, relevance, enforcement, condition


def _origin_for(use_case: UseCase):
    try:
        return use_case.architecture_origin
    except ObjectDoesNotExist:
        return None


def _append_use_case_origin(context: ReviewContext, use_case: UseCase) -> None:
    origin = _origin_for(use_case)
    if origin is None:
        context.upstream_context.append(
            "Kein Architecture-Origin gespeichert: direkter Intake oder Ursprung nicht vorhanden."
        )
        return

    value_stream = origin.stage.value_stream
    context.upstream_context.extend(
        [
            f"Value Stream: {value_stream.name}",
            f"Ursprungsphase: {origin.stage.name}",
            (
                f"Prozessanalyse: {origin.process_analysis.name}"
                if origin.process_analysis_id
                else "Prozessanalyse: nicht Teil des gespeicherten Ursprungs"
            ),
            (
                f"Loesungsoption: {origin.solution_option.name}"
                if origin.solution_option_id
                else "Loesungsoption: nicht Teil des gespeicherten Ursprungs"
            ),
        ]
    )
    differences = source_differences(
        origin.source_snapshot,
        stage=origin.stage,
        process_analysis=origin.process_analysis,
        solution_option=origin.solution_option,
    )
    for item in differences:
        context.conflicts.append(
            f"Origin-Drift: {item['source_label']} / {item['source_field']} wurde seit "
            "der Uebernahme geaendert."
        )


def _append_assessment(context: ReviewContext, use_case: UseCase) -> None:
    assessment = use_case.decision_assessments.first()
    if assessment is None:
        if use_case.status == UseCase.Status.REVIEW:
            context.readiness_gaps.append("Aktuelle strukturierte Bewertung fehlt.")
        return

    form = DecisionAssessmentForm(instance=assessment)
    for field_name in form.fields:
        field_obj = form.fields[field_name]
        answer = answer_value(assessment, field_name)
        context.questions.append(
            ReviewQuestion(
                section="Bewertung und Entscheidung",
                question_id=f"assessment.{field_name}",
                label=str(field_obj.label or field_name),
                purpose=str(field_obj.help_text or ""),
                requirement="required" if field_obj.required else "optional",
                relevance="now",
                enforcement="validation" if field_obj.required else "advisory",
                status=answer_status(answer),
                sharing_class=sharing_class(field_name),
                canonical_source="use_cases.lean_decision_forms.DecisionAssessmentForm",
                answer_source=f"DecisionAssessment.{field_name}",
                answer=answer,
                evidence=(
                    "Nachweislink vorhanden, aber aus Export entfernt."
                    if field_name == "evidence_url" and assessment.evidence_url
                    else "-"
                ),
            )
        )


def _append_governance(context: ReviewContext, use_case: UseCase) -> None:
    for status in build_governance_statuses(use_case):
        if status.state == "not_required":
            answer_state = "not_applicable"
            relevance = "not_applicable"
            enforcement = "none"
        elif status.state == "not_assessed":
            answer_state = "open"
            relevance = "now" if use_case.status != UseCase.Status.IDEA else "later"
            enforcement = "readiness"
        elif status.state == "open":
            answer_state = "open"
            relevance = "now"
            enforcement = (
                "blocker"
                if use_case.status in {UseCase.Status.REVIEW, UseCase.Status.PILOT}
                else "readiness"
            )
        else:
            answer_state = "answered"
            relevance = "now"
            enforcement = "validation"

        answer_parts = [status.label]
        if status.result:
            answer_parts.append(status.result)
        if status.rationale:
            answer_parts.append(status.rationale)
        context.questions.append(
            ReviewQuestion(
                section="Governance",
                question_id=f"governance.{status.kind.key}",
                label=status.kind.label,
                purpose=status.attribution_note,
                requirement="conditional",
                relevance=relevance,
                enforcement=enforcement,
                condition="massgebliches Governance-Screening",
                status=answer_state,
                sharing_class=SHARING_APPROVED_TARGET,
                canonical_source=("governance.current_governance_status + GovernanceReview"),
                answer_source=f"GovernanceReview/{status.kind.key}",
                answer=" | ".join(answer_parts),
            )
        )


def _append_delivery(context: ReviewContext, use_case: UseCase) -> None:
    package = use_case.delivery_packages.order_by("-version").first()
    if package is None:
        if use_case.status in {UseCase.Status.REVIEW, UseCase.Status.PILOT}:
            context.readiness_gaps.append("Kein Delivery Package vorhanden.")
        return

    required_fields = {
        field_name for fields in READY_REQUIRED_FIELDS.values() for field_name in fields
    }
    optional_moscow = {"should_scope", "could_scope", "wont_this_time"}
    for field_name in sorted(required_fields | optional_moscow):
        requirement = "required" if field_name in required_fields else "optional"
        sharing_override = (
            SHARING_OMIT if field_name == "external_delivery_url" else SHARING_APPROVED_TARGET
        )
        context.questions.append(
            model_question(
                obj=package,
                field_name=field_name,
                section=f"Delivery v{package.version}",
                question_id=f"delivery.{field_name}",
                canonical_source="delivery.DeliveryPackage + READY_REQUIRED_FIELDS",
                requirement=requirement,
                relevance="now",
                enforcement="readiness" if requirement == "required" else "none",
                sharing_override=sharing_override,
            )
        )

    for finding in evaluate_delivery_readiness(package):
        line = f"Delivery [{finding.code}] {finding.message}"
        if finding.severity == "blocker":
            context.blockers.append(line)
        else:
            context.readiness_gaps.append(line)


def _classification_answer(form, use_case, field_name: str) -> tuple[str | None, str]:
    if field_name not in CLASSIFICATION_FIELDS:
        return None, ""
    try:
        classification = use_case.classification
    except ObjectDoesNotExist:
        return "", "UseCaseClassification"
    source_field = CLASSIFICATION_FIELDS[field_name]
    raw_value = getattr(classification, source_field, "")
    if field_name == "business_domain" and raw_value:
        raw_value = classification.get_business_domain_display()
    return str(raw_value or ""), f"UseCaseClassification.{source_field}"


def _append_use_case_fields(
    context: ReviewContext,
    use_case: UseCase,
    form,
    *,
    blockers: list[str],
    warnings: list[str],
) -> None:
    for field_name in form.fields:
        field_obj = form.fields[field_name]
        label = str(field_obj.label or field_name)
        requirement, relevance, enforcement, condition = _use_case_requirement_metadata(
            use_case=use_case,
            field_name=field_name,
            label=label,
            blockers=blockers,
            warnings=warnings,
        )
        answer_override, answer_source = _classification_answer(form, use_case, field_name)
        context.questions.append(
            form_question(
                form=form,
                obj=use_case,
                field_name=field_name,
                section="Use Case",
                question_id=f"use_case.{field_name}",
                canonical_source=(
                    "use_cases.UseCase + UseCaseForm + canonical requirement/gate logic"
                ),
                requirement=requirement,
                relevance=relevance,
                enforcement=enforcement,
                condition=condition,
                answer_override=answer_override,
                answer_source=answer_source,
            )
        )


def _append_pilot_metric_set(context: ReviewContext, use_case: UseCase) -> None:
    metric_values = [getattr(use_case, name, None) for name in PILOT_METRIC_REQUIREMENTS]
    metric_lines = []
    for field_name in PILOT_METRIC_REQUIREMENTS:
        label = str(use_case._meta.get_field(field_name).verbose_name)
        value = answer_value(use_case, field_name)
        metric_lines.append(f"{label}: {value or '[offen]'}")

    context.questions.append(
        ReviewQuestion(
            section="Use Case",
            question_id="use_case.pilot_metric_set",
            label="Pilot-Metrikset",
            purpose="Kanonische Metrikbestandteile aus PILOT_METRIC_REQUIREMENTS.",
            requirement="conditional",
            relevance="later" if use_case.status == UseCase.Status.IDEA else "now",
            enforcement=(
                "readiness"
                if use_case.status in {UseCase.Status.REVIEW, UseCase.Status.PILOT}
                else "none"
            ),
            condition="fuer Pilotstart und belastbare Erfolgsmessung",
            status=compound_status(metric_values),
            sharing_class=SHARING_APPROVED_TARGET,
            canonical_source="use_cases.services.PILOT_METRIC_REQUIREMENTS",
            answer_source="UseCase metric fields",
            answer="\n".join(metric_lines),
        )
    )


def build_use_case_review_context(use_case: UseCase, actor) -> ReviewContext:
    form = UseCaseForm(instance=use_case, current_user=actor)
    decision_check = current_decision_check(use_case)
    blockers = list(decision_check.blockers)
    warnings = list(decision_check.warnings)
    context = ReviewContext(
        anchor="UseCase",
        title=use_case.title,
        reference=use_case.short_id or "Use Case",
        lifecycle=(f"{use_case.get_status_display()} | {use_case.get_decision_status_display()}"),
        source_revision=source_revision(use_case),
        blockers=blockers.copy(),
        readiness_gaps=warnings.copy(),
        traceability=[
            "UseCaseForm liefert sichtbare Labels; Requiredness kommt aus Domainregeln.",
            "INTAKE_REQUIREMENTS und Gate-/Readiness-Services liefern Pflichtlogik.",
            "Upstream wird nur ueber UseCaseOrigin eingebettet.",
            "Direkter Intake erfindet keinen Upstream-Kontext.",
            "Governance-Status kommt aus dem Governance-Bounded-Context.",
            "Delivery nutzt nur aktuelle Felder/Readiness, nie Source-Manifest oder URLs.",
        ],
    )
    _append_use_case_origin(context, use_case)
    _append_use_case_fields(
        context,
        use_case,
        form,
        blockers=blockers,
        warnings=warnings,
    )
    _append_pilot_metric_set(context, use_case)
    context.questions.append(
        model_question(
            obj=use_case,
            field_name="decision_status",
            section="Bewertung und Entscheidung",
            question_id="use_case.decision_status",
            canonical_source="use_cases.UseCase.decision_status",
            requirement="required",
            sharing_override=SHARING_UNCHANGED,
        )
    )
    _append_assessment(context, use_case)
    _append_governance(context, use_case)
    _append_delivery(context, use_case)
    return context
