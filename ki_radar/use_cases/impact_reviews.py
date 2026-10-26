"""Current shared finding; UseCase metrics and transition services stay authoritative."""

from django.core.exceptions import ObjectDoesNotExist, PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .initiative_models import ImprovementInitiative, InitiativeImpactReview
from .initiatives import can_edit_initiative, save_initiative

REVIEW_FIELDS = (
    "selection",
    "use_case",
    "process_result",
    "process_measurement",
    "business_measurement",
    "business_evidence",
    "measurement_difference",
    "attribution",
    "attribution_reason",
)


@transaction.atomic
def save_impact_review(*, initiative, actor, data, expected_revision, finalize=False):
    initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative):
        raise PermissionDenied
    if expected_revision != initiative.revision:
        raise ValidationError("Das Vorhaben wurde inzwischen geändert. Bitte neu laden.")
    if set(data) - {*REVIEW_FIELDS, "effect_status", "effect_reason"}:
        raise ValidationError("Serververwaltete Review-Felder dürfen nicht geändert werden.")
    review = InitiativeImpactReview.objects.filter(initiative=initiative).first()
    review = review or InitiativeImpactReview(initiative=initiative)
    for name in REVIEW_FIELDS:
        if name in data:
            setattr(review, name, data[name])
    # Resolve authoritative references rather than trusting cached caller objects.
    if review.selection_id:
        from ki_radar.architecture.models import SolutionSelectionDecision

        review.selection = SolutionSelectionDecision.objects.select_related(
            "process_analysis", "selected_option"
        ).get(pk=review.selection_id)
    if review.use_case_id:
        from .models import UseCase

        review.use_case = UseCase.objects.select_for_update().get(pk=review.use_case_id)
    review.full_clean()
    effect_status = data.get("effect_status", initiative.effect_status)
    effect_reason = data.get("effect_reason", initiative.effect_reason)
    if finalize:
        if review.selection_id and review.selection.outcome_review_required:
            raise ValidationError(
                "Die Lösungsgrundlage wurde geändert. Bitte im Optionenvergleich neu "
                "bewerten und auswählen, danach den Wirkungsreview erneut bestätigen. "
                "Messwerte bleiben erhalten; der Review kann als Entwurf gesichert werden."
            )
        if review.use_case_id and review.use_case.outcome_contract_version:
            from .outcome_contract import _origin_blockers

            try:
                process = review.use_case.architecture_origin.process_analysis
            except ObjectDoesNotExist:
                process = None
            if process is not None and _origin_blockers(review.use_case, process):
                raise ValidationError(
                    "Die Lösungsgrundlage der KI-Prozessmetrik benötigt eine aktuelle "
                    "menschliche Auswahl im Optionenvergleich. Messwerte bleiben erhalten."
                )
        if (
            review.use_case_id
            and review.business_measurement.strip()
            and not review.measurement_difference.strip()
        ):
            raise ValidationError("Bitte die inhaltlich andere Geschäftsergebnismetrik abgrenzen.")
        if (
            review.attribution != ImprovementInitiative.Effect.UNCLEAR
            and not review.attribution_reason.strip()
        ):
            raise ValidationError("Die Attribution benötigt eine Begründung und Evidenzgrenzen.")
        if not (review.selection_id or review.use_case_id):
            raise ValidationError("Bitte die geprüfte Intervention referenzieren.")
        if not effect_status or not effect_reason.strip():
            raise ValidationError(
                "Geschäftsergebnis bitte einordnen und begründen; ungeklärt ist zulässig."
            )
        if effect_status != ImprovementInitiative.Effect.UNCLEAR and not (
            review.business_measurement.strip() and review.business_evidence.strip()
        ):
            raise ValidationError(
                "Bestätigtes/widerlegtes Geschäftsergebnis benötigt Messstand und Nachweis."
            )
        if (
            not review.use_case_id
            and review.process_result != review.ProcessResult.UNKNOWN
            and not review.process_measurement.strip()
        ):
            raise ValidationError(
                "Die Non-KI-Prozesswirkung benötigt Messdefinition, Stand und Nachweis."
            )
    # Reuse the existing effect statement and its audit; no second business-result field.
    initiative = save_initiative(
        actor=actor,
        initiative=initiative,
        expected_revision=expected_revision,
        data={"effect_status": effect_status, "effect_reason": effect_reason},
    )
    review.initiative = initiative
    review.outcome_revision = initiative.outcome_revision if finalize else None
    review.initiative_revision = initiative.revision if finalize else None
    review.metric_history_id = (
        review.use_case.history.values_list("history_id", flat=True).first()
        if finalize and review.use_case_id
        else None
    )
    review.reviewed_by = actor if finalize else None
    review.reviewed_at = timezone.now() if finalize else None
    review._history_user = actor
    review.save()
    return review


def impact_review_context(initiative):
    """No sums, no inferred business success, no copied editable metric values."""
    from ki_radar.architecture.models import SolutionSelectionDecision

    review = (
        InitiativeImpactReview.objects.filter(initiative=initiative)
        .select_related(
            "initiative", "selection__process_analysis", "selection__selected_option", "use_case"
        )
        .first()
    )
    return {
        "impact_review": review,
        "impact_selections": SolutionSelectionDecision.objects.filter(
            process_analysis__initiative=initiative
        ).select_related("selected_option", "process_analysis"),
        "impact_use_cases": initiative.use_cases.filter(is_archived=False),
    }
