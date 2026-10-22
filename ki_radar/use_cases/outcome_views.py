"""Explicit outcome preparation, separate from intake and binding option/approval commands."""

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from ki_radar.accounts.permissions import is_coordinator
from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.permissions import can_edit_value_stream
from ki_radar.architecture.stage_focus import get_stage_focus_decision, save_stage_focus_decision

from .initiative_models import ImprovementInitiative
from .initiative_views import InitiativeForm
from .initiatives import bind_initiative, save_initiative
from .models import UseCase
from .outcome_contract import _process, confirm_initiative, set_discovery_path
from .permissions import can_edit_use_case


class OutcomePreparationForm(InitiativeForm):
    class Meta(InitiativeForm.Meta):
        fields = (
            "title",
            "business_outcome",
            "contribution",
            "impact_hypothesis",
            "evaluation_criteria",
            "outcome_owner",
            "target_group",
            "evidence_level",
            "evidence_note",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["selected_initiative", *self.Meta.fields])

    adopt_contract = forms.BooleanField(
        required=False,
        label="Historisches Objekt ausdrücklich in den neuen Outcome-Vertrag übernehmen",
    )
    selected_initiative = forms.ModelChoiceField(
        queryset=ImprovementInitiative.objects.all(),
        required=False,
        label="Vorhandenes Vorhaben laden (optional)",
    )
    confirmation_reason = forms.CharField(
        required=False, label="Fachliche Annahme begründen", widget=forms.Textarea
    )
    focus_reason = forms.CharField(
        required=False, label="Fokus auf diese Prozessphase begründen", widget=forms.Textarea
    )
    path = forms.ChoiceField(
        required=False,
        label="Fachlicher Discovery-Pfad",
        choices=[
            ("", "Noch offen"),
            ("problem", "Problemgetrieben"),
            ("strategic", "Strategisches Potenzial"),
        ],
    )
    origin_basis = forms.CharField(
        required=False, label="Dokumentierte Herkunft / Ausgangslage", widget=forms.Textarea
    )
    change_reason = forms.CharField(
        required=False, label="Grund eines Pfadwechsels", widget=forms.Textarea
    )
    strategic_potential = forms.CharField(
        required=False, label="Begründetes strategisches Potenzial", widget=forms.Textarea
    )
    validation_step = forms.CharField(
        required=False, label="Prüfbarer Validierungsschritt", widget=forms.Textarea
    )
    correction_reason = forms.CharField(
        required=False, label="Nur bei Schreibkorrektur: Begründung"
    )


@transaction.atomic
def _prepare(*, artifact, form, actor, confirm):
    existing = form.cleaned_data["selected_initiative"]
    if artifact.initiative_id and existing and artifact.initiative_id != existing.pk:
        raise ValidationError("Das Objekt ist bereits einem anderen Vorhaben zugeordnet.")
    initiative = save_initiative(
        actor=actor,
        initiative=existing,
        data={key: form.cleaned_data[key] for key in form.Meta.fields},
        expected_revision=form.cleaned_data.get("expected_revision") if existing else None,
        correction_reason=form.cleaned_data["correction_reason"],
    )
    if not confirm:
        return initiative
    if form.cleaned_data["adopt_contract"] and not artifact.outcome_contract_version:
        artifact.outcome_contract_version = 1
        artifact.save(update_fields=["outcome_contract_version", "updated_at"])
    process = _process(artifact)
    if process is not None:
        set_discovery_path(
            process=process,
            actor=actor,
            path=form.cleaned_data["path"],
            origin_basis=form.cleaned_data["origin_basis"],
            change_reason=form.cleaned_data["change_reason"],
            strategic_potential=form.cleaned_data["strategic_potential"],
            validation_step=form.cleaned_data["validation_step"],
        )
        bind_initiative(initiative=initiative, artifact=process, actor=actor)
        reason = form.cleaned_data["focus_reason"].strip()
        focus = get_stage_focus_decision(process.stage.value_stream, initiative=initiative)
        if (
            focus is None
            or focus.selected_stage_id != process.stage_id
            or (reason and reason != focus.rationale)
        ):
            save_stage_focus_decision(
                initiative=initiative,
                value_stream=process.stage.value_stream,
                selected_stage=process.stage,
                actor=actor,
                criteria_snapshot={},
                rationale=reason,
                is_short_path=True,
                short_path_reason=reason,
            )
    if artifact._meta.model_name != "processanalysis":
        bind_initiative(initiative=initiative, artifact=artifact, actor=actor)
    initiative.refresh_from_db()
    return confirm_initiative(
        initiative=initiative,
        actor=actor,
        rationale=form.cleaned_data["confirmation_reason"],
        expected_revision=initiative.revision,
    )


@login_required
def prepare_outcome(request, kind, pk):
    if kind not in {"process", "usecase"}:
        raise Http404
    artifact = get_object_or_404(ProcessAnalysis if kind == "process" else UseCase, pk=pk)
    allowed = (
        can_edit_value_stream(request.user, artifact.stage.value_stream)
        if kind == "process"
        else can_edit_use_case(request.user, artifact)
    )
    if not allowed:
        raise PermissionDenied
    selected = (
        request.POST.get("selected_initiative")
        if request.method == "POST"
        else request.GET.get("initiative")
    )
    initiative = artifact.initiative
    if selected:
        try:
            initiative = ImprovementInitiative.objects.filter(pk=selected).first()
        except (ValueError, ValidationError):
            initiative = None
        if initiative is None and request.method != "POST":
            raise Http404
    if request.method == "POST" and request.POST.get("action") == "load" and initiative:
        return redirect(f"{request.path}?initiative={initiative.pk}")
    process = _process(artifact)
    path = process.discovery_path_decisions.first() if process else None
    initial = {"selected_initiative": initiative.pk if initiative else None}
    if path:
        initial.update(
            {
                name: getattr(path, name)
                for name in (
                    "path",
                    "origin_basis",
                    "strategic_potential",
                    "validation_step",
                )
            }
        )
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and request.POST.get("action") == "save_draft":
        data["status"] = "draft"
    form = OutcomePreparationForm(data, instance=initiative, initial=initial)
    if artifact.outcome_contract_version:
        form.fields["adopt_contract"].widget = forms.HiddenInput()
    if process is None:
        for name in (
            "path",
            "origin_basis",
            "change_reason",
            "strategic_potential",
            "validation_step",
            "focus_reason",
        ):
            form.fields[name].widget = forms.HiddenInput()
    return_url = (
        reverse("architecture:solution_option_compare", args=[artifact.pk])
        if kind == "process"
        else reverse("use_cases:approval_decision_create", args=[artifact.pk])
        if is_coordinator(request.user)
        else artifact.get_absolute_url()
    )
    if request.method == "POST" and form.is_valid():
        try:
            saved = _prepare(
                artifact=artifact,
                form=form,
                actor=request.user,
                confirm=request.POST.get("action") == "confirm",
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            if request.POST.get("action") == "confirm":
                return redirect(return_url)
            return redirect(f"{request.path}?initiative={saved.pk}")
    return render(
        request,
        "use_cases/outcome_prepare.html",
        {
            "form": form,
            "artifact": artifact,
            "return_url": return_url,
            "is_process": process is not None,
        },
    )
