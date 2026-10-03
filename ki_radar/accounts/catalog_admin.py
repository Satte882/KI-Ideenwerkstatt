from .business_units import selectable_business_units


class BusinessUnitAssignmentAdminMixin:
    """Apply the catalog contract to admin assignment forms, preserving history."""

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if "business_unit" in form.base_fields:
            form.base_fields["business_unit"].queryset = selectable_business_units(
                current_id=obj.business_unit_id if obj else None
            )
        return form
