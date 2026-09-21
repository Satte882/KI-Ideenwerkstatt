from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.permissions import can_edit_package, can_transition_package
from ki_radar.delivery.readiness import delivery_status_snapshot
from ki_radar.delivery.services import current_handed_over_package
from ki_radar.use_cases.blockers import build_blocker_details
from ki_radar.use_cases.classification import UseCaseClassification
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_workspace import build_outcome_workspace_journey
from ki_radar.use_cases.permissions import can_edit_use_case
from ki_radar.use_cases.services import (
    current_decision_check,
    decision_due_date,
    decision_priority,
)
from ki_radar.use_cases.workflow import build_use_case_journey

from .portfolio import build_portfolio_context

OUTCOME_STAGE_COPY = {
    "handover": {
        "title": "Übergabe",
        "purpose": "Das freigegebene Delivery Package verbindlich an Delivery übergeben.",
        "ki_radar": (
            "Delivery Readiness, Package-Version, Übergabestatus und externer Delivery-Link."
        ),
        "external": "Übernahme von Backlog, Umsetzung, Tests und technischem Fortschritt.",
    },
    "pilot": {
        "title": "Pilot",
        "purpose": "Den operativen Pilot im führenden Delivery-System verfolgen.",
        "ki_radar": "Pilotzeitraum, Review-Termin, Zielmetrik und Link zum Delivery-System.",
        "external": "Backlog, Tasks, Sprints, technische Detailprobleme und täglicher Fortschritt.",
    },
    "effect": {
        "title": "Wirkung",
        "purpose": "Baseline, Ziel, Ist-Wert und belastbaren Messnachweis zusammenführen.",
        "ki_radar": "Entscheidungsrelevanter Mess-Snapshot zum vereinbarten Review-Zeitpunkt.",
        "external": "Operative Messdatenerhebung, technische Telemetrie und Rohdatenaufbereitung.",
    },
    "decision": {
        "title": "Ergebnisentscheidung",
        "purpose": "Die konkret verfügbare Lifecycle-Entscheidung auf Basis der Messung treffen.",
        "ki_radar": (
            "Messgrundlage, Entscheidung, Begründung und Statuswechsel im Lifecycle-Review."
        ),
        "external": "Umsetzungsplanung der beschlossenen Maßnahmen oder Skalierung.",
    },
    "operation": {
        "title": "Betrieb",
        "purpose": "Verantwortung und fällige Management-Reviews sichtbar machen.",
        "ki_radar": "Owner, nächster Review, Nutzenstatus und entscheidungsrelevante Auflagen.",
        "external": "Incident-, Change-, Release- und Service-Management.",
    },
    "closure": {
        "title": "Abschluss",
        "purpose": "Beendigung, Datenbehandlung und Lessons Learned nachvollziehbar machen.",
        "ki_radar": "Abschlussentscheidung, Beendigungsgrund, Datenbehandlung und Lessons Learned.",
        "external": "Technische Stilllegung, Archivierung und operative Restarbeiten.",
    },
}
OUTCOME_STAGE_KEYS = set(OUTCOME_STAGE_COPY)


def _normalize_outcome_stage(value: str | None) -> str:
    return value if value in OUTCOME_STAGE_KEYS else "pilot"


def _stage_action(
    phase: str,
    reason: str,
    *,
    action_label: str = "",
    url: str = "",
    external: bool = False,
    state: str = "neutral",
) -> dict[str, str | bool]:
    return {
        "phase": phase,
        "reason": reason,
        "action_label": action_label,
        "url": url,
        "external": external,
        "state": state,
    }


def _measurement_edit_action(use_case: UseCase, user) -> dict[str, str | bool]:
    phase = "Wirkung"
    if not can_edit_use_case(user, use_case):
        return _stage_action(
            phase,
            (
                "Die Wirkungsmessung ist sichtbar, kann mit der aktuellen Rolle aber nicht "
                "bearbeitet werden."
            ),
        )
    edit_url = reverse("use_cases:edit", kwargs={"pk": use_case.pk})
    required_fields = (
        ("metric_actual", use_case.metric_actual, "Ist-Wert erfassen"),
        ("metric_measurement_period", use_case.metric_measurement_period, "Messzeitraum ergänzen"),
        ("metric_measured_at", use_case.metric_measured_at, "Messdatum ergänzen"),
        ("metric_evidence_url", use_case.metric_evidence_url, "Messnachweis ergänzen"),
    )
    for field_name, value, label in required_fields:
        if value in (None, ""):
            return _stage_action(
                phase,
                "Die vorhandene Use-Case-Bearbeitung öffnet direkt das nächste fehlende Messfeld.",
                action_label=label,
                url=f"{edit_url}?highlight={field_name}",
                state="available",
            )
    return _stage_action(
        phase,
        "Messwert, Zeitraum, Datum und Nachweis liegen vor und können am Use Case geprüft werden.",
        action_label="Wirkungsmessung bearbeiten",
        url=f"{edit_url}?highlight=metric_actual",
        state="available",
    )


def _build_outcome_stage_action(
    *,
    active_stage: str,
    use_case: UseCase,
    user,
) -> dict[str, str | bool]:
    package = use_case.latest_delivery
    handed_over_package = current_handed_over_package(use_case)
    phase = OUTCOME_STAGE_COPY[active_stage]["title"]

    if active_stage == "handover":
        if package is None:
            return _stage_action(
                phase,
                "Für diesen Use Case existiert noch kein Delivery Package.",
            )
        status_snapshot = delivery_status_snapshot(package)
        if status_snapshot.handover_complete:
            return _stage_action(
                phase,
                f"Delivery Package v{package.version} wurde bereits verbindlich übergeben.",
            )
        if package.status == DeliveryPackage.Status.HANDED_OVER:
            return _stage_action(
                phase,
                status_snapshot.label,
                action_label="Übergabe prüfen",
                url=package.get_absolute_url(),
                state="available",
            )
        if package.status == DeliveryPackage.Status.READY:
            if status_snapshot.code != DeliveryPackage.Status.READY:
                return _stage_action(
                    phase,
                    status_snapshot.label,
                    action_label="Readiness prüfen",
                    url=package.get_absolute_url(),
                    state="available",
                )
            if can_transition_package(user):
                return _stage_action(
                    phase,
                    "Das vollständige Package ist bereit für die verbindliche Übergabe.",
                    action_label="An Delivery übergeben",
                    url=package.get_absolute_url(),
                    state="available",
                )
            return _stage_action(
                phase,
                "Das Package ist bereit. Nur ein KI-Koordinator darf die Übergabe bestätigen.",
            )
        if can_edit_package(user, package):
            return _stage_action(
                phase,
                "Das Delivery Package muss vor der Übergabe vervollständigt werden.",
                action_label="Delivery Package vervollständigen",
                url=reverse("delivery:package_update", kwargs={"pk": package.pk}),
                state="available",
            )
        return _stage_action(
            phase,
            (
                "Das Delivery Package ist noch unvollständig und mit der aktuellen Rolle nicht "
                "bearbeitbar."
            ),
        )

    if active_stage == "pilot":
        if use_case.status != UseCase.Status.PILOT:
            return _stage_action(
                phase,
                "Ein operativer Pilot-Link wird erst für einen gestarteten Pilot angezeigt.",
            )
        if handed_over_package is None:
            return _stage_action(
                phase,
                (
                    delivery_status_snapshot(package).label
                    if package
                    else "Das aktuelle Delivery Package wurde noch nicht verbindlich übergeben."
                ),
                action_label="Übergabe prüfen" if package else "",
                url=package.get_absolute_url() if package else "",
                state="available" if package else "blocked",
            )
        if handed_over_package.external_delivery_url:
            return _stage_action(
                phase,
                (
                    "Der operative Pilot läuft im externen Delivery-System; KI-Radar hält den "
                    "Review-Snapshot."
                ),
                action_label="Externen Pilot öffnen",
                url=handed_over_package.external_delivery_url,
                external=True,
                state="available",
            )
        if can_edit_package(user, handed_over_package):
            return _stage_action(
                phase,
                "Im Delivery Package ist noch kein externer Pilot-Link hinterlegt.",
                action_label="Delivery-Link ergänzen",
                url=(
                    f"{reverse('delivery:package_update', kwargs={'pk': handed_over_package.pk})}"
                    "?highlight=external_delivery_url"
                ),
                state="available",
            )
        if handed_over_package.status == DeliveryPackage.Status.HANDED_OVER:
            return _stage_action(
                phase,
                "Kein externer Pilot-Link hinterlegt. Das übergebene Package ist unveränderlich; "
                "der Link muss bei einer neuen Package-Version ergänzt werden.",
            )
        return _stage_action(
            phase,
            (
                "Kein externer Pilot-Link hinterlegt und aktuell keine zulässige "
                "Bearbeitungsaktion verfügbar."
            ),
        )

    if active_stage == "effect":
        return _measurement_edit_action(use_case, user)

    if active_stage == "decision":
        measurement_complete = all(
            (
                use_case.metric_actual is not None,
                bool(use_case.metric_measurement_period),
                use_case.metric_measured_at is not None,
                bool(use_case.metric_evidence_url),
            )
        )
        if not measurement_complete:
            action = _measurement_edit_action(use_case, user)
            action["phase"] = phase
            action["reason"] = (
                "Die Ergebnisentscheidung bleibt blockiert, bis die vollständige "
                "Wirkungsmessung vorliegt."
            )
            return action
        if use_case.status == UseCase.Status.PILOT and handed_over_package is None:
            return _stage_action(
                phase,
                (
                    "Die Go-live-Entscheidung ist blockiert, weil die aktuelle Delivery-"
                    "Übergabe nicht mehr gültig ist."
                ),
                action_label="Übergabe prüfen" if package else "",
                url=package.get_absolute_url() if package else "",
                state="available" if package else "blocked",
            )
        if use_case.status == UseCase.Status.PILOT and is_coordinator(user):
            return _stage_action(
                phase,
                (
                    "Die vollständige Messgrundlage liegt vor; jetzt kann über den Go-live "
                    "entschieden werden."
                ),
                action_label="Go-live entscheiden",
                url=(
                    f"{reverse('reviews:create', kwargs={'use_case_id': use_case.pk})}"
                    "?action=go_live"
                ),
                state="available",
            )
        if use_case.status in {UseCase.Status.OPERATION, UseCase.Status.ENDED}:
            return _stage_action(
                phase,
                (
                    "Die wirksame Lifecycle-Entscheidung ist bereits im Review und Status "
                    "dokumentiert."
                ),
            )
        return _stage_action(
            phase,
            "Eine Ergebnisentscheidung kann ausschließlich ein KI-Koordinator dokumentieren.",
        )

    if active_stage == "operation":
        if use_case.status == UseCase.Status.ENDED:
            return _stage_action(phase, "Der produktive Betrieb ist bereits abgeschlossen.")
        if use_case.status != UseCase.Status.OPERATION:
            return _stage_action(phase, "Der Betriebsbereich wird erst nach dem Go-live relevant.")
        today = timezone.localdate()
        review_due = use_case.next_review_date is None or use_case.next_review_date <= today
        if review_due and is_coordinator(user):
            return _stage_action(
                phase,
                "Der nächste Betriebsreview ist fällig oder noch nicht terminiert.",
                action_label="Review dokumentieren",
                url=reverse("reviews:create", kwargs={"use_case_id": use_case.pk}),
                state="available",
            )
        if review_due:
            return _stage_action(
                phase,
                (
                    "Ein Betriebsreview ist fällig, kann mit der aktuellen Rolle aber nicht "
                    "dokumentiert werden."
                ),
            )
        return _stage_action(
            phase,
            (
                "Aktuell keine Aktion erforderlich. Nächster Review: "
                f"{use_case.next_review_date:%d.%m.%Y}."
            ),
        )

    if active_stage == "closure":
        if use_case.status == UseCase.Status.ENDED:
            return _stage_action(
                phase,
                "Der Abschluss ist dokumentiert; der Use Case befindet sich im Status Beendet.",
            )
        closable_statuses = {UseCase.Status.PILOT, UseCase.Status.OPERATION}
        if use_case.status in closable_statuses and is_coordinator(user):
            return _stage_action(
                phase,
                (
                    "Beendigungsgrund und Daten-/Zugangsbehandlung werden im bestehenden Review "
                    "erfasst."
                ),
                action_label="Abschluss dokumentieren",
                url=(
                    f"{reverse('reviews:create', kwargs={'use_case_id': use_case.pk})}"
                    "?action=closure"
                ),
                state="available",
            )
        if use_case.status in closable_statuses:
            return _stage_action(
                phase,
                (
                    "Ein Abschluss ist möglich, kann mit der aktuellen Rolle aber nicht "
                    "dokumentiert werden."
                ),
            )
        return _stage_action(
            phase,
            (
                "Der Abschluss wird relevant, sobald der Use Case im Pilot oder Betrieb beendet "
                "werden soll."
            ),
        )

    return _stage_action(phase, "Für diesen Bereich ist aktuell keine Aktion verfügbar.")


@login_required
def dashboard(request):
    today = timezone.localdate()
    active_qs = (
        UseCase.objects.filter(is_archived=False)
        .exclude(status=UseCase.Status.ENDED)
        .select_related(
            "business_owner",
            "business_unit",
            "technical_owner",
            "classification",
            "architecture_origin__stage__value_stream",
            "architecture_origin__stage__value_stream__focus",
            "architecture_origin__process_analysis",
            "architecture_origin__solution_option",
        )
        .prefetch_related(
            "governance_assessments",
            "decision_assessments",
            "approval_decisions",
            "delivery_packages",
        )
    )
    active = list(active_qs)
    for item in active:
        item.decision_check = current_decision_check(item)
        item.blocker_details = build_blocker_details(item, item.decision_check.blockers)
        item.decision_due = decision_due_date(item)
        item.journey = build_use_case_journey(item, request.user)
    decision_queue = sorted(active, key=decision_priority)
    next_steps = [item for item in decision_queue if item.journey.next_action is not None]

    status_counts = {
        row["status"]: row["total"]
        for row in UseCase.objects.filter(is_archived=False)
        .values("status")
        .annotate(total=Count("id"))
    }
    blocked = sum(item.decision_check.state == "blocked" for item in active)
    overdue = sum(item.decision_due is not None and item.decision_due < today for item in active)
    measured = sum(item.metric_actual is not None for item in active)
    achieved = sum(item.metric_result == UseCase.MetricResult.ACHIEVED for item in active)

    context = {
        "status_counts": status_counts,
        "decision_queue": decision_queue[:20],
        "next_steps": next_steps[:8],
        "active_total": len(active),
        "blocked_total": blocked,
        "overdue_total": overdue,
        "measured_total": measured,
        "achieved_total": achieved,
        "due_soon_total": sum(
            item.decision_due is not None
            and today <= item.decision_due <= today + timedelta(days=30)
            for item in active
        ),
        "today": today,
    }
    return render(request, "reporting/dashboard.html", context)


@login_required
def portfolio(request):
    context = build_portfolio_context(request.GET)
    domain_labels = dict(BusinessDomain.choices)
    domain_rows = (
        UseCaseClassification.objects.filter(use_case__is_archived=False)
        .values("business_domain")
        .annotate(total=Count("use_case_id"))
        .order_by("business_domain")
    )
    context["business_domain_groups"] = [
        {
            "key": row["business_domain"],
            "label": domain_labels.get(row["business_domain"], "Nicht zugeordnet"),
            "total": row["total"],
        }
        for row in domain_rows
    ]
    return render(request, "reporting/portfolio.html", context)


@login_required
def outcome_workspace(request):
    active_stage = _normalize_outcome_stage(request.GET.get("stage"))
    use_cases = list(
        UseCase.objects.filter(is_archived=False)
        .select_related("business_owner", "technical_owner", "business_unit")
        .prefetch_related("delivery_packages", "reviews")
        .order_by("-updated_at")
    )
    for use_case in use_cases:
        use_case.latest_delivery = use_case.delivery_packages.first()

    requested_use_case = request.GET.get("use_case")
    selected_use_case = next(
        (item for item in use_cases if str(item.pk) == requested_use_case),
        None,
    )
    if selected_use_case is None:
        selected_use_case = next(
            (item for item in use_cases if item.status == UseCase.Status.PILOT),
            None,
        )
    if selected_use_case is None:
        selected_use_case = next(
            (
                item
                for item in use_cases
                if item.latest_delivery
                and item.latest_delivery.status == DeliveryPackage.Status.HANDED_OVER
            ),
            use_cases[0] if use_cases else None,
        )

    latest_scale_review = None
    if selected_use_case is not None:
        latest_scale_review = next(
            (
                review
                for review in selected_use_case.reviews.all()
                if review.scale_readiness_snapshot
            ),
            None,
        )

    journey = (
        build_outcome_workspace_journey(
            selected_use_case,
            request.user,
        )
        if selected_use_case
        else None
    )
    active_stage_action = (
        _build_outcome_stage_action(
            active_stage=active_stage,
            use_case=selected_use_case,
            user=request.user,
        )
        if selected_use_case
        else None
    )
    context = {
        "active_stage": active_stage,
        "active_stage_copy": OUTCOME_STAGE_COPY[active_stage],
        "active_stage_action": active_stage_action,
        "journey": journey,
        "selected_use_case": selected_use_case,
        "latest_scale_review": latest_scale_review,
        "use_cases": use_cases,
        "pilot_total": sum(item.status == UseCase.Status.PILOT for item in use_cases),
        "measured_total": sum(item.metric_actual is not None for item in use_cases),
        "operation_total": sum(item.status == UseCase.Status.OPERATION for item in use_cases),
        "ended_total": sum(item.status == UseCase.Status.ENDED for item in use_cases),
    }
    return render(request, "reporting/outcome_workspace.html", context)
