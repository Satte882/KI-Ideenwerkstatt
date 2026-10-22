from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from .initiative_models import ImprovementInitiative
from .initiatives import EDITABLE_FIELDS, can_edit_initiative, save_initiative


class InitiativeForm(forms.ModelForm):
    expected_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = ImprovementInitiative
        fields = EDITABLE_FIELDS
        widgets = {
            "next_review_date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            )
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-check-input"
                if isinstance(field.widget, forms.CheckboxInput)
                else "form-control"
            )
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3
        if self.instance.pk:
            self.initial["expected_revision"] = self.instance.revision


@login_required
def initiative_edit(request, pk=None):
    initiative = get_object_or_404(ImprovementInitiative, pk=pk) if pk else None
    can_edit = can_edit_initiative(request.user, initiative)
    if (request.method == "POST" or initiative is None) and not can_edit:
        raise PermissionDenied
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and data.get("action") == "save_draft":
        data["status"] = ImprovementInitiative.Status.DRAFT
    form = InitiativeForm(data, instance=initiative)
    if request.method == "POST" and form.is_valid():
        try:
            saved = save_initiative(
                actor=request.user,
                initiative=initiative,
                data={key: form.cleaned_data[key] for key in EDITABLE_FIELDS},
                expected_revision=form.cleaned_data["expected_revision"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, "Vorhaben gespeichert.")
            return redirect(saved)
    return render(
        request,
        "use_cases/initiative_form.html",
        {
            "form": form,
            "initiative": initiative,
            "can_edit": can_edit,
            "history": initiative.history.all() if initiative else [],
        },
    )
