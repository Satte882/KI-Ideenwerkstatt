"""Shared initiative editing and explicit associations; draft saves never enforce outcome gates."""

from datetime import timedelta
from unicodedata import normalize

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from ki_radar.accounts.permissions import is_business_owner, is_coordinator

from .initiative_models import ImprovementInitiative, InitiativeImpactReview

# #146 must explicitly introduce and enforce the new contract at both decision boundaries.
LEGACY_OUTCOME_CONTRACT = 0

PLAN_FIELDS = (
    "measurement_method",
    "measurement_period",
    "measurement_population",
    "measurement_reference",
    "measurement_unknowns",
)

OUTCOME_FIELDS = (
    *PLAN_FIELDS,
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
    "measurement_change_reason",
)


def can_edit_initiative(actor, initiative=None):
    if not actor or not actor.is_authenticated or not actor.is_active:
        return False
    return is_coordinator(actor) or (
        is_business_owner(actor) and (initiative is None or initiative.created_by_id == actor.pk)
    )


def _text(value):
    return " ".join(normalize("NFC", str(value)).split())


def _formal_text(value):
    # Only whitespace, Unicode composition and one optional terminal full stop.
    # Letter/number/negation, owner and evidence changes require fresh confirmation.
    text = _text(value)
    return text[:-1].rstrip() if text.endswith(".") and not text.endswith("..") else text


def initiative_claim_matches(previous, current):
    """Compare the claim reviewed for both freshness and proven completion."""
    from .outcome_contract import MATERIAL_FIELDS

    return all(
        (_formal_text if field in MATERIAL_FIELDS else _text)(getattr(previous, field))
        == (_formal_text if field in MATERIAL_FIELDS else _text)(getattr(current, field))
        for field in (*OUTCOME_FIELDS, "effect_status", "effect_reason")
    )


@transaction.atomic
def save_initiative(
    *,
    actor,
    data,
    initiative=None,
    expected_revision=None,
    source="human",
    correction_reason="",
    preparation_key=None,
    preparation_data=None,
    context_adoption=None,
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
    current_review = None
    if (
        initiative is not None
        and source == "human"
        and preparation_key is not None
        and preparation_data is not None
        and all(getattr(initiative, key) == value for key, value in data.items())
    ):
        # The initiative lock also serializes impact-review writes. Only carry
        # already-current evidence across a strictly preparation-only save.
        review = InitiativeImpactReview.objects.filter(initiative=initiative).first()
        if review is not None and not review.review_required:
            current_review = review
    material_change = False
    formal_correction = False
    if initiative is None:
        initiative = ImprovementInitiative(created_by=actor)
    else:
        changed_fields = {
            key
            for key in OUTCOME_FIELDS
            if key in data and _text(getattr(initiative, key)) != _text(data[key])
        }
        plan_changed = changed_fields & {*PLAN_FIELDS, "evaluation_criteria"}
        if (
            plan_changed
            and any(getattr(initiative, name).strip() for name in PLAN_FIELDS)
            and not data.get("measurement_change_reason", "").strip()
            and not correction_reason.strip()
        ):
            raise ValidationError("Messplan-/Kriterienänderung bitte begründen.")
        formal_correction = bool(correction_reason.strip()) and all(
            key in MATERIAL_FIELDS
            and _formal_text(getattr(initiative, key)) == _formal_text(data[key])
            for key in changed_fields
        )
        material_change = bool(changed_fields) and not formal_correction
        initiative.revision += 1
        if material_change:
            initiative.outcome_revision += 1
        if material_change or source == "ai":
            initiative.confirmed_revision = None
            initiative.confirmed_by = None
            initiative.confirmed_at = None
            initiative.confirmation_reason = ""
        if correction_reason.strip():
            label = "Schreibkorrektur" if formal_correction else "Änderung (erneut bestätigen)"
            initiative._change_reason = (label + ": " + correction_reason.strip())[:100]
    if "impact_hypothesis" in data and (
        source == "ai"
        or (
            _text(data["impact_hypothesis"]) != _text(initiative.impact_hypothesis)
            and not formal_correction
        )
    ):
        initiative.hypothesis_origin = source
    for key, value in data.items():
        setattr(initiative, key, value)
    if preparation_key is not None:
        # This context is never consumed by outcome gates or decision snapshots.
        drafts = dict(initiative.preparation_drafts)
        if preparation_data is None:
            drafts.pop(preparation_key, None)
        else:
            drafts[preparation_key] = dict(preparation_data)
        initiative.preparation_drafts = drafts
    initiative.updated_by = actor
    if context_adoption is not None:
        initiative.context_provenance = [*initiative.context_provenance, context_adoption]
    initiative._history_user = actor
    initiative.save()
    if current_review is not None:
        current_review.initiative = initiative
        current_review.initiative_revision = initiative.revision
        current_review._history_user = actor
        current_review._change_reason = "Unverbindlicher Pfadentwurf; Wirkungsevidenz unverändert"
        current_review.save(update_fields=["initiative_revision", "updated_at"])
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
