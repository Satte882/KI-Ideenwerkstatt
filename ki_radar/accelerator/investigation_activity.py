"""Product-only, chronological projection of persisted execution records."""

from __future__ import annotations

import re
from uuid import UUID

from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .investigation_execution import pending_execution_state
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


def build_execution_status(run, *, now=None):
    """Read lease/dispatch status without requiring a decision-policy budget."""
    now = now or timezone.now()
    active = run.status == "running"
    confirmed = bool(
        active
        and run.execution_generation == run.executor_generation
        and run.execution_worker_id
        and run.execution_lease_until
        and run.execution_lease_until > now
    )
    pending_state = pending_execution_state(run, now=now)
    execution_state = (
        "confirmed"
        if confirmed
        else pending_state
        if pending_state
        else "unconfirmed"
        if active
        else "stopped"
    )
    title = {
        "confirmed": "Untersuchung läuft",
        "pending": "Untersuchungsstart angefordert",
        "queued": "Untersuchung wartet auf freien Ausführungsplatz",
        "unavailable": "Untersuchung wartet auf technischen Dienst",
        "unconfirmed": "Untersuchungsausführung derzeit nicht bestätigt",
        "stopped": "Untersuchung",
    }[execution_state]
    description = {
        "confirmed": (
            "Sie können diese Seite verlassen. Die Untersuchung läuft im Hintergrund weiter."
        ),
        "pending": "Start angefordert - die Hintergrundausführung wird zugewiesen.",
        "queued": (
            "Alle Ausführungsplätze sind belegt. Die Untersuchung wartet auf den nächsten "
            "freien Platz."
        ),
        "unavailable": (
            "Die Startanforderung wurde nicht übernommen. Es findet derzeit keine "
            "bestätigte Analyse statt."
        ),
        "unconfirmed": (
            "Ausführung derzeit nicht bestätigt. Der letzte gespeicherte Stand bleibt sichtbar."
        ),
        "stopped": "",
    }[execution_state]
    return {"title": title, "description": description, "execution_state": execution_state}


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
    execution = build_execution_status(run, now=now)
    execution_state = execution["execution_state"]
    confirmed = execution_state == "confirmed"
    title = (
        execution["title"]
        if active
        else {
            "waiting_human": "Klärung erforderlich",
            "ready": "Decision Brief bereit"
            if ready
            else "Entscheidungsgrundlage derzeit nicht freigegeben",
            "failed": "Untersuchung konnte nicht abgeschlossen werden",
            "aborted": "Untersuchung abgebrochen",
        }.get(run.status, "Untersuchung")
    )
    description = execution["description"]
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
    attention_required = run.status in {"waiting_human", "failed"}
    attention_title = (
        "Entscheidungskritische Klärung"
        if run.status == "waiting_human"
        else "Technische Prüfung erforderlich"
    )
    if execution_state == "unavailable":
        attention_required = True
        attention_title = "Hintergrundausführung nicht verfügbar"
        impact = (
            "Seit mehr als 30 Sekunden hat kein Hintergrunddienst die angeforderte "
            "Untersuchung übernommen. Es liegt noch keine bestätigte Analyse vor."
        )
        required_action = (
            "Technischen Hintergrunddienst prüfen oder starten. Sie können diesen Lauf "
            "abbrechen; starten Sie ihn nicht erneut, solange die Ursache ungeklärt ist."
        )
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
        "attention_required": attention_required,
        "attention_title": attention_title,
        "server_time": now.isoformat(),
        "execution_lease_until": run.execution_lease_until.isoformat() if confirmed else None,
        "started_at": run.started_at.isoformat(),
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration": duration_label(elapsed),
        "duration_label": (
            "Gesamtdauer seit Start"
            if run.finished_at
            else "Wartezeit seit Startanforderung"
            if execution_state in {"pending", "queued", "unavailable"}
            else "Seit Start"
        ),
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
