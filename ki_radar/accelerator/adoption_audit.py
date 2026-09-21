from __future__ import annotations

from .candidate_snapshot import canonical_text_hash, canonicalize_text
from .models import FieldAdoptionAudit, FieldAdoptionCandidate


def _canonical_text_or_empty(value) -> str:
    return canonicalize_text(value) if isinstance(value, str) else ""


def record_adoption_audit(
    *,
    candidate: FieldAdoptionCandidate,
    actor,
    action: str,
    outcome: str,
    error_code: str = "",
    current_value: str = "",
    final_value: str = "",
    edited_value: str | None = None,
    target_updated_at_changed: bool = False,
) -> FieldAdoptionAudit:
    """Persist exactly one minimal, retention-safe outcome record per candidate."""
    suggestion = candidate.suggestion
    analysis = suggestion.analysis
    session = analysis.session
    adopted = outcome in {"adopted", "adopted_edited"}
    stored_value = final_value if adopted else current_value

    audit, _created = FieldAdoptionAudit.objects.get_or_create(
        candidate_id_snapshot=candidate.pk,
        defaults={
            "candidate": candidate,
            "suggestion": suggestion,
            "analysis": analysis,
            "session": session,
            "actor": actor if getattr(actor, "pk", None) else None,
            "suggestion_id_snapshot": suggestion.pk,
            "analysis_id_snapshot": analysis.pk,
            "session_id_snapshot": session.pk,
            "actor_id_snapshot": getattr(actor, "pk", None),
            "target_object_type": candidate.target_object_type,
            "target_object_id": candidate.target_object_id,
            "target_field": candidate.target_field,
            "previous_value": candidate.previous_value,
            "previous_value_hash": candidate.previous_value_hash,
            "proposed_value": candidate.proposed_value,
            "edited_value": _canonical_text_or_empty(edited_value),
            "current_value": _canonical_text_or_empty(current_value),
            "final_value": _canonical_text_or_empty(stored_value),
            "action": action,
            "outcome": outcome,
            "error_code": error_code,
            "target_updated_at_changed": target_updated_at_changed,
            "source_question": suggestion.source_question,
            "source_excerpt_hash": canonical_text_hash(suggestion.source_excerpt),
            "provider": analysis.provider,
            "model_name": analysis.model_name,
            "catalog_version": analysis.catalog_version,
            "answer_schema_version": analysis.answer_schema_version,
            "prompt_version": analysis.prompt_version,
            "extraction_schema_version": analysis.extraction_schema_version,
            "prompt_tokens": analysis.prompt_tokens,
            "completion_tokens": analysis.completion_tokens,
            "total_tokens": analysis.total_tokens,
            "cost": analysis.cost,
        },
    )
    return audit
