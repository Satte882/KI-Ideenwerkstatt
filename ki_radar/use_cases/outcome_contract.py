"""Outcome contract v1: only binding decisions enforce this shared boundary."""

from copy import deepcopy

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .initiative_models import ImprovementInitiative

OUTCOME_CONTRACT_VERSION = 1
MATERIAL_FIELDS = (
    "business_outcome",
    "contribution",
    "impact_hypothesis",
    "target_group",
    "evaluation_criteria",
)


def _process(artifact):
    if artifact._meta.model_name == "processanalysis":
        return artifact
    try:
        return artifact.architecture_origin.process_analysis
    except ObjectDoesNotExist:
        return None


def outcome_blockers(artifact):
    if not artifact.outcome_contract_version:
        return []
    initiative = artifact.initiative
    if initiative is None:
        return ["Vorhaben mit Geschäftsergebnis und Wirkannahme bewusst zuordnen"]
    missing = []
    for field, label in (
        ("business_outcome", "Geschäftsergebnis"),
        ("contribution", "Vorhabensbeitrag"),
        ("impact_hypothesis", "Wirkannahme"),
        ("outcome_owner", "Outcome Owner"),
        ("evaluation_criteria", "Prüfkriterien"),
    ):
        if not getattr(initiative, field).strip():
            missing.append(label)
    if initiative.status == ImprovementInitiative.Status.CANCELLED:
        missing.append("Abgebrochenes Vorhaben kann keine neue Freigabe tragen")
    if initiative.evidence_level != "hypothesis" and not initiative.evidence_note.strip():
        missing.append("Quelle für den höheren Evidenzstand")
    if (
        initiative.confirmed_revision != initiative.outcome_revision
        or not initiative.confirmed_by_id
        or not initiative.confirmed_at
    ):
        missing.append("Aktuelle Wirkannahme fachlich bestätigen")
    process = _process(artifact)
    if process is not None:
        missing.extend(_origin_blockers(artifact, process))
        if process.initiative_id != initiative.pk:
            missing.append("Vorhaben und Herkunftsprozess müssen übereinstimmen")
        from ki_radar.architecture.stage_focus import get_phase_focus_decision

        focus = get_phase_focus_decision(process.stage, initiative=initiative)
        if focus is None or focus.selected_stage_id != process.stage_id:
            missing.append("Aktuellen Vorhabensfokus für diese Prozessphase bestätigen")
        path = process.discovery_path_decisions.first()
        if (
            path is None
            or path.path not in {"problem", "strategic"}
            or not path.origin_basis.strip()
        ):
            missing.append("Discovery-Pfad anhand der dokumentierten Herkunft einordnen")
        elif path.path == "strategic" and not (
            path.strategic_potential.strip() and path.validation_step.strip()
        ):
            missing.append("Strategisches Potenzial und prüfbarer Validierungsschritt")
    return missing


def _origin_blockers(artifact, process):
    if artifact._meta.model_name != "usecase":
        return []
    origin = artifact.architecture_origin
    blockers = []
    if (
        origin.stage_id != process.stage_id
        or artifact.business_unit_id != process.stage.value_stream.business_unit_id
    ):
        blockers.append("Konsistente Prozessherkunft und Organisationseinheit")
    if origin.solution_option_id:
        decision = process.solution_selection_decisions.filter(
            selected_option_id=origin.solution_option_id,
        ).first()
        if origin.solution_option.process_analysis_id != process.pk or (
            process.outcome_contract_version
            and (
                decision is None
                or not decision.outcome_snapshot
                or decision.outcome_review_required
                or origin.solution_option.recommendation != "preferred"
            )
        ):
            blockers.append("Aktuelle menschliche Lösungsentscheidung der Herkunft")
    return blockers


def build_outcome_snapshot(artifact, *, lock=False):
    if not artifact.outcome_contract_version:
        return {}
    if artifact.initiative_id:
        query = (
            ImprovementInitiative.objects.select_for_update()
            if lock
            else ImprovementInitiative.objects
        )
        artifact.initiative = query.get(
            pk=artifact.initiative_id,
        )
    blockers = outcome_blockers(artifact)
    if blockers:
        raise ValidationError("Outcome-Bezug offen: " + ", ".join(blockers))
    initiative = artifact.initiative
    result = {
        "contract_version": OUTCOME_CONTRACT_VERSION,
        "initiative_id": str(initiative.pk),
        "outcome_revision": initiative.outcome_revision,
        "fields": {field: getattr(initiative, field) for field in MATERIAL_FIELDS},
        "outcome_owner": initiative.outcome_owner,
        "evidence_level": initiative.evidence_level,
        "evidence_note": initiative.evidence_note,
        "hypothesis_origin": initiative.hypothesis_origin,
        "confirmed_by": initiative.confirmed_by_id,
        "confirmed_at": initiative.confirmed_at.isoformat(),
        "confirmation_reason": initiative.confirmation_reason,
    }
    process = _process(artifact)
    if process is not None:
        from ki_radar.architecture.stage_focus import get_phase_focus_decision

        focus = get_phase_focus_decision(process.stage, initiative=initiative)
        path = process.discovery_path_decisions.first()
        result["focus"] = {
            "id": focus.pk,
            "revision": focus.revision,
            "stage_id": str(focus.selected_stage_id),
            "value_stream_id": str(focus.value_stream_id),
            "rationale": focus.rationale,
            "criteria": deepcopy(focus.criteria_snapshot),
            "selected_by": focus.selected_by_id,
        }
        result["discovery_path"] = {
            "id": path.pk,
            "revision": path.revision,
            "path": path.path,
            "origin_basis": path.origin_basis,
            "change_reason": path.change_reason,
            "strategic_potential": path.strategic_potential,
            "validation_step": path.validation_step,
            "decided_by": path.decided_by_id,
            "decided_at": path.created_at.isoformat(),
            "confirmed_cause_available": bool(process.confirmed_causes.strip()),
        }
    if (
        process is not None
        and artifact._meta.model_name == "usecase"
        and artifact.architecture_origin.solution_option_id
    ):
        decision = process.solution_selection_decisions.filter(
            selected_option_id=artifact.architecture_origin.solution_option_id,
        ).first()
        result["source_selection_id"] = decision.pk if decision else None
    return result


def snapshot_is_stale(artifact, snapshot):
    from .initiatives import _formal_text, _text

    # Historical unbound decisions are neither rewritten nor labelled stale.
    if not snapshot:
        return False
    try:
        current = build_outcome_snapshot(artifact)
    except ValidationError:
        return True
    # Revisions identify service changes; comparing the captured content also
    # protects individual ORM edits without inventing a new revision counter.
    if any(
        _formal_text(snapshot.get("fields", {}).get(field, ""))
        != _formal_text(current.get("fields", {}).get(field, ""))
        for field in MATERIAL_FIELDS
    ) or any(
        _text(snapshot.get(field, "")) != _text(current.get(field, ""))
        for field in ("outcome_owner", "evidence_level", "evidence_note", "hypothesis_origin")
    ):
        return True
    return any(
        snapshot.get(key) != current.get(key)
        for key in ("initiative_id", "outcome_revision", "source_selection_id")
    ) or any(
        snapshot.get(key, {}).get("id") != current.get(key, {}).get("id")
        for key in ("focus", "discovery_path")
    )


def validate_decision_snapshot(artifact, snapshot):
    current = build_outcome_snapshot(artifact)
    if not snapshot or current != snapshot:
        raise ValidationError("Die bindende Entscheidung benötigt den aktuellen Outcome-Snapshot.")


@transaction.atomic
def confirm_initiative(*, initiative, actor, rationale, expected_revision):
    from .initiatives import can_edit_initiative

    initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative):
        raise PermissionDenied
    if initiative.revision != expected_revision:
        raise ValidationError("Der geprüfte Vorhabensstand wurde geändert. Bitte erneut prüfen.")
    if not str(rationale).strip():
        raise ValidationError("Die fachliche Annahme der Wirkannahme muss begründet werden.")
    if not all(
        getattr(initiative, name).strip()
        for name in (
            "business_outcome",
            "contribution",
            "impact_hypothesis",
            "evaluation_criteria",
            "outcome_owner",
        )
    ):
        raise ValidationError(
            "Geschäftsergebnis, Beitrag, Wirkannahme, Owner und Prüfkriterien fehlen."
        )
    if initiative.evidence_level != "hypothesis" and not initiative.evidence_note.strip():
        raise ValidationError("Für einen höheren Evidenzstand ist die Quelle erforderlich.")
    if (
        initiative.confirmed_revision == initiative.outcome_revision
        and initiative.confirmed_by_id
        and initiative.confirmed_at
    ):
        return initiative
    initiative.confirmed_revision = initiative.outcome_revision
    initiative.confirmed_by = actor
    initiative.confirmed_at = timezone.now()
    initiative.confirmation_reason = rationale.strip()
    initiative.revision += 1
    initiative.updated_by = actor
    initiative._history_user = actor
    initiative._change_reason = "Wirkannahme fachlich angenommen; keine Erfolgsbestätigung"
    initiative.save()
    return initiative


@transaction.atomic
def set_discovery_path(
    *,
    process,
    actor,
    path,
    origin_basis,
    change_reason="",
    strategic_potential="",
    validation_step="",
):
    from ki_radar.architecture.models import ProcessAnalysis, ProcessDiscoveryPathDecision
    from ki_radar.architecture.permissions import can_edit_value_stream

    process = ProcessAnalysis.objects.select_for_update().get(pk=process.pk)
    if (
        not actor
        or not actor.is_active
        or not can_edit_value_stream(actor, process.stage.value_stream)
    ):
        raise PermissionDenied
    previous = process.discovery_path_decisions.first()
    if not origin_basis.strip() or path not in {"problem", "strategic"}:
        raise ValidationError("Pfad und dokumentierte fachliche Herkunft sind erforderlich.")
    if previous and previous.path != path and not change_reason.strip():
        raise ValidationError("Der Pfadwechsel benötigt eine explizite fachliche Begründung.")
    values = {
        "path": path,
        "origin_basis": origin_basis.strip(),
        "strategic_potential": strategic_potential.strip(),
        "validation_step": validation_step.strip(),
    }
    if previous and all(getattr(previous, key) == value for key, value in values.items()):
        return previous
    return ProcessDiscoveryPathDecision.objects.create(
        process_analysis=process,
        path=path,
        origin_basis=origin_basis.strip(),
        change_reason=change_reason.strip(),
        strategic_potential=strategic_potential.strip(),
        validation_step=validation_step.strip(),
        decided_by=actor,
        revision=previous.revision + 1 if previous else 1,
    )
