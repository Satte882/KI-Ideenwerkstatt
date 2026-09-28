from __future__ import annotations

import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from ki_radar.core.llm_policy import LLMConfigurationError, get_accelerator_llm_policy
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter

from .analysis_service import (
    CaptureAnalysisQuotaExceeded,
    log_capture_analysis,
    mark_capture_analysis_failed,
    reserve_accelerator_quotas,
)
from .architect_contract import (
    DISCOVERY_PROMPT_VERSION,
    DISCOVERY_SCHEMA_VERSION,
    DiscoveryContractError,
    build_discovery_json_schema,
    build_discovery_verifier_schema,
    validate_discovery_payload,
    validate_verifier_payload,
)
from .investigation_tools import get_discovery_source_snapshot
from .models import CaptureAnalysis, CaptureSession
from .services import get_owned_autonomous_capture_session

logger = logging.getLogger(__name__)

DISCOVERY_SYSTEM_PROMPT = """Du arbeitest als autonomer Business Architect.
Erzeuge ausschließlich aus dem bereitgestellten Problem, Geschäftskontext, Nutzerkorrekturen
und den autorisierten Quellen einen strukturierten Business-Discovery-Entwurf.

Regeln:
- Erfinde keine Fakten, Messwerte, Rollen, Systeme oder Prozessschritte.
- Quellenreferenzen dürfen nur die gelieferten Handles U0, S1, S2 ... verwenden.
- U0 steht für Problem, Geschäftskontext und Nutzerkorrekturen. Ordne Aussagen aus
  diesen Eingaben U0 zu, nicht pauschal einer Quelldatei S1/S2. Bei einem Objekt,
  das Aussagen aus U0 und einer Datei kombiniert, nenne beide tragenden Handles.
- Trenne berichtete Fakten, Hypothesen, Unknowns, Clarifications und Widersprüche explizit.
- Ein Widerspruch ist nur zulässig, wenn mindestens zwei unterschiedliche Input-Handles
  einander widersprechende Aussagen tragen; evidence_refs muss dann mindestens diese beiden
  unterschiedlichen Handles enthalten. Mit nur einer tragenden Quelle ist es kein Widerspruch.
- Zahlen in Fakten und Baselines dürfen nur vorkommen, wenn sie im Input tatsächlich genannt sind.
- Der Value Stream ist End-to-End breiter als der vorgeschlagene Process Scope.
- value_stream.scope_in/scope_out beschreiben die Grenze des gesamten Value Streams,
  nicht die engere Process-Analysis-Grenze. Jede aufgeführte Value-Stream-Phase muss
  zur Value-Stream-Grenze und zu ihrem Trigger/Outcome passen.
- Phasen bilden eine plausible lückenlose Reihenfolge; Unsicherheit bleibt sichtbar.
- Wenn process_analysis.current_flow Phasenschlüssel nennt, müssen diese exakt
  den Schlüsseln und Namen der erzeugten Phasen entsprechen.
- Bewerte für jede Phase Impact, Problemintensität, Verbesserungspotenzial,
  Datenzugänglichkeit und Veränderungsaufwand mit low/medium/high sowie Time-to-Value
  mit unknown/short/medium/long. Diese Werte sind Screening-Einschätzungen, keine Messwerte.
- evidence_basis ist hypothesis, indicative oder measured. Nutze indicative/measured nur,
  wenn die autorisierten Quellen diese Stärke tragen; sonst hypothesis.
- Die Fokusphase muss zum Problem und zum vollständigen Phasenvergleich passen.
- Lösungsoffen bleiben: keine KI-Lösung, Automatisierung oder Software vorwegnehmen.
- Eine Clarification ist nur blocking=true, wenn Scope/Fokus ohne die Antwort nicht
  verantwortbar entschieden werden kann.
- Leere Detailfelder sind zulässig, wenn der Input nichts Belastbares hergibt.
Gib ausschließlich das verlangte JSON-Objekt zurück."""

VERIFIER_SYSTEM_PROMPT = """Du bist ein unabhängiger Reviewer für einen Business-Discovery-Draft.
Prüfe gegen den vollständigen autorisierten Input und nicht gegen Plausibilität allein.

Kritisch sind insbesondere:
- tragende Aussagen ohne Quelle;
- U0 ist der autorisierte Input-Handle für problem_statement, business_context
  und corrections. Diese Feldnamen selbst sind keine zulässigen Evidence-Refs.
- erfundene Zahlen oder Fakten;
- Value-Stream-Grenzen, die nur den Einzelprozess wiederholen;
- unplausible oder lückenhafte Phasenfolge;
- Fokusphase passt nicht zum Problem;
- Process Scope ist nicht enger als der Value Stream oder fachlich unklar;
- Hypothesen werden als Fakten behandelt;
- entscheidungsrelevante Unknowns fehlen;
- Widersprüche zwischen Quellen werden geglättet.

Kalibrierung der Checks:
- Fordere keine eigene Phase für bloßes Warten oder einen nur implizierten Übergang,
  wenn die Quellen dort keine fachliche Tätigkeit beschreiben. Erfinde keine Phase,
  um eine formal lückenlose Sequenz zu erzwingen.
- Low/medium/high in Phasenvergleich und Fokus sind vorläufige Screening-Einschätzungen,
  keine gemessenen Fakten. Verlange dafür keine Einzelquelle; prüfe stattdessen, ob
  ihre Begründung zum Problem passt und relevante Unsicherheit sichtbar bleibt.
- Unknowns müssen entscheidungsrelevante Lücken abdecken, nicht jede denkbare
  Detailfrage. Ein vorhandener Unknown ist nicht allein deshalb unzureichend,
  weil sich noch weitere Fragen formulieren ließen.
- Eine direkt durch eine Quelle berichtete Phasenbeschreibung ist qualitativ
  belegt (indicative), auch wenn für die Phase keine Messwerte vorliegen.
- Markiere nur Findings als kritisch, die Scope, Fokus, Quellenwahrheit oder
  Materialisierung tatsächlich beeinträchtigen. Repair-Anweisungen müssen sich
  auf diese konkreten Findings beschränken.

Status:
- approved: alle sieben Checks sind true und es gibt kein kritisches Finding.
- repair: Draft kann ohne neue menschliche Information gezielt korrigiert werden.
- waiting_human: eine entscheidungskritische Information fehlt; stelle genau die präzise
  fachliche Frage, die Scope/Fokus entscheidet.
Gib ausschließlich das verlangte JSON-Objekt zurück."""

REPAIR_SYSTEM_PROMPT = """Du reparierst einen Business-Discovery-Draft anhand eines unabhängigen
Verifier-Findings oder einer deterministischen serverseitigen Contract-Verletzung. Verwende nur
den ursprünglichen autorisierten Input. Erfinde keine fehlende Information. Wenn etwas nicht
belegt ist, verschiebe es in Hypothesen/Unknowns oder lasse ein Detailfeld leer. Bei einem
Widerspruch müssen mindestens zwei unterschiedliche Input-Handles die gegensätzlichen Aussagen
tragen; andernfalls entferne den Widerspruch oder ordne die Aussage korrekt als Hypothese/Unknown
ein. U0 ist der autorisierte Handle für problem_statement, business_context und corrections;
die Feldnamen selbst sind keine gültigen Evidence-Refs. Falls ein Verifier-Finding das anders
behauptet, behalte U0 und korrigiere nur die tatsächlich fehlerhafte Quellenzuordnung.
Gib den vollständigen korrigierten Draft im verlangten JSON-Schema zurück."""


class DiscoveryAnalysisError(RuntimeError):
    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.code = code


def _usage_int(result: OpenRouterResult, key: str) -> int:
    value = result.usage.get(key)
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _usage_cost(result: OpenRouterResult) -> Decimal:
    value = result.usage.get("cost")
    try:
        return Decimal(str(value or "0"))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def _source_document(*, session: CaptureSession, snapshot) -> tuple[dict[str, Any], set[str], str]:
    problem = str(session.answers.get("problem_statement") or "").strip()
    business_context = str(session.answers.get("business_context") or "").strip()
    corrections = [
        str(item.get("text") or "").strip()
        for item in list(session.answers.get("corrections") or [])
        if isinstance(item, dict) and str(item.get("text") or "").strip()
    ]
    sources = []
    allowed_refs = {"U0"}
    evidence_parts = [problem, business_context, *corrections]
    for index, source in enumerate(snapshot.sources.order_by("filename", "id"), start=1):
        ref = f"S{index}"
        allowed_refs.add(ref)
        evidence_parts.append(source.content)
        sources.append(
            {
                "ref": ref,
                "filename": source.filename,
                "source_type": source.source_type,
                "content_sha256": source.content_sha256,
                "row_count": source.row_count,
                "columns": list(source.columns),
                "content": source.content,
            }
        )
    document = {
        "input_ref": "U0",
        "capture_session_id": str(session.pk),
        "capture_revision": session.revision,
        "business_unit": session.owner.business_unit.name,
        "problem_statement": problem,
        "business_context": business_context,
        "corrections": corrections,
        "sources": sources,
    }
    return document, allowed_refs, "\n".join(evidence_parts)


def _decode_json(result: OpenRouterResult, *, code: str) -> dict[str, Any]:
    if result.finish_reason == "length":
        raise DiscoveryAnalysisError(
            "Die strukturierte Discovery-Antwort wurde am Ausgabelimit abgeschnitten.",
            code="output_truncated",
        )
    try:
        payload = json.loads(result.content)
    except json.JSONDecodeError as exc:
        raise DiscoveryAnalysisError(
            "Der Provider lieferte kein gültiges JSON-Objekt.",
            code=code,
        ) from exc
    if not isinstance(payload, dict):
        raise DiscoveryAnalysisError(
            "Der Provider lieferte kein JSON-Objekt.",
            code=code,
        )
    return payload


def _provider_call(
    *,
    actor,
    session: CaptureSession,
    policy,
    messages: list[dict[str, str]],
    schema_name: str,
    schema: dict[str, Any],
) -> OpenRouterResult:
    # A timed-out provider response has no usable draft. Investigation already
    # allows one transport retry; keep the same bounded rule for Discovery.
    for attempt in range(2):
        try:
            reserve_accelerator_quotas(
                actor=actor,
                session=session,
                policy=policy,
                include_context=False,
            )
            # The large discovery schema needs output room, but producer/repair
            # should spend that room on the draft instead of extended reasoning.
            reasoning_effort = (
                "medium" if schema_name == "autonomous_business_discovery_verifier_v1" else "low"
            )
            return request_openrouter(
                messages=messages,
                max_tokens=policy.capture_max_output_tokens,
                timeout_seconds=policy.timeout_seconds,
                temperature=policy.capture_temperature,
                reasoning_effort=reasoning_effort,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema_name,
                        "strict": True,
                        "schema": schema,
                    },
                },
                provider={"require_parameters": True, "sort": "throughput"},
            )
        except OpenRouterUnavailable as exc:
            if exc.code == "timeout" and attempt == 0:
                logger.warning("discovery_provider_retry schema=%s code=timeout", schema_name)
                continue
            raise DiscoveryAnalysisError(str(exc), code=exc.code) from exc
        except CaptureAnalysisQuotaExceeded as exc:
            raise DiscoveryAnalysisError(str(exc), code=exc.code) from exc
    raise AssertionError("Discovery-Provider-Retry-Budget wurde unerwartet überschritten.")


def _prompt_payload(system_prompt: str, document: dict[str, Any]) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": json.dumps(document, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _input_chars(messages: list[dict[str, str]]) -> int:
    return sum(len(message["content"]) for message in messages)


def _analysis_source_hash(snapshot, session: CaptureSession) -> str:
    return hashlib.sha256(f"{snapshot.manifest_hash}:{session.revision}".encode()).hexdigest()


def _store_terminal_analysis(
    *,
    analysis_id,
    status: str,
    draft: dict[str, Any],
    verifier: dict[str, Any],
    source_labels: dict[str, str],
    snapshot_id,
    results: list[OpenRouterResult],
) -> CaptureAnalysis:
    with transaction.atomic():
        analysis = CaptureAnalysis.objects.select_for_update().get(pk=analysis_id)
        if analysis.status != CaptureAnalysis.Status.RUNNING:
            raise DiscoveryAnalysisError(
                "Der Discovery-Lauf ist nicht mehr offen.",
                code="analysis_not_running",
            )
        finished_at = timezone.now()
        analysis.status = status
        analysis.finished_at = finished_at
        analysis.duration_ms = max(
            0,
            round((finished_at - analysis.started_at).total_seconds() * 1000),
        )
        analysis.model_name = results[-1].model if results else ""
        analysis.output_chars = sum(result.output_chars for result in results)
        analysis.prompt_tokens = sum(_usage_int(result, "prompt_tokens") for result in results)
        analysis.completion_tokens = sum(
            _usage_int(result, "completion_tokens") for result in results
        )
        analysis.total_tokens = sum(_usage_int(result, "total_tokens") for result in results)
        analysis.cost = sum((_usage_cost(result) for result in results), Decimal("0"))
        analysis.open_questions = list(draft.get("clarifications") or [])
        analysis.contradictions = list(draft.get("contradictions") or [])
        analysis.result_payload = {
            "draft": draft,
            "source_labels": source_labels,
            "discovery_snapshot_id": str(snapshot_id),
        }
        analysis.verification_payload = verifier
        analysis.error_code = ""
        analysis.save(
            update_fields=[
                "status",
                "finished_at",
                "duration_ms",
                "model_name",
                "output_chars",
                "prompt_tokens",
                "completion_tokens",
                "total_tokens",
                "cost",
                "open_questions",
                "contradictions",
                "result_payload",
                "verification_payload",
                "error_code",
                "updated_at",
            ]
        )
    log_capture_analysis(analysis, purpose="autonomous_business_discovery")
    return analysis


def _store_failure_diagnostics(
    *,
    analysis_id,
    draft: dict[str, Any],
    verifier: dict[str, Any],
    snapshot_id,
) -> None:
    """Persist the last validated draft/reviewer finding before fail-closed termination."""
    with transaction.atomic():
        analysis = CaptureAnalysis.objects.select_for_update().get(pk=analysis_id)
        if analysis.status != CaptureAnalysis.Status.RUNNING:
            return
        analysis.open_questions = list(draft.get("clarifications") or [])
        analysis.contradictions = list(draft.get("contradictions") or [])
        analysis.result_payload = {
            "draft": draft,
            "discovery_snapshot_id": str(snapshot_id),
        }
        analysis.verification_payload = verifier
        analysis.save(
            update_fields=[
                "open_questions",
                "contradictions",
                "result_payload",
                "verification_payload",
                "updated_at",
            ]
        )


@sensitive_variables("document", "producer_messages", "verifier_document", "repair_document")
def execute_autonomous_business_discovery(
    *,
    actor,
    session_id,
    snapshot_id,
) -> CaptureAnalysis:
    session = get_owned_autonomous_capture_session(actor=actor, session_id=session_id)
    if session.status != CaptureSession.Status.DRAFT:
        raise PermissionDenied("Die autonome Discovery ist nicht mehr bearbeitbar.")
    if session.owner.business_unit is None or not session.owner.business_unit.is_active:
        raise DiscoveryAnalysisError(
            "Für die autonome Discovery fehlt eine aktive Organisationseinheit.",
            code="missing_business_unit",
        )

    snapshot = get_discovery_source_snapshot(actor=actor, snapshot_id=snapshot_id)
    if snapshot.capture_session_id != session.pk:
        raise PermissionDenied("Der Discovery-Snapshot gehört nicht zu dieser Erfassung.")

    try:
        policy = get_accelerator_llm_policy()
    except LLMConfigurationError as exc:
        raise DiscoveryAnalysisError(str(exc), code="invalid_configuration") from exc

    document, allowed_refs, evidence_text = _source_document(session=session, snapshot=snapshot)
    producer_messages = _prompt_payload(DISCOVERY_SYSTEM_PROMPT, document)
    chars = _input_chars(producer_messages)
    if chars > policy.discovery_max_input_chars:
        raise DiscoveryAnalysisError(
            "Die autorisierten Quellen überschreiten das Discovery-Eingabelimit. "
            "Bitte den Quellenraum auf die entscheidungsrelevanten Dateien begrenzen.",
            code="source_pack_too_large",
        )

    source_hash = _analysis_source_hash(snapshot, session)
    try:
        analysis = CaptureAnalysis.objects.create(
            session=session,
            requested_by=actor,
            source_revision=session.revision,
            source_hash=source_hash,
            capture_type=session.capture_type,
            catalog_version=session.catalog_version,
            answer_schema_version=session.schema_version,
            prompt_version=DISCOVERY_PROMPT_VERSION,
            extraction_schema_version=DISCOVERY_SCHEMA_VERSION,
            input_chars=chars,
        )
    except IntegrityError as exc:
        raise DiscoveryAnalysisError(
            "Für diesen unveränderten Discovery-Stand läuft bereits eine Analyse.",
            code="analysis_already_running",
        ) from exc

    results: list[OpenRouterResult] = []
    last_result: OpenRouterResult | None = None
    try:
        producer = _provider_call(
            actor=actor,
            session=session,
            policy=policy,
            messages=producer_messages,
            schema_name="autonomous_business_discovery_v1",
            schema=build_discovery_json_schema(),
        )
        results.append(producer)
        last_result = producer
        producer_payload = _decode_json(producer, code="invalid_discovery_response")
        repair_used = False
        try:
            draft = validate_discovery_payload(
                producer_payload,
                allowed_refs=allowed_refs,
                evidence_text=evidence_text,
            )
        except DiscoveryContractError as contract_exc:
            contract_repair_document = {
                "input": document,
                "draft": producer_payload,
                "contract_errors": list(contract_exc.errors),
            }
            contract_repair_messages = _prompt_payload(
                REPAIR_SYSTEM_PROMPT,
                contract_repair_document,
            )
            if _input_chars(contract_repair_messages) > policy.discovery_max_input_chars:
                raise DiscoveryAnalysisError(
                    "Der Contract-Repair überschreitet das Eingabelimit.",
                    code="repair_input_too_large",
                ) from contract_exc
            repair_result = _provider_call(
                actor=actor,
                session=session,
                policy=policy,
                messages=contract_repair_messages,
                schema_name="autonomous_business_discovery_repair_v1",
                schema=build_discovery_json_schema(),
            )
            results.append(repair_result)
            last_result = repair_result
            draft = validate_discovery_payload(
                _decode_json(repair_result, code="invalid_repair_response"),
                allowed_refs=allowed_refs,
                evidence_text=evidence_text,
            )
            repair_used = True

        verifier_document = {"input": document, "draft": draft}
        verifier_messages = _prompt_payload(VERIFIER_SYSTEM_PROMPT, verifier_document)
        if _input_chars(verifier_messages) > policy.discovery_max_input_chars:
            raise DiscoveryAnalysisError(
                "Der Discovery-Draft überschreitet zusammen mit den Quellen das Verifier-Limit.",
                code="verifier_input_too_large",
            )
        verifier_result = _provider_call(
            actor=actor,
            session=session,
            policy=policy,
            messages=verifier_messages,
            schema_name="autonomous_business_discovery_verifier_v1",
            schema=build_discovery_verifier_schema(),
        )
        results.append(verifier_result)
        last_result = verifier_result
        verifier = validate_verifier_payload(
            _decode_json(verifier_result, code="invalid_verifier_response")
        )

        if verifier["status"] == "repair":
            _store_failure_diagnostics(
                analysis_id=analysis.pk,
                draft=draft,
                verifier=verifier,
                snapshot_id=snapshot.pk,
            )
            if repair_used:
                raise DiscoveryAnalysisError(
                    "Der Discovery-Draft benötigt nach dem einmaligen Repair weitere Korrekturen.",
                    code="verification_not_converged",
                )
            repair_document = {
                "input": document,
                "draft": draft,
                "verifier": verifier,
            }
            repair_messages = _prompt_payload(REPAIR_SYSTEM_PROMPT, repair_document)
            if _input_chars(repair_messages) > policy.discovery_max_input_chars:
                raise DiscoveryAnalysisError(
                    "Der gezielte Discovery-Repair überschreitet das Eingabelimit.",
                    code="repair_input_too_large",
                )
            repair_result = _provider_call(
                actor=actor,
                session=session,
                policy=policy,
                messages=repair_messages,
                schema_name="autonomous_business_discovery_repair_v1",
                schema=build_discovery_json_schema(),
            )
            results.append(repair_result)
            last_result = repair_result
            draft = validate_discovery_payload(
                _decode_json(repair_result, code="invalid_repair_response"),
                allowed_refs=allowed_refs,
                evidence_text=evidence_text,
            )

            second_verifier_document = {"input": document, "draft": draft}
            second_verifier_messages = _prompt_payload(
                VERIFIER_SYSTEM_PROMPT,
                second_verifier_document,
            )
            if _input_chars(second_verifier_messages) > policy.discovery_max_input_chars:
                raise DiscoveryAnalysisError(
                    (
                        "Der reparierte Draft überschreitet zusammen mit den Quellen "
                        "das Verifier-Limit."
                    ),
                    code="verifier_input_too_large",
                )
            second_verifier_result = _provider_call(
                actor=actor,
                session=session,
                policy=policy,
                messages=second_verifier_messages,
                schema_name="autonomous_business_discovery_verifier_v1",
                schema=build_discovery_verifier_schema(),
            )
            results.append(second_verifier_result)
            last_result = second_verifier_result
            verifier = validate_verifier_payload(
                _decode_json(second_verifier_result, code="invalid_verifier_response")
            )
            if verifier["status"] == "repair":
                _store_failure_diagnostics(
                    analysis_id=analysis.pk,
                    draft=draft,
                    verifier=verifier,
                    snapshot_id=snapshot.pk,
                )
                raise DiscoveryAnalysisError(
                    "Der Discovery-Draft konvergiert nach dem begrenzten Repair nicht.",
                    code="verification_not_converged",
                )

        source_labels = {"U0": "Problem, Kontext und Nutzerkorrekturen"}
        for index, source in enumerate(snapshot.sources.order_by("filename", "id"), start=1):
            source_labels[f"S{index}"] = source.filename

        status = (
            CaptureAnalysis.Status.SUCCESS
            if verifier["status"] == "approved"
            else CaptureAnalysis.Status.WAITING_HUMAN
        )
        return _store_terminal_analysis(
            analysis_id=analysis.pk,
            status=status,
            draft=draft,
            verifier=verifier,
            source_labels=source_labels,
            snapshot_id=snapshot.pk,
            results=results,
        )
    except DiscoveryContractError as exc:
        mark_capture_analysis_failed(
            analysis_id=analysis.pk,
            error_code="invalid_discovery_contract",
            result=last_result,
        )
        raise DiscoveryAnalysisError(
            "Die Discovery-Antwort hat die serverseitige Vertragsprüfung nicht bestanden.",
            code="invalid_discovery_contract",
        ) from exc
    except DiscoveryAnalysisError as exc:
        mark_capture_analysis_failed(
            analysis_id=analysis.pk,
            error_code=exc.code,
            result=last_result,
        )
        raise
