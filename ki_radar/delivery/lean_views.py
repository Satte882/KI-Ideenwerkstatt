from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from ki_radar.accounts.permissions import is_business_owner, is_coordinator

from .lean_services import hand_over_package, mark_package_ready
from .models import DeliveryPackage


def _can_transition(user, package: DeliveryPackage) -> bool:
    return bool(
        user
        and user.is_authenticated
        and (
            is_coordinator(user)
            or (is_business_owner(user) and package.use_case.business_owner_id == user.id)
        )
    )


def _package(pk):
    return get_object_or_404(
        DeliveryPackage.objects.select_related(
            "use_case__business_owner",
            "technical_owner",
        ).prefetch_related("section_reviews"),
        pk=pk,
    )


@login_required
@require_POST
def package_mark_ready(request, pk):
    package = _package(pk)
    if not _can_transition(request.user, package):
        raise PermissionDenied
    try:
        mark_package_ready(package)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if exc.messages else str(exc))
    else:
        messages.success(
            request,
            "Delivery Package wurde als bereit markiert. "
            "Offene Readiness-Hinweise bleiben sichtbar.",
        )
    return redirect(package)


@login_required
@require_POST
def package_handover(request, pk):
    package = _package(pk)
    if not _can_transition(request.user, package):
        raise PermissionDenied
    try:
        hand_over_package(package, request.user)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages) if exc.messages else str(exc))
    else:
        messages.success(
            request,
            "Delivery Package wurde verbindlich übergeben. "
            "Offene Readiness-Hinweise bleiben nachvollziehbar.",
        )
    return redirect(package)
