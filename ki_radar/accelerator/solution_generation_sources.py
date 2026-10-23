LEGACY_SOURCE_SCHEMA_VERSION = "block7_sources_v1"
SOURCE_SCHEMA_VERSION = "block7_sources_v2"
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
INITIATIVE_SOURCE_FIELDS = (
    "business_outcome",
    "contribution",
    "impact_hypothesis",
    "evaluation_criteria",
    "evidence_level",
    "outcome_revision",
)
ALLOWED_SOURCE_IDS = tuple(
    [f"process.{field_name}" for field_name in PROCESS_SOURCE_FIELDS]
    + ["stage.name", "value_stream.constraints"]
    + [f"initiative.{name}" for name in INITIATIVE_SOURCE_FIELDS]
)
LEGACY_ALLOWED_SOURCE_IDS = ALLOWED_SOURCE_IDS
DISCOVERY_SOURCE_FIELDS = (
    "id",
    "revision",
    "path",
    "origin_basis",
    "strategic_potential",
    "validation_step",
)
ALLOWED_SOURCE_IDS += tuple(f"discovery_path.{name}" for name in DISCOVERY_SOURCE_FIELDS)


def source_version_for_run(run) -> str:
    versions = (run.generation_schema_version, run.prompt_version)
    if versions in {("1.0", "1.2"), ("1.0", "1.3")}:
        return LEGACY_SOURCE_SCHEMA_VERSION
    if versions == ("2.0", "2.0"):
        return SOURCE_SCHEMA_VERSION
    raise ValueError("Nicht unterstützte Generator-Vertragsversionen.")


def allowed_source_ids(version: str) -> tuple[str, ...]:
    if version == LEGACY_SOURCE_SCHEMA_VERSION:
        return LEGACY_ALLOWED_SOURCE_IDS
    if version == SOURCE_SCHEMA_VERSION:
        return ALLOWED_SOURCE_IDS
    raise ValueError("Nicht unterstützte Quellenvertragsversion.")


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
        "source_schema_version",
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
        source_schema_version: str = LEGACY_SOURCE_SCHEMA_VERSION,
    ) -> None:
        self.process_analysis_id = process_analysis_id
        self.process_version = process_version
        self.validation_state = validation_state
        self.source_hash = source_hash
        self.missing_required = missing_required
        self.facts = facts
        allowed_source_ids(source_schema_version)
        self.source_schema_version = source_schema_version

    @property
    def generation_versions(self) -> tuple[str, str]:
        return (
            ("1.0", "1.3")
            if self.source_schema_version == LEGACY_SOURCE_SCHEMA_VERSION
            else ("2.0", "2.0")
        )

    @property
    def is_ready(self) -> bool:
        return not self.missing_required

    def provider_payload(self) -> dict[str, object]:
        return {
            "source_schema_version": self.source_schema_version,
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
    if process_analysis.initiative_id:
        for name in INITIATIVE_SOURCE_FIELDS:
            value = _clean_text(getattr(process_analysis.initiative, name))
            if value:
                facts.append(SourceFact(source_id=f"initiative.{name}", field=name, value=value))
    return tuple(facts)


def _source_hash(
    *,
    process_analysis,
    facts: tuple[SourceFact, ...],
    source_schema_version=LEGACY_SOURCE_SCHEMA_VERSION,
) -> str:
    import hashlib
    import json

    document = {
        "process_analysis_id": str(process_analysis.pk),
        "process_version": process_analysis.version,
        "facts": [fact.as_dict() for fact in facts],
    }
    if source_schema_version != LEGACY_SOURCE_SCHEMA_VERSION:
        document["source_schema_version"] = source_schema_version
    serialized = json.dumps(
        document,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def build_solution_generation_source_context(
    process_analysis, *, source_schema_version=SOURCE_SCHEMA_VERSION
) -> SolutionGenerationSourceContext:
    allowed_source_ids(source_schema_version)
    required = REQUIRED_PROCESS_FIELDS
    facts = _source_facts(process_analysis)
    path_missing = ()
    if source_schema_version == SOURCE_SCHEMA_VERSION:
        decision = process_analysis.discovery_path_decisions.order_by("-revision").first()
        if decision is not None:
            facts += tuple(
                SourceFact(
                    source_id=f"discovery_path.{name}",
                    field=name,
                    value=_clean_text(getattr(decision, name)),
                )
                for name in DISCOVERY_SOURCE_FIELDS
                if _clean_text(getattr(decision, name))
            )
        if decision is not None and decision.path == "strategic":
            required = tuple(
                name for name in required if name not in {"bottlenecks", "baseline_metrics"}
            )
            path_missing = tuple(
                f"discovery_path.{name}"
                for name in ("origin_basis", "strategic_potential", "validation_step")
                if not _clean_text(getattr(decision, name))
            )
    missing_required = tuple(
        field_name
        for field_name in required
        if not _clean_text(getattr(process_analysis, field_name))
    )
    return SolutionGenerationSourceContext(
        process_analysis_id=str(process_analysis.pk),
        process_version=process_analysis.version,
        validation_state=_validation_state(process_analysis),
        source_hash=_source_hash(
            process_analysis=process_analysis,
            facts=facts,
            source_schema_version=source_schema_version,
        ),
        source_schema_version=source_schema_version,
        missing_required=missing_required + path_missing,
        facts=facts,
    )


def require_solution_generation_ready(process_analysis) -> SolutionGenerationSourceContext:
    context = build_solution_generation_source_context(process_analysis)
    if not context.is_ready:
        raise SolutionGenerationReadinessError(context.missing_required)
    return context
