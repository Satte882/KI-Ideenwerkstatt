from __future__ import annotations

from copy import deepcopy

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream

from .models import SolutionGenerationRun, SolutionQualityRun
from .solution_generation_adoption import (
    SolutionGenerationAdoptionError,
    adopt_solution_generation_bundle,
)
from .solution_generation_contract import GENERATED_OPTION_FIELDS, OPTION_LANES
from .solution_generation_effective import build_validated_effective_solution_payload
from .solution_generation_forms import (
    FIELD_LABELS,
    LANE_LABELS,
    SOURCE_LABELS,
    UNCERTAINTY_LABELS,
    VALIDATION_LABELS,
    SolutionGenerationPreviewEditForm,
    preview_form_field_name,
)
from .solution_generation_preview import (
    SolutionGenerationPreviewError,
    build_solution_generation_preview_state,
    build_solution_quality_preview_state,
    update_solution_generation_preview_edits,
)
from .solution_generation_service import SolutionGenerationError, generate_solution_preview
from .solution_generation_sources import build_solution_generation_source_context
from .solution_repair_contract import SolutionRepairContractError
from .solution_repair_service import run_targeted_solution_repair

CRITIC_CRITERION_LABELS = {
    "distinctiveness": "Abgrenzung der Optionen",
    "bottleneck_fit": "Passung zum Engpass",
    "grounding_consistency": "Konsistenz mit Quellen",
    "evidence_discipline": "Evidenzdisziplin",
    "complexity_proportionality": "Verhältnismäßigkeit der Komplexität",
}
CRITIC_CRITERION_ORDER = tuple(CRITIC_CRITERION_LABELS)


def _generation_error_message(exc: SolutionGenerationError) -> str:
    if exc.code in {
        "context_quota_exceeded",
        "user_quota_exceeded",
        "global_quota_exceeded",
        "generation_already_running",
        "generation_superseded",
        "process_not_ready",
        "input_too_large",
        "invalid_configuration",
        "invalid_generation_payload",
        "internal_error",
        "not_configured",
        "unauthorized",
        "provider_schema_unsupported",
        "provider_unavailable",
        "provider_error",
        "invalid_response",
        "empty_response",
        "response_too_large",
        "unavailable",
    }:
        return str(exc)
    if exc.code == "rate_limit":
        return (
            "Der KI-Dienst hat sein aktuelles Anfrage-Limit erreicht. "
            "Bestehende Prozessdaten und Lösungsoptionen bleiben unverändert."
        )
    if exc.code == "timeout":
        return (
            "Die KI-Generierung hat das Zeitlimit überschritten. "
            "Es wurden keine Lösungsoptionen angelegt."
        )
    if exc.code == "output_truncated":
        return (
            "Die KI-Antwort war unvollständig und wurde verworfen. "
            "Es wurden keine Lösungsoptionen angelegt."
        )
    return (
        "Die KI-Generierung ist derzeit nicht verfügbar. Es wurden keine Lösungsoptionen angelegt."
    )


def _process_queryset():
    return ProcessAnalysis.objects.select_related(
        "stage__value_stream__owner",
    ).prefetch_related("validations")


def _run_queryset():
    return SolutionGenerationRun.objects.select_related(
        "process_analysis__stage__value_stream__owner",
    ).prefetch_related("process_analysis__validations", "quality_runs")


@login_required
@require_POST
def solution_generation_start(request, process_pk):
    process_analysis = get_object_or_404(_process_queryset(), pk=process_pk)
    if not can_edit_value_stream(request.user, process_analysis.stage.value_stream):
        raise PermissionDenied

    try:
        run = generate_solution_preview(
            actor=request.user,
            process_analysis_id=process_analysis.pk,
        )
    except SolutionGenerationError as exc:
        messages.error(
            request,
            _generation_error_message(exc),
            extra_tags="solution-generation-feedback",
        )
        return HttpResponseRedirect(f"{process_analysis.get_absolute_url()}#loesungsoptionen")

    preview_url = reverse("accelerator:solution_generation_preview", kwargs={"run_id": run.pk})
    return HttpResponseRedirect(f"{preview_url}#solution-generation-result")


@login_required
@require_POST
def solution_generation_adopt(request, run_id):
    run = get_object_or_404(
        _run_queryset(),
        pk=run_id,
        status=SolutionGenerationRun.Status.SUCCESS,
    )
    process_analysis = run.process_analysis
    if not can_edit_value_stream(request.user, process_analysis.stage.value_stream):
        raise PermissionDenied

    selected_lanes = None
    if request.POST.get("selection_mode") == "explicit":
        selected_lanes = tuple(request.POST.getlist("selected_lanes"))

    try:
        result = adopt_solution_generation_bundle(
            actor=request.user,
            run_id=run.pk,
            selected_lanes=selected_lanes,
        )
    except SolutionGenerationAdoptionError as exc:
        messages.error(request, str(exc))
        preview_url = reverse(
            "accelerator:solution_generation_preview",
            kwargs={"run_id": run.pk},
        )
        return HttpResponseRedirect(f"{preview_url}#solution-generation-adoption")

    option_count = len(result.options)
    if result.created:
        if option_count == 1:
            message = (
                "Der ausgewählte KI-Entwurf wurde als reguläre, noch nicht bewertete "
                "Lösungsoption übernommen."
            )
        else:
            message = (
                f"{option_count} ausgewählte KI-Entwürfe wurden als reguläre, noch nicht "
                "bewertete Lösungsoptionen übernommen."
            )
        messages.success(request, message)
    else:
        messages.info(
            request,
            "Die ausgewählten KI-Entwürfe waren bereits übernommen.",
        )
    return redirect("architecture:solution_option_compare", pk=process_analysis.pk)


@login_required
@require_POST
def solution_generation_repair(request, run_id):
    run = get_object_or_404(
        _run_queryset(),
        pk=run_id,
        status=SolutionGenerationRun.Status.SUCCESS,
    )
    process_analysis = run.process_analysis
    if not can_edit_value_stream(request.user, process_analysis.stage.value_stream):
        raise PermissionDenied

    preview_state = build_solution_generation_preview_state(run)
    if not preview_state.editable:
        messages.warning(
            request,
            "Diese Vorschau ist nicht mehr für einen Repair verfügbar. Bitte neu generieren.",
        )
        return HttpResponseRedirect(
            f"{reverse('accelerator:solution_generation_preview', args=[run.pk])}"
            "#solution-generation-quality"
        )

    try:
        repair_run = run_targeted_solution_repair(
            solution_generation_run_id=run.pk,
            actor=request.user,
        )
    except SolutionRepairContractError as exc:
        if exc.code in {"repair_stale", "human_edit_conflict"}:
            messages.warning(
                request,
                "Vorschau wurde seit der Prüfung bearbeitet, Reparatur nicht mehr möglich.",
            )
        else:
            messages.warning(request, str(exc))
    else:
        if repair_run.status == SolutionQualityRun.Status.SUCCESS:
            messages.success(
                request,
                "Reparierbare Findings wurden einmalig korrigiert. "
                "Die finale Qualitätsprüfung läuft automatisch.",
            )
        else:
            messages.warning(
                request,
                "Der einmalige Repair konnte nicht angewendet werden. "
                "Die letzte deterministisch valide Vorschau bleibt erhalten; "
                "bitte fachlich prüfen.",
            )

    return HttpResponseRedirect(
        f"{reverse('accelerator:solution_generation_preview', args=[run.pk])}"
        "#solution-generation-quality"
    )


def _preview_source_facts(preview_payload: dict) -> list[dict[str, str]]:
    facts = preview_payload.get("source_context", {}).get("facts", [])
    return [
        {
            "source_id": fact["source_id"],
            "label": SOURCE_LABELS.get(fact["source_id"], fact["source_id"]),
            "value": fact["value"],
        }
        for fact in facts
    ]


def _preview_options(preview_payload: dict, form) -> list[dict[str, object]]:
    options = preview_payload.get("options", {})
    edits = preview_payload.get("edits", {})
    result: list[dict[str, object]] = []

    for lane in OPTION_LANES:
        lane_edits = edits.get(lane, {})
        fields: list[dict[str, object]] = []
        for field_name in GENERATED_OPTION_FIELDS:
            statement = options[lane][field_name]
            key = preview_form_field_name(lane, field_name)
            source_ids = statement.get("source_ids", [])
            uncertainty = statement.get("uncertainty", {})
            fields.append(
                {
                    "name": field_name,
                    "label": FIELD_LABELS[field_name],
                    "text": lane_edits.get(field_name, statement["text"]),
                    "edited": field_name in lane_edits,
                    "form_field": form[key] if form is not None else None,
                    "sources": [
                        {
                            "source_id": source_id,
                            "label": SOURCE_LABELS.get(source_id, source_id),
                        }
                        for source_id in source_ids
                    ],
                    "assumptions": statement.get("assumptions", []),
                    "open_evidence": statement.get("open_evidence", []),
                    "uncertainty_label": UNCERTAINTY_LABELS.get(
                        uncertainty.get("level", ""),
                        uncertainty.get("level", ""),
                    ),
                    "uncertainty_reason": uncertainty.get("reason", ""),
                }
            )
        result.append(
            {
                "lane": lane,
                "label": LANE_LABELS[lane],
                "fields": fields,
            }
        )
    return result


def _quality_findings(findings) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for finding in findings:
        option = str(finding.get("option") or "")
        criterion = str(finding.get("criterion") or "")
        field_name = str(finding.get("field") or "")
        source_ids = finding.get("source_ids", [])
        result.append(
            {
                "finding_id": finding.get("finding_id", ""),
                "option": option,
                "option_label": LANE_LABELS.get(option, option),
                "criterion": criterion,
                "criterion_label": CRITIC_CRITERION_LABELS.get(criterion, criterion),
                "field": field_name,
                "field_label": FIELD_LABELS.get(field_name, field_name) if field_name else "",
                "finding": finding.get("finding", ""),
                "repairable": finding.get("repairable") is True,
                "sources": [
                    {
                        "source_id": source_id,
                        "label": SOURCE_LABELS.get(source_id, source_id),
                    }
                    for source_id in source_ids
                    if isinstance(source_id, str)
                ],
            }
        )
    return sorted(
        result,
        key=lambda item: (
            OPTION_LANES.index(item["option"]) if item["option"] in OPTION_LANES else 999,
            CRITIC_CRITERION_ORDER.index(item["criterion"])
            if item["criterion"] in CRITIC_CRITERION_ORDER
            else 999,
            str(item["field_label"]),
        ),
    )


@login_required
def solution_generation_preview(request, run_id):
    run = get_object_or_404(
        _run_queryset(),
        pk=run_id,
        status=SolutionGenerationRun.Status.SUCCESS,
    )
    process_analysis = run.process_analysis
    value_stream = process_analysis.stage.value_stream
    can_edit = can_edit_value_stream(request.user, value_stream)
    state = build_solution_generation_preview_state(run)
    quality_state = build_solution_quality_preview_state(run, preview_state=state)
    editable = can_edit and state.editable

    current_source_context = build_solution_generation_source_context(process_analysis)
    effective_payload = build_validated_effective_solution_payload(
        run.preview_payload,
        current_source_context,
    )
    effective_preview_payload = deepcopy(run.preview_payload)
    effective_preview_payload["options"] = effective_payload["options"]

    form = SolutionGenerationPreviewEditForm(
        request.POST or None,
        preview_payload=effective_preview_payload,
    )
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        if not state.editable:
            messages.warning(
                request,
                "Diese Vorschau ist nicht mehr bearbeitbar. Bitte neu generieren.",
            )
            return redirect("accelerator:solution_generation_preview", run_id=run.pk)
        if form.is_valid():
            try:
                machine_repaired_preview_payload = deepcopy(run.preview_payload)
                machine_repaired_preview_payload["edits"] = {}
                machine_repaired_payload = build_validated_effective_solution_payload(
                    machine_repaired_preview_payload,
                    current_source_context,
                )
                update_solution_generation_preview_edits(
                    run_id=run.pk,
                    edits=form.normalized_edits(machine_repaired_payload),
                )
            except SolutionGenerationPreviewError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Die Bearbeitungen am KI-Entwurf wurden gespeichert.",
                )
            return redirect("accelerator:solution_generation_preview", run_id=run.pk)

    frozen_source_context = run.preview_payload.get("source_context", {})
    frozen_validation_state = frozen_source_context.get("validation_state", "")
    return render(
        request,
        "accelerator/solution_generation_preview.html",
        {
            "run": run,
            "process_analysis": process_analysis,
            "state": state,
            "quality_state": quality_state,
            "quality_findings": _quality_findings(quality_state.findings),
            "repair_action_available": editable and quality_state.repair_available,
            "editable": editable,
            "form": form,
            "preview_options": _preview_options(
                effective_preview_payload,
                form if editable else None,
            ),
            "source_facts": _preview_source_facts(run.preview_payload),
            "frozen_validation_label": VALIDATION_LABELS.get(
                frozen_validation_state,
                frozen_validation_state,
            ),
            "current_validation_label": VALIDATION_LABELS.get(
                state.validation_state,
                state.validation_state,
            ),
        },
    )
