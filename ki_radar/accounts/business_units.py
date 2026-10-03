from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import BusinessUnit


def active_productive_business_units() -> QuerySet[BusinessUnit]:
    return BusinessUnit.objects.filter(
        is_active=True,
        catalog_scope=BusinessUnit.CatalogScope.PRODUCTIVE,
    ).order_by("name")


def selectable_business_units(*, current_id=None) -> QuerySet[BusinessUnit]:
    query = Q(
        is_active=True,
        catalog_scope=BusinessUnit.CatalogScope.PRODUCTIVE,
    )
    if current_id:
        query |= Q(pk=current_id)
    return BusinessUnit.objects.filter(query).distinct().order_by("name")


def active_productive_business_unit(*, pk) -> BusinessUnit | None:
    try:
        return active_productive_business_units().filter(pk=pk).first()
    except (TypeError, ValueError):
        return None


def is_active_productive_business_unit(unit: BusinessUnit | None) -> bool:
    return bool(
        unit is not None
        and unit.is_active
        and unit.catalog_scope == BusinessUnit.CatalogScope.PRODUCTIVE
    )
