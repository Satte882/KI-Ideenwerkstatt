import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from ki_radar.accounts.models import BusinessUnit
from ki_radar.core.models import TimeStampedModel

from .models import UseCase


class IdeaCandidate(TimeStampedModel):
    class State(models.TextChoices):
        OPEN = "open", "Offen"
        DISMISSED = "dismissed", "Nicht weiterverfolgt"
        PROMOTED = "promoted", "Übernommen"

    class Score(models.IntegerChoices):
        ONE = 1, "1"
        TWO = 2, "2"
        THREE = 3, "3"
        FOUR = 4, "4"
        FIVE = 5, "5"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    description = models.TextField()
    business_unit = models.ForeignKey(
        BusinessUnit,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="idea_candidates",
    )
    source_note = models.TextField(blank=True)
    impact = models.PositiveSmallIntegerField(
        choices=Score.choices,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    confidence = models.PositiveSmallIntegerField(
        choices=Score.choices,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    ease = models.PositiveSmallIntegerField(
        choices=Score.choices,
        null=True,
        blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Validierbarkeit",
    )
    state = models.CharField(
        max_length=20,
        choices=State.choices,
        default=State.OPEN,
        db_index=True,
    )
    decision_note = models.TextField(blank=True)
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL,
        related_name="submitted_idea_candidates",
    )
    triaged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="triaged_idea_candidates",
    )
    triaged_at = models.DateTimeField(null=True, blank=True)
    promoted_use_case = models.OneToOneField(
        UseCase,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="origin_idea_candidate",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["state", "-created_at"], name="idea_state_created_idx"),
            models.Index(fields=["business_unit", "state"], name="idea_bu_state_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(state="promoted", promoted_use_case__isnull=False)
                    | (~Q(state="promoted") & Q(promoted_use_case__isnull=True))
                ),
                name="idea_promoted_link_matches_state",
            ),
            models.CheckConstraint(
                condition=(~Q(state="dismissed") | ~Q(decision_note="")),
                name="idea_dismissed_requires_note",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self):
        return reverse("use_cases:idea_detail", kwargs={"pk": self.pk})

    def clean(self):
        super().clean()
        if self.state == self.State.DISMISSED and not self.decision_note.strip():
            raise ValidationError(
                {
                    "decision_note": (
                        "Für nicht weiterverfolgte Ideen ist eine Begründung erforderlich."
                    )
                }
            )
        if self.state == self.State.PROMOTED and self.promoted_use_case_id is None:
            raise ValidationError(
                {
                    "promoted_use_case": (
                        "Eine übernommene Idee muss mit genau einem Use Case verknüpft sein."
                    )
                }
            )
        if self.state != self.State.PROMOTED and self.promoted_use_case_id is not None:
            raise ValidationError(
                {
                    "promoted_use_case": (
                        "Nur übernommene Ideen dürfen mit einem Use Case verknüpft sein."
                    )
                }
            )

    @property
    def triage_complete(self) -> bool:
        return all(value is not None for value in (self.impact, self.confidence, self.ease))

    @property
    def quick_score(self) -> float | None:
        if not self.triage_complete:
            return None
        return round((self.impact + self.confidence + self.ease) / 3, 1)

    @property
    def age_days(self) -> int:
        if not self.created_at:
            return 0
        return max((timezone.now().date() - self.created_at.date()).days, 0)

    @property
    def is_stale(self) -> bool:
        return self.state == self.State.OPEN and self.age_days >= 30
