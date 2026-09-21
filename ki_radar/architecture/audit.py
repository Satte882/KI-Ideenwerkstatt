from django.core.exceptions import ValidationError
from django.db import models


class ImmutableDecisionQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")

    def delete(self):
        raise ValidationError("Dokumentierte Lösungsentscheidungen sind unveränderlich.")


class ImmutableDecisionManager(models.Manager.from_queryset(ImmutableDecisionQuerySet)):
    pass
