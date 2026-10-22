from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from ki_radar.architecture.models import SolutionSelectionDecision

from .impact_reviews import REVIEW_FIELDS, impact_review_context, save_impact_review
from .initiative_models import ImprovementInitiative, InitiativeImpactReview
from .initiatives import can_edit_initiative


class ImpactReviewForm(forms.ModelForm):
    expected_revision = forms.IntegerField(widget=forms.HiddenInput)
    effect_status = forms.ChoiceField(
        choices=[("", "Noch nicht eingeordnet"), *ImprovementInitiative.Effect.choices],
        required=False,
        label="Geschäftsergebnis: Wirkungsaussage",
    )
    effect_reason = forms.CharField(
        widget=forms.Textarea,
        required=False,
        label="Begründung zum Geschäftsergebnis",
    )

    class Meta:
        model = InitiativeImpactReview
        fields = REVIEW_FIELDS

    def __init__(self, *args, initiative, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.initiative = initiative
        self.fields["selection"].queryset = SolutionSelectionDecision.objects.filter(
            process_analysis__initiative=initiative
        )
        self.fields["use_case"].queryset = initiative.use_cases.filter(is_archived=False)
        self.initial.update(
            expected_revision=initiative.revision,
            effect_status=initiative.effect_status,
            effect_reason=initiative.effect_reason,
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = (
                "form-select" if isinstance(field.widget, forms.Select) else "form-control"
            )
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs["rows"] = 3


@login_required
def impact_review_edit(request, pk):
    initiative = get_object_or_404(ImprovementInitiative, pk=pk)
    if not can_edit_initiative(request.user, initiative):
        raise PermissionDenied
    context = impact_review_context(initiative)
    form = ImpactReviewForm(
        request.POST if request.method == "POST" else None,
        initiative=initiative,
        instance=context["impact_review"],
    )
    if request.method == "POST" and form.is_valid():
        try:
            save_impact_review(
                initiative=initiative,
                actor=request.user,
                expected_revision=form.cleaned_data["expected_revision"],
                data={
                    key: form.cleaned_data[key]
                    for key in (*REVIEW_FIELDS, "effect_status", "effect_reason")
                },
                finalize=request.POST.get("action") == "review",
            )
        except ValidationError as exc:
            # Keep all user input on failed explicit review commands.
            form.add_error(None, ValidationError(exc.messages))
        else:
            messages.success(
                request, "Aktueller Wirkungsstand gespeichert; keine Pilot-/Betriebsfreigabe."
            )
            return redirect(initiative)
    return render(
        request,
        "use_cases/impact_review_form.html",
        {
            "form": form,
            "initiative": initiative,
            **context,
        },
    )
