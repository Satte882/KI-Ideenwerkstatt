from django.core.exceptions import ValidationError
from django.db import transaction

from .models import SolutionOption
from .permissions import can_edit_value_stream
from .retirement_models import SolutionOptionRetirement


@transaction.atomic
def retire_solution_option(*, option: SolutionOption, actor) -> SolutionOptionRetirement:
    option = (
        SolutionOption.objects.select_for_update()
        .select_related("process_analysis__stage__value_stream")
        .get(pk=option.pk)
    )
    if not can_edit_value_stream(actor, option.process_analysis.stage.value_stream):
        raise ValidationError("Für diese Lösungsoption fehlt die Bearbeitungsberechtigung.")
    if option.recommendation == SolutionOption.Recommendation.PREFERRED:
        raise ValidationError(
            "Eine bevorzugte Lösungsoption kann nicht als nicht weiterverfolgt markiert werden."
        )
    if option.selection_decisions.exists():
        raise ValidationError(
            "Eine bereits ausgewählte Lösungsoption kann nicht als nicht weiterverfolgt "
            "markiert werden."
        )
    if option.use_case_origins.exists():
        raise ValidationError(
            "Eine mit einem Use Case verknüpfte Lösungsoption kann nicht als nicht "
            "weiterverfolgt markiert werden."
        )

    retirement, created = SolutionOptionRetirement.objects.get_or_create(
        option=option,
        defaults={"retired_by": actor},
    )
    if created and option.recommendation != SolutionOption.Recommendation.REJECTED:
        option.recommendation = SolutionOption.Recommendation.REJECTED
        option.save(update_fields=["recommendation", "updated_at"])
    return retirement


def active_solution_options(process_analysis):
    return process_analysis.solution_options.filter(retirement__isnull=True)
