from __future__ import annotations

import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.review_export_security import sanitize_external_markdown

from .investigation_brief import (
    freeze_review_revision,
    materialize_decision_brief,
    render_decision_brief_markdown,
)
from .investigation_loop import run_until_boundary
from .investigation_models import (
    InvestigationRun,
    InvestigationSource,
    InvestigationToolResult,
)
from .investigation_runtime import (
    DEFAULT_BUDGET,
    InvestigationRunError,
    StartInvestigationRequest,
    abort_investigation,
    continue_with_human_input,
    evaluate_run_policy,
    read_run,
    start_investigation,
)
from .investigation_tools import (
    InvestigationToolError,
    SnapshotRequest,
    create_source_snapshot,
)


def _editable_process(user, process: ProcessAnalysis) -> bool:
    return process.status == ProcessAnalysis.Status.DRAFT and can_edit_value_stream(
        user, process.stage.value_stream
    )


def _run_redirect(run_id):
    return redirect("accelerator:investigation_detail", run_id=run_id)


def _referenced_tool_result_ids(value) -> set[uuid.UUID]:
    result_ids: set[uuid.UUID] = set()
    if isinstance(value, dict):
        raw_result_id = value.get("tool_result_id")
        if raw_result_id:
            try:
                result_ids.add(uuid.UUID(str(raw_result_id)))
            except (TypeError, ValueError):
                pass
        for nested in value.values():
            result_ids.update(_referenced_tool_result_ids(nested))
    elif isinstance(value, list):
        for nested in value:
            result_ids.update(_referenced_tool_result_ids(nested))
    return result_ids


def _tool_results_for_run(run: InvestigationRun):
    result_ids = _referenced_tool_result_ids(run.brief_payload)
    for result_ref in run.steps.values_list("result_ref", flat=True):
        result_ids.update(_referenced_tool_result_ids(result_ref))
    return InvestigationToolResult.objects.filter(
        snapshot=run.source_snapshot,
        pk__in=result_ids,
    )


@login_required
def investigation_authorize(request, process_pk):
    process = get_object_or_404(
        ProcessAnalysis.objects.select_related("stage__value_stream"),
        pk=process_pk,
    )
    if not _editable_process(request.user, process):
        raise PermissionDenied

    folders = list(process.investigation_source_folders.filter(is_active=True).order_by("name"))
    if not folders:
        messages.warning(
            request,
            "Für diese Prozessanalyse ist noch kein aktiver Fallordner administrativ registriert.",
        )
        return redirect(process)

    default_question = (
        f"Welche Lösungsrichtung ist für „{process.name}“ durch die Evidenz gestützt?"
    )
    question = str(request.POST.get("decision_question") or default_question).strip()
    selected_folder_id = str(
        request.POST.get("folder_id") or (folders[0].pk if len(folders) == 1 else "")
    )

    if request.method == "POST":
        folder = next(
            (item for item in folders if str(item.pk) == selected_folder_id),
            None,
        )
        if folder is None:
            messages.error(request, "Bitte einen registrierten Quellenraum auswählen.")
        elif not question:
            messages.error(request, "Die Richtungsfrage darf nicht leer sein.")
        else:
            try:
                snapshot = create_source_snapshot(
                    actor=request.user,
                    request=SnapshotRequest(
                        process_analysis_id=process.pk,
                        folder_id=folder.pk,
                        decision_question=question,
                        run_limits={},
                    ),
                )
            except InvestigationToolError as exc:
                messages.error(
                    request,
                    f"Quellenraum konnte nicht autorisiert werden: {exc}",
                )
            else:
                messages.success(
                    request,
                    (
                        f"Quellenrevision {snapshot.revision} und Run-Budget wurden "
                        "unveränderlich autorisiert."
                    ),
                )
                return redirect(process)

    return render(
        request,
        "accelerator/investigation_authorize.html",
        {
            "process_analysis": process,
            "folders": folders,
            "selected_folder_id": selected_folder_id,
            "decision_question": question,
            "budget": DEFAULT_BUDGET,
        },
    )


@login_required
@require_POST
def investigation_start(request, process_pk):
    process = get_object_or_404(
        ProcessAnalysis.objects.select_related("stage__value_stream"),
        pk=process_pk,
    )
    if not _editable_process(request.user, process):
        raise PermissionDenied

    snapshot = (
        process.investigation_source_snapshots.select_related("folder")
        .filter(process_version=process.version, folder__is_active=True)
        .order_by("-revision")
        .first()
    )
    if snapshot is None:
        messages.warning(
            request,
            "Vor dem Start wird ein aktueller, autorisierter Quellen-Snapshot für diese "
            "ProcessAnalysis-Version benötigt.",
        )
        return redirect(process)

    idempotency_key = str(request.POST.get("idempotency_key") or "").strip()
    if not idempotency_key:
        idempotency_key = f"ui-{uuid.uuid4().hex[:40]}"

    try:
        handle = start_investigation(
            actor=request.user,
            request=StartInvestigationRequest(
                snapshot_id=snapshot.pk,
                idempotency_key=idempotency_key,
                decision_brief_required=True,
            ),
        )
        if not handle.reused and handle.status == InvestigationRun.Status.RUNNING:
            run_until_boundary(
                actor=request.user,
                run_id=handle.run_id,
                executor_token=handle.executor_token,
            )
    except InvestigationRunError as exc:
        if exc.existing_run_id:
            messages.info(request, "Die bereits laufende Untersuchung wird geöffnet.")
            return _run_redirect(exc.existing_run_id)
        messages.error(request, f"Untersuchung konnte nicht fortgesetzt werden: {exc}")
        return redirect(process)

    return _run_redirect(handle.run_id)


@login_required
@require_GET
def investigation_detail(request, run_id):
    run = read_run(actor=request.user, run_id=run_id)
    policy = evaluate_run_policy(run)
    sources = list(run.source_snapshot.sources.order_by("filename"))
    tool_results = list(_tool_results_for_run(run).order_by("created_at"))
    latest_materialization = run.materializations.select_related("brief_revision").first()
    return render(
        request,
        "accelerator/investigation_detail.html",
        {
            "run": run,
            "policy": policy,
            "sources": sources,
            "tool_results": tool_results,
            "latest_materialization": latest_materialization,
        },
    )


@login_required
@require_POST
def investigation_abort(request, run_id):
    try:
        run = abort_investigation(actor=request.user, run_id=run_id)
    except InvestigationRunError as exc:
        messages.error(request, str(exc))
        return _run_redirect(run_id)
    messages.info(request, f"Untersuchung: {run.get_status_display()}.")
    return _run_redirect(run.pk)


@login_required
@require_POST
def investigation_continue(request, run_id):
    answer = str(request.POST.get("answer") or "").strip()
    if not answer:
        messages.warning(request, "Für die offene Klärung wird eine Antwort benötigt.")
        return _run_redirect(run_id)
    try:
        handle = continue_with_human_input(
            actor=request.user,
            run_id=run_id,
            payload={"answer": answer},
        )
        if handle.status == InvestigationRun.Status.RUNNING:
            run_until_boundary(
                actor=request.user,
                run_id=handle.run_id,
                executor_token=handle.executor_token,
            )
    except InvestigationRunError as exc:
        messages.error(request, f"Untersuchung konnte nicht fortgesetzt werden: {exc}")
    return _run_redirect(run_id)


@login_required
@require_POST
def investigation_materialize(request, run_id):
    try:
        result = materialize_decision_brief(
            actor=request.user,
            run_id=run_id,
            operation_key=str(request.POST.get("operation_key") or f"ui-{uuid.uuid4().hex[:40]}"),
        )
    except InvestigationRunError as exc:
        messages.error(request, f"Decision Brief konnte nicht übernommen werden: {exc}")
        return _run_redirect(run_id)

    if result.conflicts:
        messages.warning(
            request,
            "Der fachliche Stand hat sich geändert. Nicht überschreibbare Differenzen werden "
            "im Decision Brief angezeigt.",
        )
    else:
        messages.success(
            request,
            "Belegte Prozessbefunde und SolutionOption-Entwürfe wurden in die bestehenden "
            "Fachobjekte übernommen.",
        )
    return _run_redirect(run_id)


@login_required
@require_GET
def investigation_export(request, run_id):
    revision = freeze_review_revision(actor=request.user, run_id=run_id)
    content = sanitize_external_markdown(render_decision_brief_markdown(revision))
    response = HttpResponse(content, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="decision-brief-{revision.run_id}-r{revision.revision}.md"'
    )
    return response


@login_required
@require_GET
def investigation_source(request, run_id, source_id):
    run = read_run(actor=request.user, run_id=run_id)
    try:
        source = InvestigationSource.objects.get(pk=source_id, snapshot=run.source_snapshot)
    except (InvestigationSource.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    return render(
        request,
        "accelerator/investigation_artifact.html",
        {
            "run": run,
            "title": source.filename,
            "subtitle": f"Source {source.pk} · SHA-256 {source.content_sha256}",
            "content": source.content,
        },
    )


@login_required
@require_GET
def investigation_tool_result(request, run_id, result_id):
    run = read_run(actor=request.user, run_id=run_id)
    try:
        result = _tool_results_for_run(run).get(pk=result_id)
    except (InvestigationToolResult.DoesNotExist, ValueError) as exc:
        raise Http404 from exc
    payload = {
        "tool": result.tool_name,
        "tool_version": result.tool_version,
        "source_id": str(result.source_id),
        "source_hash": result.source_hash,
        "parameters": result.parameters,
        "result": result.result_payload,
        "population": result.population,
        "excluded_rows": result.excluded_rows,
        "group_sizes": result.group_sizes,
        "missing_values": result.missing_values,
        "units": result.units,
    }
    return render(
        request,
        "accelerator/investigation_artifact.html",
        {
            "run": run,
            "title": f"Analyse {result.tool_name}",
            "subtitle": f"ToolResult {result.pk}",
            "content": json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        },
    )
