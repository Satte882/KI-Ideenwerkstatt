"""Navigation and explicit intake reuse for initiative discovery; no decision gates."""

import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from ki_radar.architecture.permissions import can_manage_architecture

from .idea_discovery import active_idea_discovery
from .idea_models import IdeaCandidate
from .initiative_models import ImprovementInitiative
from .initiatives import bind_initiative, can_edit_initiative


def initiative_discovery_context(initiative, actor):
    paths = []
    for idea in initiative.ideas.select_related("discovery_process_analysis", "submitted_by"):
        session = active_idea_discovery(idea)
        paths.append(
            {
                "idea": idea,
                "session": session,
                "can_resume": bool(
                    session and session.owner_id == actor.pk and can_manage_architecture(actor)
                ),
            }
        )
    return {
        "discovery_paths": paths,
        "initiative_processes": initiative.process_analyses.all(),
        "can_start_initiative_discovery": can_edit_initiative(actor, initiative)
        and can_manage_architecture(actor),
    }


@transaction.atomic
def initiative_discovery_idea(*, initiative, actor):
    initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative) or not can_manage_architecture(actor):
        raise PermissionDenied
    # Serialize creation on the existing aggregate. Never pick an arbitrary idea
    # when historical data contains multiple legitimate origins.
    ideas = list(initiative.ideas.order_by("created_at"))
    if len(ideas) > 1:
        raise ValidationError(
            "Mehrere Ideen sind zugeordnet. Bitte die passende Ursprungsidee öffnen."
        )
    if ideas:
        return ideas[0]
    if initiative.process_analyses.exists():
        raise ValidationError("Bereits vorhandene Prozessanalyse öffnen und dort fortsetzen.")
    idea = IdeaCandidate.objects.create(
        title=initiative.title,
        description=initiative.business_outcome,
        source_note=(
            f"Vorhaben {initiative.pk}, Revision {initiative.revision}; "
            "menschliche Eingabe, kein unabhängiger Nachweis.\n"
            f"Ursprüngliches Geschäftsziel: {initiative.business_outcome}\n"
            + (
                json.dumps(initiative.context_provenance, ensure_ascii=False)
                if initiative.context_provenance
                else ""
            )
        ),
        submitted_by=actor,
    )
    return bind_initiative(initiative=initiative, artifact=idea, actor=actor)
