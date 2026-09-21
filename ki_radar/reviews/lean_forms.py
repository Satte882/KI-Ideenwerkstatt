from django import forms
from django.utils import timezone

from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_confirm_go_live_exception
from ki_radar.use_cases.scale_readiness import (
    evaluate_scale_readiness,
    scale_evidence_from_mapping,
)

from .forms import ReviewForm as LegacyReviewForm
from .models import Review


class ReviewForm(LegacyReviewForm):
    """UI validation aligned with the lean transition policy.

    Domain enforcement remains in ``use_cases.transition_policy``. This form only blocks
    malformed command shapes, invalid dates and the explicit failed-pilot Go-live exception.
    Readiness findings stay visible through ``scale_readiness_result`` without becoming form
    errors.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "decision" in self.fields:
            self.fields["decision"].choices = [
                choice
                for choice in self.fields["decision"].choices
                if str(choice[0]) != Review.Decision.RETURN
            ]
        if "rationale" in self.fields:
            self.fields["rationale"].required = False

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.add("rationale")
        return exclude

    def clean(self):
        # Deliberately bypass the legacy ReviewForm.clean(), which encoded the former
        # documentation-heavy hard gates. Field-level Django validation has already run.
        cleaned = forms.ModelForm.clean(self)

        if self.pilot_start_only:
            cleaned["decision"] = Review.Decision.START_PILOT
            cleaned["new_status"] = UseCase.Status.PILOT
            cleaned["go_live_exception_confirmed"] = False

        decision = cleaned.get("decision")
        new_status = cleaned.get("new_status")
        expected = {
            Review.Decision.START_REVIEW: UseCase.Status.REVIEW,
            Review.Decision.START_PILOT: UseCase.Status.PILOT,
            Review.Decision.GO_LIVE: UseCase.Status.OPERATION,
            Review.Decision.END: UseCase.Status.ENDED,
        }.get(decision)
        if expected and new_status != expected:
            self.add_error(
                "new_status",
                f"Diese Entscheidung erfordert den Status {UseCase.Status(expected).label}.",
            )

        if decision == Review.Decision.RETURN:
            self.add_error(
                "decision",
                "Lifecycle-Rückstufungen sind nicht mehr vorgesehen; bitte Rework verwenden.",
            )

        if (
            decision in {Review.Decision.PAUSE, Review.Decision.REWORK, Review.Decision.CONTINUE}
            and new_status != self.use_case.status
        ):
            self.add_error(
                "new_status",
                "Fortführen, Pausieren und Überarbeiten ändern den Lifecycle-Status nicht.",
            )

        if decision == Review.Decision.START_PILOT:
            pilot_start = cleaned.get("pilot_start")
            if pilot_start is None:
                self.add_error("pilot_start", "Der tatsächliche Pilotbeginn ist erforderlich.")
            elif pilot_start > timezone.localdate():
                self.add_error(
                    "pilot_start",
                    "Der tatsächliche Pilotbeginn darf nicht in der Zukunft liegen.",
                )
        else:
            cleaned["pilot_start"] = None

        scale_evidence = scale_evidence_from_mapping(cleaned)
        if self.use_case.status == UseCase.Status.PILOT and decision in {
            Review.Decision.GO_LIVE,
            Review.Decision.CONTINUE,
            Review.Decision.REWORK,
            Review.Decision.END,
        }:
            self.scale_readiness_result = evaluate_scale_readiness(self.use_case, scale_evidence)

        ml_score_date = cleaned.get("ml_score_date")
        if ml_score_date and ml_score_date > timezone.localdate():
            self.add_error(
                "ml_score_date",
                "Das Datum der ML-Test-Score-Erhebung darf nicht in der Zukunft liegen.",
            )

        exception_required = (
            decision == Review.Decision.GO_LIVE
            and self.use_case.metric_result == UseCase.MetricResult.NOT_ACHIEVED
        )
        if exception_required and not can_confirm_go_live_exception(self.actor):
            self.add_error(
                "go_live_exception_confirmed",
                "Nur ein KI-Koordinator darf die erforderliche Go-live-Ausnahme bestätigen.",
            )
        elif exception_required and not cleaned.get("go_live_exception_confirmed"):
            self.add_error(
                "go_live_exception_confirmed",
                "Die Ausnahme muss bei verfehltem Pilotziel ausdrücklich bestätigt werden.",
            )
        if not exception_required:
            cleaned["go_live_exception_confirmed"] = False

        # An early Go-live is no longer a separate hard gate. Keep submitted legacy evidence
        # for transparency, but do not require confirmation or additional text fields.
        if cleaned.get("early_go_live_exception_confirmed"):
            cleaned["early_go_live_original_pilot_end"] = self.use_case.planned_pilot_end

        return cleaned
