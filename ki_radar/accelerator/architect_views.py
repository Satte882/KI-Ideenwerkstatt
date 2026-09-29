from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.debug import sensitive_post_parameters

from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.permissions import can_manage_architecture

from .architect_contract import DISCOVERY_PROMPT_VERSION
from .architect_forms import (
    AutonomousDiscoveryStartForm,
    DiscoveryConfirmForm,
    DiscoveryCorrectionForm,
)
from .architect_service import DiscoveryAnalysisError, execute_autonomous_business_discovery
from .investigation_ingestion import (
    InvestigationSourceUploadError,
    create_managed_discovery_source_folder,
)
from .investigation_tools import (
    DiscoverySnapshotRequest,
    InvestigationToolError,
    create_discovery_source_snapshot,
)
from .models import CaptureAnalysis, CaptureSession
from .services import (
    CaptureRevisionConflict,
    CaptureStateError,
    add_autonomous_discovery_correction,
    create_autonomous_capture_session,
    get_owned_autonomous_capture_session,
)


def _latest_analysis(session: CaptureSession) -> CaptureAnalysis | None:
    return (
        session.analyses.filter(prompt_version=DISCOVERY_PROMPT_VERSION)
        .order_by("-created_at")
        .first()
    )


def _latest_snapshot(session: CaptureSession):
    return session.discovery_source_snapshots.order_by("-captured_at").first()


def _evidence_labels(refs, source_labels: dict[str, str]) -> list[dict[str, str]]:
    return [
        {"ref": str(ref), "label": source_labels.get(str(ref), str(ref))}
        for ref in list(refs or [])
    ]


def _presentation(analysis: CaptureAnalysis | None) -> dict:
    if analysis is None or not isinstance(analysis.result_payload, dict):
        return {}
    draft = analysis.result_payload.get("draft")
    if not isinstance(draft, dict):
        return {}
    source_labels = dict(analysis.result_payload.get("source_labels") or {})

    value_stream = dict(draft.get("value_stream") or {})
    value_stream["evidence_labels"] = _evidence_labels(
        value_stream.get("evidence_refs"),
        source_labels,
    )
    focus = dict(draft.get("focus") or {})
    focus["evidence_labels"] = _evidence_labels(focus.get("evidence_refs"), source_labels)
    process = dict(draft.get("process_analysis") or {})
    process["evidence_labels"] = _evidence_labels(process.get("evidence_refs"), source_labels)

    stages = []
    for stage in list(draft.get("stages") or []):
        item = dict(stage)
        item["evidence_labels"] = _evidence_labels(item.get("evidence_refs"), source_labels)
        item["is_recommended"] = str(item.get("key") or "") == str(
            focus.get("recommended_stage_key") or ""
        )
        stages.append(item)

    def with_evidence(items):
        values = []
        for raw in list(items or []):
            item = dict(raw)
            item["evidence_labels"] = _evidence_labels(
                item.get("evidence_refs"),
                source_labels,
            )
            values.append(item)
        return values

    return {
        "draft": draft,
        "source_labels": source_labels,
        "value_stream": value_stream,
        "focus": focus,
        "process": process,
        "stages": stages,
        "facts": with_evidence(draft.get("facts")),
        "hypotheses": with_evidence(draft.get("hypotheses")),
        "unknowns": list(draft.get("unknowns") or []),
        "clarifications": list(draft.get("clarifications") or []),
        "contradictions": with_evidence(draft.get("contradictions")),
        "verifier": dict(analysis.verification_payload or {}),
    }


def _run_analysis(request, *, session: CaptureSession, snapshot) -> CaptureAnalysis | None:
    try:
        return execute_autonomous_business_discovery(
            actor=request.user,
            session_id=session.pk,
            snapshot_id=snapshot.pk,
        )
    except DiscoveryAnalysisError as exc:
        messages.error(request, f"Discovery konnte nicht abgeschlossen werden: {exc}")
        return None


@sensitive_post_parameters()
@login_required
def autonomous_discovery_start(request):
    if not can_manage_architecture(request.user):
        raise PermissionDenied

    if request.method == "POST":
        form = AutonomousDiscoveryStartForm(request.POST)
        uploads = request.FILES.getlist("sources")
        if not uploads:
            form.add_error(None, "Bitte mindestens eine .md-, .txt- oder .csv-Quelle auswählen.")
        if form.is_valid():
            try:
                session = create_autonomous_capture_session(
                    actor=request.user,
                    problem_statement=form.cleaned_data["problem_statement"],
                    business_context=form.cleaned_data["business_context"],
                )
            except ValidationError as exc:
                error_map = getattr(
                    exc,
                    "message_dict",
                    {"__all__": exc.messages},
                )
                for field, errors in error_map.items():
                    target = field if field in form.fields else None
                    for error in errors:
                        form.add_error(target, error)
            else:
                try:
                    folder = create_managed_discovery_source_folder(
                        actor=request.user,
                        capture_session_id=session.pk,
                        name="Autorisierte Discovery-Quellen",
                        uploads=uploads,
                    )
                except (InvestigationSourceUploadError, InvestigationToolError) as exc:
                    session.delete()
                    form.add_error(None, str(exc))
                else:
                    try:
                        snapshot_result = create_discovery_source_snapshot(
                            actor=request.user,
                            request=DiscoverySnapshotRequest(
                                capture_session_id=session.pk,
                                folder_id=folder.pk,
                            ),
                        )
                        snapshot = session.discovery_source_snapshots.get(
                            pk=snapshot_result.snapshot_id
                        )
                    except InvestigationToolError as exc:
                        messages.error(
                            request,
                            f"Der Quellenstand konnte nicht autorisiert werden: {exc}",
                        )
                        return redirect(
                            "accelerator:autonomous_discovery_review",
                            session_id=session.pk,
                        )
                    analysis = _run_analysis(request, session=session, snapshot=snapshot)
                    if analysis is not None:
                        if analysis.status == CaptureAnalysis.Status.WAITING_HUMAN:
                            messages.warning(
                                request,
                                "Die Discovery benötigt genau eine fachliche Klärung.",
                            )
                        else:
                            messages.success(
                                request,
                                "Discovery-Draft und unabhängiger Review sind abgeschlossen.",
                            )
                    return redirect(
                        "accelerator:autonomous_discovery_review",
                        session_id=session.pk,
                    )
    else:
        form = AutonomousDiscoveryStartForm()

    return render(
        request,
        "accelerator/autonomous_discovery_start.html",
        {"form": form},
    )


@sensitive_post_parameters()
@login_required
def autonomous_discovery_review(request, session_id):
    try:
        session = get_owned_autonomous_capture_session(
            actor=request.user,
            session_id=session_id,
        )
    except CaptureSession.DoesNotExist as exc:
        raise Http404 from exc
    latest = _latest_analysis(session)
    snapshot = _latest_snapshot(session)

    if request.method == "POST":
        action = str(request.POST.get("action") or "").strip()
        if action == "retry":
            if session.status != CaptureSession.Status.DRAFT:
                messages.error(
                    request,
                    "Eine abgeschlossene Discovery kann nicht erneut analysiert werden.",
                )
            elif snapshot is None:
                messages.error(
                    request,
                    "Für diese Discovery fehlt ein autorisierter Quellenstand.",
                )
            else:
                _run_analysis(request, session=session, snapshot=snapshot)
            return redirect("accelerator:autonomous_discovery_review", session_id=session.pk)

        if action == "correct":
            correction_form = DiscoveryCorrectionForm(request.POST)
            if correction_form.is_valid():
                try:
                    session = add_autonomous_discovery_correction(
                        actor=request.user,
                        session_id=session.pk,
                        expected_revision=correction_form.cleaned_data["revision"],
                        correction=correction_form.cleaned_data["correction"],
                    )
                except (CaptureRevisionConflict, CaptureStateError, ValidationError) as exc:
                    messages.error(request, str(exc))
                else:
                    snapshot = _latest_snapshot(session)
                    if snapshot is None:
                        messages.error(
                            request,
                            "Für diese Discovery fehlt ein autorisierter Quellenstand.",
                        )
                    else:
                        _run_analysis(request, session=session, snapshot=snapshot)
                return redirect(
                    "accelerator:autonomous_discovery_review",
                    session_id=session.pk,
                )

        if action == "confirm":
            presentation = _presentation(latest)
            stage_choices = [
                (str(stage.get("key") or ""), str(stage.get("name") or ""))
                for stage in presentation.get("stages", [])
            ]
            confirm_form = DiscoveryConfirmForm(
                request.POST,
                stage_choices=stage_choices,
            )
            if confirm_form.is_valid() and latest is not None:
                selected_stage_key = confirm_form.cleaned_data["selected_stage_key"]
                recommended_stage_key = str(
                    presentation.get("focus", {}).get("recommended_stage_key") or ""
                )
                if selected_stage_key != recommended_stage_key:
                    selected_stage = next(
                        (
                            stage
                            for stage in presentation.get("stages", [])
                            if str(stage.get("key") or "") == selected_stage_key
                        ),
                        {},
                    )
                    selected_name = str(selected_stage.get("name") or selected_stage_key)
                    recommended_stage = next(
                        (
                            stage
                            for stage in presentation.get("stages", [])
                            if str(stage.get("key") or "") == recommended_stage_key
                        ),
                        {},
                    )
                    recommended_name = str(recommended_stage.get("name") or recommended_stage_key)
                    correction = (
                        "Scope-/Fokus-Review: Die Fokusphase soll "
                        f"„{selected_name}“ statt „{recommended_name}“ sein. "
                        "Richte Fokusvorschlag und ProcessAnalysis-Scope auf diese "
                        "menschliche Entscheidung aus. Erfinde keine fehlende Evidenz; "
                        "fehlende Details bleiben Unknowns."
                    )
                    try:
                        session = add_autonomous_discovery_correction(
                            actor=request.user,
                            session_id=session.pk,
                            expected_revision=confirm_form.cleaned_data["revision"],
                            correction=correction,
                        )
                    except (
                        CaptureRevisionConflict,
                        CaptureStateError,
                        ValidationError,
                    ) as exc:
                        messages.error(request, str(exc))
                    else:
                        snapshot = _latest_snapshot(session)
                        if snapshot is None:
                            messages.error(
                                request,
                                "Für diese Discovery fehlt ein autorisierter Quellenstand.",
                            )
                        else:
                            analysis = _run_analysis(
                                request,
                                session=session,
                                snapshot=snapshot,
                            )
                            if analysis is not None:
                                messages.info(
                                    request,
                                    (
                                        "Die alternative Fokusphase wurde als menschliche "
                                        "Entscheidung übernommen. Process Scope und Fokus "
                                        "wurden neu abgeleitet und müssen erneut geprüft werden."
                                    ),
                                )
                    return redirect(
                        "accelerator:autonomous_discovery_review",
                        session_id=session.pk,
                    )

                try:
                    result = materialize_discovery_and_start_investigation(
                        actor=request.user,
                        session_id=session.pk,
                        analysis_id=latest.pk,
                        selected_stage_key=selected_stage_key,
                        expected_revision=confirm_form.cleaned_data["revision"],
                    )
                except DiscoveryMaterializationError as exc:
                    messages.error(request, str(exc))
                else:
                    messages.success(
                        request,
                        (
                            "Scope und Fokus wurden übernommen. "
                            "Die bestehende Investigation wurde gestartet."
                        ),
                    )
                    return redirect(
                        "accelerator:investigation_activity",
                        run_id=result.investigation_run_id,
                    )
            elif latest is None:
                messages.error(request, "Es liegt kein geprüfter Discovery-Draft vor.")
            else:
                messages.error(request, "Bitte eine gültige Fokusphase auswählen.")

    latest = _latest_analysis(session)
    presentation = _presentation(latest)
    stage_choices = [
        (str(stage.get("key") or ""), str(stage.get("name") or ""))
        for stage in presentation.get("stages", [])
    ]
    recommended = str(presentation.get("focus", {}).get("recommended_stage_key") or "")
    correction_form = DiscoveryCorrectionForm(initial={"revision": session.revision})
    confirm_form = DiscoveryConfirmForm(
        stage_choices=stage_choices,
        initial={
            "revision": session.revision,
            "selected_stage_key": recommended,
        },
    )
    materialization = dict((session.answers or {}).get("materialization") or {})

    return render(
        request,
        "accelerator/autonomous_discovery_review.html",
        {
            "session": session,
            "analysis": latest,
            "presentation": presentation,
            "correction_form": correction_form,
            "confirm_form": confirm_form,
            "materialization": materialization,
            "can_confirm": bool(
                latest
                and latest.status == CaptureAnalysis.Status.SUCCESS
                and session.status == CaptureSession.Status.DRAFT
            ),
            "waiting_human": bool(latest and latest.status == CaptureAnalysis.Status.WAITING_HUMAN),
            "analysis_failed": bool(latest and latest.status == CaptureAnalysis.Status.FAILED),
        },
    )
