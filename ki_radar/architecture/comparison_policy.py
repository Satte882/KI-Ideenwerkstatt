"""Shared assessment requirements for human solution comparison (not generation contracts)."""

DIAGNOSIS_BASES = (
    ("assumption", "Fachlich angenommene Ursache; empirischer Nachweis offen"),
    ("evidence", "Ursache anhand benannter Evidenz beurteilt; Grenzen beachten"),
)


def requires_decision_quality(process):
    return bool(process.outcome_contract_version and process.comparison_contract_version)


COVERAGE_LABEL = "Abdeckung von Engpass/Ursache oder begründetem Potenzial"
NON_TECHNICAL_TYPES = frozenset({"organizational", "no_tech"})
TECHNICAL_TEXT_FIELDS = ("data_requirements", "application_impact", "integration_impact")
TECHNICAL_FIELDS = (*TECHNICAL_TEXT_FIELDS, "integration_effort")
COMMON_TEXT_FIELDS = (
    "description",
    "expected_value",
    "bottleneck_coverage",
    "risks",
    "architecture_fit",
)


def required_assessment_fields(option_type):
    fields = (*COMMON_TEXT_FIELDS, "feasibility", "time_to_value")
    if option_type not in NON_TECHNICAL_TYPES:
        fields += TECHNICAL_FIELDS
    return fields


def missing_assessment_fields(option_type, values):
    return [
        field
        for field in required_assessment_fields(option_type)
        if not str(values.get(field) or "").strip()
        or (
            field in {"feasibility", "integration_effort", "time_to_value"}
            and values.get(field) == "not_assessed"
        )
    ]


def comparison_field_label(model, field):
    return (
        COVERAGE_LABEL
        if field == "bottleneck_coverage"
        else str(model._meta.get_field(field).verbose_name)
    )


def technical_field_not_applicable(option_type, field, value):
    return (
        option_type in NON_TECHNICAL_TYPES
        and field in (*TECHNICAL_FIELDS, "technology_constraints")
        and (
            not str(value or "").strip()
            or (field == "integration_effort" and value == "not_assessed")
        )
    )


def assessment_field_error(model, field):
    label = comparison_field_label(model, field)
    if field in {"feasibility", "integration_effort"}:
        return f"{label} muss für den Status 'Bewertet' bewertet sein."
    if field == "time_to_value":
        return (
            "Time-to-Value muss für den Status 'Bewertet' eingeordnet werden; "
            "'Unbekannt' ist zulässig, wenn keine belastbare Zeitangabe vorliegt."
        )
    return f"{label} ist für den Status 'Bewertet' erforderlich."
