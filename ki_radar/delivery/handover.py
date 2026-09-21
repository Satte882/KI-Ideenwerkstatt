from __future__ import annotations

from .models import DeliveryPackage
from .services import current_handed_over_package as current_handed_over_package


def recorded_handover_package(use_case) -> DeliveryPackage | None:
    """Return the current package once the handover milestone was persisted.

    This is the Delivery-owned historical handover fact used by lifecycle enforcement.
    Later readiness findings may make the current package inconsistent, but they do not erase
    an already recorded handover. A recorded handover therefore requires both the
    ``HANDED_OVER`` status and its timestamp.
    """

    package = use_case.delivery_packages.order_by("-version", "-created_at").first()
    if (
        package is not None
        and package.status == DeliveryPackage.Status.HANDED_OVER
        and package.handed_over_at is not None
    ):
        return package
    return None
