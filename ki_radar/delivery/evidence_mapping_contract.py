from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class TransformKind(StrEnum):
    DIRECT = "direct"
    PRIORITY_FIRST_NON_EMPTY = "priority_first_non_empty"
    COMPOSE_STRUCTURED = "compose_structured"


class SourceVersionRule(StrEnum):
    UPDATED_AT = "updated_at"
    PROCESS_VERSION = "process_version"
    ASSESSMENT_VERSION = "assessment_version"
    IMMUTABLE_DECISION_SNAPSHOT = "immutable_decision_snapshot"
    FINAL_APPROVAL_SNAPSHOT = "final_approval_snapshot"


class MultiSourcePolicy(StrEnum):
    SINGLE = "single"
    PRIORITY = "priority"
    COMPOSE = "compose"


class GapPolicy(StrEnum):
    VISIBLE_GAP = "visible_gap"


class ConflictPolicy(StrEnum):
    THREE_STATE_NO_OVERWRITE = "three_state_no_overwrite"


class LLMRestTask(StrEnum):
    LANGUAGE_COMPACTION = "language_compaction"


@dataclass(frozen=True, slots=True)
class SourceRule:
    kind: str
    fields: tuple[str, ...]
    version_rule: SourceVersionRule
    priority: int = 1
    required_fields: tuple[str, ...] = ()
    constraint: str = ""


@dataclass(frozen=True, slots=True)
class DeliveryFieldMappingSpec:
    target_field: str
    section_key: str
    sources: tuple[SourceRule, ...]
    transform: TransformKind
    multi_source_policy: MultiSourcePolicy
    gap_policy: GapPolicy = GapPolicy.VISIBLE_GAP
    conflict_policy: ConflictPolicy = ConflictPolicy.THREE_STATE_NO_OVERWRITE
    llm_rest_task: LLMRestTask | None = None


MAPPING_CONTRACT_VERSION = "block8.v1"

# These fields stay deliberately outside automatic Block-8 filling unless a later
# version adds an explicit, reviewed evidence rule. Their current generic templates
# must not become evidence merely because they contain text.
FORBIDDEN_AUTOMATED_DELIVERY_FIELDS = frozenset(
    {
        "mvp_scope",
        "should_scope",
        "could_scope",
        "wont_this_time",
        "functional_requirements",
        "non_functional_requirements",
        "logging_and_audit",
        "test_scenarios",
        "dependencies",
        "assumptions",
        "architecture_decisions",
        "initial_backlog",
        "system_responsibilities",
        "data_quality_and_access",
        "integration_contracts",
        "integration_operations",
    }
)

# Historical system-generated working text. Block 8 may recognize these as legacy
# placeholders during refresh, but must never treat them as confirmed evidence.
LEGACY_PLACEHOLDER_FRAGMENTS = (
    "im delivery package konkretisieren",
    "konkretisieren.",
    "kleinsten ende-zu-ende-ablauf",
    "kernablauf aus dem freigegebenen use case umsetzen",
    "fachliche entscheidung und ergebnis nachvollziehbar darstellen",
    "happy path, datenfehler, fachliche ausnahme",
    "epic 1: kernprozess und nutzerfluss",
    "betriebsverantwortung festlegen",
    "menschliche kontrolle konkretisieren",
    "erfolgsmessung im delivery package konkretisieren",
    "führendes system/system of record: konkretisieren",
    "integrationsvertrag konkretisieren",
    "authentifizierung, auslöser/frequenz, fehlerbehandlung",
)

V1_DELIVERY_FIELD_MAPPINGS: dict[str, DeliveryFieldMappingSpec] = {
    "problem_context": DeliveryFieldMappingSpec(
        target_field="problem_context",
        section_key="problem_and_target",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("problem_statement",),
                required_fields=("problem_statement",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "target_outcome": DeliveryFieldMappingSpec(
        target_field="target_outcome",
        section_key="problem_and_target",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("expected_benefit",),
                required_fields=("expected_benefit",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "in_scope": DeliveryFieldMappingSpec(
        target_field="in_scope",
        section_key="scope_and_users",
        sources=(
            SourceRule(
                kind="value_stream",
                fields=("scope_in",),
                required_fields=("scope_in",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=1,
            ),
            SourceRule(
                kind="use_case",
                fields=("summary",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=2,
                constraint="fallback_when_no_architecture_value_stream",
            ),
            SourceRule(
                kind="use_case",
                fields=("affected_process",),
                required_fields=("affected_process",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=3,
                constraint="fallback_when_no_architecture_value_stream",
            ),
        ),
        transform=TransformKind.PRIORITY_FIRST_NON_EMPTY,
        multi_source_policy=MultiSourcePolicy.PRIORITY,
    ),
    "out_of_scope": DeliveryFieldMappingSpec(
        target_field="out_of_scope",
        section_key="scope_and_users",
        sources=(
            SourceRule(
                kind="value_stream",
                fields=("scope_out",),
                required_fields=("scope_out",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "users_and_scenarios": DeliveryFieldMappingSpec(
        target_field="users_and_scenarios",
        section_key="scope_and_users",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("intended_users",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=1,
            ),
            SourceRule(
                kind="use_case",
                fields=("target_users",),
                required_fields=("target_users",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=2,
            ),
        ),
        transform=TransformKind.PRIORITY_FIRST_NON_EMPTY,
        multi_source_policy=MultiSourcePolicy.PRIORITY,
    ),
    "solution_outline": DeliveryFieldMappingSpec(
        target_field="solution_outline",
        section_key="solution_direction",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("intended_purpose",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=1,
            ),
            SourceRule(
                kind="use_case",
                fields=("summary",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=2,
            ),
            SourceRule(
                kind="solution_selection_snapshot",
                fields=("description",),
                version_rule=SourceVersionRule.IMMUTABLE_DECISION_SNAPSHOT,
                priority=3,
                constraint="selected_solution_only",
            ),
        ),
        transform=TransformKind.PRIORITY_FIRST_NON_EMPTY,
        multi_source_policy=MultiSourcePolicy.PRIORITY,
    ),
    "system_context": DeliveryFieldMappingSpec(
        target_field="system_context",
        section_key="architecture_and_data",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("source_systems",),
                required_fields=("source_systems",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "data_context": DeliveryFieldMappingSpec(
        target_field="data_context",
        section_key="architecture_and_data",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("data_sources",),
                required_fields=("data_sources",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "integrations": DeliveryFieldMappingSpec(
        target_field="integrations",
        section_key="architecture_and_data",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("interface_description",),
                required_fields=("interface_description",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "human_oversight": DeliveryFieldMappingSpec(
        target_field="human_oversight",
        section_key="requirements_and_governance",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("human_oversight",),
                required_fields=("human_oversight",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "operations_and_support": DeliveryFieldMappingSpec(
        target_field="operations_and_support",
        section_key="requirements_and_governance",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("support_responsibility",),
                required_fields=("support_responsibility",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "measurement_plan": DeliveryFieldMappingSpec(
        target_field="measurement_plan",
        section_key="acceptance_and_measurement",
        sources=(
            SourceRule(
                kind="use_case",
                fields=(
                    "metric_name",
                    "metric_type",
                    "metric_direction",
                    "metric_unit",
                    "metric_baseline",
                    "metric_target",
                    "metric_measurement_method",
                    "metric_measurement_period",
                ),
                required_fields=(
                    "metric_name",
                    "metric_baseline",
                    "metric_target",
                    "metric_measurement_method",
                ),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
        ),
        transform=TransformKind.COMPOSE_STRUCTURED,
        multi_source_policy=MultiSourcePolicy.COMPOSE,
    ),
    "acceptance_criteria": DeliveryFieldMappingSpec(
        target_field="acceptance_criteria",
        section_key="acceptance_and_measurement",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("success_criterion",),
                version_rule=SourceVersionRule.UPDATED_AT,
            ),
            SourceRule(
                kind="use_case",
                fields=(
                    "metric_name",
                    "metric_direction",
                    "metric_unit",
                    "metric_baseline",
                    "metric_target",
                ),
                required_fields=("metric_name", "metric_target"),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=2,
            ),
        ),
        transform=TransformKind.COMPOSE_STRUCTURED,
        multi_source_policy=MultiSourcePolicy.COMPOSE,
        llm_rest_task=LLMRestTask.LANGUAGE_COMPACTION,
    ),
    "risks": DeliveryFieldMappingSpec(
        target_field="risks",
        section_key="delivery_control",
        sources=(
            SourceRule(
                kind="solution_selection_snapshot",
                fields=("risks",),
                required_fields=("risks",),
                version_rule=SourceVersionRule.IMMUTABLE_DECISION_SNAPSHOT,
                constraint="selected_solution_only",
            ),
        ),
        transform=TransformKind.DIRECT,
        multi_source_policy=MultiSourcePolicy.SINGLE,
    ),
    "handover_notes": DeliveryFieldMappingSpec(
        target_field="handover_notes",
        section_key="delivery_control",
        sources=(
            SourceRule(
                kind="approval_decision",
                fields=(
                    "decision_status",
                    "rationale",
                    "conditions",
                    "condition_owner_id",
                    "condition_due_date",
                    "finalized_at",
                ),
                required_fields=("decision_status", "rationale", "finalized_at"),
                version_rule=SourceVersionRule.FINAL_APPROVAL_SNAPSHOT,
                constraint="read_existing_final_positive_approval_only",
            ),
        ),
        transform=TransformKind.COMPOSE_STRUCTURED,
        multi_source_policy=MultiSourcePolicy.COMPOSE,
    ),
    "system_landscape": DeliveryFieldMappingSpec(
        target_field="system_landscape",
        section_key="architecture_and_data",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("source_systems",),
                required_fields=("source_systems",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=1,
            ),
            SourceRule(
                kind="solution_selection_snapshot",
                fields=("application_impact",),
                version_rule=SourceVersionRule.IMMUTABLE_DECISION_SNAPSHOT,
                priority=2,
                constraint="selected_solution_only",
            ),
        ),
        transform=TransformKind.COMPOSE_STRUCTURED,
        multi_source_policy=MultiSourcePolicy.COMPOSE,
        llm_rest_task=LLMRestTask.LANGUAGE_COMPACTION,
    ),
    "data_flows": DeliveryFieldMappingSpec(
        target_field="data_flows",
        section_key="architecture_and_data",
        sources=(
            SourceRule(
                kind="use_case",
                fields=("data_sources", "interface_description"),
                required_fields=("data_sources",),
                version_rule=SourceVersionRule.UPDATED_AT,
                priority=1,
            ),
            SourceRule(
                kind="solution_selection_snapshot",
                fields=("integration_impact",),
                version_rule=SourceVersionRule.IMMUTABLE_DECISION_SNAPSHOT,
                priority=2,
                constraint="selected_solution_only",
            ),
        ),
        transform=TransformKind.COMPOSE_STRUCTURED,
        multi_source_policy=MultiSourcePolicy.COMPOSE,
    ),
}


def mapping_spec(target_field: str) -> DeliveryFieldMappingSpec:
    """Return a statically approved Block-8 mapping or fail closed."""

    try:
        return V1_DELIVERY_FIELD_MAPPINGS[target_field]
    except KeyError as exc:
        raise ValueError(
            f"Delivery-Feld ist für Block 8 nicht freigegeben: {target_field}"
        ) from exc
