from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class StructuredContractError(ValueError):
    """Raised when a provider suggestion is outside the Block-6 V1 contract."""


class StructuredCandidateKind(StrEnum):
    METRIC_SET = "metric_set"
    VALUE_STREAM_STAGE = "value_stream_stage"
    PROCESS_ANALYSIS = "process_analysis"


class StructuredFieldType(StrEnum):
    TEXT = "text"
    INTEGER = "integer"
    DECIMAL = "decimal"
    ENUM = "enum"


@dataclass(frozen=True)
class StructuredFieldSpec:
    target_path: str
    candidate_kind: StructuredCandidateKind
    model_field: str
    field_type: StructuredFieldType
    repeated: bool = False
    required_for_object: bool = False


METRIC_FIELD_SPECS = (
    StructuredFieldSpec(
        "use_case.metric.name",
        StructuredCandidateKind.METRIC_SET,
        "metric_name",
        StructuredFieldType.TEXT,
    ),
    StructuredFieldSpec(
        "use_case.metric.type",
        StructuredCandidateKind.METRIC_SET,
        "metric_type",
        StructuredFieldType.ENUM,
    ),
    StructuredFieldSpec(
        "use_case.metric.direction",
        StructuredCandidateKind.METRIC_SET,
        "metric_direction",
        StructuredFieldType.ENUM,
    ),
    StructuredFieldSpec(
        "use_case.metric.unit",
        StructuredCandidateKind.METRIC_SET,
        "metric_unit",
        StructuredFieldType.TEXT,
    ),
    StructuredFieldSpec(
        "use_case.metric.baseline",
        StructuredCandidateKind.METRIC_SET,
        "metric_baseline",
        StructuredFieldType.DECIMAL,
    ),
    StructuredFieldSpec(
        "use_case.metric.target",
        StructuredCandidateKind.METRIC_SET,
        "metric_target",
        StructuredFieldType.DECIMAL,
    ),
    StructuredFieldSpec(
        "use_case.metric.measurement_method",
        StructuredCandidateKind.METRIC_SET,
        "metric_measurement_method",
        StructuredFieldType.TEXT,
    ),
)

STAGE_FIELD_SPECS = (
    StructuredFieldSpec(
        "value_stream.stages[].sequence",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "sequence",
        StructuredFieldType.INTEGER,
        repeated=True,
        required_for_object=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].name",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "name",
        StructuredFieldType.TEXT,
        repeated=True,
        required_for_object=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].description",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "description",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].actors",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "actors",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].systems",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "systems",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].documents",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "documents",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].pain_points",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "pain_points",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
    StructuredFieldSpec(
        "value_stream.stages[].baseline_metrics",
        StructuredCandidateKind.VALUE_STREAM_STAGE,
        "baseline_metrics",
        StructuredFieldType.TEXT,
        repeated=True,
    ),
)

_PROCESS_FIELDS = (
    ("name", True),
    ("scope_start", True),
    ("scope_end", True),
    ("trigger", True),
    ("outcome", True),
    ("current_flow", True),
    ("roles", True),
    ("systems", True),
    ("data_objects", True),
    ("business_rules", False),
    ("handoffs", False),
    ("bottlenecks", True),
    ("exceptions", False),
    ("baseline_metrics", True),
    ("target_state_principles", False),
)
PROCESS_ANALYSIS_FIELD_SPECS = tuple(
    StructuredFieldSpec(
        f"process_analysis.{field_name}",
        StructuredCandidateKind.PROCESS_ANALYSIS,
        field_name,
        StructuredFieldType.TEXT,
        required_for_object=required,
    )
    for field_name, required in _PROCESS_FIELDS
)

STRUCTURED_FIELD_SPECS = {
    spec.target_path: spec
    for spec in (*METRIC_FIELD_SPECS, *STAGE_FIELD_SPECS, *PROCESS_ANALYSIS_FIELD_SPECS)
}
ACTIVE_ENUM_TARGETS = frozenset(
    {
        "use_case.metric.type",
        "use_case.metric.direction",
    }
)
UNSUPPORTED_PROVIDER_TYPES = frozenset({"boolean", "date", "uuid", "reference"})
LOCAL_KEY_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CASCADE_INVALIDATING_STATES = frozenset(
    {
        "rejected",
        "ambiguous",
        "invalid",
        "conflict",
        "superseded",
        "stale",
        "failed",
    }
)


def structured_field_spec(
    *,
    target_path: str,
    provider_field_type: str,
) -> StructuredFieldSpec:
    """Return an explicit V1 specification or fail closed.

    A provider field type never grants write access by itself.
    """

    spec = STRUCTURED_FIELD_SPECS.get(target_path)
    if spec is None:
        raise StructuredContractError("Der Zielpfad ist nicht für Block 6 V1 freigegeben.")
    if provider_field_type != spec.field_type.value:
        raise StructuredContractError(
            "Der Provider-Feldtyp stimmt nicht mit dem freigegebenen Zielpfad überein."
        )
    return spec


def validate_local_key(local_key: str) -> str:
    normalized = str(local_key).strip()
    if not normalized or LOCAL_KEY_PATTERN.fullmatch(normalized) is None:
        raise StructuredContractError("Der lokale Objektschlüssel ist ungültig.")
    return normalized


def process_dependency_key(*, referenced_stage_key: str) -> str:
    """Validate the only local object dependency supported by Block 6 V1."""

    return validate_local_key(referenced_stage_key)


def dependency_is_invalidating(state: str) -> bool:
    return state in CASCADE_INVALIDATING_STATES
