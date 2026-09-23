from __future__ import annotations

import hashlib
import json
import os
import platform
import uuid
from collections.abc import Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

import django
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, connection, transaction
from django.db.models import Max
from django.utils import timezone

from ki_radar.architecture.models import ProcessAnalysis, SolutionOption
from ki_radar.architecture.permissions import can_edit_value_stream

from .investigation_models import (
    InvestigationBriefRevision,
    InvestigationEvidenceCampaign,
    InvestigationInputRevision,
    InvestigationRun,
    InvestigationSource,
    InvestigationSourceSnapshot,
    InvestigationStep,
    InvestigationToolResult,
)
from .investigation_policy import (
    POLICY_VERSION,
    PolicyCheck,
    PolicyDecision,
    PolicyState,
    VerifierState,
    evaluate_policy,
)
from .investigation_prompts import (
    PLANNER_INSTRUCTION,
    PLANNER_PROMPT_VERSION,
    PLANNER_SCHEMA_VERSION,
    PLANNER_TOOL_NAMES,
    VERIFIER_INSTRUCTION,
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SCHEMA_VERSION,
)
from .investigation_tools import (
    TOOL_VERSION,
    CompareGroupsRequest,
    CsvProfileRequest,
    FilterSpec,
    ReadRequest,
    SearchRequest,
    _authorized_snapshot,
    compare_groups,
    list_sources,
    profile_csv,
    read_source,
    search_sources,
)

LOOP_VERSION = "vs1-agent-loop-v4"
BUDGET_VERSION = "vs1-budget-v4"
TRANSPORT_VERSION = "vs1-openrouter-deepinfra-fp8-v2"
# Verified for the pinned DeepInfra fp8 endpoint. This is an execution contract,
# not live provider metadata: changes require a deliberate transport revision.
ENDPOINT_CAPABILITY = {
    "version": TRANSPORT_VERSION,
    "model": "deepseek/deepseek-v4.1-flash",
    "provider": "deepinfra/fp8",
    "context_tokens": 1_048_576,
    "completion_tokens": 131_072,
}
# Strict planner JSON carries complete claims/brief; the verifier returns findings
# and references. Hidden medium reasoning also consumes completion tokens. A
# 4096-token completion yielded no visible content, so 8192 is the minimum
# viable window for reasoning plus structured output, never a per-call ceiling.
MIN_PLANNER_COMPLETION_TOKENS = 8_192
MIN_VERIFIER_COMPLETION_TOKENS = 8_192
MIN_PLANNER_TIMEOUT_SECONDS = 60
MIN_VERIFIER_TIMEOUT_SECONDS = 75
FIXED_ROUTE_VERSION = "vs1-fixed-route-v1"
TOOL_SCHEMA_VERSION = "vs1-tool-schema-v1"
ISSUE4_INVESTIGATION_PROVIDER_POLICY = {
    "zdr": True,
    "data_collection": "deny",
    "order": ["deepinfra/fp8"],
    "allow_fallbacks": False,
    "require_parameters": True,
}

DEFAULT_BUDGET = {
    "max_tool_calls": 12,
    # Up to 10 planner attempts plus two verifier rounds
    # (initial verification + one repair cycle), each verifier round allowing
    # the existing two-call read-and-recheck path.
    "max_model_calls": 14,
    "max_verifier_calls": 4,
    # Restore the original v1 per-call input/runtime headroom (60k/8 and
    # 600s/8), which budget v2 did not scale when model calls increased.
    # One run can use one endpoint-sized output window, but cannot claim an
    # entire campaign. Four verifier calls retain one viable response each.
    "max_runtime_seconds": 1_050,
    "max_input_tokens": 105_000,
    "max_output_tokens": 131_072,
    "verifier_reserved_model_calls": 4,
    "verifier_reserved_input_tokens": 20_000,
    "verifier_reserved_output_tokens": 4 * MIN_VERIFIER_COMPLETION_TOKENS,
    "verifier_reserved_seconds": 300,
    "max_verifier_reads": 12,
    "max_repair_cycles": 1,
}
USAGE_KEYS = (
    "tool_calls",
    "model_calls",
    "verifier_calls",
    "input_tokens",
    "output_tokens",
    "verifier_reads",
    "provider_attempts",
)
ALLOWED_TOOLS = frozenset(PLANNER_TOOL_NAMES)
TRANSIENT_TOOL_CODES = frozenset({"source_path_unreadable"})


class InvestigationRunError(RuntimeError):
    def __init__(self, message: str, *, code: str, existing_run_id=None) -> None:
        super().__init__(message)
        self.code = code
        self.existing_run_id = existing_run_id


@dataclass(frozen=True)
class StartInvestigationRequest:
    snapshot_id: uuid.UUID | str
    idempotency_key: str
    evidence_campaign_id: uuid.UUID | str | None = None
    execution_mode: str = "adaptive"
    evidence_metadata: Mapping[str, Any] | None = None
    decision_brief_required: bool = False


@dataclass(frozen=True)
class RunHandle:
    run_id: uuid.UUID
    executor_token: uuid.UUID
    executor_generation: int
    status: str
    reused: bool = False


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def content_hash(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, uuid.UUID):
        return str(value)
    return value


def runtime_version_snapshot() -> dict[str, object]:
    base_dir = Path(getattr(settings, "BASE_DIR", "."))
    lock_hashes: dict[str, str] = {}
    for name in ("uv.lock", "pyproject.toml"):
        path = base_dir / name
        if path.is_file():
            try:
                lock_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                lock_hashes[name] = "unreadable"

    postgres_version: str | int = "unknown"
    if connection.vendor == "postgresql":
        try:
            postgres_version = connection.pg_version
        except Exception:
            postgres_version = "unknown"

    return {
        "code_revision": (
            os.getenv("RENDER_GIT_COMMIT")
            or os.getenv("GIT_COMMIT")
            or os.getenv("SOURCE_VERSION")
            or "unknown"
        ),
        "python": platform.python_version(),
        "django": django.get_version(),
        "postgresql": postgres_version,
        "dependency_lock_hashes": lock_hashes,
    }


def normalize_idempotency_key(value: object) -> str:
    key = str(value or "").strip()
    if not key or len(key) > 64:
        raise InvestigationRunError(
            "Der Idempotenzschlüssel muss 1 bis 64 Zeichen enthalten.",
            code="invalid_idempotency_key",
        )
    return key


def budget_from_snapshot(run_limits: Mapping[str, int]) -> dict[str, int]:
    budget = dict(DEFAULT_BUDGET)
    for key, value in dict(run_limits or {}).items():
        if key not in budget:
            raise InvestigationRunError(f"Unbekanntes Run-Limit: {key}.", code="invalid_budget")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise InvestigationRunError(
                "Run-Limits müssen nichtnegative Ganzzahlen sein.",
                code="invalid_budget",
            )
        if value > budget[key]:
            raise InvestigationRunError(
                f"Run-Limit {key} darf die VS1-Obergrenze nicht überschreiten.",
                code="budget_expansion_forbidden",
            )
        budget[key] = value
    if budget["max_verifier_calls"] > budget["max_model_calls"]:
        raise InvestigationRunError(
            "Verifier-Limit überschreitet Modell-Limit.",
            code="invalid_budget",
        )
    return budget


def initial_usage() -> dict[str, int]:
    return {key: 0 for key in USAGE_KEYS}


def contract_payload(
    snapshot: InvestigationSourceSnapshot,
    budget: Mapping[str, int],
) -> dict[str, object]:
    return {
        "decision_question": snapshot.decision_question,
        "process_analysis_id": str(snapshot.process_analysis_id),
        "process_version": snapshot.process_version,
        "manifest_hash": snapshot.manifest_hash,
        "policy_version": POLICY_VERSION,
        "budget_version": BUDGET_VERSION,
        "budget_limits": dict(budget),
        "required_areas": [
            "problem_context",
            "competing_hypotheses",
            "solution_options",
            "constraints_risks",
            "recommendation_validation",
        ],
    }


def domain_materialization_snapshot(process: ProcessAnalysis) -> dict[str, object]:
    options = [
        {
            "id": str(option.pk),
            "updated_at": option.updated_at.isoformat(),
            "name": option.name,
            "option_type": option.option_type,
            "recommendation": option.recommendation,
            "evaluation_status": option.evaluation_status,
            "evidence_basis": option.evidence_basis,
            "description": option.description,
            "expected_value": option.expected_value,
            "bottleneck_coverage": option.bottleneck_coverage,
            "data_requirements": option.data_requirements,
            "application_impact": option.application_impact,
            "integration_impact": option.integration_impact,
            "risks": option.risks,
            "architecture_fit": option.architecture_fit,
        }
        for option in process.solution_options.order_by("id")
    ]
    payload = {
        "process": {
            "id": str(process.pk),
            "version": process.version,
            "updated_at": process.updated_at.isoformat(),
            "diagnostic_observations": process.diagnostic_observations,
            "cause_hypotheses": process.cause_hypotheses,
            "baseline_metrics": process.baseline_metrics,
        },
        "solution_options": options,
    }
    return {**payload, "content_hash": content_hash(payload)}


def base_execution_snapshot(
    snapshot: InvestigationSourceSnapshot,
    budget: Mapping[str, int],
    *,
    process: ProcessAnalysis,
    execution_mode: str = "adaptive",
    evidence_campaign: InvestigationEvidenceCampaign | None = None,
    evidence_metadata: Mapping[str, Any] | None = None,
    decision_brief_required: bool = False,
) -> dict[str, object]:
    return {
        "runtime": runtime_version_snapshot(),
        "loop_version": LOOP_VERSION,
        "policy_version": POLICY_VERSION,
        "budget_version": BUDGET_VERSION,
        "budget_limits": dict(budget),
        "execution_mode": execution_mode,
        "fixed_route_version": (FIXED_ROUTE_VERSION if execution_mode == "fixed" else None),
        "evidence_metadata": dict(evidence_metadata or {}),
        "decision_brief_required": bool(decision_brief_required),
        "evidence_campaign": (
            {
                "id": str(evidence_campaign.pk),
                "key": evidence_campaign.campaign_key,
                "revision": evidence_campaign.revision,
                "limits": dict(evidence_campaign.limits),
                "pricing_version": evidence_campaign.pricing_version,
                "currency": evidence_campaign.currency,
            }
            if evidence_campaign is not None
            else None
        ),
        "domain_materialization_base": domain_materialization_snapshot(process),
        "source_snapshot_id": str(snapshot.pk),
        "manifest_hash": snapshot.manifest_hash,
        "model_transport": {
            "provider": "openrouter",
            "provider_policy": dict(ISSUE4_INVESTIGATION_PROVIDER_POLICY),
            "requested_model": str(
                getattr(
                    settings,
                    "OPENROUTER_MODEL",
                    os.getenv("OPENROUTER_MODEL", ""),
                )
                or ""
            ),
            "temperature": 0.1,
            "reasoning_effort": "medium",
            "endpoint_capability": dict(ENDPOINT_CAPABILITY),
        },
        "process_version": snapshot.process_version,
        "planner": {
            "prompt_version": PLANNER_PROMPT_VERSION,
            "instruction_hash": hashlib.sha256(PLANNER_INSTRUCTION.encode("utf-8")).hexdigest(),
            "instruction_template": PLANNER_INSTRUCTION,
            "schema_version": PLANNER_SCHEMA_VERSION,
        },
        "verifier": {
            "prompt_version": VERIFIER_PROMPT_VERSION,
            "instruction_hash": hashlib.sha256(VERIFIER_INSTRUCTION.encode("utf-8")).hexdigest(),
            "instruction_template": VERIFIER_INSTRUCTION,
            "schema_version": VERIFIER_SCHEMA_VERSION,
        },
        "tools": {
            "allowlist": sorted(ALLOWED_TOOLS),
            "schema_version": TOOL_SCHEMA_VERSION,
            "implementation_version": TOOL_VERSION,
        },
    }


def input_revision_count(run: InvestigationRun) -> int:
    return run.input_revisions.count()


def register_hash(
    run: InvestigationRun,
    claims: list[dict[str, Any]] | None = None,
    relevance: Mapping[str, Any] | None = None,
) -> str:
    return content_hash(
        {
            "claims": run.claim_register if claims is None else claims,
            "source_relevance": run.source_relevance if relevance is None else relevance,
            "input_revision_count": input_revision_count(run),
        }
    )


def brief_hash(payload: Mapping[str, Any]) -> str:
    return content_hash(dict(payload))


def assert_actor_can_edit_run(actor, run: InvestigationRun) -> None:
    if actor is None or getattr(actor, "pk", None) is None:
        raise PermissionDenied("Der Investigation-Run ist nicht zugänglich.")
    process = run.process_analysis
    if process.status != ProcessAnalysis.Status.DRAFT:
        raise PermissionDenied("Der gebundene ProcessAnalysis-Entwurf ist nicht mehr bearbeitbar.")
    if not can_edit_value_stream(actor, process.stage.value_stream):
        raise PermissionDenied("Der Investigation-Run ist nicht zugänglich.")
    snapshot = run.source_snapshot
    if not snapshot.folder.is_active:
        raise PermissionDenied("Der Quellenraum wurde entzogen.")
    if snapshot.process_analysis_id != process.pk:
        raise PermissionDenied("Der Quellenraum gehört nicht zu diesem Fall.")


def locked_run(*, actor, run_id) -> InvestigationRun:
    try:
        run = (
            InvestigationRun.objects.select_for_update()
            .select_related(
                "process_analysis__stage__value_stream",
                "source_snapshot__folder",
            )
            .get(pk=run_id)
        )
    except (InvestigationRun.DoesNotExist, ValueError) as exc:
        raise PermissionDenied("Der Investigation-Run ist nicht zugänglich.") from exc
    assert_actor_can_edit_run(actor, run)
    return run


def assert_executor(run: InvestigationRun, executor_token) -> None:
    if str(run.executor_token) != str(executor_token):
        raise InvestigationRunError(
            "Der Ausführer ist veraltet; ein neuer Executor besitzt das Schreibrecht.",
            code="stale_executor",
        )


def assert_active(run: InvestigationRun) -> None:
    if run.status not in InvestigationRun.ACTIVE_STATUSES:
        raise InvestigationRunError(
            "Der Investigation-Run ist bereits beendet.",
            code="run_terminal",
        )


def elapsed_seconds(run: InvestigationRun) -> int:
    return max(0, int((timezone.now() - run.started_at).total_seconds()))


def _remaining_verifier_reserve(run: InvestigationRun) -> dict[str, int]:
    limits = run.budget_limits
    usage = run.usage
    max_verifier_calls = int(limits["max_verifier_calls"])
    remaining_verifier_calls = max(
        0,
        max_verifier_calls - int(usage.get("verifier_calls", 0)),
    )
    if max_verifier_calls <= 0 or remaining_verifier_calls <= 0:
        return {
            "model_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "seconds": 0,
        }

    def proportional_reserve(total: int) -> int:
        return (
            int(total) * remaining_verifier_calls + max_verifier_calls - 1
        ) // max_verifier_calls

    return {
        "model_calls": proportional_reserve(limits["verifier_reserved_model_calls"]),
        "input_tokens": proportional_reserve(limits["verifier_reserved_input_tokens"]),
        "output_tokens": proportional_reserve(limits["verifier_reserved_output_tokens"]),
        "seconds": proportional_reserve(limits["verifier_reserved_seconds"]),
    }


def budget_exhausted(run: InvestigationRun, *, reserve_verifier: bool = False) -> bool:
    limits = run.budget_limits
    usage = run.usage
    if elapsed_seconds(run) >= limits["max_runtime_seconds"]:
        return True
    if usage["tool_calls"] >= limits["max_tool_calls"]:
        return True
    if usage["model_calls"] >= limits["max_model_calls"]:
        return True
    if usage["input_tokens"] >= limits["max_input_tokens"]:
        return True
    if usage["output_tokens"] >= limits["max_output_tokens"]:
        return True
    if reserve_verifier:
        reserve = _remaining_verifier_reserve(run)
        return (
            limits["max_model_calls"] - usage["model_calls"] <= reserve["model_calls"]
            or limits["max_input_tokens"] - usage["input_tokens"] <= reserve["input_tokens"]
            or limits["max_output_tokens"] - usage["output_tokens"] <= reserve["output_tokens"]
            or limits["max_runtime_seconds"] - elapsed_seconds(run) <= reserve["seconds"]
        )
    return False


def start_investigation(*, actor, request: StartInvestigationRequest) -> RunHandle:
    key = normalize_idempotency_key(request.idempotency_key)
    snapshot = _authorized_snapshot(actor=actor, snapshot_id=request.snapshot_id)
    budget = budget_from_snapshot(snapshot.run_limits)

    with transaction.atomic():
        process = (
            ProcessAnalysis.objects.select_for_update()
            .select_related("stage__value_stream")
            .get(pk=snapshot.process_analysis_id)
        )
        if process.status != ProcessAnalysis.Status.DRAFT or not can_edit_value_stream(
            actor, process.stage.value_stream
        ):
            raise PermissionDenied("Die Prozessanalyse ist nicht bearbeitbar.")

        snapshot = InvestigationSourceSnapshot.objects.select_related(
            "folder",
            "process_analysis",
        ).get(pk=snapshot.pk)
        if not snapshot.folder.is_active:
            raise PermissionDenied("Der Quellenraum wurde vor dem Start entzogen.")
        if process.version != snapshot.process_version:
            raise InvestigationRunError(
                "Der Quellen-Snapshot gehört zu einer älteren ProcessAnalysis-Version.",
                code="process_version_conflict",
            )

        same = InvestigationRun.objects.filter(
            process_analysis=process,
            idempotency_key=key,
        ).first()
        if same is not None:
            assert_actor_can_edit_run(actor, same)
            return RunHandle(
                same.pk,
                same.executor_token,
                same.executor_generation,
                same.status,
                reused=True,
            )

        active = InvestigationRun.objects.filter(
            process_analysis=process,
            status__in=InvestigationRun.ACTIVE_STATUSES,
        ).first()
        if active is not None:
            raise InvestigationRunError(
                "Für diese ProcessAnalysis läuft bereits eine Untersuchung.",
                code="active_run_exists",
                existing_run_id=active.pk,
            )

        execution_mode = str(request.execution_mode or "adaptive").strip().casefold()
        if execution_mode not in {"adaptive", "fixed"}:
            raise InvestigationRunError(
                "Unbekannte Vergleichsstrecke.",
                code="invalid_execution_mode",
            )
        evidence_metadata = dict(request.evidence_metadata or {})
        evidence_campaign = None
        if request.evidence_campaign_id is not None:
            try:
                evidence_campaign = InvestigationEvidenceCampaign.objects.select_for_update().get(
                    pk=request.evidence_campaign_id
                )
            except (InvestigationEvidenceCampaign.DoesNotExist, ValueError) as exc:
                raise InvestigationRunError(
                    "Das konfigurierte Gesamtnachweisbudget ist nicht verfügbar.",
                    code="evidence_budget_required",
                ) from exc
            if evidence_campaign.process_analysis_id != process.pk:
                raise InvestigationRunError(
                    "Das Gesamtnachweisbudget gehört nicht zu diesem Fall.",
                    code="invalid_evidence_budget",
                )
        evidence_provider_mode = (
            str(evidence_metadata.get("provider_mode") or "").strip().casefold()
        )
        evidence_phase = (
            str(evidence_metadata.get("phase") or evidence_metadata.get("evidence_phase") or "")
            .strip()
            .casefold()
        )
        real_evidence_run = evidence_provider_mode == "real" and bool(evidence_phase)
        if (execution_mode == "fixed" or real_evidence_run) and evidence_campaign is None:
            raise InvestigationRunError(
                "Die reale Nachweisphase darf ohne explizites persistentes "
                "Gesamtbudget nicht starten.",
                code="evidence_budget_required",
            )

        execution_snapshot = base_execution_snapshot(
            snapshot,
            budget,
            process=process,
            execution_mode=execution_mode,
            evidence_campaign=evidence_campaign,
            evidence_metadata=evidence_metadata,
            decision_brief_required=bool(request.decision_brief_required),
        )
        try:
            with transaction.atomic():
                run = InvestigationRun.objects.create(
                    process_analysis=process,
                    source_snapshot=snapshot,
                    evidence_campaign=evidence_campaign,
                    execution_mode=execution_mode,
                    evidence_metadata=evidence_metadata,
                    requested_by=actor,
                    idempotency_key=key,
                    process_version=process.version,
                    decision_question=snapshot.decision_question,
                    contract_hash=content_hash(contract_payload(snapshot, budget)),
                    manifest_hash=snapshot.manifest_hash,
                    policy_version=POLICY_VERSION,
                    budget_version=BUDGET_VERSION,
                    loop_version=LOOP_VERSION,
                    budget_limits=budget,
                    usage=initial_usage(),
                    execution_snapshot=execution_snapshot,
                    claim_register=[],
                    source_relevance={},
                    register_hash=content_hash(
                        {
                            "claims": [],
                            "source_relevance": {},
                            "input_revision_count": 0,
                        }
                    ),
                    brief_payload={},
                    brief_hash=brief_hash({}),
                )
        except IntegrityError as exc:
            same = InvestigationRun.objects.filter(
                process_analysis=process,
                idempotency_key=key,
            ).first()
            if same is not None:
                return RunHandle(
                    same.pk,
                    same.executor_token,
                    same.executor_generation,
                    same.status,
                    reused=True,
                )
            active = InvestigationRun.objects.filter(
                process_analysis=process,
                status__in=InvestigationRun.ACTIVE_STATUSES,
            ).first()
            raise InvestigationRunError(
                "Für diese ProcessAnalysis wurde parallel bereits eine Untersuchung reserviert.",
                code="active_run_exists",
                existing_run_id=active.pk if active else None,
            ) from exc

    return RunHandle(run.pk, run.executor_token, run.executor_generation, run.status)


@transaction.atomic
def recover_investigation(*, actor, run_id) -> RunHandle:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    if run.status == InvestigationRun.Status.WAITING_HUMAN:
        raise InvestigationRunError(
            "Ein Run mit offener menschlicher Klärung wird durch eine Nutzerantwort fortgesetzt.",
            code="human_input_required",
        )
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(update_fields=["executor_generation", "executor_token", "updated_at"])
    return RunHandle(run.pk, run.executor_token, run.executor_generation, run.status)


@transaction.atomic
def abort_investigation(*, actor, run_id) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    if run.status not in InvestigationRun.ACTIVE_STATUSES:
        return run
    run.status = InvestigationRun.Status.ABORTED
    run.finished_at = timezone.now()
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "status",
            "finished_at",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def continue_with_human_input(
    *,
    actor,
    run_id,
    payload: Mapping[str, Any],
) -> RunHandle:
    run = locked_run(actor=actor, run_id=run_id)
    if run.status != InvestigationRun.Status.WAITING_HUMAN:
        raise InvestigationRunError(
            "Dieser Run wartet nicht auf menschliche Klärung.",
            code="not_waiting_human",
        )
    normalized = dict(payload or {})
    if not normalized:
        raise InvestigationRunError(
            "Eine leere Nutzerantwort löst keine Klärung.",
            code="empty_human_input",
        )
    revision = (run.input_revisions.aggregate(value=Max("revision"))["value"] or 0) + 1
    InvestigationInputRevision.objects.create(
        run=run,
        revision=revision,
        supplied_by=actor,
        payload=normalized,
        payload_hash=content_hash(normalized),
    )
    run.register_revision += 1
    run.register_hash = register_hash(run)
    run.status = InvestigationRun.Status.RUNNING
    run.clarification_reason = ""
    run.clarification_payload = {}
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "register_revision",
            "register_hash",
            "status",
            "clarification_reason",
            "clarification_payload",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return RunHandle(run.pk, run.executor_token, run.executor_generation, run.status)


def validate_locator(source: InvestigationSource, locator: Mapping[str, Any]) -> bool:
    if source.source_type in {
        InvestigationSource.SourceType.TEXT,
        InvestigationSource.SourceType.MARKDOWN,
    }:
        line = locator.get("line")
        return isinstance(line, int) and 1 <= line <= max(1, len(source.content.splitlines()))
    row = locator.get("row")
    column = locator.get("column")
    if not isinstance(row, int) or row < 1:
        return False
    if source.row_count is not None and row > source.row_count:
        return False
    return column is None or column in source.columns


def reference_valid(run: InvestigationRun, reference: Mapping[str, Any]) -> bool:
    source_id = reference.get("source_id")
    tool_result_id = reference.get("tool_result_id")
    if source_id:
        try:
            source = run.source_snapshot.sources.get(pk=source_id)
        except (InvestigationSource.DoesNotExist, ValueError):
            return False
        if str(reference.get("revision_hash") or "") != source.content_sha256:
            return False
        locator = reference.get("locator")
        return isinstance(locator, Mapping) and validate_locator(source, locator)
    if tool_result_id:
        try:
            stored = InvestigationToolResult.objects.get(
                pk=tool_result_id,
                snapshot=run.source_snapshot,
            )
        except (InvestigationToolResult.DoesNotExist, ValueError):
            return False
        return str(reference.get("revision_hash") or "") == stored.source_hash
    return False


def decision_brief_blockers(run: InvestigationRun) -> tuple[str, ...]:
    if not bool(run.execution_snapshot.get("decision_brief_required")):
        return ()

    payload = run.brief_payload if isinstance(run.brief_payload, Mapping) else {}
    blockers: list[str] = []

    question_scope = payload.get("question_scope")
    if not isinstance(question_scope, Mapping):
        blockers.append("decision_brief_question_scope_missing")
    else:
        question = str(question_scope.get("question") or "").strip()
        scope = str(question_scope.get("scope") or "").strip()
        if not question or question != run.decision_question.strip():
            blockers.append("decision_brief_question_mismatch")
        if not scope:
            blockers.append("decision_brief_scope_missing")

    problem = payload.get("problem")
    if not isinstance(problem, Mapping) or not str(problem.get("statement") or "").strip():
        blockers.append("decision_brief_problem_missing")
    else:
        references = [item for item in problem.get("references", []) if isinstance(item, Mapping)]
        if not references or not all(reference_valid(run, item) for item in references):
            blockers.append("decision_brief_problem_reference_invalid")

    hypotheses = [item for item in payload.get("hypotheses", []) if isinstance(item, Mapping)]
    if len(hypotheses) < 2:
        blockers.append("decision_brief_competing_hypotheses_missing")
    for index, hypothesis in enumerate(hypotheses):
        statement = str(hypothesis.get("statement") or "").strip()
        status = str(hypothesis.get("status") or "").strip()
        if not statement or status not in {"open", "supported", "refuted", "conflicting"}:
            blockers.append(f"decision_brief_hypothesis_invalid:{index}")
            continue
        evidence_refs = [
            item for item in hypothesis.get("references", []) if isinstance(item, Mapping)
        ]
        counter_refs = [
            item for item in hypothesis.get("counterevidence_refs", []) if isinstance(item, Mapping)
        ]
        required_refs = evidence_refs + counter_refs
        if status in {"supported", "refuted", "conflicting"} and (
            not required_refs or not all(reference_valid(run, item) for item in required_refs)
        ):
            blockers.append(f"decision_brief_hypothesis_reference_invalid:{index}")

    calculations = [item for item in payload.get("calculations", []) if isinstance(item, Mapping)]
    if not calculations:
        blockers.append("decision_brief_calculation_missing")
    for index, calculation in enumerate(calculations):
        reference = calculation.get("reference")
        if (
            not str(calculation.get("summary") or "").strip()
            or not isinstance(reference, Mapping)
            or not reference.get("tool_result_id")
            or not reference_valid(run, reference)
        ):
            blockers.append(f"decision_brief_calculation_reference_invalid:{index}")
        if not isinstance(calculation.get("population"), Mapping):
            blockers.append(f"decision_brief_calculation_population_missing:{index}")
        if not str(calculation.get("limits") or "").strip():
            blockers.append(f"decision_brief_calculation_limits_missing:{index}")

    options = [item for item in payload.get("options", []) if isinstance(item, Mapping)]
    if len(options) < 2:
        blockers.append("decision_brief_options_missing")
    if options and not any(bool(item.get("non_ai")) for item in options):
        blockers.append("decision_brief_non_ai_option_missing")
    if options and not any(bool(item.get("status_quo")) for item in options):
        blockers.append("decision_brief_status_quo_missing")
    allowed_option_types = {choice for choice, _label in SolutionOption.OptionType.choices}
    for index, option in enumerate(options):
        if (
            not str(option.get("name") or "").strip()
            or not str(option.get("description") or "").strip()
            or not str(option.get("expected_value") or "").strip()
            or str(option.get("option_type") or "") not in allowed_option_types
        ):
            blockers.append(f"decision_brief_option_invalid:{index}")

    recommendation = payload.get("recommendation")
    if not isinstance(recommendation, Mapping):
        blockers.append("decision_brief_recommendation_missing")
    else:
        refs = [item for item in recommendation.get("references", []) if isinstance(item, Mapping)]
        if (
            not str(recommendation.get("summary") or "").strip()
            or not str(recommendation.get("rationale") or "").strip()
            or not refs
            or not all(reference_valid(run, item) for item in refs)
        ):
            blockers.append("decision_brief_recommendation_invalid")

    if not isinstance(payload.get("risks_unknowns"), list):
        blockers.append("decision_brief_risks_unknowns_missing")

    validation = payload.get("validation_step")
    if (
        not isinstance(validation, Mapping)
        or not str(validation.get("step") or "").strip()
        or not str(validation.get("measurement") or "").strip()
    ):
        blockers.append("decision_brief_validation_step_missing")

    return tuple(sorted(set(blockers)))


def normalize_claim(run: InvestigationRun, raw: Mapping[str, Any]) -> dict[str, Any]:
    claim_id = str(raw.get("claim_id") or "").strip()
    area = str(raw.get("area") or "").strip()
    claim_kind = str(raw.get("claim_kind") or "").strip()
    status = str(raw.get("status") or "").strip()
    if not claim_id or len(claim_id) > 100:
        raise InvestigationRunError("Claim-ID ist ungültig.", code="invalid_claim")
    if area not in {
        "problem_context",
        "competing_hypotheses",
        "solution_options",
        "constraints_risks",
        "recommendation_validation",
    }:
        raise InvestigationRunError("Claim-Bereich ist ungültig.", code="invalid_claim")
    if not claim_kind:
        raise InvestigationRunError("Claim-Art ist ungültig.", code="invalid_claim")
    if status not in {"open", "supported", "refuted", "conflicting"}:
        raise InvestigationRunError("Claim-Status ist ungültig.", code="invalid_claim")
    evidence_refs = [
        dict(item) for item in raw.get("evidence_refs", []) if isinstance(item, Mapping)
    ]
    counter_refs = [
        dict(item) for item in raw.get("counterevidence_refs", []) if isinstance(item, Mapping)
    ]
    return {
        "claim_id": claim_id,
        "area": area,
        "claim_kind": claim_kind,
        "critical": bool(raw.get("critical")),
        "status": status,
        "evidence_refs": evidence_refs,
        "counterevidence_refs": counter_refs,
        "remaining_assumption": str(raw.get("remaining_assumption") or "").strip(),
        "references_valid": all(
            reference_valid(run, item) for item in evidence_refs + counter_refs
        ),
        "change_guard_valid": True,
        "used_as_premise": bool(raw.get("used_as_premise")),
        "optional_unknown_justified": bool(raw.get("optional_unknown_justified")),
        "optional_unknown_verified": bool(raw.get("optional_unknown_verified")),
        "metadata": dict(raw.get("metadata") or {}),
    }


def enforce_claim_guard(
    previous: list[dict[str, Any]],
    proposed: list[dict[str, Any]],
) -> None:
    by_id = {item["claim_id"]: item for item in proposed}
    for old in previous:
        if not old.get("critical"):
            continue
        new = by_id.get(old["claim_id"])
        if new is None or not new.get("critical"):
            raise InvestigationRunError(
                "Ein kritischer Prüfpunkt darf nicht gelöscht, umbenannt oder herabgestuft werden.",
                code="critical_claim_guard",
            )


def normalize_claim_register(
    run: InvestigationRun,
    raw_claims: list[Any] | tuple[Any, ...],
) -> list[dict[str, Any]]:
    """Normalize one complete proposed claim register against the current run."""
    if not all(isinstance(item, Mapping) for item in raw_claims):
        raise InvestigationRunError(
            "Claim Register enthält einen ungültigen Eintrag.",
            code="invalid_claim",
        )
    try:
        normalized = [normalize_claim(run, item) for item in raw_claims]
    except (TypeError, ValueError) as exc:
        raise InvestigationRunError(
            "Claim Register enthält einen ungültigen Eintrag.",
            code="invalid_claim",
        ) from exc
    if len({item["claim_id"] for item in normalized}) != len(normalized):
        raise InvestigationRunError(
            "Claim-IDs müssen eindeutig sein.",
            code="duplicate_claim_id",
        )
    enforce_claim_guard(list(run.claim_register), normalized)
    return normalized


def meaningful_register_change(
    before: list[dict[str, Any]],
    after: list[dict[str, Any]],
) -> bool:
    if content_hash(before) == content_hash(after):
        return False
    old = {item["claim_id"]: item for item in before}
    for item in after:
        previous = old.get(item["claim_id"])
        if previous is None:
            if item.get("evidence_refs") or item.get("counterevidence_refs"):
                return True
            continue
        if previous.get("status") != item.get("status"):
            return True
        if content_hash(previous.get("evidence_refs", [])) != content_hash(
            item.get("evidence_refs", [])
        ):
            return True
        if content_hash(previous.get("counterevidence_refs", [])) != content_hash(
            item.get("counterevidence_refs", [])
        ):
            return True
    return False


@transaction.atomic
def apply_planner_state(
    *,
    actor,
    run_id,
    executor_token,
    claim_register: tuple[Mapping[str, Any], ...] | None = None,
    brief_payload: Mapping[str, Any] | None = None,
    progress_kind: str = "none",
    progress_payload: Mapping[str, Any] | None = None,
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    before = list(run.claim_register)
    register_changed = False
    brief_changed = False

    if claim_register is not None:
        normalized = normalize_claim_register(run, claim_register)
        register_changed = content_hash(before) != content_hash(normalized)
        if register_changed:
            run.claim_register = normalized
            run.register_revision += 1
            run.register_hash = register_hash(run, normalized)

    if brief_payload is not None:
        normalized_brief = dict(brief_payload)
        new_hash = brief_hash(normalized_brief)
        if new_hash != run.brief_hash:
            run.brief_payload = normalized_brief
            run.brief_revision += 1
            run.brief_hash = new_hash
            brief_changed = True

    # Evidence-linked claim changes are observable progress even when the planner
    # labels its own action as "none" (for example while planning the next tool).
    legitimate_progress = meaningful_register_change(before, list(run.claim_register)) or (
        progress_kind
        in {
            InvestigationStep.ProgressKind.EVIDENCE,
            InvestigationStep.ProgressKind.REFUTATION,
            InvestigationStep.ProgressKind.CONTRADICTION,
            InvestigationStep.ProgressKind.COVERAGE,
        }
        and bool(dict(progress_payload or {}).get("coverage_change"))
    )
    if legitimate_progress:
        run.no_progress_streak = 0
        run.last_progress_at = timezone.now()
    elif register_changed or brief_changed or progress_kind == InvestigationStep.ProgressKind.NONE:
        run.no_progress_streak += 1

    latest_step = (
        run.steps.filter(status=InvestigationStep.Status.SUCCESS).order_by("-sequence").first()
    )
    if (
        latest_step is not None
        and progress_kind in {item.value for item in InvestigationStep.ProgressKind}
        and (
            progress_kind != InvestigationStep.ProgressKind.NONE
            or latest_step.progress_kind == InvestigationStep.ProgressKind.NONE
        )
    ):
        latest_step.progress_kind = progress_kind
        latest_step.progress_payload = dict(progress_payload or {})
        latest_step.save(update_fields=["progress_kind", "progress_payload", "updated_at"])

    run.save(
        update_fields=[
            "claim_register",
            "register_revision",
            "register_hash",
            "brief_payload",
            "brief_revision",
            "brief_hash",
            "no_progress_streak",
            "last_progress_at",
            "updated_at",
        ]
    )
    return run


def normalize_tool_parameters(
    tool_name: str,
    raw: Mapping[str, Any],
    *,
    allowed_source_ids: frozenset[str] | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise InvestigationRunError(
            "Werkzeugparameter müssen ein Objekt sein.",
            code="invalid_tool_parameters",
        )
    params = dict(raw)

    def reject_unknown(allowed: set[str]) -> None:
        if unknown := sorted(set(params) - allowed):
            raise InvestigationRunError(
                f"Unbekannte Werkzeugparameter: {', '.join(unknown)}.",
                code="invalid_tool_parameters",
            )

    def integer(name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
        value = params.get(name, default)
        if isinstance(value, bool) or not isinstance(value, int):
            raise InvestigationRunError(
                f"{name} muss eine Ganzzahl sein.",
                code="invalid_tool_parameters",
            )
        if value < minimum or (maximum is not None and value > maximum):
            raise InvestigationRunError(
                f"{name} liegt außerhalb des zulässigen Bereichs.",
                code="invalid_tool_parameters",
            )
        return value

    def nonempty_text(name: str) -> str:
        value = params.get(name)
        if not isinstance(value, str) or not value.strip():
            raise InvestigationRunError(
                f"{name} muss eine nichtleere Zeichenfolge sein.",
                code="invalid_tool_parameters",
            )
        return value.strip()

    def source_id() -> str:
        raw_source_id = nonempty_text("source_id")
        try:
            normalized = str(uuid.UUID(raw_source_id))
        except (ValueError, AttributeError) as exc:
            raise InvestigationRunError(
                "source_id muss eine gültige UUID sein.",
                code="invalid_tool_parameters",
            ) from exc
        if allowed_source_ids is not None and normalized not in allowed_source_ids:
            raise InvestigationRunError(
                "source_id gehört nicht zum gebundenen Quellen-Snapshot.",
                code="invalid_tool_parameters",
            )
        return normalized

    if tool_name == "list_sources":
        if params:
            raise InvestigationRunError(
                "list_sources akzeptiert keine Parameter.",
                code="invalid_tool_parameters",
            )
        return {}
    if tool_name == "search_sources":
        reject_unknown({"query", "cursor", "limit"})
        return {
            "query": nonempty_text("query"),
            "cursor": integer("cursor", 0, minimum=0),
            "limit": integer("limit", 20, minimum=1, maximum=50),
        }
    if tool_name == "read_source":
        reject_unknown({"source_id", "cursor", "limit", "columns"})
        columns = params.get("columns", [])
        if not isinstance(columns, list) or any(
            not isinstance(item, str) or not item for item in columns
        ):
            raise InvestigationRunError(
                "columns muss eine Liste nichtleerer Zeichenfolgen sein.",
                code="invalid_tool_parameters",
            )
        if len(columns) != len(set(columns)):
            raise InvestigationRunError(
                "columns darf keine Duplikate enthalten.",
                code="invalid_tool_parameters",
            )
        return {
            "source_id": source_id(),
            "cursor": integer("cursor", 0, minimum=0),
            "limit": integer("limit", 100, minimum=1, maximum=200),
            "columns": list(columns),
        }
    if tool_name == "profile_csv":
        reject_unknown({"source_id"})
        return {"source_id": source_id()}
    if tool_name == "compare_groups":
        reject_unknown(
            {"source_id", "group_by", "aggregation", "value_column", "filters", "unit_column"}
        )
        filters = params.get("filters", [])
        if not isinstance(filters, list):
            raise InvestigationRunError(
                "filters muss eine Liste sein.",
                code="invalid_tool_parameters",
            )
        normalized_filters = []
        allowed_operators = {
            "eq",
            "neq",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "not_in",
            "is_null",
            "not_null",
        }
        for item in filters:
            if not isinstance(item, Mapping) or set(item) != {"column", "operator", "value"}:
                raise InvestigationRunError(
                    "Jeder Filter benötigt genau column, operator und value.",
                    code="invalid_tool_parameters",
                )
            column = item.get("column")
            operator = item.get("operator")
            if (
                not isinstance(column, str)
                or not column.strip()
                or operator not in allowed_operators
            ):
                raise InvestigationRunError(
                    "Filterspalte oder -operator ist ungültig.",
                    code="invalid_tool_parameters",
                )
            value = item.get("value")
            if operator in {"in", "not_in"} and not isinstance(value, list):
                raise InvestigationRunError(
                    "in/not_in benötigen eine Werteliste.",
                    code="invalid_tool_parameters",
                )
            normalized_filters.append(
                {"column": column.strip(), "operator": operator, "value": value}
            )
        aggregation = nonempty_text("aggregation")
        if aggregation not in {"count", "sum", "mean", "median", "min", "max"}:
            raise InvestigationRunError(
                "aggregation ist ungültig.",
                code="invalid_tool_parameters",
            )
        value_column = params.get("value_column")
        unit_column = params.get("unit_column")
        for name, value in (("value_column", value_column), ("unit_column", unit_column)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise InvestigationRunError(
                    f"{name} muss null oder eine nichtleere Zeichenfolge sein.",
                    code="invalid_tool_parameters",
                )
        if aggregation != "count" and value_column is None:
            raise InvestigationRunError(
                "Diese Aggregation benötigt value_column.",
                code="invalid_tool_parameters",
            )
        return {
            "source_id": source_id(),
            "group_by": nonempty_text("group_by"),
            "aggregation": aggregation,
            "value_column": value_column.strip() if value_column is not None else None,
            "filters": normalized_filters,
            "unit_column": unit_column.strip() if unit_column is not None else None,
        }
    raise InvestigationRunError("Werkzeug ist nicht erlaubt.", code="tool_not_allowed")


def run_tool(
    actor,
    run: InvestigationRun,
    tool_name: str,
    params: Mapping[str, Any],
) -> Any:
    snapshot_id = run.source_snapshot_id
    if tool_name == "list_sources":
        return list_sources(actor=actor, snapshot_id=snapshot_id)
    if tool_name == "search_sources":
        return search_sources(
            actor=actor,
            snapshot_id=snapshot_id,
            request=SearchRequest(**params),
        )
    if tool_name == "read_source":
        return read_source(
            actor=actor,
            snapshot_id=snapshot_id,
            request=ReadRequest(
                source_id=params["source_id"],
                cursor=params["cursor"],
                limit=params["limit"],
                columns=tuple(params["columns"]),
            ),
        )
    if tool_name == "profile_csv":
        return profile_csv(
            actor=actor,
            snapshot_id=snapshot_id,
            request=CsvProfileRequest(source_id=params["source_id"]),
        )
    if tool_name == "compare_groups":
        return compare_groups(
            actor=actor,
            snapshot_id=snapshot_id,
            request=CompareGroupsRequest(
                source_id=params["source_id"],
                group_by=params["group_by"],
                aggregation=params["aggregation"],
                value_column=params["value_column"],
                filters=tuple(FilterSpec(**item) for item in params["filters"]),
                unit_column=params["unit_column"],
            ),
        )
    raise InvestigationRunError("Werkzeug ist nicht erlaubt.", code="tool_not_allowed")


@transaction.atomic
def fail_run_technical(
    *,
    actor,
    run_id,
    executor_token,
    error: InvestigationRunError,
    impact: str,
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    run.status = InvestigationRun.Status.FAILED
    run.clarification_reason = "technical_failure"
    run.clarification_payload = {
        "error_code": error.code,
        "impact": impact,
        "required_action": (
            "Tool-/Schema-Vertrag technisch prüfen; keinen fachlichen Schluss ableiten."
        ),
    }
    run.finished_at = timezone.now()
    run.executor_generation += 1
    run.executor_token = uuid.uuid4()
    run.save(
        update_fields=[
            "status",
            "clarification_reason",
            "clarification_payload",
            "finished_at",
            "executor_generation",
            "executor_token",
            "updated_at",
        ]
    )
    return run


def _new_tool_coverage(
    run: InvestigationRun, step: InvestigationStep, payload: dict[str, Any]
) -> bool:
    """Count only new source content or a new analytical result as tool progress."""
    if step.tool_name not in {"read_source", "search_sources", "profile_csv", "compare_groups"}:
        return False
    earlier = run.steps.filter(status=InvestigationStep.Status.SUCCESS).exclude(pk=step.pk)
    if step.tool_name == "read_source":
        items = payload.get("items") or []
        if not items:
            return False
        seen = {
            content_hash(item)
            for previous in earlier.filter(tool_name="read_source")
            if previous.parameters.get("source_id") == step.parameters.get("source_id")
            for item in (previous.result_payload.get("items") or [])
        }
        return any(content_hash(item) not in seen for item in items)
    if step.tool_name == "search_sources":
        hits = payload.get("hits") or []
        if not hits:
            return False
        seen = {
            content_hash(hit)
            for previous in earlier.filter(tool_name="search_sources")
            for hit in (previous.result_payload.get("hits") or [])
        }
        return any(content_hash(hit) not in seen for hit in hits)
    return bool(payload) and not any(
        previous.parameters == step.parameters
        for previous in earlier.filter(tool_name=step.tool_name)
    )


def execute_tool_step(
    *,
    actor,
    run_id,
    executor_token,
    tool_name: str,
    parameters: Mapping[str, Any],
    target_claim_id: str = "",
    expected_discriminating_finding: str = "",
    verifier_read: bool = False,
) -> InvestigationStep:
    if tool_name not in ALLOWED_TOOLS:
        raise InvestigationRunError("Werkzeug ist nicht erlaubt.", code="tool_not_allowed")
    allowed_source_ids = frozenset(
        str(source_id)
        for source_id in InvestigationSource.objects.filter(
            snapshot__investigation_runs__pk=run_id
        ).values_list("pk", flat=True)
    )
    try:
        params = normalize_tool_parameters(
            tool_name,
            parameters,
            allowed_source_ids=allowed_source_ids,
        )
    except InvestigationRunError as exc:
        if exc.code == "invalid_tool_parameters":
            fail_run_technical(
                actor=actor,
                run_id=run_id,
                executor_token=executor_token,
                error=exc,
                impact="Die Untersuchung wurde wegen ungültiger Werkzeugparameter beendet.",
            )
        raise

    with transaction.atomic():
        run = locked_run(actor=actor, run_id=run_id)
        assert_active(run)
        assert_executor(run, executor_token)
        if run.status != InvestigationRun.Status.RUNNING:
            raise InvestigationRunError(
                "Der Run wartet auf menschliche Klärung.",
                code="human_input_required",
            )
        if run.process_analysis.version != run.process_version:
            raise InvestigationRunError(
                "Die ProcessAnalysis wurde während des Runs geändert.",
                code="process_version_conflict",
            )
        step_key = content_hash(
            {
                "tool": tool_name,
                "parameters": params,
                "manifest_hash": run.manifest_hash,
                "target_claim_id": target_claim_id,
            }
        )
        existing = run.steps.filter(step_key=step_key).first()
        if existing is not None and existing.status == InvestigationStep.Status.SUCCESS:
            return existing

        usage = dict(run.usage)
        if verifier_read:
            if tool_name != "read_source":
                raise InvestigationRunError(
                    "Verifier darf im separaten Lese-Budget nur read_source verwenden.",
                    code="verifier_tool_not_allowed",
                )
            if usage["verifier_reads"] >= run.budget_limits["max_verifier_reads"]:
                raise InvestigationRunError(
                    "Verifier-Lesebudget ist erschöpft.",
                    code="budget_exhausted",
                )
            usage["verifier_reads"] += 1
        else:
            if usage["tool_calls"] >= run.budget_limits["max_tool_calls"]:
                raise InvestigationRunError(
                    "Werkzeugbudget ist erschöpft.",
                    code="budget_exhausted",
                )
            if budget_exhausted(run, reserve_verifier=True):
                raise InvestigationRunError(
                    "Die für die Verifikation reservierten Budgets würden verletzt.",
                    code="budget_exhausted",
                )
            usage["tool_calls"] += 1

        if existing is None:
            sequence = (run.steps.aggregate(value=Max("sequence"))["value"] or 0) + 1
            step = InvestigationStep.objects.create(
                run=run,
                sequence=sequence,
                step_key=step_key,
                target_claim_id=str(target_claim_id or "")[:100],
                expected_discriminating_finding=str(expected_discriminating_finding or ""),
                tool_name=tool_name,
                parameters=params,
                executor_generation=run.executor_generation,
            )
        else:
            if (
                existing.status != InvestigationStep.Status.FAILED
                or existing.attempts >= 2
                or existing.error_code not in TRANSIENT_TOOL_CODES
            ):
                raise InvestigationRunError(
                    "Dieser fehlgeschlagene Schritt darf nicht erneut ausgeführt werden.",
                    code="retry_exhausted",
                )
            step = existing
            step.status = InvestigationStep.Status.RUNNING
            step.attempts += 1
            step.error_code = ""
            step.finished_at = None
            step.executor_generation = run.executor_generation
            step.save(
                update_fields=[
                    "status",
                    "attempts",
                    "error_code",
                    "finished_at",
                    "executor_generation",
                    "updated_at",
                ]
            )

        run.usage = usage
        run.save(update_fields=["usage", "updated_at"])
        generation = run.executor_generation

    try:
        payload = jsonable(run_tool(actor, run, tool_name, params))
    except Exception as exc:
        with transaction.atomic():
            current = InvestigationStep.objects.select_for_update().get(pk=step.pk)
            locked = locked_run(actor=actor, run_id=run_id)
            if locked.executor_generation == generation and str(locked.executor_token) == str(
                executor_token
            ):
                current.status = InvestigationStep.Status.FAILED
                current.finished_at = timezone.now()
                current.error_code = str(getattr(exc, "code", "tool_failure"))[:50]
                current.save(
                    update_fields=[
                        "status",
                        "finished_at",
                        "error_code",
                        "updated_at",
                    ]
                )
        raise

    stale_result = False
    with transaction.atomic():
        locked = locked_run(actor=actor, run_id=run_id)
        current = InvestigationStep.objects.select_for_update().get(pk=step.pk)
        stale_result = (
            locked.executor_generation != generation
            or str(locked.executor_token) != str(executor_token)
            or locked.status != InvestigationRun.Status.RUNNING
        )
        if stale_result:
            current.status = InvestigationStep.Status.DISCARDED
            current.finished_at = timezone.now()
            current.error_code = "stale_executor"
            current.save(
                update_fields=[
                    "status",
                    "finished_at",
                    "error_code",
                    "updated_at",
                ]
            )
        else:
            new_coverage = not verifier_read and _new_tool_coverage(locked, current, payload)
            current.status = InvestigationStep.Status.SUCCESS
            current.result_payload = payload
            current.result_hash = content_hash(payload)
            if new_coverage:
                current.progress_kind = InvestigationStep.ProgressKind.COVERAGE
                current.progress_payload = {"coverage_change": True}
                locked.no_progress_streak = 0
                locked.last_progress_at = timezone.now()
            if tool_name in {"profile_csv", "compare_groups"}:
                current.result_ref = {"tool_result_id": payload.get("result_id")}
                locked.data_check_executed = True
            current.finished_at = timezone.now()
            current.save(
                update_fields=[
                    "status",
                    "result_payload",
                    "result_hash",
                    "result_ref",
                    "progress_kind",
                    "progress_payload",
                    "finished_at",
                    "updated_at",
                ]
            )

            if tool_name == "search_sources":
                query = str(params.get("query") or "").casefold()
                if any(
                    marker in query
                    for marker in ("gegen", "counter", "wider", "alternative", "nicht")
                ):
                    locked.counterevidence_search_executed = True
                    locked.counterevidence_hits_processed = not bool(payload.get("hits"))

            locked.save(
                update_fields=[
                    "data_check_executed",
                    "counterevidence_search_executed",
                    "counterevidence_hits_processed",
                    "no_progress_streak",
                    "last_progress_at",
                    "updated_at",
                ]
            )

    if stale_result:
        raise InvestigationRunError(
            "Das Werkzeugresultat stammt von einem abgelösten Executor und wurde verworfen.",
            code="stale_executor",
        )
    return current


def policy_checks(run: InvestigationRun) -> tuple[PolicyCheck, ...]:
    return tuple(
        PolicyCheck(
            claim_id=item["claim_id"],
            area=item["area"],
            claim_kind=item["claim_kind"],
            critical=bool(item.get("critical")),
            status=item["status"],
            evidence_refs=tuple(item.get("evidence_refs", [])),
            counterevidence_refs=tuple(item.get("counterevidence_refs", [])),
            remaining_assumption=str(item.get("remaining_assumption") or ""),
            references_valid=bool(item.get("references_valid", False)),
            change_guard_valid=bool(item.get("change_guard_valid", True)),
            used_as_premise=bool(item.get("used_as_premise")),
            optional_unknown_justified=bool(item.get("optional_unknown_justified")),
            optional_unknown_verified=bool(item.get("optional_unknown_verified")),
            metadata=dict(item.get("metadata") or {}),
        )
        for item in run.claim_register
    )


def latest_verifier_state(run: InvestigationRun) -> VerifierState | None:
    report = run.verifier_reports.order_by("-revision").first()
    if report is None:
        return None
    return VerifierState(
        success=report.success,
        critical_findings=report.critical_findings,
        bound_hashes=report.bound_hashes,
        source_references_valid=report.source_references_valid,
        checked_critical_claims=frozenset(report.checked_critical_claims),
    )


def policy_state_for_run(
    run: InvestigationRun,
    *,
    allowed_action_available: bool = False,
    external_critical_gap: bool = False,
    permission_or_scope_block: bool = False,
    value_tradeoff: bool = False,
    technical_failure: bool = False,
    retry_available: bool = False,
    replan_available: bool = False,
) -> PolicyState:
    return PolicyState(
        checks=policy_checks(run),
        data_check_executed=run.data_check_executed,
        counterevidence_search_executed=run.counterevidence_search_executed,
        counterevidence_hits_processed=run.counterevidence_hits_processed,
        source_relevance_complete=run.source_relevance_complete,
        contract_hash=run.contract_hash,
        manifest_hash=run.manifest_hash,
        register_hash=run.register_hash,
        brief_hash=run.brief_hash,
        brief_blockers=decision_brief_blockers(run),
        verifier=latest_verifier_state(run),
        allowed_action_available=allowed_action_available,
        external_critical_gap=external_critical_gap,
        permission_or_scope_block=permission_or_scope_block,
        value_tradeoff=value_tradeoff,
        budget_exhausted=budget_exhausted(run),
        technical_failure=technical_failure,
        retry_available=retry_available,
        no_progress_streak=run.no_progress_streak,
        replan_available=replan_available,
        repair_available=run.repair_cycles < run.budget_limits["max_repair_cycles"],
        aborted=run.status == InvestigationRun.Status.ABORTED,
    )


def evaluate_run_policy(run: InvestigationRun, **kwargs) -> PolicyDecision:
    return evaluate_policy(policy_state_for_run(run, **kwargs))


@transaction.atomic
def mark_counterevidence_processed(
    *,
    actor,
    run_id,
    executor_token,
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    if not run.counterevidence_search_executed:
        raise InvestigationRunError(
            "Ohne ausgeführte Gegenbelegsuche kann nichts als verarbeitet markiert werden.",
            code="counterevidence_missing",
        )

    searches = [
        step
        for step in run.steps.filter(
            status=InvestigationStep.Status.SUCCESS,
            tool_name="search_sources",
        ).order_by("sequence")
        if any(
            marker in str(step.parameters.get("query") or "").casefold()
            for marker in ("gegen", "counter", "wider", "alternative", "nicht")
        )
    ]
    reads = list(
        run.steps.filter(
            status=InvestigationStep.Status.SUCCESS,
            tool_name="read_source",
        ).order_by("sequence")
    )
    unread_hits: list[dict[str, Any]] = []
    for search in searches:
        for hit in search.result_payload.get("hits", []):
            source_id = str(hit.get("source_id") or "")
            locator = hit.get("locator") or {}
            line_or_row = locator.get("line", locator.get("row"))
            matched = False
            for read in reads:
                if str(read.parameters.get("source_id") or "") != source_id:
                    continue
                cursor = int(read.parameters.get("cursor", 0))
                limit = int(read.parameters.get("limit", 100))
                if isinstance(line_or_row, int) and cursor < line_or_row <= cursor + limit:
                    matched = True
                    break
            if not matched:
                unread_hits.append({"source_id": source_id, "locator": locator})

    if unread_hits:
        raise InvestigationRunError(
            "Gegenbelegtreffer müssen gelesen werden, bevor sie als verarbeitet gelten.",
            code="counterevidence_unread",
        )
    run.counterevidence_hits_processed = True
    run.save(update_fields=["counterevidence_hits_processed", "updated_at"])
    return run


@transaction.atomic
def set_source_relevance(
    *,
    actor,
    run_id,
    executor_token,
    relevance: Mapping[str, Mapping[str, Any]],
) -> InvestigationRun:
    run = locked_run(actor=actor, run_id=run_id)
    assert_active(run)
    assert_executor(run, executor_token)
    listed = list_sources(actor=actor, snapshot_id=run.source_snapshot_id)
    source_ids = {str(item.source_id) for item in listed.sources}
    supplied = {str(key): dict(value) for key, value in dict(relevance or {}).items()}
    if set(supplied) != source_ids:
        raise InvestigationRunError(
            "Für jede Manifestquelle ist genau eine Relevanzbegründung erforderlich.",
            code="source_relevance_incomplete",
        )

    normalized: dict[str, dict[str, Any]] = {}
    for source_id, item in supplied.items():
        reason = str(item.get("reason") or "").strip()
        relevant = item.get("relevant")
        reference = item.get("reference")
        if not reason or not isinstance(relevant, bool) or not isinstance(reference, Mapping):
            raise InvestigationRunError(
                "Relevanzbegründung benötigt relevant, reason und eine reale Fundstelle/Analyse.",
                code="invalid_source_relevance",
            )
        if not reference_valid(run, reference):
            raise InvestigationRunError(
                "Relevanzbegründung verweist nicht auf eine gültige Fundstelle/Analyse.",
                code="invalid_source_relevance",
            )
        normalized[source_id] = {
            "relevant": relevant,
            "reason": reason,
            "reference": dict(reference),
        }

    run.source_relevance = normalized
    run.source_relevance_complete = True
    run.register_revision += 1
    run.register_hash = register_hash(run, relevance=normalized)
    run.save(
        update_fields=[
            "source_relevance",
            "source_relevance_complete",
            "register_revision",
            "register_hash",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def materialize_brief_revision(
    *,
    actor,
    run_id,
    operation_key: str,
    expected_process_version: int,
) -> InvestigationBriefRevision:
    run = locked_run(actor=actor, run_id=run_id)
    key = normalize_idempotency_key(operation_key)
    existing = run.brief_revisions.filter(operation_key=key).first()
    if existing is not None:
        return existing
    if (
        run.process_analysis.version != expected_process_version
        or run.process_version != expected_process_version
    ):
        raise InvestigationRunError(
            "Die fachliche Ausgangsversion hat sich geändert; keine Teilübernahme.",
            code="process_version_conflict",
        )
    if run.status != InvestigationRun.Status.READY:
        raise InvestigationRunError(
            "Nur ein technisch READY-geprüfter Brief kann materialisiert werden.",
            code="ready_required",
        )
    revision = (run.brief_revisions.aggregate(value=Max("revision"))["value"] or 0) + 1
    try:
        with transaction.atomic():
            return InvestigationBriefRevision.objects.create(
                run=run,
                revision=revision,
                payload=run.brief_payload,
                content_hash=run.brief_hash,
                operation_key=key,
                process_version=run.process_version,
            )
    except IntegrityError:
        existing = run.brief_revisions.filter(operation_key=key).first()
        if existing is not None:
            return existing
        raise
