from django import template

from ki_radar.use_cases.measurement_plan import business_context

register = template.Library()


@register.simple_tag
def current_business_context(use_case):
    return business_context(use_case)
