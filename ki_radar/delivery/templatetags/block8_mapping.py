from django import template

from ki_radar.delivery.mapping_presentation import build_delivery_mapping_status

register = template.Library()


@register.simple_tag
def block8_mapping_status(package, user=None):
    return build_delivery_mapping_status(package, user=user)
