from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models, transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from ki_radar.core.models import TimeStampedModel
from ki_radar.core.taxonomy import ScreeningLevel

from .audit import ImmutableDecisionManager

CRITERIA_KEYS = (
    "impact",
    "pain_intensity",
    "improvement_potential",
    "data_accessibility",
    "change_effort",
    "time_to_value",
)
EVIDENCE_BASIS_KEY = "evidence_basis"


class StageFocusDecision(TimeStampedModel):
    value_stream = models.OneToOneField(
        "architecture.ValueStream",
        on_delete=models.CASCADE,
        related_name="stage_focus_decision",
    )
    selected_stage = models.ForeignKey(
        "architecture.ValueStreamStage",
        on_delete=models.CASCADE,
        related_name="focus_decisions",
        verbose_name="Fokusphase",
    )
    criteria_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    rationale = models.TextField(verbose_name="Begründung der Phasenauswahl")
    is_short_path = models.BooleanField(default=False, verbose_name="Bewusster Kurzpfad")
    short_path_reason = models.TextField(blank=True, verbose_name="Begründung des Kurzpfads")
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage_focus_decisions",
    )

    class Meta:
        ordering = ["value_stream__business_unit__name", "value_stream__name"]

    def clean(self):
        errors = {}
        if (
            self.selected_stage_id
            and self.value_stream_id
            and self.selected_stage.value_stream_id != self.value_stream_id
        ):
            errors["selected_stage"] = "Die Fokusphase gehört nicht zu diesem Value Stream."
        if not self.rationale.strip():
            errors["rationale"] = "Die Auswahl der Fokusphase muss begründet werden."
        if self.is_short_path and not self.short_path_reason.strip():
            errors["short_path_reason"] = "Der bewusste Kurzpfad muss begründet werden."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def criteria_for(self, stage) -> dict:
        return self.criteria_snapshot.get(str(stage.pk), {})

    def __str__(self) -> str:
        return f"{self.value_stream}: {self.selected_stage}"


class InitiativeStageFocusDecision(TimeStampedModel):
    """Append-only focus history, isolated from the global legacy projection."""

    initiative = models.ForeignKey(
        "use_cases.ImprovementInitiative",
        on_delete=models.PROTECT,
        related_name="stage_focus_decisions",
    )
    value_stream = models.ForeignKey(
        "architecture.ValueStream",
        on_delete=models.PROTECT,
        related_name="initiative_focus_decisions",
    )
    selected_stage = models.ForeignKey(
        "architecture.ValueStreamStage",
        on_delete=models.PROTECT,
        related_name="initiative_focus_decisions",
    )
    revision = models.PositiveIntegerField()
    criteria_snapshot = models.JSONField(default=dict, blank=True, editable=False)
    rationale = models.TextField()
    is_short_path = models.BooleanField(default=False)
    short_path_reason = models.TextField(blank=True)
    selected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="initiative_stage_focus_decisions",
    )
    objects = ImmutableDecisionManager()

    class Meta:
        ordering = ["-revision", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["initiative", "value_stream", "revision"],
                name="unique_initiative_stream_focus_revision",
            )
        ]

    def clean(self):
        StageFocusDecision.clean(self)

    def criteria_for(self, stage) -> dict:
        return self.criteria_snapshot.get(str(stage.pk), {})

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError("Eine dokumentierte Fokusentscheidung ist unveränderlich.")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Eine dokumentierte Fokusentscheidung darf nicht gelöscht werden.")


@transaction.atomic
def save_stage_focus_decision(
    *,
    value_stream,
    selected_stage,
    criteria_snapshot: dict,
    rationale: str,
    actor,
    is_short_path: bool = False,
    short_path_reason: str = "",
    initiative=None,
) -> StageFocusDecision | InitiativeStageFocusDecision:
    """Persist a focus decision through one domain-level invariant boundary."""
    from .models import EvidenceBasis, TimeToValue
    from .permissions import can_edit_value_stream

    if not can_edit_value_stream(actor, value_stream):
        raise ValidationError("Für die Fokusentscheidung fehlt die Berechtigung.")
    if selected_stage.value_stream_id != value_stream.pk:
        raise ValidationError(
            {"selected_stage": "Die Fokusphase gehört nicht zu diesem Value Stream."}
        )

    rationale_text = str(rationale or "").strip()
    if not rationale_text:
        raise ValidationError({"rationale": "Die Auswahl der Fokusphase muss begründet werden."})

    short_reason = str(short_path_reason or "").strip()
    if is_short_path:
        if not short_reason:
            raise ValidationError(
                {"short_path_reason": "Der bewusste Kurzpfad muss begründet werden."}
            )
    else:
        allowed_levels = set(ScreeningLevel.values)
        allowed_time_to_value = {
            TimeToValue.UNKNOWN,
            TimeToValue.SHORT,
            TimeToValue.MEDIUM,
            TimeToValue.LONG,
        }
        allowed_evidence_basis = set(EvidenceBasis.values)
        errors: dict[str, str] = {}
        for stage in value_stream.stages.all():
            row = criteria_snapshot.get(str(stage.pk))
            if not isinstance(row, dict):
                errors[str(stage.pk)] = (
                    f"Für die Phase „{stage.name}“ fehlt die vollständige Kriterienbewertung."
                )
                continue

            for criterion in CRITERIA_KEYS:
                value = str(row.get(criterion) or "").strip()
                if not value:
                    errors[f"{stage.pk}:{criterion}"] = (
                        f"Für „{stage.name}“ fehlt die Einordnung {criterion}."
                    )
                    continue
                if criterion == "time_to_value":
                    if value not in allowed_time_to_value:
                        errors[f"{stage.pk}:{criterion}"] = (
                            f"Ungültige Time-to-Value-Einordnung für „{stage.name}“."
                        )
                elif value not in allowed_levels:
                    errors[f"{stage.pk}:{criterion}"] = (
                        f"Ungültige Screening-Einordnung für „{stage.name}“."
                    )

            evidence_basis = str(row.get(EVIDENCE_BASIS_KEY) or "").strip()
            if evidence_basis not in allowed_evidence_basis:
                errors[f"{stage.pk}:{EVIDENCE_BASIS_KEY}"] = (
                    f"Ungültige Evidenzbasis für „{stage.name}“."
                )

        if errors:
            raise ValidationError(errors)

    defaults = {
        "selected_stage": selected_stage,
        "criteria_snapshot": criteria_snapshot,
        "rationale": rationale_text,
        "is_short_path": is_short_path,
        "short_path_reason": short_reason,
        "selected_by": actor,
    }
    if initiative is not None:
        from ki_radar.use_cases.initiative_models import ImprovementInitiative
        from ki_radar.use_cases.initiatives import can_edit_initiative

        initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
        if not can_edit_initiative(actor, initiative):
            raise ValidationError("Für die Vorhabensentscheidung fehlt die Berechtigung.")
        previous = get_stage_focus_decision(value_stream, initiative=initiative)
        if previous and all(
            getattr(previous, key) == value
            for key, value in defaults.items()
            if key != "selected_by"
        ):
            return previous
        return InitiativeStageFocusDecision.objects.create(
            initiative=initiative,
            value_stream=value_stream,
            revision=previous.revision + 1 if previous else 1,
            **defaults,
        )
    decision, _created = StageFocusDecision.objects.update_or_create(
        value_stream=value_stream,
        defaults=defaults,
    )
    return decision


def get_stage_focus_decision(value_stream, *, initiative=None):
    if initiative is not None:
        return InitiativeStageFocusDecision.objects.filter(
            initiative=initiative,
            value_stream=value_stream,
        ).first()
    try:
        return value_stream.stage_focus_decision
    except ObjectDoesNotExist:
        return None


def stage_is_selected(stage, *, initiative=None) -> bool:
    decision = get_stage_focus_decision(stage.value_stream, initiative=initiative)
    return bool(decision and decision.selected_stage_id == stage.pk)


def _legacy_snapshot(stage) -> dict:
    return {
        str(stage.pk): {
            "sequence": stage.sequence,
            "name": stage.name,
            "impact": "",
            "pain_intensity": "",
            "improvement_potential": "",
            "data_accessibility": "",
            "change_effort": "",
            "time_to_value": "not_assessed",
            "evidence_basis": "hypothesis",
            "indicators": {
                "pain_points": stage.pain_points,
                "baseline_metrics": stage.baseline_metrics,
            },
        }
    }


def ensure_single_stage_focus(*, stage, actor=None) -> bool:
    if get_stage_focus_decision(stage.value_stream) is not None:
        return True
    if stage.value_stream.stages.count() != 1:
        return False
    StageFocusDecision.objects.create(
        value_stream=stage.value_stream,
        selected_stage=stage,
        criteria_snapshot=_legacy_snapshot(stage),
        rationale="Die einzige erfasste Phase ist zugleich die eindeutige Fokusphase.",
        is_short_path=True,
        short_path_reason=(
            "Ein-Phasen-Value-Stream: Ein Vergleich mit weiteren Phasen ist nicht möglich."
        ),
        selected_by=actor,
    )
    return True


def ensure_stage_focus_for_existing_path(*, stage, actor=None, source_label: str) -> None:
    if get_stage_focus_decision(stage.value_stream) is not None:
        return
    StageFocusDecision.objects.create(
        value_stream=stage.value_stream,
        selected_stage=stage,
        criteria_snapshot=_legacy_snapshot(stage),
        rationale=f"Fokusphase aus bereits dokumentiertem {source_label} übernommen.",
        is_short_path=True,
        short_path_reason=(
            "Bestandsübernahme: Der nachgelagerte Architekturpfad war bereits dokumentiert."
        ),
        selected_by=actor,
    )


@receiver(post_save, sender="architecture.ProcessAnalysis")
def persist_focus_from_existing_process(sender, instance, created, **kwargs):
    if created and instance.initiative_id is None and not instance.outcome_contract_version:
        ensure_stage_focus_for_existing_path(
            stage=instance.stage,
            actor=instance.analyzed_by,
            source_label="Prozess-Deep-Dive",
        )


@receiver(post_save, sender="architecture.UseCaseOrigin")
def persist_focus_from_existing_origin(sender, instance, created, **kwargs):
    if (
        created
        and instance.use_case.initiative_id is None
        and not instance.use_case.outcome_contract_version
        and (
            not instance.process_analysis_id
            or (
                instance.process_analysis.initiative_id is None
                and not instance.process_analysis.outcome_contract_version
            )
        )
    ):
        ensure_stage_focus_for_existing_path(
            stage=instance.stage,
            actor=getattr(instance.use_case, "created_by", None),
            source_label="Use-Case-Ursprung",
        )
