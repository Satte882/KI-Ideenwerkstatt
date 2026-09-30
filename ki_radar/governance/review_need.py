"""Deterministic review needs for known and unknown governance facts."""

from collections.abc import Mapping
from dataclasses import dataclass

FACT_FIELDS = (
    "personal_data",
    "employee_data",
    "automated_person_assessment",
    "influences_person_decisions",
    "biometric_data",
    "safety_critical",
    "regulated_product",
    "health_safety_rights_impact",
    "external_ai_or_cloud",
    "generated_external_content",
    "human_oversight_planned",
)

_TRIGGERS = {
    "privacy": (
        ("personal_data", True),
        ("employee_data", True),
        ("biometric_data", True),
    ),
    "security": (
        ("personal_data", True),
        ("external_ai_or_cloud", True),
        ("safety_critical", True),
        ("regulated_product", True),
    ),
    "legal": (
        ("automated_person_assessment", True),
        ("influences_person_decisions", True),
        ("biometric_data", True),
        ("safety_critical", True),
        ("regulated_product", True),
        ("health_safety_rights_impact", True),
        ("generated_external_content", True),
        ("human_oversight_planned", False),
    ),
}


@dataclass(frozen=True)
class ReviewNeedResolution:
    needs: dict[str, bool | None]
    critical_unknowns: tuple[str, ...]

    @property
    def is_determinate(self) -> bool:
        return all(value is not None for value in self.needs.values())


def resolve_review_needs(facts: Mapping[str, bool | None]) -> ReviewNeedResolution:
    """Resolve reviews without treating an unknown fact as a negative answer.

    An unknown is decision-critical only while it can still turn an unresolved
    review need into ``required``. Once another fact requires that review, its
    remaining unknown triggers no longer need a human answer for screening.
    """

    if set(facts) != set(FACT_FIELDS) or any(
        value is not True and value is not False and value is not None for value in facts.values()
    ):
        raise ValueError("Governance facts must contain every tri-state field.")

    needs: dict[str, bool | None] = {}
    critical: set[str] = set()
    for review, triggers in _TRIGGERS.items():
        if any(facts[name] is trigger for name, trigger in triggers):
            needs[review] = True
            continue
        unknowns = [name for name, _trigger in triggers if facts[name] is None]
        if unknowns:
            needs[review] = None
            critical.update(unknowns)
        else:
            needs[review] = False

    return ReviewNeedResolution(
        needs=needs,
        critical_unknowns=tuple(name for name in FACT_FIELDS if name in critical),
    )
