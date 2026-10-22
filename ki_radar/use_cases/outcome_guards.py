"""Protect server-owned outcome contracts on ORM/admin compatibility paths."""

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver


class OutcomeQuerySet(models.QuerySet):
    def bulk_update(self, objs, fields, batch_size=None):
        if set(fields) & {"outcome_contract_version", "decision_status"}:
            raise ValidationError("Serververwaltete Entscheidungsfelder benötigen den Service.")
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        if kwargs.get("update_conflicts") or any(
            obj.outcome_contract_version
            and getattr(obj, "decision_status", "") in {"approved", "approved_with_conditions"}
            for obj in objs
        ):
            raise ValidationError(
                "Positive Freigaben benötigen den zentralen Entscheidungsservice."
            )
        return super().bulk_create(objs, **kwargs)

    def update(self, **kwargs):
        if "outcome_snapshot" in kwargs:
            raise ValidationError("Outcome-Snapshots sind unveränderlich.")
        if (
            "outcome_contract_version" in kwargs
            and self.filter(outcome_contract_version__gte=1).exists()
        ):
            raise ValidationError("Eine aktive Outcome-Kohorte darf nicht zurückgesetzt werden.")
        if (
            kwargs.get("decision_status") in {"approved", "approved_with_conditions"}
            and self.filter(
                outcome_contract_version__gte=1,
            ).exists()
        ):
            raise ValidationError(
                "Positive Freigaben benötigen den zentralen Entscheidungsservice."
            )
        return super().update(**kwargs)


class OutcomeManager(models.Manager.from_queryset(OutcomeQuerySet)):
    pass


class ApprovalQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if "outcome_snapshot" in kwargs:
            raise ValidationError("Outcome-Snapshots sind unveränderlich.")
        if (
            set(kwargs)
            & {
                "decision_status",
                "finalized_at",
                "use_case",
                "decided_by",
                "rationale",
                "assessment",
                "conditions",
                "condition_owner",
            }
            and self.filter(
                use_case__outcome_contract_version__gte=1,
            ).exists()
        ):
            raise ValidationError("Neue Freigaben benötigen den zentralen Entscheidungsservice.")
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Freigaben benötigen den zentralen Entscheidungsservice.")


class ApprovalManager(models.Manager.from_queryset(ApprovalQuerySet)):
    pass


class OptionQuerySet(models.QuerySet):
    def bulk_update(self, objs, fields, batch_size=None):
        if "recommendation" in fields:
            raise ValidationError(
                "Bindende Lösungswahl nur über den zentralen Entscheidungsservice."
            )
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def update(self, **kwargs):
        if (
            kwargs.get("recommendation") == "preferred"
            and self.filter(
                process_analysis__outcome_contract_version__gte=1,
            ).exists()
        ):
            raise ValidationError(
                "Bindende Lösungswahl nur über den zentralen Entscheidungsservice."
            )
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        if kwargs.get("update_conflicts") or any(
            obj.recommendation == "preferred" and obj.process_analysis.outcome_contract_version
            for obj in objs
        ):
            raise ValidationError(
                "Bindende Lösungswahl nur über den zentralen Entscheidungsservice."
            )
        return super().bulk_create(objs, **kwargs)


class OptionManager(models.Manager.from_queryset(OptionQuerySet)):
    pass


def protect_cohort(instance):
    previous = (
        type(instance)
        .objects.filter(pk=instance.pk)
        .values_list(
            "outcome_contract_version",
            flat=True,
        )
        .first()
    )
    if previous and previous != instance.outcome_contract_version:
        raise ValidationError(
            "Die serververwaltete Outcome-Kohorte darf nicht zurückgesetzt werden."
        )


@receiver(pre_delete, sender="use_cases.ApprovalDecision")
def protect_outcome_snapshot_deletion(sender, instance, **kwargs):
    if instance.outcome_snapshot:
        raise ValidationError(
            "Dokumentierte Outcome-Entscheidungsstände dürfen nicht gelöscht werden."
        )
