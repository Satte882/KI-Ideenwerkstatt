from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Max

from ki_radar.architecture.investigation_adoption import (
    InvestigationDraftAdoptionError,
    adopt_investigation_drafts,
    preview_investigation_draft_adoption,
)
from ki_radar.architecture.models import EvidenceBasis, ProcessAnalysis, SolutionOption

from .investigation_models import (
    InvestigationBriefRevision,
    InvestigationMaterialization,
    InvestigationRun,
)
from .investigation_presentation import humanize_investigation_text, population_summary
from .investigation_runtime import (
    InvestigationRunError,
    content_hash,
    decision_brief_blockers,
    locked_run,
    normalize_idempotency_key,
    read_run,
)


def _reference_label(reference: Mapping[str, Any]) -> str:
    source_id = str(reference.get("source_id") or "")
    tool_result_id = str(reference.get("tool_result_id") or "")
    locator = reference.get("locator")
    revision_hash = str(reference.get("revision_hash") or "")
    if source_id:
        return f"source:{source_id} locator:{locator} sha256:{revision_hash}"
    if tool_result_id:
        return f"tool-result:{tool_result_id} source-sha256:{revision_hash}"
    return "unbekannte Referenz"


def _list_text(value: object) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return "; ".join(f"{key}: {item}" for key, item in value.items() if str(item).strip())
    return str(value or "").strip()


@transaction.atomic
def freeze_review_revision(
    *,
    actor,
    run_id,
    operation_key: str | None = None,
) -> InvestigationBriefRevision:
    run = locked_run(actor=actor, run_id=run_id)
    if run.status != InvestigationRun.Status.READY:
        raise InvestigationRunError(
            "Nur ein technisch READY-geprüfter Brief kann als Review-Snapshot eingefroren werden.",
            code="ready_required",
        )
    blockers = decision_brief_blockers(run)
    if blockers:
        raise InvestigationRunError(
            "Der Decision Brief erfüllt den VS1/3-Vertrag noch nicht.",
            code="decision_brief_incomplete",
        )
    key = normalize_idempotency_key(operation_key or f"review-{run.brief_hash[:48]}")
    existing = run.brief_revisions.filter(operation_key=key).first()
    if existing is not None:
        return existing
    same_content = run.brief_revisions.filter(content_hash=run.brief_hash).first()
    if same_content is not None:
        return same_content
    revision = (run.brief_revisions.aggregate(value=Max("revision"))["value"] or 0) + 1
    try:
        with transaction.atomic():
            return InvestigationBriefRevision.objects.create(
                run=run,
                revision=revision,
                payload=run.brief_payload,
                content_hash=run.brief_hash,
                operation_key=key,
                process_version=run.process_version,
            )
    except IntegrityError:
        existing = run.brief_revisions.filter(operation_key=key).first()
        if existing is not None:
            return existing
        raise


def _base_options(run: InvestigationRun) -> dict[str, dict[str, Any]]:
    base = run.execution_snapshot.get("domain_materialization_base") or {}
    return {
        str(item.get("id")): dict(item)
        for item in base.get("solution_options", [])
        if isinstance(item, Mapping) and item.get("id")
    }


def _process_base(run: InvestigationRun) -> dict[str, Any]:
    base = run.execution_snapshot.get("domain_materialization_base") or {}
    process = base.get("process")
    return dict(process) if isinstance(process, Mapping) else {}


def _target_process_fields(payload: Mapping[str, Any]) -> dict[str, str]:
    problem = payload.get("problem")
    hypotheses = [item for item in payload.get("hypotheses", []) if isinstance(item, Mapping)]
    calculations = [item for item in payload.get("calculations", []) if isinstance(item, Mapping)]

    hypothesis_labels = {
        "supported": "Durch Evidenz gestützt",
        "refuted": "Durch Evidenz nicht gestützt",
        "conflicting": "Widersprüchliche Evidenz",
        "open": "Noch offen",
    }
    hypothesis_lines = []
    for item in hypotheses:
        statement = humanize_investigation_text(item.get("statement"))
        if not statement:
            continue
        status = str(item.get("status") or "open")
        label = hypothesis_labels.get(status, "Noch offen")
        hypothesis_lines.append(f"{label}: {statement}")

    calculation_lines: list[str] = []
    for item in calculations:
        summary = humanize_investigation_text(item.get("summary"))
        reference = item.get("reference")
        if not summary or not isinstance(reference, Mapping):
            continue

        parts = [summary]
        data_basis = population_summary(item.get("population"))
        if data_basis:
            parts.append(f"Datenbasis: {data_basis}")
        limits = humanize_investigation_text(item.get("limits"))
        if limits:
            parts.append(f"Aussagegrenze: {limits}")
        calculation_lines.append(" · ".join(parts))

    return {
        "diagnostic_observations": (
            humanize_investigation_text(problem.get("statement"))
            if isinstance(problem, Mapping)
            else ""
        ),
        "cause_hypotheses": "\n".join(hypothesis_lines),
        "baseline_metrics": "\n".join(calculation_lines),
    }


def _option_payload(option: Mapping[str, Any]) -> dict[str, Any]:
    evidence_basis = str(option.get("evidence_basis") or EvidenceBasis.HYPOTHESIS)
    if evidence_basis not in {choice for choice, _label in EvidenceBasis.choices}:
        evidence_basis = EvidenceBasis.HYPOTHESIS
    allowed_types = {choice for choice, _label in SolutionOption.OptionType.choices}
    option_type = str(option.get("option_type") or SolutionOption.OptionType.OTHER)
    if option_type not in allowed_types:
        option_type = SolutionOption.OptionType.OTHER
    return {
        "name": str(option.get("name") or "").strip()[:200],
        "option_type": option_type,
        "description": str(option.get("description") or "").strip(),
        "expected_value": str(option.get("expected_value") or "").strip(),
        "bottleneck_coverage": str(option.get("bottleneck_coverage") or "").strip(),
        "data_requirements": str(option.get("data_requirements") or "").strip(),
        "application_impact": str(option.get("application_impact") or "").strip(),
        "integration_impact": str(option.get("integration_impact") or "").strip(),
        "risks": str(option.get("risks") or "").strip(),
        "architecture_fit": str(option.get("architecture_fit") or "").strip(),
        "evidence_basis": evidence_basis,
    }


def _current_domain_hash(process: ProcessAnalysis) -> str:
    options = [
        {
            "id": str(option.pk),
            "updated_at": option.updated_at.isoformat(),
            "name": option.name,
            "description": option.description,
            "expected_value": option.expected_value,
            "recommendation": option.recommendation,
        }
        for option in process.solution_options.order_by("id")
    ]
    return content_hash(
        {
            "process": {
                "id": str(process.pk),
                "version": process.version,
                "updated_at": process.updated_at.isoformat(),
                "diagnostic_observations": process.diagnostic_observations,
                "cause_hypotheses": process.cause_hypotheses,
                "baseline_metrics": process.baseline_metrics,
            },
            "solution_options": options,
        }
    )


def _solution_proposals(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for raw_option in (item for item in payload.get("options", []) if isinstance(item, Mapping)):
        proposal = _option_payload(raw_option)
        if not proposal["name"]:
            continue
        proposal["existing_option_id"] = str(raw_option.get("existing_option_id") or "").strip()
        proposals.append(proposal)
    return proposals


def preview_decision_brief_materialization(*, actor, run_id) -> dict[str, Any]:
    """Describe domain-owned draft adoption without writing anything."""

    run = read_run(actor=actor, run_id=run_id)
    if bool(run.execution_snapshot.get("historical_snapshot_replay")):
        raise InvestigationRunError(
            "Historische Post-Fix-Replays sind reine Nachweisartefakte und können nicht "
            "in den aktuellen Lösungsraum übernommen werden.",
            code="historical_snapshot_replay_read_only",
        )
    if run.status != InvestigationRun.Status.READY:
        raise InvestigationRunError(
            "Nur ein technisch READY-geprüfter Brief kann zur Übernahme vorbereitet werden.",
            code="ready_required",
        )
    blockers = decision_brief_blockers(run)
    if blockers:
        raise InvestigationRunError(
            "Der Decision Brief erfüllt den VS1/3-Vertrag noch nicht.",
            code="decision_brief_incomplete",
        )

    payload = run.brief_payload if isinstance(run.brief_payload, Mapping) else {}
    try:
        return preview_investigation_draft_adoption(
            actor=actor,
            process_analysis_id=run.process_analysis_id,
            expected_process_version=run.process_version,
            base_process=_process_base(run),
            base_options=_base_options(run),
            process_fields=_target_process_fields(payload),
            solution_proposals=_solution_proposals(payload),
        )
    except InvestigationDraftAdoptionError as exc:
        raise InvestigationRunError(str(exc), code=exc.code) from exc


@transaction.atomic
def materialize_decision_brief(
    *,
    actor,
    run_id,
    operation_key: str,
) -> InvestigationMaterialization:
    run = locked_run(actor=actor, run_id=run_id)
    if bool(run.execution_snapshot.get("historical_snapshot_replay")):
        raise InvestigationRunError(
            "Historische Post-Fix-Replays sind reine Nachweisartefakte und können nicht "
            "materialisiert werden.",
            code="historical_snapshot_replay_read_only",
        )
    key = normalize_idempotency_key(operation_key)
    existing = run.materializations.filter(operation_key=key).first()
    if existing is not None:
        return existing

    revision = freeze_review_revision(
        actor=actor,
        run_id=run.pk,
        operation_key=f"review-{run.brief_hash[:48]}",
    )
    existing_for_revision = InvestigationMaterialization.objects.filter(
        brief_revision=revision
    ).first()
    if existing_for_revision is not None:
        return existing_for_revision

    payload = revision.payload if isinstance(revision.payload, Mapping) else {}
    base_domain_hash = str(
        (run.execution_snapshot.get("domain_materialization_base") or {}).get("content_hash") or ""
    )
    try:
        adoption = adopt_investigation_drafts(
            actor=actor,
            process_analysis_id=run.process_analysis_id,
            expected_process_version=run.process_version,
            base_process=_process_base(run),
            base_options=_base_options(run),
            process_fields=_target_process_fields(payload),
            solution_proposals=_solution_proposals(payload),
        )
    except InvestigationDraftAdoptionError as exc:
        raise InvestigationRunError(str(exc), code=exc.code) from exc

    process = ProcessAnalysis.objects.get(pk=run.process_analysis_id)
    return InvestigationMaterialization.objects.create(
        run=run,
        brief_revision=revision,
        operation_key=key,
        outcome=(
            InvestigationMaterialization.Outcome.CONFLICT
            if adoption.conflicts
            else InvestigationMaterialization.Outcome.APPLIED
        ),
        base_domain_hash=base_domain_hash,
        resulting_domain_hash=_current_domain_hash(process),
        applied_fields=adoption.applied_fields,
        created_solution_option_ids=list(adoption.created_solution_option_ids),
        updated_solution_option_ids=list(adoption.updated_solution_option_ids),
        conflicts=list(adoption.conflicts),
        materialized_by=actor,
    )


def render_decision_brief_markdown(revision: InvestigationBriefRevision) -> str:
    run = revision.run
    payload = revision.payload if isinstance(revision.payload, Mapping) else {}
    question_scope = payload.get("question_scope") or {}
    problem = payload.get("problem") or {}
    lines = [
        "# Decision Brief",
        "",
        f"- Run: {run.pk}",
        f"- Brief-Revision: {revision.revision}",
        f"- Brief-Hash: {revision.content_hash}",
        f"- ProcessAnalysis-Version: {revision.process_version}",
        "",
        "## Frage und Scope",
        "",
        str(question_scope.get("question") or run.decision_question),
        "",
        str(question_scope.get("scope") or ""),
        "",
        "## Belegtes Problem",
        "",
        str(problem.get("statement") or ""),
    ]
    for reference in problem.get("references", []):
        if isinstance(reference, Mapping):
            lines.append(f"- Nachweis: {_reference_label(reference)}")

    lines.extend(["", "## Konkurrierende Ursachen", ""])
    for hypothesis in payload.get("hypotheses", []):
        if not isinstance(hypothesis, Mapping):
            continue
        lines.append(
            "- **"
            + str(hypothesis.get("status") or "open")
            + "** — "
            + str(hypothesis.get("statement") or "")
        )
        for reference in hypothesis.get("references", []):
            if isinstance(reference, Mapping):
                lines.append(f"  - Evidenz: {_reference_label(reference)}")
        for reference in hypothesis.get("counterevidence_refs", []):
            if isinstance(reference, Mapping):
                lines.append(f"  - Gegenbeleg: {_reference_label(reference)}")

    lines.extend(["", "## Berechnete Befunde", ""])
    for calculation in payload.get("calculations", []):
        if not isinstance(calculation, Mapping):
            continue
        lines.append("- " + str(calculation.get("summary") or ""))
        lines.append(f"  - Population: {_list_text(calculation.get('population'))}")
        lines.append("  - Grenzen: " + str(calculation.get("limits") or ""))
        reference = calculation.get("reference")
        if isinstance(reference, Mapping):
            lines.append(f"  - Analyse: {_reference_label(reference)}")

    lines.extend(["", "## Handlungsoptionen", ""])
    for option in payload.get("options", []):
        if not isinstance(option, Mapping):
            continue
        markers: list[str] = []
        if option.get("non_ai"):
            markers.append("Non-AI")
        if option.get("status_quo"):
            markers.append("Status quo")
        marker = f" ({', '.join(markers)})" if markers else ""
        lines.extend(
            [
                "### " + str(option.get("name") or "Option") + marker,
                "",
                str(option.get("description") or ""),
                "",
                "Erwarteter Beitrag: " + str(option.get("expected_value") or ""),
                "Risiken: " + str(option.get("risks") or ""),
                "",
            ]
        )

    recommendation = payload.get("recommendation") or {}
    lines.extend(
        [
            "## Empfehlung für die menschliche Richtungsentscheidung",
            "",
            str(recommendation.get("summary") or ""),
            "",
            str(recommendation.get("rationale") or ""),
        ]
    )
    for reference in recommendation.get("references", []):
        if isinstance(reference, Mapping):
            lines.append(f"- Nachweis: {_reference_label(reference)}")

    lines.extend(["", "## Risiken und Unbekanntes", ""])
    for item in payload.get("risks_unknowns", []):
        lines.append(f"- {_list_text(item)}")

    validation = payload.get("validation_step") or {}
    lines.extend(
        [
            "",
            "## Kleinster Validierungsschritt",
            "",
            str(validation.get("step") or ""),
            "",
            "Messansatz: " + str(validation.get("measurement") or ""),
            "",
            "## Untersuchungsspur",
            "",
        ]
    )
    for step in run.steps.order_by("sequence"):
        if step.status != step.Status.SUCCESS:
            continue
        change = _list_text(step.progress_payload)
        lines.append(
            f"- Schritt {step.sequence}: {step.tool_name} — "
            f"Erkenntnisänderung: {change or step.get_progress_kind_display()}"
        )
    return "\n".join(lines).strip() + "\n"
