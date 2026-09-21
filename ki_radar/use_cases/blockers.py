from __future__ import annotations

from dataclasses import dataclass

from django.urls import reverse

from .models import UseCase
from .services import EARLY_GO_LIVE_BLOCKER


@dataclass(frozen=True)
class BlockerDetail:
    code: str
    label: str
    category: str
    action_label: str
    target_url: str
    target_anchor: str = ""
    field_name: str = ""

    @property
    def target_href(self) -> str:
        return f"{self.target_url}{self.target_anchor}"


FIELD_TARGETS = {
    "Titel": "title",
    "Problemstellung": "problem_statement",
    "Organisationseinheit": "business_unit",
    "Betroffener Prozess": "affected_process",
    "Fachlich verantwortliche Person": "business_owner",
    "Erwarteter Nutzen": "expected_benefit",
    "Primäre Erfolgsmetrik": "metric_name",
    "Metriktyp": "metric_type",
    "Optimierungsrichtung": "metric_direction",
    "Einheit": "metric_unit",
    "Baseline-Wert": "metric_baseline",
    "Zielwert": "metric_target",
    "Messmethode": "metric_measurement_method",
    "Datenquellen": "data_sources",
    "Nächster Entscheidungstermin": "next_review_date",
    "Geplantes Pilotende": "planned_pilot_end",
    "Technischer Owner": "technical_owner",
    "Einmalige Kosten": "one_time_cost",
    "Laufende Kosten": "recurring_cost",
    "Support-Verantwortung": "support_responsibility",
    "Menschliche Aufsicht": "human_oversight",
    "Umgang mit Daten und Zugängen": "data_and_access_handling",
    "Beendigungsgrund": "ending_reason",
}

GOVERNANCE_REVIEW_BLOCKERS = {
    "Datenschutzprüfung": "privacy",
    "Informationssicherheitsprüfung": "security",
    "Rechtsprüfung": "legal",
}

ASSESSMENT_BLOCKERS = {
    "Aktuelle strukturierte Bewertung",
    "Confidence ist für eine Freigabe zu niedrig",
    "Technische Machbarkeit ist zu niedrig",
    "Datenverfügbarkeit und -qualität sind zu niedrig",
    "Risiko und Komplexität sind für eine Freigabe zu hoch",
}

ROLE_SEPARATION_BLOCKERS = {
    "Bewertende und entscheidende Person müssen verschieden sein",
    "Fachlich verantwortliche und freigebende Person müssen verschieden sein",
}

DECISION_BLOCKERS = {
    "Positive Freigabeentscheidung",
    "Separate Governance-Bestätigung durch die entscheidende Person",
    *ROLE_SEPARATION_BLOCKERS,
}

DELIVERY_BLOCKERS = {
    "Aktuelles Delivery Package",
    "Verbindliche Übergabe des aktuellen Delivery Packages",
}


def _code(label: str) -> str:
    return "".join(character.lower() if character.isalnum() else "_" for character in label).strip(
        "_"
    )


def build_blocker_details(use_case: UseCase, blockers: list[str]) -> list[BlockerDetail]:
    """Derive actionable metadata from the canonical string blockers."""

    edit_url = reverse("use_cases:edit", kwargs={"pk": use_case.pk})
    detail_url = use_case.get_absolute_url()
    has_assessment = use_case.decision_assessments.exists()
    details: list[BlockerDetail] = []

    for label in blockers:
        if label == EARLY_GO_LIVE_BLOCKER:
            details.append(
                BlockerDetail(
                    code="pilot_period_running",
                    label=label,
                    category="time",
                    action_label="Ausnahme prüfen",
                    target_url=(
                        f"{reverse('reviews:create', kwargs={'use_case_id': use_case.pk})}"
                        "?action=go_live"
                    ),
                )
            )
            continue

        if label in {"Governance-Screening", "Governance-Vorprüfung"}:
            details.append(
                BlockerDetail(
                    code="governance_screening_missing",
                    label=label,
                    category="process",
                    action_label="Governance-Screening öffnen",
                    target_url=reverse("governance:create", kwargs={"use_case_id": use_case.pk}),
                )
            )
            continue

        review_type = GOVERNANCE_REVIEW_BLOCKERS.get(label)
        if review_type:
            details.append(
                BlockerDetail(
                    code=f"governance_{review_type}_review_open",
                    label=label,
                    category="process",
                    action_label=f"{label} durchführen",
                    target_url=reverse(
                        "governance:review",
                        kwargs={"use_case_id": use_case.pk, "review_type": review_type},
                    ),
                )
            )
            continue

        field_name = FIELD_TARGETS.get(label)
        if field_name:
            details.append(
                BlockerDetail(
                    code=f"missing_{field_name}",
                    label=label,
                    category="data",
                    action_label=f"{label} ergänzen",
                    target_url=f"{edit_url}?highlight={field_name}",
                    target_anchor=f"#field-{field_name}",
                    field_name=field_name,
                )
            )
            continue

        if label in ROLE_SEPARATION_BLOCKERS:
            details.append(
                BlockerDetail(
                    code=_code(label),
                    label=label,
                    category="role",
                    action_label="Andere KI-Koordination zuweisen",
                    target_url=f"{edit_url}?highlight=coordinator",
                    target_anchor="#field-coordinator",
                    field_name="coordinator",
                )
            )
            continue

        if label in DELIVERY_BLOCKERS:
            package = use_case.delivery_packages.first()
            details.append(
                BlockerDetail(
                    code=_code(label),
                    label=label,
                    category="process",
                    action_label=(
                        "Delivery Package öffnen" if package else "Delivery-Bereich öffnen"
                    ),
                    target_url=(
                        package.get_absolute_url() if package else reverse("delivery:package_list")
                    ),
                )
            )
            continue

        if label == "Lifecycle-Status Prüfung":
            details.append(
                BlockerDetail(
                    code="pilot_requires_review_status",
                    label=label,
                    category="process",
                    action_label="Use Case öffnen",
                    target_url=detail_url,
                )
            )
            continue

        if label in ASSESSMENT_BLOCKERS:
            details.append(
                BlockerDetail(
                    code=_code(label),
                    label=label,
                    category="process",
                    action_label="Bewertung öffnen",
                    target_url=reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk}),
                )
            )
            continue

        if label in DECISION_BLOCKERS:
            target_url = (
                reverse("use_cases:approval_decision_create", kwargs={"pk": use_case.pk})
                if has_assessment
                else reverse("use_cases:assessment_create", kwargs={"pk": use_case.pk})
            )
            action_label = "Freigabeentscheidung öffnen" if has_assessment else "Bewertung anlegen"
            details.append(
                BlockerDetail(
                    code=_code(label),
                    label=label,
                    category="process",
                    action_label=action_label,
                    target_url=target_url,
                )
            )
            continue

        details.append(
            BlockerDetail(
                code=_code(label),
                label=label,
                category="process",
                action_label="Use Case öffnen",
                target_url=detail_url,
            )
        )

    return details
