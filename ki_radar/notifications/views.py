from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.permissions import can_edit_use_case

from .forms import EvidenceLinkForm


@login_required
def evidence_create(request, use_case_id):
    use_case = get_object_or_404(UseCase, pk=use_case_id)
    if not can_edit_use_case(request.user, use_case):
        raise PermissionDenied
    if request.method == "POST":
        form = EvidenceLinkForm(request.POST)
        if form.is_valid():
            evidence = form.save(commit=False)
            evidence.use_case = use_case
            evidence.created_by = request.user
            evidence.save()
            messages.success(request, "Nachweislink wurde gespeichert.")
            return redirect(use_case)
    else:
        form = EvidenceLinkForm()
    return render(request, "notifications/evidence_form.html", {"form": form, "use_case": use_case})
