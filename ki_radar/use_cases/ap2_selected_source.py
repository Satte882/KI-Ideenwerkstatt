"""Keep later AP2 drafts bound to the current human selection."""

from django.core.exceptions import ValidationError

from .services import create_use_case_from_selected_solution


def require_current_selected_use_case(*, use_case, actor) -> None:
    origin = use_case.architecture_origin
    process = origin.process_analysis
    decision = process.solution_selection_decisions.order_by("-decided_at").first()
    if decision is None or decision.selected_option_id != origin.solution_option_id:
        raise ValidationError("Der Use Case gehört nicht zur aktuellen menschlichen Lösungswahl.")
    result = create_use_case_from_selected_solution(decision=decision, actor=actor)
    if result.use_case.pk != use_case.pk:
        raise ValidationError("Die aktuelle Lösungswahl verweist auf einen anderen Use Case.")
