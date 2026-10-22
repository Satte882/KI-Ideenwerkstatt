"""Optional capability validation UI, separate from business decisions and intake."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .capability_experiments import CAPABILITY_FIELDS, save_capability_experiment
from .capability_models import CapabilityExperiment
from .initiative_models import ImprovementInitiative
from .initiatives import can_edit_initiative


class CapabilityExperimentForm(forms.ModelForm):
    expected_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = CapabilityExperiment
        fields = CAPABILITY_FIELDS

    def __init__(self, *args, initiative, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.initiative = initiative
        self.fields["retest_of"].queryset = initiative.capability_experiments.filter(
            reviewed_at__isnull=False
        )
        self.fields["retest_of"].label = "Nachtest zu geprüftem Capability-Nachweis (optional)"
        if self.instance.pk:
            self.initial["expected_revision"] = self.instance.revision
        for field in self.fields.values():
            if field.widget.is_hidden:
                continue
            field.widget.attrs["class"] = (
                "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3


@login_required
def capability_experiment_edit(request, initiative_id, pk=None):
    initiative = get_object_or_404(ImprovementInitiative, pk=initiative_id)
    experiment = (
        get_object_or_404(CapabilityExperiment, pk=pk, initiative=initiative)
        if pk is not None
        else None
    )
    can_edit = can_edit_initiative(request.user, initiative)
    if (request.method == "POST" or experiment is None) and not can_edit:
        raise PermissionDenied
    if request.method == "POST" and experiment and experiment.is_reviewed:
        raise PermissionDenied

    initial = {}
    if experiment is None and request.method == "GET" and request.GET.get("retest_of"):
        previous = get_object_or_404(
            CapabilityExperiment,
            pk=request.GET["retest_of"],
            initiative=initiative,
            reviewed_at__isnull=False,
        )
        initial["retest_of"] = previous.pk

    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and request.POST.get("action") != "review":
        # A title-only draft does not need explicit evidence or a data classification.
        data.setdefault("finding", CapabilityExperiment.Finding.OPEN)
        data.setdefault("data_kind", CapabilityExperiment.DataKind.SYNTHETIC)
    form = CapabilityExperimentForm(
        data,
        initiative=initiative,
        instance=experiment,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        try:
            experiment = save_capability_experiment(
                initiative=initiative,
                actor=request.user,
                experiment=experiment,
                expected_revision=form.cleaned_data["expected_revision"],
                data={key: form.cleaned_data[key] for key in CAPABILITY_FIELDS},
                finalize=request.POST.get("action") == "review",
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request,
                "Capability-Nachweis dokumentiert - keine KI-/Betriebsfreigabe "
                "und kein nachgewiesener Geschäftsnutzen.",
            )
            return redirect(experiment.get_absolute_url())

    return render(
        request,
        "use_cases/capability_experiment_form.html",
        {
            "initiative": initiative,
            "experiment": experiment,
            "form": form,
            "can_edit": can_edit,
            "read_only": bool(experiment and experiment.is_reviewed),
        },
    )
