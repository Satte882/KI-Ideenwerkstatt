from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .access import ROLES, master_for, switch_identity
from .scenarios import PACKETS, start_discovery


@login_required
def panel(request):
    master_for(request)
    active_role = next(
        (key for key, row in ROLES.items() if row[0] == request.user.username), "master"
    )
    return render(
        request,
        "solo/panel.html",
        {
            "roles": ROLES,
            "packets": PACKETS,
            "active_role": active_role,
        },
    )


@login_required
@require_POST
def switch(request):
    switch_identity(request, request.POST.get("role"))
    return redirect("solo:panel")


@login_required
@require_POST
def discovery(request, case):
    master_for(request)
    if request.user.username != ROLES["owner"][0] or case not in PACKETS:
        raise PermissionDenied
    session = start_discovery(request.user, case)
    return redirect("accelerator:autonomous_discovery_review", session_id=session.pk)
