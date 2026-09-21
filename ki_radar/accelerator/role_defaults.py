from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from django.contrib.auth import get_user_model

from ki_radar.accounts.permissions import is_business_owner, is_coordinator
from ki_radar.delivery.permissions import can_confirm_business, can_confirm_technical

EXISTING = "existing"
PREFILL = "prefill"
SUGGESTION = "suggestion"
ROLE_ONLY = "role_only"
OPEN = "open"
CONFLICT = "conflict"
INELIGIBLE = "ineligible"


@dataclass(frozen=True)
class RoleDefaultResolution:
    role_key: str
    state: str
    user_id: int | None = None
    user_label: str = ""
    source_kind: str = ""
    source_id: str = ""
    source_label: str = ""
    reason: str = ""

    @property
    def has_user(self) -> bool:
        return self.user_id is not None


@dataclass(frozen=True)
class DeliveryReviewResolution:
    role: str
    resolution: RoleDefaultResolution


def _object_id(value) -> str:
    pk = value.pk if value is not None else None
    return "" if pk is None else str(pk)


def _load_user(user_id: int | None):
    if user_id is None:
        return None
    return get_user_model().objects.filter(pk=user_id).first()


def _is_currently_usable(
    user,
    predicate: Callable | None = None,
) -> bool:
    if user is None or not user.is_active or user.is_anonymized:
        return False
    return predicate is None or predicate(user)


def _person_resolution(
    *,
    role_key: str,
    eligible_state: str,
    user_id: int | None,
    source_kind: str,
    source,
    source_label: str,
    predicate: Callable | None = None,
    reason: str = "",
) -> RoleDefaultResolution:
    user = _load_user(user_id)
    if not _is_currently_usable(user, predicate):
        return RoleDefaultResolution(
            role_key=role_key,
            state=INELIGIBLE,
            user_id=user_id,
            user_label=user.get_display_name() if user is not None else "",
            source_kind=source_kind,
            source_id=_object_id(source),
            source_label=source_label,
            reason=reason or "Die Rollenquelle ist aktuell nicht zulässig.",
        )
    return RoleDefaultResolution(
        role_key=role_key,
        state=eligible_state,
        user_id=user.pk,
        user_label=user.get_display_name(),
        source_kind=source_kind,
        source_id=_object_id(source),
        source_label=source_label,
        reason=reason,
    )


def open_resolution(
    role_key: str,
    *,
    reason: str = "Keine eindeutige Rollenquelle.",
) -> RoleDefaultResolution:
    return RoleDefaultResolution(role_key=role_key, state=OPEN, reason=reason)


def resolve_use_case_business_owner(
    *,
    use_case=None,
    value_stream=None,
) -> RoleDefaultResolution:
    if use_case is not None and use_case.business_owner_id:
        return _person_resolution(
            role_key="business_owner",
            eligible_state=EXISTING,
            user_id=use_case.business_owner_id,
            source_kind="use_case",
            source=use_case,
            source_label="Business Owner des Use Cases",
            predicate=is_business_owner,
        )

    if value_stream is not None and value_stream.owner_id:
        return _person_resolution(
            role_key="business_owner",
            eligible_state=SUGGESTION,
            user_id=value_stream.owner_id,
            source_kind="value_stream",
            source=value_stream,
            source_label="Owner des zugehörigen Value Streams",
            predicate=is_business_owner,
            reason=(
                "Cross-Role-Vorschlag: Value-Stream-Owner und Business Owner sind getrennte Rollen."
            ),
        )

    return open_resolution("business_owner")


def resolve_use_case_coordinator(
    *,
    use_case=None,
) -> RoleDefaultResolution:
    if use_case is not None and use_case.coordinator_id:
        return _person_resolution(
            role_key="coordinator",
            eligible_state=EXISTING,
            user_id=use_case.coordinator_id,
            source_kind="use_case",
            source=use_case,
            source_label="KI-Koordinator des Use Cases",
            predicate=is_coordinator,
        )
    return open_resolution("coordinator")


def resolve_use_case_technical_owner(
    *,
    use_case=None,
) -> RoleDefaultResolution:
    if use_case is not None and use_case.technical_owner_id:
        return _person_resolution(
            role_key="technical_owner",
            eligible_state=EXISTING,
            user_id=use_case.technical_owner_id,
            source_kind="use_case",
            source=use_case,
            source_label="Technical Owner des Use Cases",
        )
    return open_resolution("technical_owner")


def resolve_delivery_technical_owner(
    *,
    use_case,
    package=None,
) -> RoleDefaultResolution:
    if package is not None and package.technical_owner_id:
        return _person_resolution(
            role_key="technical_owner",
            eligible_state=EXISTING,
            user_id=package.technical_owner_id,
            source_kind="delivery_package",
            source=package,
            source_label="Technical Owner des Delivery Packages",
        )

    if use_case.technical_owner_id:
        return _person_resolution(
            role_key="technical_owner",
            eligible_state=PREFILL,
            user_id=use_case.technical_owner_id,
            source_kind="use_case",
            source=use_case,
            source_label="Technical Owner des Use Cases",
        )

    return open_resolution("technical_owner")


def resolve_condition_owner(
    *,
    decision=None,
) -> RoleDefaultResolution:
    if decision is not None and decision.condition_owner_id:
        return _person_resolution(
            role_key="condition_owner",
            eligible_state=EXISTING,
            user_id=decision.condition_owner_id,
            source_kind="approval_decision",
            source=decision,
            source_label="Auflagenverantwortlicher der Freigabe",
        )
    return open_resolution("condition_owner")


def resolve_second_approver(
    *,
    use_case,
    first_decider,
    assigned=None,
) -> RoleDefaultResolution:
    from ki_radar.use_cases.services import eligible_second_approvers

    eligible = eligible_second_approvers(use_case=use_case, first_decider=first_decider)
    if assigned is not None and eligible.filter(pk=assigned.pk).exists():
        return _person_resolution(
            role_key="second_approver",
            eligible_state=EXISTING,
            user_id=assigned.pk,
            source_kind="approval_decision",
            source=use_case,
            source_label="Bereits zugewiesene unabhängige Zweitprüfung",
        )
    if assigned is not None:
        return RoleDefaultResolution(
            role_key="second_approver",
            state=INELIGIBLE,
            user_id=assigned.pk,
            user_label=assigned.get_display_name(),
            source_kind="approval_decision",
            source_id=_object_id(use_case),
            source_label="Bereits zugewiesene unabhängige Zweitprüfung",
            reason="Die zugewiesene Person ist aktuell nicht mehr unabhängig berechtigt.",
        )

    candidates = list(eligible[:2])
    if len(candidates) == 1:
        candidate = candidates[0]
        return _person_resolution(
            role_key="second_approver",
            eligible_state=SUGGESTION,
            user_id=candidate.pk,
            source_kind="eligible_second_approvers",
            source=use_case,
            source_label="Einzige aktuell zulässige unabhängige Zweitprüfung",
            reason="Eindeutiger Eligibility-Vorschlag; keine automatische Zuweisung.",
        )
    if not candidates:
        return open_resolution(
            "second_approver",
            reason="Keine aktuell zulässige unabhängige Zweitprüfung.",
        )
    return open_resolution(
        "second_approver",
        reason=("Mehrere unabhängige Zweitprüfer sind zulässig; keine Person wird bevorzugt."),
    )


def resolve_delivery_review_roles(
    *,
    package,
    review,
) -> tuple[DeliveryReviewResolution, ...]:
    resolutions: list[DeliveryReviewResolution] = []
    required = review.required_confirmations

    if "business" in required and review.business_confirmed_at is None:
        owner_id = package.use_case.business_owner_id
        owner = _load_user(owner_id)
        owner_is_eligible = _is_currently_usable(owner) and can_confirm_business(
            owner,
            package,
            review.section_key,
        )
        if owner_is_eligible:
            resolution = _person_resolution(
                role_key="delivery_review_business",
                eligible_state=SUGGESTION,
                user_id=owner_id,
                source_kind="use_case",
                source=package.use_case,
                source_label="Business Owner des Use Cases",
                reason="Accountable Business-Rolle; Bestätigung bleibt manuell.",
            )
        else:
            resolution = RoleDefaultResolution(
                role_key="delivery_review_business",
                state=ROLE_ONLY,
                source_kind="delivery_section",
                source_id=_object_id(review),
                source_label="Erforderliche Business Confirmation",
                reason=(
                    "Die Rolle ist erforderlich, aber keine eindeutige zulässige Person verfügbar."
                ),
            )
        resolutions.append(DeliveryReviewResolution(role="business", resolution=resolution))

    if "technical" in required and review.technical_confirmed_at is None:
        owner_id = package.technical_owner_id
        owner = _load_user(owner_id)
        owner_is_eligible = _is_currently_usable(owner) and can_confirm_technical(
            owner,
            package,
            review.section_key,
        )
        if owner_is_eligible:
            resolution = _person_resolution(
                role_key="delivery_review_technical",
                eligible_state=SUGGESTION,
                user_id=owner_id,
                source_kind="delivery_package",
                source=package,
                source_label="Technical Owner des Delivery Packages",
                reason="Accountable Technical-Rolle; Bestätigung bleibt manuell.",
            )
        else:
            resolution = RoleDefaultResolution(
                role_key="delivery_review_technical",
                state=ROLE_ONLY,
                source_kind="delivery_section",
                source_id=_object_id(review),
                source_label="Erforderliche Technical Confirmation",
                reason=(
                    "Die Rolle ist erforderlich, aber keine eindeutige zulässige Person verfügbar."
                ),
            )
        resolutions.append(DeliveryReviewResolution(role="technical", resolution=resolution))

    return tuple(resolutions)


def resolve_governance_review_role(
    *,
    review,
) -> RoleDefaultResolution:
    role_label = (review.responsible_role or "").strip()
    if not role_label:
        role_label = review.get_review_type_display()
    return RoleDefaultResolution(
        role_key=f"governance_review:{review.review_type}",
        state=ROLE_ONLY,
        source_kind="governance_review",
        source_id=_object_id(review),
        source_label=role_label,
        reason="Governance-Kontext benennt eine Prüfrolle, aber keine eindeutige Person.",
    )
