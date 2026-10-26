"""Historical references, never a second metric store or a success inference."""

from copy import deepcopy

from django.core.exceptions import ObjectDoesNotExist

from .initiatives import OUTCOME_FIELDS, PLAN_FIELDS


def original_measurement_anchor(*, selection=None, use_case=None):
    """Earliest binding record for this intervention; reselection cannot backdate it."""
    if selection is None and use_case is not None:
        try:
            origin = use_case.architecture_origin
        except ObjectDoesNotExist:
            origin = None
        if origin and origin.solution_option_id:
            selection = (
                origin.process_analysis.solution_selection_decisions.filter(
                    selected_option_id=origin.solution_option_id
                )
                .order_by("decided_at", "pk")
                .first()
            )
    if selection is not None:
        original = (
            selection.process_analysis.solution_selection_decisions.filter(
                selected_option_id=selection.selected_option_id
            )
            .order_by("decided_at", "pk")
            .first()
        )
        return {
            "kind": "selection",
            "id": original.pk,
            "at": original.decided_at.isoformat(),
            "actor_id": original.decided_by_id,
            "outcome": deepcopy(original.outcome_snapshot),
            "timing_limit": "Auswahl belegt; externer Umsetzungsbeginn bleibt offen.",
        }
    if use_case is not None:
        approval = (
            use_case.approval_decisions.filter(
                decision_status__in=["approved", "approved_with_conditions"],
                finalized_at__isnull=False,
            )
            .order_by("finalized_at", "pk")
            .first()
        )
        if approval is not None:
            return {
                "kind": "approval",
                "id": str(approval.pk),
                "at": approval.finalized_at.isoformat(),
                "actor_id": approval.decided_by_id,
                "outcome": deepcopy(approval.outcome_snapshot),
                "timing_limit": "Freigabe belegt; Pilotbeginn separat nachvollziehen.",
            }
    return {}


def build_criteria_snapshot(review):
    anchor = original_measurement_anchor(selection=review.selection, use_case=review.use_case)
    # Only interventions covered by the outcome contract acquire the new review contract.
    if not (
        anchor.get("outcome") or (review.use_case_id and review.use_case.outcome_contract_version)
    ):
        return {}
    initiative = review.initiative
    return {
        "version": 1,
        "original": anchor,
        "current": {name: getattr(initiative, name) for name in OUTCOME_FIELDS},
        "initiative_history_id": initiative.history.values_list("history_id", flat=True).first(),
        "measurement_change_reason": initiative.measurement_change_reason,
    }


def criteria_review_blocker(review):
    if not review.criteria_assessment.strip() or not review.assessment_basis:
        return "Geschäftsergebnis benötigt historischen Kriterienabgleich und zeitliche Einordnung."
    original = review.criteria_snapshot.get("original", {}).get("outcome", {})
    fields = original.get("fields", {})
    if review.assessment_basis == "original":
        if original.get("measurement_plan", {}).get("state") != "documented":
            return "Vorab-Messplan fehlt; nachträglich bewerten oder ungeklärt lassen."
        if (
            any(
                fields.get(name, "") != getattr(review.initiative, name)
                for name in (*PLAN_FIELDS, "evaluation_criteria")
            )
            and not review.criteria_deviation.strip()
        ):
            return "Abweichung zum historischen Maßstab und Zeitpunkt bitte ausdrücklich einordnen."
    elif not review.criteria_deviation.strip():
        return "Nachträgliche Bewertung benötigt Zeitpunkt, Grund und Evidenzgrenzen."
    return ""


def business_context(use_case):
    """Read-only, non-blocking context for existing Delivery/Scale decisions."""
    initiative = use_case.initiative
    if initiative is None:
        return {}
    try:
        review = initiative.impact_review
    except ObjectDoesNotExist:
        review = None
    return {
        "initiative_id": str(initiative.pk),
        "initiative_history_id": initiative.history.values_list("history_id", flat=True).first(),
        "current": {name: getattr(initiative, name) for name in OUTCOME_FIELDS},
        "original": original_measurement_anchor(use_case=use_case),
        "effect_status": initiative.effect_status,
        "effect_label": initiative.get_effect_status_display() or "Noch ungeklärt",
        "effect_reason": initiative.effect_reason,
        "review_id": review.pk if review else None,
        "review_history_id": review.history.values_list("history_id", flat=True).first()
        if review
        else None,
        "review_required": review.review_required if review else True,
        "attribution": review.attribution if review else "unclear",
        "attribution_label": review.get_attribution_display() if review else "Noch ungeklärt",
        "attribution_reason": review.attribution_reason if review else "",
        "contribution_boundary": review.contribution_boundary if review else "",
        "coverage_limit": "Ein strukturierter Auswahl-/Use-Case-Bezug; keine ROI-Addition.",
    }
