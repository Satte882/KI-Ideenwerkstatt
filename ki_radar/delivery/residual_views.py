from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .models import DeliveryPackage
from .permissions import can_edit_package
from .residual_text import ResidualTextError, refine_delivery_residual_text


@login_required
@require_POST
def refine_mapping_text(request, pk, target_field):
    package = get_object_or_404(
        DeliveryPackage.objects.select_related(
            "use_case",
            "generated_from_decision",
            "architecture_artifacts",
        ).prefetch_related("section_reviews"),
        pk=pk,
    )
    if not can_edit_package(request.user, package):
        raise PermissionDenied

    try:
        result = refine_delivery_residual_text(
            package=package,
            target_field=target_field,
            actor=request.user,
        )
    except ResidualTextError as exc:
        messages.error(request, str(exc))
    else:
        if result.cached:
            messages.info(
                request,
                "Der bereits validierte Resttext wurde unverändert wiederverwendet.",
            )
        else:
            messages.success(request, "Der bestätigte Quelleninhalt wurde sprachlich verdichtet.")
    return redirect(f"{package.get_absolute_url()}#block8-mapping-status")
