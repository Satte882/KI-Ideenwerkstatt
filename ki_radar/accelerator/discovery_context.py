from django.core.exceptions import ValidationError
from django.db import transaction

from ki_radar.accounts.models import BusinessUnit

from .models import CaptureSession


def default_discovery_business_unit(*, actor, idea=None):
    unit = idea.business_unit if idea is not None and idea.business_unit_id else actor.business_unit
    return unit if unit is not None and unit.is_active else None


def discovery_business_unit_context(session):
    if "business_unit" in session.answers:
        context = session.answers["business_unit"]
        if not isinstance(context, dict) or not context.get("id") or not context.get("name"):
            raise ValidationError("Die Organisationseinheit dieser Untersuchung ist ungültig.")
        return context
    # Older runs used the owner's unit. Freeze that legacy default on the next write.
    unit = session.owner.business_unit
    if unit is None:
        raise ValidationError("Für diesen bisherigen Lauf fehlt eine Organisationseinheit.")
    return {"id": unit.pk, "name": unit.name}


def active_discovery_business_unit(session):
    context = discovery_business_unit_context(session)
    try:
        unit = BusinessUnit.objects.filter(pk=context["id"], is_active=True).first()
    except (ValueError, TypeError) as exc:
        raise ValidationError("Die Organisationseinheit dieser Untersuchung ist ungültig.") from exc
    if unit is None:
        raise ValidationError(
            "Die ausgewählte Organisationseinheit ist nicht mehr aktiv oder verfügbar. "
            "Die Discovery bleibt erhalten. Für eine andere Zuordnung verwerfen Sie "
            "diesen Lauf und starten Sie eine neue Untersuchung."
        )
    return unit


@transaction.atomic
def freeze_legacy_discovery_business_unit(session):
    if "business_unit" in session.answers:
        return active_discovery_business_unit(session)
    locked = (
        CaptureSession.objects.select_for_update()
        .select_related("owner")
        .get(pk=session.pk)
    )
    unit = active_discovery_business_unit(locked)
    if "business_unit" not in locked.answers:
        locked.answers = {
            **locked.answers,
            "business_unit": discovery_business_unit_context(locked),
        }
        locked.save(update_fields=["answers", "updated_at"])
    session.answers = locked.answers
    return unit
