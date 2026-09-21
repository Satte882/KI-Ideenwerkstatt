from __future__ import annotations

from datetime import date

from django import template
from django.utils import timezone

from ki_radar.core.navigation import with_return_to
from ki_radar.delivery.actions import primary_delivery_action

register = template.Library()


def _action_priority(use_case, action, user) -> int:
    if action.key == "delivery":
        package = use_case.delivery_packages.first()
        if package is not None:
            primary = primary_delivery_action(package, user)
            if primary is not None:
                return primary.priority_class
        return 5
    if action.key == "use_case":
        return 3
    if action.key == "assessment":
        return 2
    if action.key == "approval":
        return 4
    if action.key == "pilot_start":
        return 5
    return 5


@register.simple_tag(takes_context=True)
def worklist_rows(context, items):
    request = context["request"]
    today = timezone.localdate()
    return_to = request.get_full_path()
    rows = []
    for use_case in items:
        action = use_case.journey.next_action
        if action is None or not action.url:
            continue
        due = use_case.decision_due
        priority_class = _action_priority(use_case, action, request.user)
        rows.append(
            {
                "use_case": use_case,
                "action": action,
                "action_url": with_return_to(action.url, return_to),
                "priority_class": priority_class,
                "due": due,
                "overdue": bool(due and due < today),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["priority_class"],
            0 if row["overdue"] else 1,
            row["due"] or date.max,
            row["use_case"].short_id,
        ),
    )
