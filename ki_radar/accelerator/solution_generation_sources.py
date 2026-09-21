SOURCE_SCHEMA_VERSION = "block7_sources_v1"
VALIDATION_CURRENT = "current_validated"
VALIDATION_MISSING = "not_validated"
VALIDATION_STALE = "validation_stale"
PROCESS_STATUS_REVIEW_REQUIRED = "review_required"

REQUIRED_PROCESS_FIELDS = (
    "name",
    "scope_start",
    "scope_end",
    "trigger",
    "outcome",
    "current_flow",
    "roles",
    "systems",
    "data_objects",
    "bottlenecks",
    "baseline_metrics",
)

OPTIONAL_PROCESS_FIELDS = (
    "business_rules",
    "handoffs",
    "exceptions",
    "target_state_principles",
    "diagnostic_observations",
    "cause_hypotheses",
    "confirmed_causes",
    "constraints",
)

PROCESS_SOURCE_FIELDS = REQUIRED_PROCESS_FIELDS + OPTIONAL_PROCESS_FIELDS
ALLOWED_SOURCE_IDS = tuple(
    [f"process.{field_name}" for field_name in PROCESS_SOURCE_FIELDS]
    + ["stage.name", "value_stream.constraints"]
)


class SolutionGenerationReadinessError(RuntimeError):
    def __init__(self, missing_fields: tuple[str, ...]) -> None:
        self.missing_fields = missing_fields
        labels = ", ".join(missing_fields)
        super().__init__(f"Die Prozessanalyse ist für die Generierung unvollständig: {labels}.")


class SourceFact:
    __slots__ = ("field", "source_id", "value")

    def __init__(self, *, source_id: str, field: str, value: str) -> None:
        self.source_id = source_id
        self.field = field
        self.value = value

    def as_dict(self) -> dict[str, str]:
        return {
            "source_id": self.source_id,
            "field": self.field,
            "value": self.value,
        }


class SolutionGenerationSourceContext:
    __slots__ = (
        "facts",
        "missing_required",
        "process_analysis_id",
        "process_version",
        "source_hash",
        "validation_state",
    )

    def __init__(
        self,
        *,
        process_analysis_id: str,
        process_version: int,
        validation_state: str,
        source_hash: str,
        missing_required: tuple[str, ...],
        facts: tuple[SourceFact, ...],
    ) -> None:
        self.process_analysis_id = process_analysis_id
        self.process_version = process_version
        self.validation_state = validation_state
        self.source_hash = source_hash
        self.missing_required = missing_required
        self.facts = facts

    @property
    def is_ready(self) -> bool:
        return not self.missing_required

    def provider_payload(self) -> dict[str, object]:
        return {
            "source_schema_version": SOURCE_SCHEMA_VERSION,
            "process_version": self.process_version,
            "validation_state": self.validation_state,
            "facts": [fact.as_dict() for fact in self.facts],
        }


def _clean_text(value: object) -> str:
    return str(value or "").strip()


def _validation_state(process_analysis) -> str:
    validations = process_analysis.validations.all()
    if process_analysis.status == PROCESS_STATUS_REVIEW_REQUIRED:
        return VALIDATION_STALE if validations.exists() else VALIDATION_MISSING
    if validations.filter(process_version=process_analysis.version).exists():
        return VALIDATION_CURRENT
    if validations.exists():
        return VALIDATION_STALE
    return VALIDATION_MISSING


def _source_facts(process_analysis) -> tuple[SourceFact, ...]:
    facts: list[SourceFact] = []
    for field_name in PROCESS_SOURCE_FIELDS:
        value = _clean_text(getattr(process_analysis, field_name))
        if value:
            facts.append(
                SourceFact(
                    source_id=f"process.{field_name}",
                    field=field_name,
                    value=value,
                )
            )

    stage_name = _clean_text(process_analysis.stage.name)
    if stage_name:
        facts.append(SourceFact(source_id="stage.name", field="name", value=stage_name))

    constraints = _clean_text(process_analysis.stage.value_stream.constraints)
    if constraints:
        facts.append(
            SourceFact(
                source_id="value_stream.constraints",
                field="constraints",
                value=constraints,
            )
        )
    return tuple(facts)


def _source_hash(*, process_analysis, facts: tuple[SourceFact, ...]) -> str:
    import hashlib
    import json

    document = {
        "process_analysis_id": str(process_analysis.pk),
        "process_version": process_analysis.version,
        "facts": [fact.as_dict() for fact in facts],
    }
    serialized = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def build_solution_generation_source_context(process_analysis) -> SolutionGenerationSourceContext:
    missing_required = tuple(
        field_name
        for field_name in REQUIRED_PROCESS_FIELDS
        if not _clean_text(getattr(process_analysis, field_name))
    )
    facts = _source_facts(process_analysis)
    return SolutionGenerationSourceContext(
        process_analysis_id=str(process_analysis.pk),
        process_version=process_analysis.version,
        validation_state=_validation_state(process_analysis),
        source_hash=_source_hash(process_analysis=process_analysis, facts=facts),
        missing_required=missing_required,
        facts=facts,
    )


def require_solution_generation_ready(process_analysis) -> SolutionGenerationSourceContext:
    context = build_solution_generation_source_context(process_analysis)
    if not context.is_ready:
        raise SolutionGenerationReadinessError(context.missing_required)
    return context
