from decimal import Decimal
from uuid import UUID

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Model
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ki_radar.accounts.models import BusinessUnit
from ki_radar.accounts.permissions import is_business_owner
from ki_radar.core.taxonomy import BusinessDomain

from .lean_intake import WIZARD_STEPS
from .models import UseCase
from .permissions import can_create_use_case
from .services import intake_blockers

SESSION_KEY = "use_case_intake"
IDEA_CANDIDATE_SESSION_KEY = "use_case_intake_idea_candidate"
STEP_LABELS = {
    1: "Problem",
    2: "Prozess",
    3: "Nutzung",
    4: "Nutzen",
    5: "Daten",
    6: "Vorprüfung",
}


def _serialize_cleaned_data(cleaned_data: dict) -> dict:
    serialized = {}
    for key, value in cleaned_data.items():
        if isinstance(value, Model):
            serialized[key] = str(value.pk) if isinstance(value.pk, UUID) else value.pk
        elif isinstance(value, Decimal):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


def _optional_decimal(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(value)


def _completion_field_names(form_class) -> tuple[str, ...]:
    return tuple(name for name in form_class.base_fields if name != "process_analysis")


def _form_initial(step: int, stored: dict) -> dict:
    fields = WIZARD_STEPS[step]["form"].base_fields
    return {name: stored[name] for name in fields if name in stored}


def _source_value_stream(stored: dict):
    source_stage_id = stored.get("source_stage_id")
    if not source_stage_id:
        return None
    from ki_radar.architecture.models import ValueStreamStage

    stage = (
        ValueStreamStage.objects.select_related("value_stream__owner")
        .filter(pk=source_stage_id)
        .first()
    )
    return stage.value_stream if stage is not None else None


def _selected_business_unit(stored: dict):
    business_unit_id = stored.get("business_unit")
    if not business_unit_id:
        return None
    return BusinessUnit.objects.filter(pk=business_unit_id).first()


def _current_business_owner(stored: dict):
    business_owner_id = stored.get("business_owner")
    if not business_owner_id:
        return None
    owner = (
        get_user_model()
        .objects.filter(pk=business_owner_id, is_active=True, is_anonymized=False)
        .first()
    )
    if owner is None or not is_business_owner(owner):
        return None
    return owner


def _wizard_step_states(
    *,
    stored: dict,
    current_step: int,
    error_step: int | None = None,
) -> list[dict]:
    states = []
    for number in WIZARD_STEPS:
        form_class = WIZARD_STEPS[number]["form"]
        complete = number == 6 and current_step == 6
        if form_class is not None:
            complete = all(name in stored for name in _completion_field_names(form_class))
        if number == error_step:
            state = "error"
            symbol = "!"
        elif complete:
            state = "complete"
            symbol = "✓"
        else:
            state = "pending"
            symbol = str(number)
        states.append(
            {
                "number": number,
                "label": STEP_LABELS[number],
                "state": state,
                "symbol": symbol,
                "is_current": number == current_step,
                "is_reachable": number <= current_step,
            }
        )
    return states


def _build_use_case(*, stored: dict, user, business_owner) -> UseCase:
    affected_process = stored.get("affected_process", "")
    candidate = UseCase(
        title=stored["title"],
        summary=stored.get("summary", ""),
        problem_statement=stored.get("problem_statement", ""),
        business_unit=get_object_or_404(BusinessUnit, pk=stored["business_unit"]),
        affected_process=affected_process,
        target_users=stored.get("target_users", ""),
        submitter=user,
        business_owner=business_owner,
        source_systems=stored.get("source_systems", ""),
        data_sources=stored.get("data_sources", ""),
        intended_users=stored.get("intended_users", ""),
        intended_purpose=stored.get("intended_purpose", ""),
        expected_benefit=stored.get("expected_benefit", ""),
        metric_name=stored.get("metric_name", ""),
        metric_type=stored.get("metric_type", ""),
        metric_direction=stored.get("metric_direction", ""),
        metric_unit=stored.get("metric_unit", ""),
        metric_baseline=_optional_decimal(stored.get("metric_baseline")),
        metric_target=_optional_decimal(stored.get("metric_target")),
        metric_measurement_method=stored.get("metric_measurement_method", ""),
        privacy_review_required=stored.get("privacy_review_required", False),
        security_review_required=stored.get("security_review_required", False),
        legal_review_required=stored.get("legal_review_required", False),
        solution_type=stored.get("solution_type", ""),
        hosting_type=stored.get("hosting_type", ""),
        decision_status=UseCase.DecisionStatus.READY,
    )
    candidate._classification_payload = {
        "business_domain": stored.get("business_domain") or BusinessDomain.OTHER,
        "capability": stored.get("business_capability", ""),
        "process_area": affected_process,
    }
    return candidate


def _persist_optional_origin(*, candidate: UseCase, stored: dict) -> None:
    source_stage_id = stored.get("source_stage_id")
    source_process_id = stored.get("source_process_analysis_id")
    selected_process_id = stored.get("process_analysis")
    source_option_id = stored.get("source_solution_option_id")
    if not any((source_stage_id, source_process_id, selected_process_id, source_option_id)):
        return

    from ki_radar.architecture.models import (
        ProcessAnalysis,
        SolutionOption,
        UseCaseOrigin,
        ValueStreamStage,
    )
    from ki_radar.architecture.provenance import build_use_case_source_snapshot

    stage = None
    process_analysis = None

    if source_process_id:
        process_analysis = (
            ProcessAnalysis.objects.select_related("stage__value_stream")
            .filter(pk=source_process_id)
            .first()
        )
        if process_analysis is None:
            raise ValidationError(
                "Der aus Discovery übernommene Ursprungsprozess ist nicht mehr verfügbar."
            )
        stage = process_analysis.stage
        if source_stage_id and str(stage.pk) != str(source_stage_id):
            raise ValidationError(
                "Der Discovery-Ursprungsprozess gehört nicht mehr zur erwarteten "
                "Value-Stream-Phase."
            )
    elif selected_process_id:
        process_analysis = (
            ProcessAnalysis.objects.select_related("stage__value_stream")
            .filter(pk=selected_process_id)
            .first()
        )
        if process_analysis is None:
            raise ValidationError("Der gewählte Ursprungsprozess ist nicht mehr verfügbar.")
        stage = process_analysis.stage
        if source_stage_id and str(stage.pk) != str(source_stage_id):
            raise ValidationError(
                "Der gewählte Ursprungsprozess gehört nicht zur Discovery-Phase dieses Intake."
            )
    elif source_stage_id:
        stage = (
            ValueStreamStage.objects.select_related("value_stream")
            .filter(pk=source_stage_id)
            .first()
        )
        if stage is None:
            raise ValidationError(
                "Die aus Discovery übernommene Value-Stream-Phase ist nicht mehr verfügbar."
            )

    if stage is None:
        raise ValidationError("Der Ursprung des Use Cases ist nicht konsistent auflösbar.")
    if stage.value_stream.business_unit_id != candidate.business_unit_id:
        raise ValidationError(
            "Der Ursprungsprozess gehört nicht zur gewählten Organisationseinheit. "
            "Bitte prüfen Sie Prozess und Organisationseinheit."
        )
    if process_analysis is not None and candidate.affected_process != process_analysis.name:
        raise ValidationError(
            "Der betroffene Prozess stimmt nicht mit dem gewählten Ursprungsprozess überein."
        )

    solution_option = None
    if source_option_id:
        if process_analysis is None:
            raise ValidationError(
                "Die Discovery-Lösungsoption kann ohne Ursprungsprozess nicht übernommen werden."
            )
        solution_option = SolutionOption.objects.filter(
            pk=source_option_id,
            process_analysis=process_analysis,
        ).first()
        if solution_option is None:
            raise ValidationError(
                "Die aus Discovery übernommene Lösungsoption gehört nicht mehr zum "
                "Ursprungsprozess."
            )

    UseCaseOrigin.objects.create(
        use_case=candidate,
        stage=stage,
        process_analysis=process_analysis,
        solution_option=solution_option,
        source_snapshot=build_use_case_source_snapshot(
            stage=stage,
            process_analysis=process_analysis,
            solution_option=solution_option,
        ),
    )


def _lock_idea_candidate_for_promotion(request):
    idea_candidate_id = request.session.get(IDEA_CANDIDATE_SESSION_KEY)
    if not idea_candidate_id:
        return None

    from .idea_models import IdeaCandidate

    idea = IdeaCandidate.objects.select_for_update().filter(pk=idea_candidate_id).first()
    if idea is None:
        raise ValidationError("Die Ursprungsidee ist nicht mehr verfügbar.")
    if idea.state != IdeaCandidate.State.OPEN or idea.promoted_use_case_id is not None:
        raise ValidationError(
            "Die Ursprungsidee wurde bereits abgeschlossen und kann nicht erneut übernommen werden."
        )
    return idea


@login_required
def use_case_intake(request, step: int = 1):
    if not can_create_use_case(request.user):
        raise PermissionDenied
    if step not in WIZARD_STEPS:
        return redirect("use_cases:create")

    stored = request.session.get(SESSION_KEY, {})
    step_config = WIZARD_STEPS[step]
    form_class = step_config["form"]
    progress_class = f"wizard-progress-{step}"

    if step == 6:
        required_steps_complete = all(
            all(name in stored for name in _completion_field_names(WIZARD_STEPS[number]["form"]))
            for number in range(1, 6)
        )
        if not required_steps_complete:
            messages.warning(request, "Die Aufnahme ist noch nicht vollständig.")
            return redirect("use_cases:create")
        business_owner = _current_business_owner(stored)
        if business_owner is None:
            messages.warning(
                request,
                "Der gewählte Business Owner ist aktuell nicht mehr zulässig. Bitte neu wählen.",
            )
            return redirect("use_cases:create")
        candidate = _build_use_case(
            stored=stored,
            user=request.user,
            business_owner=business_owner,
        )
        blockers = intake_blockers(candidate)
        if request.method == "POST":
            if blockers:
                messages.error(
                    request,
                    "Der Use Case ist noch nicht bewertbar: " + ", ".join(blockers),
                )
            else:
                try:
                    with transaction.atomic():
                        idea = _lock_idea_candidate_for_promotion(request)
                        candidate._history_user = request.user
                        candidate.save()
                        _persist_optional_origin(candidate=candidate, stored=stored)
                        if idea is not None:
                            from .idea_models import IdeaCandidate

                            idea.state = IdeaCandidate.State.PROMOTED
                            idea.promoted_use_case = candidate
                            idea.save(update_fields=["state", "promoted_use_case", "updated_at"])
                except ValidationError as exc:
                    messages.error(request, " ".join(exc.messages))
                else:
                    request.session.pop(SESSION_KEY, None)
                    request.session.pop(IDEA_CANDIDATE_SESSION_KEY, None)
                    messages.success(
                        request,
                        f"Use Case {candidate.short_id} ist bereit zur Bewertung.",
                    )
                    return redirect(candidate)
        return render(
            request,
            "use_cases/intake_wizard.html",
            {
                "step": step,
                "step_config": step_config,
                "total_steps": len(WIZARD_STEPS),
                "progress_class": progress_class,
                "step_states": _wizard_step_states(stored=stored, current_step=step),
                "stored": stored,
                "candidate": candidate,
                "blockers": blockers,
                "has_intake_draft": bool(stored),
            },
        )

    error_step = None
    form_kwargs = {}
    if step == 1:
        form_kwargs["value_stream"] = _source_value_stream(stored)
    elif step == 2:
        form_kwargs = {
            "business_unit": _selected_business_unit(stored),
            "source_stage_id": stored.get("source_stage_id"),
            "source_process_analysis_id": stored.get("source_process_analysis_id"),
        }

    if request.method == "POST":
        form = form_class(request.POST, **form_kwargs)
        if form.is_valid():
            stored.update(_serialize_cleaned_data(form.cleaned_data))
            request.session[SESSION_KEY] = stored
            request.session.modified = True
            return redirect("use_cases:intake_step", step=step + 1)
        error_step = step
    else:
        form = form_class(initial=_form_initial(step, stored), **form_kwargs)

    return render(
        request,
        "use_cases/intake_wizard.html",
        {
            "form": form,
            "step": step,
            "step_config": step_config,
            "total_steps": len(WIZARD_STEPS),
            "progress_class": progress_class,
            "step_states": _wizard_step_states(
                stored=stored,
                current_step=step,
                error_step=error_step,
            ),
            "previous_step": step - 1 if step > 1 else None,
            "has_intake_draft": bool(stored),
        },
    )


@login_required
@require_POST
def discard_use_case_intake(request):
    if not can_create_use_case(request.user):
        raise PermissionDenied
    request.session.pop(SESSION_KEY, None)
    request.session.pop(IDEA_CANDIDATE_SESSION_KEY, None)
    request.session.modified = True
    messages.success(request, "Laufende Use-Case-Aufnahme wurde verworfen.")
    return redirect("use_cases:create")
