from django import template

from ki_radar.use_cases.context_adoption import OUTCOME_LABELS

register = template.Library()


@register.filter
def context_field_label(item):
    label = item.get("label", item["field"])
    return OUTCOME_LABELS.get(item["field"], label) if label == item["field"] else label
