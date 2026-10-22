"""Shared initiative editing and explicit associations; draft saves never enforce outcome gates."""

from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from ki_radar.accounts.permissions import is_business_owner, is_coordinator

from .initiative_models import ImprovementInitiative

# #146 must explicitly introduce and enforce the new contract at both decision boundaries.
LEGACY_OUTCOME_CONTRACT = 0

OUTCOME_FIELDS = (
    "business_outcome",
    "contribution",
    "impact_hypothesis",
    "evaluation_criteria",
    "evidence_level",
    "evidence_note",
    "outcome_owner",
    "target_group",
)
EDITABLE_FIELDS = (
    "title",
    *OUTCOME_FIELDS,
    "status",
    "next_review_date",
    "effect_status",
    "effect_reason",
    "cancellation_reason",
)


def can_edit_initiative(actor, initiative=None):
    if not actor or not actor.is_authenticated or not actor.is_active:
        return False
    return is_coordinator(actor) or (
        is_business_owner(actor) and (initiative is None or initiative.created_by_id == actor.pk)
    )


@transaction.atomic
def save_initiative(
    *, actor, data, initiative=None, expected_revision=None, source="human", correction_reason=""
):
    from .outcome_contract import MATERIAL_FIELDS

    data = dict(data)
    if source not in {"human", "ai"}:
        raise ValidationError("Unbekannte Herkunft der Wirkannahme.")
    if source == "ai":
        data["evidence_level"] = "hypothesis"
    if initiative is not None:
        initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative):
        raise PermissionDenied
    if expected_revision is not None and initiative and initiative.revision != expected_revision:
        raise ValidationError("Das Vorhaben wurde inzwischen geändert. Bitte neu laden.")
    unknown = set(data) - set(EDITABLE_FIELDS)
    if unknown:
        raise ValidationError("Serververwaltete Vorhabensfelder dürfen nicht geändert werden.")
    if initiative is None:
        initiative = ImprovementInitiative(created_by=actor)
    else:
        changed_outcome = any(
            key in data
            and " ".join(str(getattr(initiative, key)).split()) != " ".join(str(data[key]).split())
            for key in (*MATERIAL_FIELDS, "evidence_level", "evidence_note", "outcome_owner")
        )
        initiative.revision += 1
        if changed_outcome and not correction_reason.strip():
            initiative.outcome_revision += 1
        if (changed_outcome and not correction_reason.strip()) or source == "ai":
            initiative.confirmed_revision = None
            initiative.confirmed_by = None
            initiative.confirmed_at = None
            initiative.confirmation_reason = ""
        if correction_reason.strip():
            initiative._change_reason = "Schreibkorrektur: " + correction_reason.strip()[:75]
    if "impact_hypothesis" in data and (
        source == "ai"
        or (
            data["impact_hypothesis"] != initiative.impact_hypothesis
            and not correction_reason.strip()
        )
    ):
        initiative.hypothesis_origin = source
    for key, value in data.items():
        setattr(initiative, key, value)
    initiative.updated_by = actor
    initiative._history_user = actor
    initiative.save()
    return initiative


@transaction.atomic
def bind_initiative(*, initiative, artifact, actor):
    """Explicit association only; never creates an initiative or authorizes a decision."""
    from ki_radar.architecture.models import ProcessAnalysis
    from ki_radar.architecture.permissions import can_edit_value_stream

    from .idea_models import IdeaCandidate
    from .models import UseCase
    from .permissions import can_edit_use_case, can_triage_idea

    if not isinstance(artifact, (IdeaCandidate, ProcessAnalysis, UseCase)):
        raise ValidationError("Dieses Objekt kann keinem Vorhaben zugeordnet werden.")
    artifact = type(artifact).objects.select_for_update().get(pk=artifact.pk)
    initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative):
        raise PermissionDenied
    if isinstance(artifact, ProcessAnalysis):
        allowed = can_edit_value_stream(actor, artifact.stage.value_stream)
    elif isinstance(artifact, UseCase):
        allowed = can_edit_use_case(actor, artifact)
    else:
        allowed = can_triage_idea(actor, artifact)
    if not allowed:
        raise PermissionDenied
    if artifact.initiative_id and artifact.initiative_id != initiative.pk:
        raise ValidationError("Das Objekt ist bereits einem anderen Vorhaben zugeordnet.")
    if artifact.initiative_id == initiative.pk:
        return artifact
    artifact.initiative = initiative
    artifact.save(update_fields=["initiative", "updated_at"])
    initiative.revision += 1
    initiative.updated_by = actor
    initiative._history_user = actor
    initiative._change_reason = f"Zuordnung {artifact._meta.label_lower}:{artifact.pk}"
    initiative.save()
    return artifact


def initiative_review_summary(*, today=None):
    today = today or timezone.localdate()
    active = ImprovementInitiative.objects.filter(
        status__in=[ImprovementInitiative.Status.DRAFT, ImprovementInitiative.Status.ACTIVE]
    )
    return {
        "overdue": active.filter(next_review_date__lt=today).count(),
        "due_within_30_days": active.filter(
            next_review_date__gte=today, next_review_date__lte=today + timedelta(days=30)
        ).count(),
        "missing_review_date": active.filter(next_review_date__isnull=True).count(),
    }
