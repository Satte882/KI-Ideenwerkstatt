from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse

from .initiatives import can_edit_initiative
from .permissions import can_create_idea, can_create_use_case
from .topic_contract import OCCASIONS, PERSPECTIVES
from .topics import save_topic, saved_topic, topic_token


class TopicForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput, max_length=1000)
    text = forms.CharField(
        max_length=4000,
        strip=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
    )
    title = forms.CharField(
        label="Kurztitel (optional)",
        max_length=200,
        required=False,
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Wird aus deinem Satz vorgeschlagen"}
        ),
    )
    perspectives = forms.MultipleChoiceField(
        label="Wen betrifft es? (optional)",
        choices=PERSPECTIVES,
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def clean_text(self):
        text = self.cleaned_data["text"]
        if not text.strip():
            raise forms.ValidationError("Bitte beschreibe dein Anliegen in einem kurzen Satz.")
        return text


@login_required
def topic_start(request, occasion=None):
    if not can_create_idea(request.user):
        raise PermissionDenied
    if occasion is None:
        return render(
            request,
            "use_cases/topics/choose.html",
            {
                "occasions": [(key, *value) for key, value in OCCASIONS.items()],
                "can_direct_intake": can_create_use_case(request.user),
            },
        )
    if occasion not in OCCASIONS:
        raise Http404
    if request.method == "GET" and not request.GET.get("draft"):
        query = urlencode({"draft": topic_token(actor=request.user, occasion=occasion)})
        return redirect(reverse("use_cases:topic_capture", args=[occasion]) + "?" + query)
    if request.method == "GET":
        try:
            saved = saved_topic(actor=request.user, token=request.GET["draft"], occasion=occasion)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
            return redirect("use_cases:topic_capture", occasion=occasion)
        if saved is not None:
            return redirect(saved)
    label, question, example = OCCASIONS[occasion]
    can_submit = occasion != "goal" or can_edit_initiative(request.user)
    form = TopicForm(
        request.POST if request.method == "POST" else None,
        initial={"token": request.GET.get("draft", "")},
    )
    form.fields["text"].label = question
    form.fields["text"].widget.attrs["placeholder"] = example
    if request.method == "POST" and form.is_valid():
        if not can_submit:
            form.add_error(
                None,
                "Ein Zielvorhaben kann ein Business Owner oder die KI-Koordination speichern. "
                "Bitte gemeinsam mit einer berechtigten Person fortfahren.",
            )
        else:
            try:
                idea = save_topic(actor=request.user, occasion=occasion, **form.cleaned_data)
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                messages.success(
                    request, "Dein Thema ist gespeichert. Es wurde noch keine Analyse gestartet."
                )
                return redirect(idea)
    return render(
        request,
        "use_cases/topics/form.html",
        {
            "form": form,
            "occasion_label": label,
            "example": example,
            "can_submit": can_submit,
        },
    )
