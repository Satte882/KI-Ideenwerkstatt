from django.core.exceptions import ValidationError
from django.db import models


class ImmutableDecisionQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        if kwargs.get("update_conflicts"):
            raise ValidationError("Dokumentierte Entscheidungen dürfen nicht überschrieben werden.")
        if any(
            hasattr(obj, "outcome_snapshot") and obj.process_analysis.outcome_contract_version
            for obj in objs
        ):
            raise ValidationError("Neue Lösungsentscheidungen benötigen den Entscheidungsservice.")
        return super().bulk_create(objs, **kwargs)

    def update(self, **kwargs):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")

    def delete(self):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")


class ImmutableDecisionManager(models.Manager.from_queryset(ImmutableDecisionQuerySet)):
    pass
