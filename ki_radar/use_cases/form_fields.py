from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import forms
from django.utils.formats import get_format


def format_decimal_input(value: Decimal) -> str:
    """Format a Decimal for localized form input without grouping or rounding."""

    text = format(value, "f")
    integer, separator, fraction = text.partition(".")
    if separator:
        fraction = fraction.rstrip("0")
    normalized = f"{integer}.{fraction}" if fraction else integer
    if normalized == "-0":
        normalized = "0"
    return normalized.replace(".", str(get_format("DECIMAL_SEPARATOR")))


class LocalizedDecimalInput(forms.TextInput):
    def __init__(self, attrs=None):
        default_attrs = {"inputmode": "decimal", "autocomplete": "off"}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        if value in (None, ""):
            return ""
        if isinstance(value, Decimal):
            return format_decimal_input(value)
        try:
            decimal_value = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return super().format_value(value)
        return format_decimal_input(decimal_value)


class LocalizedDecimalField(forms.DecimalField):
    widget = LocalizedDecimalInput

    def __init__(self, *args, **kwargs):
        kwargs["localize"] = True
        super().__init__(*args, **kwargs)
