"""Assignment forms for the explicit blueprint seed path, including demo data."""

from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.forms import ValueStreamForm
from ki_radar.use_cases.forms import UseCaseForm


class BlueprintValueStreamForm(ValueStreamForm):
    def __init__(self, *args, business_unit, **kwargs):
        super().__init__(*args, **kwargs)
        if business_unit.catalog_scope == BusinessUnit.CatalogScope.DEMO_TEST:
            self.fields["business_unit"].queryset = BusinessUnit.objects.filter(
                pk=business_unit.pk,
                is_active=True,
                catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
            )

    def clean_business_unit(self):
        unit = self.cleaned_data["business_unit"]
        if unit.is_active and unit.catalog_scope == BusinessUnit.CatalogScope.DEMO_TEST:
            return unit
        return super().clean_business_unit()


class BlueprintUseCaseForm(UseCaseForm):
    def __init__(self, *args, business_unit, **kwargs):
        super().__init__(*args, **kwargs)
        if business_unit.catalog_scope == BusinessUnit.CatalogScope.DEMO_TEST:
            self.fields["business_unit"].queryset = BusinessUnit.objects.filter(
                pk=business_unit.pk,
                is_active=True,
                catalog_scope=BusinessUnit.CatalogScope.DEMO_TEST,
            )
