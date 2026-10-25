"""One transactional intake into existing ideas and, for goals, initiatives."""

from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from .idea_models import IdeaCandidate
from .initiatives import bind_initiative, can_edit_initiative, save_initiative
from .permissions import can_create_idea
from .topic_contract import OCCASIONS, SCHEMA, validate_intake_context

SALT = "use_cases.topic-intake-v1"


def topic_token(*, actor, occasion):
    return signing.dumps({"id": str(uuid4()), "actor": actor.pk, "occasion": occasion}, salt=SALT)


def suggested_title(text):
    compact = " ".join(text.split())
    if len(compact) <= 80:
        return compact
    head = compact[:79]
    return (head.rsplit(" ", 1)[0] or head) + "…"


def _topic_id(*, actor, token, occasion):
    if not can_create_idea(actor):
        raise PermissionDenied
    try:
        request = signing.loads(token, salt=SALT)
        idea_id = UUID(str(request["id"]))
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise ValidationError("Die Erfassung ist ungültig. Bitte das Thema erneut öffnen.") from exc
    if request.get("actor") != actor.pk:
        raise PermissionDenied
    if occasion not in OCCASIONS or request.get("occasion") != occasion:
        raise ValidationError("Der Anlass passt nicht zu dieser Erfassung.")
    return idea_id


def saved_topic(*, actor, token, occasion):
    idea_id = _topic_id(actor=actor, token=token, occasion=occasion)
    return IdeaCandidate.objects.filter(pk=idea_id, submitted_by=actor).first()


@transaction.atomic
def save_topic(*, actor, token, occasion, text, title="", perspectives=()):
    idea_id = _topic_id(actor=actor, token=token, occasion=occasion)
    context = {
        "schema_version": SCHEMA,
        "occasion": occasion,
        "perspectives": list(perspectives),
        "original_text": text,
    }
    validate_intake_context(context)
    title = title.strip() or suggested_title(text)
    if len(title) > 200:
        raise ValidationError("Der Kurztitel ist zu lang.")

    def reuse(idea):
        if idea.submitted_by_id != actor.pk:
            raise PermissionDenied
        if idea.intake_context != context or idea.title != title:
            raise ValidationError(
                "Dieses Thema wurde bereits mit anderen Angaben gespeichert. "
                "Bitte den gespeicherten Eintrag öffnen."
            )
        return idea

    existing = IdeaCandidate.objects.select_for_update().filter(pk=idea_id).first()
    if existing is not None:
        return reuse(existing)
    if occasion == "goal" and not can_edit_initiative(actor):
        raise PermissionDenied
    try:
        with transaction.atomic():
            idea = IdeaCandidate(
                id=idea_id,
                title=title,
                description=text,
                submitted_by=actor,
                intake_context=context,
            )
            idea.full_clean(validate_unique=False)
            idea.save(force_insert=True)
    except IntegrityError:
        existing = IdeaCandidate.objects.select_for_update().filter(pk=idea_id).first()
        if existing is None:
            raise
        return reuse(existing)
    if occasion == "goal":
        initiative = save_initiative(actor=actor, data={"title": title, "business_outcome": text})
        idea = bind_initiative(initiative=initiative, artifact=idea, actor=actor)
    return idea
