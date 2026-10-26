from django import template

from ki_radar.use_cases.measurement_plan import business_context, business_context_review_label

register = template.Library()


@register.simple_tag
def current_business_context(use_case):
    return business_context(use_case)


@register.simple_tag
def context_review_label(context):
    return business_context_review_label(context)
