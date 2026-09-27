"""Product-only, chronological projection of persisted execution records."""

from __future__ import annotations

import re
from uuid import UUID

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .investigation_policy import PolicyOutcome
from .investigation_presentation import build_decision_surface, humanize_investigation_text
from .investigation_runtime import evaluate_run_policy

TOOL_LABELS = {
    "list_sources": ("Quellenbestand wird geprüft", "Quellenbestand geprüft"),
    "read_source": ("Quelle wird ausgewertet", "Quelle ausgewertet"),
    "search_sources": ("Belege und Gegenbelege werden gesucht", "Belege und Gegenbelege gesucht"),
    "profile_csv": ("Datenbasis wird analysiert", "Datenbasis analysiert"),
    "compare_groups": ("Datenvergleich wird durchgeführt", "Datenvergleich durchgeführt"),
}


def duration_label(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}" if hours else f"{minutes:02}:{seconds:02}"


def build_activity(run, *, now=None):
    now = now or timezone.now()
    policy = evaluate_run_policy(run)
    surface = build_decision_surface(
        run=run,
        policy=policy,
        latest_materialization=None,
        materialization_preview=None,
    )
    ready = run.status == "ready" and policy.outcome == PolicyOutcome.READY_FOR_DECISION
    active = run.status == "running"
    confirmed = bool(
        active
        and run.execution_generation == run.executor_generation
        and run.execution_worker_id
        and run.execution_lease_until
        and run.execution_lease_until > now
    )
    pending = (
        active
        and run.execution_requested_at
        and run.execution_generation != run.executor_generation
    )
    execution_state = (
        "confirmed"
        if confirmed
        else "pending"
        if pending
        else "unconfirmed"
        if active
        else "stopped"
    )
    title = {
        "running": "Untersuchung läuft",
        "waiting_human": "Klärung erforderlich",
        "ready": "Decision Brief bereit"
        if ready
        else "Entscheidungsgrundlage derzeit nicht freigegeben",
        "failed": "Untersuchung konnte nicht abgeschlossen werden",
        "aborted": "Untersuchung abgebrochen",
    }.get(run.status, "Untersuchung")
    description = {
        "confirmed": (
            "Sie können diese Seite verlassen. Die Untersuchung läuft im Hintergrund weiter."
        ),
        "pending": "Start angefordert - Ausführung ausstehend.",
        "unconfirmed": (
            "Ausführung derzeit nicht bestätigt. Der letzte gespeicherte Stand bleibt sichtbar."
        ),
        "stopped": "",
    }[execution_state]
    sources = {str(source.pk): source.filename for source in run.source_snapshot.sources.all()}
    entries = []

    def entry(key, started, finished, status, labels, *, detail="", technical="", error=""):
        stored_status = status
        if status == "running" and not confirmed:
            status = "pending" if active else "discarded"
        label = labels[0] if stored_status == "running" else labels[1]
        if stored_status == "failed":
            label = labels[0].replace(" wird ", " wurde ").replace(" werden ", " wurden ")
            label += " - technisch fehlgeschlagen"
        if status == "discarded":
            label = labels[0] + " - beendet ohne bestätigten Abschluss"
        end = finished or (now if active else run.finished_at or now)
        seconds = (end - started).total_seconds() if started else None
        entries.append(
            {
                "id": key,
                "status": status,
                "label": label,
                "detail": detail,
                "technical": technical,
                "error": bool(error),
                "audit_url": None,
                "started_at": started.isoformat() if started else None,
                "finished_at": finished.isoformat() if finished else None,
                "duration": duration_label(seconds)
                if seconds is not None
                else "Dauer nicht dokumentiert",
            }
        )

    entry(
        "foundation",
        run.started_at,
        run.started_at,
        "success",
        ("Untersuchungsgrundlage übernommen", "Untersuchungsgrundlage übernommen"),
        detail=f"Autorisierter Quellenstand · {len(sources)} Quellen",
    )
    for step in run.steps.all():
        labels = TOOL_LABELS.get(
            step.tool_name, ("Analyseschritt wird ausgeführt", "Analyseschritt abgeschlossen")
        )
        source_name = sources.get(str(step.parameters.get("source_id", "")), "")
        detail = source_name
        # Deterministic source context only. Unvalidated model reasoning is never
        # promoted to a factual finding on this activity page.
        history = list(step.attempt_history)
        for previous in history[:-1]:
            entry(
                f"step-{step.pk}-{previous['attempt']}",
                parse_datetime(previous["started_at"]) if previous.get("started_at") else None,
                parse_datetime(previous["finished_at"]) if previous.get("finished_at") else None,
                previous["status"],
                labels,
                detail=detail,
                technical=f"Versuch {previous['attempt']} · {previous.get('error_code', '')}",
                error=previous.get("error_code"),
            )
        started = parse_datetime(history[-1]["started_at"]) if history else step.started_at
        if step.attempts > 1 and not history:
            started = None  # Old retries cannot be reconstructed honestly.
        entry(
            f"step-{step.pk}-{step.attempts}",
            started,
            step.finished_at,
            "discarded"
            if step.status == "running" and step.executor_generation != run.executor_generation
            else step.status,
            labels,
            detail=detail,
            technical=f"Werkzeug: {step.tool_name} · Versuch {step.attempts} · {step.error_code}",
            error=step.error_code,
        )
        if source_name:
            entries[-1]["audit_url"] = reverse(
                "accelerator:investigation_source", args=[run.pk, step.parameters["source_id"]]
            )
        result_id = step.result_ref.get("tool_result_id")
        if result_id:
            try:
                result_uuid = UUID(str(result_id))
            except ValueError:
                pass
            else:
                entries[-1]["audit_url"] = reverse(
                    "accelerator:investigation_tool_result", args=[run.pk, result_uuid]
                )
    synthesis_count = 0
    reports = {report.model_call_id: report for report in run.verifier_reports.all()}
    for call in run.model_calls.all():
        if call.role == "planner":
            labels = (
                "Nächster Untersuchungsschritt wird bestimmt",
                "Nächsten Untersuchungsschritt bestimmt",
            )
        elif call.role == "synthesizer":
            synthesis_count += 1
            labels = (
                ("Decision Brief wird erstellt", "Decision Brief erstellt")
                if synthesis_count == 1
                else ("Decision Brief wird aktualisiert", "Decision Brief aktualisiert")
            )
        else:
            labels = ("Entscheidungsgrundlage wird geprüft", "Prüfung durchgeführt")
        report = reports.get(call.pk)
        if report and (
            not report.success or report.critical_findings or not report.source_references_valid
        ):
            labels = (labels[0], "Prüfung ergab weiteren Prüfbedarf")
        entry(
            f"call-{call.pk}",
            call.started_at,
            call.finished_at,
            "discarded"
            if call.status == "running" and call.executor_generation != run.executor_generation
            else call.status,
            labels,
            technical=f"Status: {call.get_status_display()} · {call.error_code}",
            error=call.error_code,
        )
        if report and labels[1] == "Prüfung ergab weiteren Prüfbedarf":
            entries[-1]["status"] = "review"
    for revision in run.input_revisions.all():
        entry(
            f"input-{revision.pk}",
            revision.created_at,
            revision.created_at,
            "success",
            ("Klärung beantwortet", "Klärung beantwortet"),
        )
    if ready:
        entry(
            "ready",
            run.finished_at,
            run.finished_at,
            "success",
            ("Entscheidungsgrundlage verifiziert", "Entscheidungsgrundlage verifiziert"),
        )
    entries.sort(key=lambda item: (item["started_at"] or "", item["id"]))
    elapsed = ((run.finished_at or now) - run.started_at).total_seconds()
    impact = humanize_investigation_text(run.clarification_payload.get("impact", ""))
    required_action = surface["required_action"]
    internal_terms = re.compile(
        r"planner|synthesizer|verifier|policy|schema|tool|fingerprint", re.I
    )
    if run.status == "failed":
        if internal_terms.search(impact):
            impact = (
                "Die Untersuchung konnte technisch nicht vollständig geprüft werden. "
                "Zwischenstände sind nicht als Entscheidungsgrundlage freigegeben."
            )
        if internal_terms.search(required_action):
            required_action = (
                "Technische Ausführung prüfen lassen und danach aus der Prozessanalyse "
                "eine neue Untersuchung vorbereiten."
            )
    editable = False
    # The caller supplies permissions separately; a read projection cannot
    # authorize editing merely because a run is waiting.
    return {
        "status": run.status,
        "title": title,
        "description": description,
        "execution_state": execution_state,
        "server_time": now.isoformat(),
        "execution_lease_until": run.execution_lease_until.isoformat() if confirmed else None,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration": duration_label(elapsed),
        "entries": entries,
        "ready": ready,
        "can_continue": editable,
        "can_abort": editable,
        "question": humanize_investigation_text(run.decision_question),
        "clarification_question": surface["clarification_question"],
        "needed_evidence": surface["needed_evidence"],
        "impact": impact,
        "required_action": required_action,
        "brief_url": reverse("accelerator:investigation_detail", args=[run.pk]) if ready else None,
    }
