"""Unveränderliche QuerySet- und Manager-Bausteine für Delivery-Auditdaten."""

from django.core.exceptions import ValidationError
from django.db import models


class ImmutableAuditQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Dokumentierte Quellenentscheidungen sind unveränderlich.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Dokumentierte Quellenentscheidungen sind unveränderlich.")

    def delete(self):
        raise ValidationError("Dokumentierte Quellenentscheidungen sind unveränderlich.")


class ImmutableAuditManager(models.Manager.from_queryset(ImmutableAuditQuerySet)):
    pass
