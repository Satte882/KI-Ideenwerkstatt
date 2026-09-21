from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ki_radar.accounts.models import BusinessUnit

from .idea_forms import IdeaCandidateForm, IdeaDismissForm, IdeaTriageForm
from .idea_models import IdeaCandidate
from .intake_views import IDEA_CANDIDATE_SESSION_KEY, SESSION_KEY
from .permissions import (
    can_create_idea,
    can_edit_idea,
    can_promote_idea,
    can_triage_idea,
)


@login_required
def idea_list(request):
    base = IdeaCandidate.objects.select_related(
        "business_unit", "submitted_by", "triaged_by", "promoted_use_case"
    )
    stats = {
        "all": base.count(),
        "open": base.filter(state=IdeaCandidate.State.OPEN).count(),
        "dismissed": base.filter(state=IdeaCandidate.State.DISMISSED).count(),
        "promoted": base.filter(state=IdeaCandidate.State.PROMOTED).count(),
    }

    state_filter = request.GET.get("state", IdeaCandidate.State.OPEN)
    if state_filter != "all" and state_filter in IdeaCandidate.State.values:
        base = base.filter(state=state_filter)

    business_unit_id = request.GET.get("business_unit", "")
    if business_unit_id:
        base = base.filter(business_unit_id=business_unit_id)

    query = request.GET.get("q", "").strip()
    if query:
        base = base.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(source_note__icontains=query)
        )

    ideas = list(base.order_by("-created_at"))
    sort = request.GET.get("sort", "newest")
    if sort == "score":
        ideas.sort(
            key=lambda idea: (
                idea.quick_score is not None,
                idea.quick_score or 0,
                idea.created_at,
            ),
            reverse=True,
        )

    return render(
        request,
        "use_cases/ideas/list.html",
        {
            "ideas": ideas,
            "stats": stats,
            "state_filter": state_filter,
            "business_unit_id": business_unit_id,
            "business_units": BusinessUnit.objects.filter(is_active=True),
            "query": query,
            "sort": sort,
            "can_create_idea": can_create_idea(request.user),
        },
    )


@login_required
def idea_create(request):
    if not can_create_idea(request.user):
        raise PermissionDenied
    if request.method == "POST":
        form = IdeaCandidateForm(request.POST)
        if form.is_valid():
            idea = form.save(commit=False)
            idea.submitted_by = request.user
            idea.save()
            messages.success(request, "Idee wurde in der Ideen-Inbox erfasst.")
            return redirect(idea)
    else:
        form = IdeaCandidateForm()
    return render(
        request,
        "use_cases/ideas/form.html",
        {"form": form, "page_title": "Idee erfassen", "submit_label": "Idee speichern"},
    )


@login_required
def idea_detail(request, pk):
    idea = get_object_or_404(
        IdeaCandidate.objects.select_related(
            "business_unit", "submitted_by", "triaged_by", "promoted_use_case"
        ),
        pk=pk,
    )
    return render(
        request,
        "use_cases/ideas/detail.html",
        {
            "idea": idea,
            "triage_form": IdeaTriageForm(instance=idea),
            "dismiss_form": IdeaDismissForm(),
            "can_edit": can_edit_idea(request.user, idea),
            "can_triage": can_triage_idea(request.user, idea),
            "can_promote": can_promote_idea(request.user, idea),
            "has_intake_draft": bool(request.session.get(SESSION_KEY)),
        },
    )


@login_required
def idea_edit(request, pk):
    idea = get_object_or_404(IdeaCandidate, pk=pk)
    if not can_edit_idea(request.user, idea):
        raise PermissionDenied
    if request.method == "POST":
        form = IdeaCandidateForm(request.POST, instance=idea)
        if form.is_valid():
            form.save()
            messages.success(request, "Idee wurde aktualisiert.")
            return redirect(idea)
    else:
        form = IdeaCandidateForm(instance=idea)
    return render(
        request,
        "use_cases/ideas/form.html",
        {
            "form": form,
            "page_title": "Idee bearbeiten",
            "submit_label": "Änderungen speichern",
        },
    )


@login_required
@require_POST
def idea_triage(request, pk):
    idea = get_object_or_404(IdeaCandidate, pk=pk)
    if not can_triage_idea(request.user, idea):
        raise PermissionDenied
    form = IdeaTriageForm(request.POST, instance=idea)
    if not form.is_valid():
        messages.error(
            request,
            "Triage konnte nicht gespeichert werden. Werte müssen zwischen 1 und 5 liegen.",
        )
        return redirect(idea)
    idea = form.save(commit=False)
    idea.triaged_by = request.user
    idea.triaged_at = timezone.now()
    idea.save(
        update_fields=[
            "impact",
            "confidence",
            "ease",
            "triaged_by",
            "triaged_at",
            "updated_at",
        ]
    )
    messages.success(request, "Quick-Triage wurde gespeichert.")
    return redirect(idea)


@login_required
@require_POST
def idea_dismiss(request, pk):
    form = IdeaDismissForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Für „Nicht weiterverfolgen“ ist eine Begründung erforderlich.")
        return redirect("use_cases:idea_detail", pk=pk)

    with transaction.atomic():
        idea = get_object_or_404(IdeaCandidate.objects.select_for_update(), pk=pk)
        if not can_triage_idea(request.user, idea):
            raise PermissionDenied
        idea.state = IdeaCandidate.State.DISMISSED
        idea.decision_note = form.cleaned_data["decision_note"].strip()
        idea.triaged_by = request.user
        idea.triaged_at = timezone.now()
        idea.save(
            update_fields=[
                "state",
                "decision_note",
                "triaged_by",
                "triaged_at",
                "updated_at",
            ]
        )
    messages.success(
        request,
        "Idee wurde nachvollziehbar als nicht weiterzuverfolgen abgeschlossen.",
    )
    return redirect(idea)


@login_required
@require_POST
def idea_promote(request, pk):
    idea = get_object_or_404(IdeaCandidate, pk=pk)
    if not can_promote_idea(request.user, idea):
        raise PermissionDenied
    if idea.state != IdeaCandidate.State.OPEN or idea.promoted_use_case_id is not None:
        messages.warning(
            request,
            "Diese Idee wurde bereits abgeschlossen und kann nicht erneut übernommen werden.",
        )
        return redirect(idea)

    if request.session.get(SESSION_KEY):
        messages.warning(
            request,
            "Es läuft bereits eine Use-Case-Aufnahme. Setzen Sie diese fort oder verwerfen Sie "
            "den Draft bewusst, bevor Sie eine Idee übernehmen.",
        )
        return redirect(idea)

    initial = {
        "title": idea.title,
        "problem_statement": idea.description,
    }
    if idea.business_unit_id:
        initial["business_unit"] = idea.business_unit_id
    request.session[SESSION_KEY] = initial
    request.session[IDEA_CANDIDATE_SESSION_KEY] = str(idea.pk)
    request.session.modified = True
    messages.info(
        request,
        "Die Idee wurde in den bestehenden Intake vorbefüllt. Erst der erfolgreiche Abschluss "
        "von Schritt 6 übernimmt sie als Use Case.",
    )
    return redirect("use_cases:create")
