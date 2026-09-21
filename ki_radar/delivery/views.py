from pathlib import Path
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from ki_radar.core.navigation import requested_return_to
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.workflow import build_delivery_package_journey

from .actions import build_actionable_findings, primary_delivery_action, section_responsibility
from .forms import DeliveryPackageForm
from .models import DELIVERY_SECTION_DEFINITIONS, DeliveryPackage
from .permissions import (
    allowed_edit_sections,
    can_create_package,
    can_edit_package,
    can_review_section,
    can_transition_package,
    can_use_admin_confirmation_override,
    can_view_package,
    reviewer_roles,
)
from .readiness import delivery_status_snapshot, missing_ready_fields
from .services import (
    APPROVED_STATUSES,
    create_delivery_package,
    delivery_source_differences,
    hand_over_package,
    mark_package_ready,
    render_delivery_markdown,
    resolve_technical_owner_source_change,
    review_delivery_section,
    technical_owner_source_state,
)

METHODOLOGY_PATH = Path(settings.BASE_DIR) / "docs" / "DELIVERY_METHODOLOGY.md"
METHODOLOGY_DOWNLOAD_NAME = "KI-Radar_Vorgehensmodell_CRISP-MLQ_ML-Test-Score_v2.0.md"
SECTION_KEYS = tuple(key for key, _label in DELIVERY_SECTION_DEFINITIONS)


def _validation_message(exc: ValidationError) -> str:
    return "; ".join(exc.messages) if exc.messages else str(exc)


def _package_queryset():
    return DeliveryPackage.objects.select_related(
        "use_case__business_unit",
        "use_case__business_owner",
        "use_case__technical_owner",
        "technical_owner",
        "use_case__classification",
        "generated_from_decision__assessment",
        "generated_from_decision__condition_owner",
        "created_by",
        "handed_over_by",
        "architecture_artifacts",
    ).prefetch_related(
        "section_reviews__reviewed_by",
        "section_reviews__business_confirmed_by",
        "section_reviews__technical_confirmed_by",
        "role_source_decisions__decided_by",
        "use_case__decision_assessments",
        "use_case__approval_decisions",
        "use_case__delivery_packages",
        "use_case__architecture_origin__stage__value_stream",
        "use_case__architecture_origin__stage__value_stream__focus",
        "use_case__architecture_origin__process_analysis",
        "use_case__architecture_origin__solution_option",
    )


def _package_list_status_queryset():
    return DeliveryPackage.objects.select_related(
        "technical_owner",
        "generated_from_decision__condition_owner",
        "architecture_artifacts",
        "use_case__business_owner",
        "use_case__technical_owner",
    ).prefetch_related(
        "section_reviews__business_confirmed_by",
        "section_reviews__technical_confirmed_by",
    )


def _section_edit_url(package: DeliveryPackage, section_key: str, return_to: str) -> str:
    base = reverse("delivery:package_update", kwargs={"pk": package.pk})
    return f"{base}?{urlencode({'section': section_key, 'return_to': return_to})}"


def _section_state(review, findings) -> tuple[str, str]:
    blocker_count = sum(finding.severity == "blocker" for finding in findings)
    if blocker_count or (review and review.review_status == "blocked"):
        return "blocked", "Blockiert"
    if review and review.review_status == "confirmed" and review.confirmations_complete:
        return "confirmed", "Bestätigt"
    return "open", "Offen"


def _section_rows(
    *,
    package: DeliveryPackage,
    user,
    finding_actions,
    return_to: str,
    active_section: str = "",
    primary_finding=None,
) -> list[dict]:
    reviews = {review.section_key: review for review in package.section_reviews.all()}
    findings_by_section = {key: [] for key in SECTION_KEYS}
    for finding in finding_actions:
        findings_by_section.setdefault(finding.section_key, []).append(finding)
    editable_sections = allowed_edit_sections(user, package)
    rows = []
    for section_key, section_label in DELIVERY_SECTION_DEFINITIONS:
        responsible_role, responsible_person = section_responsibility(package, section_key)
        review = reviews.get(section_key)
        findings = findings_by_section.get(section_key, [])
        state, state_label = _section_state(review, findings)
        roles = reviewer_roles(user, package, section_key)
        required = review.required_confirmations if review else frozenset()
        shared_section = {"business", "technical"}.issubset(required)
        source_manifest = review.source_manifest if review else {}
        field_sources = source_manifest.get("field_sources") or {}
        blockers = [finding for finding in findings if finding.severity == "blocker"]
        field_blockers = {finding.field_name for finding in blockers if finding.field_name}
        rows.append(
            {
                "key": section_key,
                "label": section_label,
                "review": review,
                "findings": findings,
                "blocker_count": len(blockers),
                "finding_count": len(findings),
                "open_field_count": len(field_blockers),
                "source_count": len(field_sources),
                "state": state,
                "state_label": state_label,
                "is_primary": bool(primary_finding and primary_finding.section_key == section_key),
                "is_active": section_key == active_section,
                "can_edit": section_key in editable_sections,
                "edit_url": _section_edit_url(package, section_key, return_to),
                "can_review": can_review_section(user, package, section_key),
                "can_confirm_business": bool(
                    review
                    and "business" in roles
                    and "business" in required
                    and (
                        review.business_confirmed_at is None
                        or (review.has_role_collapse and review.business_confirmed_by_id != user.id)
                    )
                ),
                "can_confirm_technical": bool(
                    review
                    and "technical" in roles
                    and "technical" in required
                    and (
                        review.technical_confirmed_at is None
                        or (
                            review.has_role_collapse and review.technical_confirmed_by_id != user.id
                        )
                    )
                ),
                "show_admin_override_reason": bool(
                    shared_section and can_use_admin_confirmation_override(user)
                ),
                "requires_business": "business" in required,
                "requires_technical": "technical" in required,
                "business_complete": bool(review and review.business_confirmed_at),
                "technical_complete": bool(review and review.technical_confirmed_at),
                "responsible_role": responsible_role,
                "responsible_person": responsible_person,
            }
        )
    return rows


def _active_edit_section(package: DeliveryPackage, user, requested: str, highlight: str) -> str:
    editable_sections = allowed_edit_sections(user, package)
    if requested in editable_sections:
        return requested
    highlight_section = DeliveryPackageForm.section_for_field(highlight)
    if highlight_section in editable_sections:
        return highlight_section
    return next((key for key in SECTION_KEYS if key in editable_sections), "")


@login_required
def package_list(request):
    use_cases = list(
        UseCase.objects.filter(
            is_archived=False,
            decision_status__in=APPROVED_STATUSES,
        )
        .select_related("business_unit", "business_owner", "classification")
        .prefetch_related(
            Prefetch("delivery_packages", queryset=_package_list_status_queryset()),
            "approval_decisions",
        )
        .order_by("business_unit__name", "short_id")
    )
    rows = []
    for use_case in use_cases:
        decisions = list(use_case.approval_decisions.all())
        final_decision = next(
            (
                decision
                for decision in decisions
                if decision.decision_status in APPROVED_STATUSES
                and decision.finalized_at is not None
            ),
            None,
        )
        packages = list(use_case.delivery_packages.all())
        latest_package = packages[0] if packages else None
        rows.append(
            {
                "use_case": use_case,
                "eligible": final_decision is not None,
                "eligibility_reason": (
                    ""
                    if final_decision
                    else "Die positive Freigabe ist noch nicht final dokumentiert."
                ),
                "latest_package": latest_package,
                "latest_package_status": (
                    delivery_status_snapshot(latest_package) if latest_package else None
                ),
            }
        )
    return render(
        request,
        "delivery/package_list.html",
        {"rows": rows, "can_create": can_create_package(request.user)},
    )


@login_required
@require_POST
def package_create(request, use_case_id):
    if not can_create_package(request.user):
        raise PermissionDenied
    use_case = get_object_or_404(
        UseCase.objects.select_related(
            "business_unit",
            "business_owner",
            "technical_owner",
            "classification",
            "architecture_origin__stage__value_stream__focus",
            "architecture_origin__process_analysis",
            "architecture_origin__solution_option",
        ).prefetch_related(
            "approval_decisions__assessment",
            "delivery_packages",
        ),
        pk=use_case_id,
    )
    try:
        package = create_delivery_package(use_case=use_case, actor=request.user)
    except ValidationError as exc:
        messages.error(request, _validation_message(exc))
        return redirect("delivery:package_list")
    messages.success(
        request,
        f"Delivery Package v{package.version} wurde aus der finalen Freigabe erzeugt.",
    )
    return redirect(package)


@login_required
def package_detail(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_view_package(request.user, package):
        raise PermissionDenied

    finding_actions = build_actionable_findings(package, request.user)
    primary_finding = primary_delivery_action(package, request.user)
    section_rows = _section_rows(
        package=package,
        user=request.user,
        finding_actions=finding_actions,
        return_to=package.get_absolute_url(),
        primary_finding=primary_finding,
    )

    role_collapse = bool(
        package.technical_owner_id
        and package.technical_owner_id == package.use_case.business_owner_id
    )
    technical_owner_change = technical_owner_source_state(package)
    status_snapshot = delivery_status_snapshot(package)
    return render(
        request,
        "delivery/package_detail.html",
        {
            "package": package,
            "delivery_status": status_snapshot,
            "journey": build_delivery_package_journey(package, request.user),
            "can_edit": can_edit_package(request.user, package),
            "can_transition": can_transition_package(request.user),
            "missing_ready_fields": missing_ready_fields(package),
            "readiness_findings": finding_actions,
            "primary_readiness_finding": primary_finding,
            "section_rows": section_rows,
            "owner_role_collapse": role_collapse,
            "delivery_source_rows": delivery_source_differences(package),
            "technical_owner_source_change": (
                technical_owner_change
                if technical_owner_change and technical_owner_change["source_changed"]
                else None
            ),
            "role_source_decisions": package.role_source_decisions.all(),
        },
    )


@login_required
def package_update(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_edit_package(request.user, package):
        raise PermissionDenied

    return_to = requested_return_to(request, package.get_absolute_url())
    requested_highlight = request.POST.get("highlight") or request.GET.get("highlight", "")
    requested_section = request.POST.get("section") or request.GET.get("section", "")
    active_section = _active_edit_section(
        package,
        request.user,
        requested_section,
        requested_highlight,
    )
    form = DeliveryPackageForm(
        request.POST or None,
        instance=package,
        actor=request.user,
        active_section=active_section,
    )
    highlight_field = requested_highlight if requested_highlight in form.fields else ""
    highlight_section = form.section_for_field(highlight_field)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(
            request,
            (
                "Delivery-Sektion wurde aktualisiert; die Readiness wurde vollständig neu "
                "bewertet und die geänderte Sektion benötigt eine neue Bestätigung."
            ),
        )
        return redirect(return_to)

    finding_actions = build_actionable_findings(package, request.user)
    section_rows = _section_rows(
        package=package,
        user=request.user,
        finding_actions=finding_actions,
        return_to=return_to,
        active_section=active_section,
        primary_finding=next(
            (finding for finding in finding_actions if finding.severity == "blocker"),
            None,
        ),
    )
    return render(
        request,
        "delivery/package_form.html",
        {
            "form": form,
            "package": package,
            "return_to": return_to,
            "highlight_field": highlight_field,
            "highlight_section": highlight_section,
            "active_section": active_section,
            "section_rows": section_rows,
        },
    )


@login_required
@require_POST
def package_section_review(request, pk, section_key):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if section_key not in dict(DELIVERY_SECTION_DEFINITIONS):
        raise PermissionDenied
    if not can_review_section(request.user, package, section_key):
        raise PermissionDenied
    try:
        review_delivery_section(
            package=package,
            section_key=section_key,
            action=request.POST.get("action", ""),
            actor=request.user,
            note=request.POST.get("review_note", ""),
            role_collapse_reason=request.POST.get("role_collapse_reason", ""),
        )
    except ValidationError as exc:
        messages.error(request, _validation_message(exc))
    else:
        messages.success(request, "Sektionsprüfung wurde gespeichert.")
    return redirect(f"{package.get_absolute_url()}#section-{section_key}")


@login_required
@require_POST
def package_resolve_technical_owner_source(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_transition_package(request.user):
        raise PermissionDenied
    try:
        resolve_technical_owner_source_change(
            package=package,
            action=request.POST.get("action", ""),
            rationale=request.POST.get("rationale", ""),
            actor=request.user,
        )
    except ValidationError as exc:
        messages.error(request, _validation_message(exc))
    else:
        messages.success(request, "Die Änderung des Technical Owners wurde entschieden.")
    return redirect(f"{package.get_absolute_url()}#technical-owner-source-change")


@login_required
@require_POST
def package_mark_ready(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_transition_package(request.user):
        raise PermissionDenied
    try:
        mark_package_ready(package)
    except ValidationError as exc:
        messages.error(request, _validation_message(exc))
    else:
        messages.success(request, "Delivery Package ist bereit zur Übergabe.")
    return redirect(package)


@login_required
@require_POST
def package_handover(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_transition_package(request.user):
        raise PermissionDenied
    try:
        hand_over_package(package, request.user)
    except ValidationError as exc:
        messages.error(request, _validation_message(exc))
    else:
        messages.success(request, "Delivery Package wurde verbindlich übergeben.")
    return redirect(package)


@login_required
def package_export_markdown(request, pk):
    package = get_object_or_404(_package_queryset(), pk=pk)
    if not can_view_package(request.user, package):
        raise PermissionDenied
    response = HttpResponse(
        render_delivery_markdown(package),
        content_type="text/markdown; charset=utf-8",
    )
    response["Content-Disposition"] = (
        f'attachment; filename="{package.use_case.short_id}-delivery-v{package.version}.md"'
    )
    return response


@login_required
def methodology_reference(request):
    methodology = METHODOLOGY_PATH.read_text(encoding="utf-8")
    return render(
        request,
        "delivery/methodology_reference.html",
        {"methodology": methodology},
    )


@login_required
def methodology_download(request):
    methodology = METHODOLOGY_PATH.read_text(encoding="utf-8")
    response = HttpResponse(methodology, content_type="text/markdown; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{METHODOLOGY_DOWNLOAD_NAME}"'
    return response
