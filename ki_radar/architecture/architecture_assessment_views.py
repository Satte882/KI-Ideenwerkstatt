from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from .architecture_assessment import save_solution_architecture_assessment
from .architecture_assessment_forms import SolutionArchitectureAssessmentForm
from .models import SolutionOption
from .permissions import can_edit_value_stream


@login_required
@require_POST
def solution_architecture_assessment_update(request, pk):
    option = get_object_or_404(
        SolutionOption.objects.select_related("process_analysis__stage__value_stream"),
        pk=pk,
    )
    if not can_edit_value_stream(request.user, option.process_analysis.stage.value_stream):
        raise PermissionDenied

    form = SolutionArchitectureAssessmentForm(request.POST)
    target = reverse("architecture:solution_option_update", kwargs={"pk": option.pk})
    target = f"{target}#architecture-assessment"
    if not form.is_valid():
        messages.error(request, "Bitte alle vier Architekturfragen beantworten.")
        return redirect(target)

    save_solution_architecture_assessment(
        solution_option=option,
        answers=form.cleaned_data,
        actor=request.user,
    )
    messages.success(request, "Architektur-Einschätzung wurde gespeichert.")
    return redirect(target)
