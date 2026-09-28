from __future__ import annotations

import copy
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator import architect_service, architect_views
from ki_radar.accelerator.architect_contract import (
    DISCOVERY_PROMPT_VERSION,
    DISCOVERY_SCHEMA_VERSION,
    DISCOVERY_VERIFIER_SCHEMA_VERSION,
    DiscoveryContractError,
    validate_discovery_payload,
)
from ki_radar.accelerator.architect_service import (
    DiscoveryAnalysisError,
    execute_autonomous_business_discovery,
)
from ki_radar.accelerator.investigation_ingestion import (
    create_managed_discovery_source_folder,
)
from ki_radar.accelerator.investigation_models import (
    InvestigationRun,
    InvestigationSourceFolder,
    InvestigationSourceSnapshot,
)
from ki_radar.accelerator.investigation_tools import (
    DiscoverySnapshotRequest,
    create_discovery_source_snapshot,
    get_discovery_source_snapshot,
)
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.retention import purge_terminal_capture_sessions
from ki_radar.accelerator.services import (
    add_autonomous_discovery_correction,
    create_autonomous_capture_session,
    create_capture_session,
)
from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.architecture.stage_focus import StageFocusDecision
from ki_radar.core.openrouter import OpenRouterResult
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def test_verifier_prompt_keeps_screening_and_implicit_transitions_in_scope():
    prompt = architect_service.VERIFIER_SYSTEM_PROMPT
    assert "Fordere keine eigene Phase für bloßes Warten" in prompt
    assert "keine gemessenen Fakten" in prompt
    assert "nicht jede denkbare" in prompt
    assert "belegt (indicative)" in prompt.replace("\n  ", " ")


@pytest.mark.parametrize(
    ("schema_name", "expected_effort"),
    [
        ("autonomous_business_discovery_v1", "low"),
        ("autonomous_business_discovery_repair_v1", "low"),
        ("autonomous_business_discovery_verifier_v1", "medium"),
    ],
)
def test_discovery_provider_reasoning_budget_matches_role(
    monkeypatch, schema_name, expected_effort
):
    observed = {}
    monkeypatch.setattr(architect_service, "reserve_accelerator_quotas", lambda **_: None)

    def fake_request(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setattr(architect_service, "request_openrouter", fake_request)
    policy = SimpleNamespace(
        capture_max_output_tokens=32768,
        timeout_seconds=120,
        capture_temperature=None,
    )

    architect_service._provider_call(
        actor=object(),
        session=object(),
        policy=policy,
        messages=[{"role": "user", "content": "input"}],
        schema_name=schema_name,
        schema={"type": "object"},
    )

    assert observed["reasoning_effort"] == expected_effort
    assert observed["max_tokens"] == policy.capture_max_output_tokens
    assert observed["timeout_seconds"] == policy.timeout_seconds
    assert observed["provider"] == {"require_parameters": True, "sort": "throughput"}


def _source_uploads(*, contradictory: bool = False):
    files = [
        SimpleUploadedFile(
            "interview.md",
            (
                "# Einkauf\n"
                "Ein freigegebener Beschaffungsbedarf startet die Lieferantenauswahl.\n"
                "Angebote werden per E-Mail eingeholt und anschließend manuell verglichen.\n"
                "Einkauf und Fachbereich bereiten die Entscheidung vor.\n"
            ).encode(),
            content_type="text/markdown",
        )
    ]
    if contradictory:
        files.append(
            SimpleUploadedFile(
                "prozessnotiz.txt",
                (
                    "Die finale Auswahl wird laut Prozessnotiz ausschließlich durch den "
                    "Fachbereich vorbereitet; der Einkauf prüft erst danach.\n"
                ).encode(),
                content_type="text/plain",
            )
        )
    return files


def _draft(*, contradiction: bool = False):
    return {
        "schema_version": DISCOVERY_SCHEMA_VERSION,
        "value_stream": {
            "name": "Beschaffung bis Lieferantenentscheidung",
            "description": "Bedarf, Lieferantensuche, Angebotsvergleich und Entscheidung.",
            "trigger": "Freigegebener Beschaffungsbedarf",
            "outcome": "Vorbereitete Lieferantenentscheidung",
            "scope_in": "Vom freigegebenen Bedarf bis zur vorbereiteten Lieferantenentscheidung",
            "scope_out": "",
            "strategic_objective": "",
            "stakeholders": "Einkauf und Fachbereich",
            "constraints": "",
            "evidence_refs": ["U0", "S1"],
        },
        "stages": [
            {
                "key": "offers",
                "sequence": 1,
                "name": "Angebote einholen",
                "description": "Angebote werden per E-Mail eingeholt.",
                "roles": "Einkauf",
                "systems": "E-Mail",
                "documents": "Lieferantenangebote",
                "pain_points": "",
                "baseline_metrics": "",
                "impact": ScreeningLevel.MEDIUM,
                "pain_intensity": ScreeningLevel.LOW,
                "improvement_potential": ScreeningLevel.MEDIUM,
                "data_accessibility": ScreeningLevel.MEDIUM,
                "change_effort": ScreeningLevel.MEDIUM,
                "time_to_value": "medium",
                "evidence_basis": "indicative",
                "evidence_refs": ["S1"],
            },
            {
                "key": "compare",
                "sequence": 2,
                "name": "Angebote vergleichen",
                "description": (
                    "Angebote werden manuell verglichen und die Entscheidung vorbereitet."
                ),
                "roles": "Einkauf und Fachbereich",
                "systems": "E-Mail",
                "documents": "Lieferantenangebote",
                "pain_points": "Manueller Vergleich",
                "baseline_metrics": "",
                "impact": ScreeningLevel.HIGH,
                "pain_intensity": ScreeningLevel.HIGH,
                "improvement_potential": ScreeningLevel.HIGH,
                "data_accessibility": ScreeningLevel.MEDIUM,
                "change_effort": ScreeningLevel.MEDIUM,
                "time_to_value": "short",
                "evidence_basis": "indicative",
                "evidence_refs": ["U0", "S1"],
            },
        ],
        "focus": {
            "recommended_stage_key": "compare",
            "business_domain": BusinessDomain.PROCUREMENT,
            "capability": "Supplier Sourcing und Angebotsvergleich",
            "strategic_impact": ScreeningLevel.MEDIUM,
            "economic_potential": ScreeningLevel.MEDIUM,
            "pain_intensity": ScreeningLevel.HIGH,
            "data_accessibility": ScreeningLevel.MEDIUM,
            "change_effort": ScreeningLevel.MEDIUM,
            "rationale": "Der geschilderte Engpass liegt im manuellen Angebotsvergleich.",
            "tradeoffs": ["Der vorgelagerte Angebotseingang bleibt Teil des Value Streams."],
            "uncertainties": [],
            "evidence_refs": ["U0", "S1"],
        },
        "process_analysis": {
            "name": "Lieferantenangebote vergleichen",
            "scope_start": "Angebote liegen vor",
            "scope_end": "Entscheidung ist vorbereitet",
            "trigger": "Lieferantenangebote sind eingegangen",
            "outcome": "Vergleichbare Entscheidungsgrundlage",
            "current_flow": "Einkauf und Fachbereich vergleichen Angebote manuell.",
            "roles": "Einkauf und Fachbereich",
            "systems": "E-Mail",
            "data_objects": "Lieferantenangebote",
            "business_rules": "",
            "handoffs": "",
            "bottlenecks": "Manueller Angebotsvergleich",
            "observations": "Der Vergleich ist der geschilderte Engpass.",
            "cause_hypotheses": (
                "Uneinheitliche Angebotsstruktur könnte den manuellen Aufwand erhöhen."
            ),
            "constraints": "",
            "exceptions": "",
            "baseline_metrics": "",
            "evidence_refs": ["U0", "S1"],
        },
        "facts": [
            {
                "statement": "Angebote werden per E-Mail eingeholt und manuell verglichen.",
                "evidence_refs": ["S1"],
            }
        ],
        "hypotheses": [
            {
                "statement": (
                    "Uneinheitliche Angebotsstrukturen könnten den manuellen Aufwand erhöhen."
                ),
                "evidence_refs": ["S1"],
            }
        ],
        "unknowns": [
            {
                "statement": "Eine belastbare Zeitbaseline ist nicht genannt.",
                "impact": (
                    "Der Scope kann entschieden werden; der spätere Nutzen braucht Messwerte."
                ),
            }
        ],
        "clarifications": [],
        "contradictions": (
            [
                {
                    "statement": (
                        "Interview und Prozessnotiz beschreiben die Rollenfolge bei der "
                        "Entscheidungsvorbereitung unterschiedlich."
                    ),
                    "evidence_refs": ["S1", "S2"],
                }
            ]
            if contradiction
            else []
        ),
    }


def _verifier(status="approved", *, human_question="", repair_instructions=""):
    checks = {
        "source_grounding": True,
        "scope_quality": True,
        "stage_sequence": True,
        "focus_fit": True,
        "hypothesis_separation": True,
        "unknowns_visible": True,
        "contradictions_preserved": True,
    }
    findings = []
    if status == "repair":
        checks["source_grounding"] = False
        findings = [
            {
                "code": "unsupported_statement",
                "message": "Eine Aussage ist nicht hinreichend belegt.",
            }
        ]
    if status == "waiting_human":
        checks["scope_quality"] = False
        findings = [
            {
                "code": "scope_ambiguity",
                "message": "Zwei fachlich plausible Scope-Grenzen bleiben offen.",
            }
        ]
    return {
        "schema_version": DISCOVERY_VERIFIER_SCHEMA_VERSION,
        "status": status,
        "checks": checks,
        "critical_findings": findings,
        "repair_instructions": repair_instructions,
        "human_question": human_question,
    }


def _result(payload):
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model="test/model",
        usage={
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "cost": "0.001",
        },
        output_chars=len(content),
        finish_reason="stop",
    )


def _session_and_snapshot(*, owner, tmp_path, contradictory=False):
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement=(
            "Die Bearbeitung von Lieferantenangeboten dauert zu lange. "
            "Angebote werden manuell verglichen."
        ),
        business_context=(
            "Der Einkauf bereitet mit dem Fachbereich die Lieferantenentscheidung vor."
        ),
    )
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        folder = create_managed_discovery_source_folder(
            actor=owner,
            capture_session_id=session.pk,
            name="AP1 Quellen",
            uploads=_source_uploads(contradictory=contradictory),
        )
        result = create_discovery_source_snapshot(
            actor=owner,
            request=DiscoverySnapshotRequest(
                capture_session_id=session.pk,
                folder_id=folder.pk,
            ),
        )
    return session, InvestigationSourceSnapshot.objects.get(pk=result.snapshot_id)


def _approved_analysis(*, session, snapshot, draft=None):
    draft = copy.deepcopy(draft or _draft())
    now = timezone.now()
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=session.owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        model_name="test/model",
        prompt_version=DISCOVERY_PROMPT_VERSION,
        extraction_schema_version=DISCOVERY_SCHEMA_VERSION,
        finished_at=now,
        result_payload={
            "draft": draft,
            "source_labels": {"U0": "Problem und Kontext", "S1": "interview.md"},
            "discovery_snapshot_id": str(snapshot.pk),
        },
        verification_payload=_verifier(),
    )


@pytest.mark.django_db
def test_autonomous_capture_reuses_capture_session_without_guided_questionnaire(owner):
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement="Angebote werden manuell verglichen.",
        business_context="Einkauf",
    )

    assert session.capture_type == CaptureSession.CaptureType.VALUE_STREAM
    assert session.mode == CaptureSession.Mode.AUTONOMOUS
    assert session.required_question_count == 0
    assert session.answers["problem_statement"] == "Angebote werden manuell verglichen."


@pytest.mark.django_db
def test_guided_capture_remains_default(owner):
    session = create_capture_session(
        actor=owner,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )

    assert session.mode == CaptureSession.Mode.GUIDED
    assert session.required_question_count > 0


@pytest.mark.django_db
def test_autonomous_capture_requires_active_user_business_unit(owner):
    owner.business_unit.is_active = False
    owner.business_unit.save(update_fields=["is_active"])

    with pytest.raises(ValidationError, match="aktive Organisationseinheit"):
        create_autonomous_capture_session(
            actor=owner,
            problem_statement="Manuelle Bearbeitung dauert zu lange.",
        )


@pytest.mark.django_db
def test_discovery_snapshot_uses_existing_source_contract_and_is_capture_bound(owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)

    assert snapshot.capture_session == session
    assert snapshot.process_analysis is None
    assert snapshot.process_version is None
    assert snapshot.sources.count() == 1
    assert snapshot.sources.get().filename == "interview.md"
    assert snapshot.sources.get().content_sha256
    assert snapshot.manifest_hash


@pytest.mark.django_db
def test_discovery_snapshot_is_not_readable_by_other_owner(owner, other_owner, tmp_path):
    _session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)

    with pytest.raises(PermissionDenied):
        get_discovery_source_snapshot(actor=other_owner, snapshot_id=snapshot.pk)


@pytest.mark.django_db
def test_case_a_clear_scope_finishes_ready_for_scope_review(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    calls = iter([_result(_draft()), _result(_verifier())])
    monkeypatch.setattr(architect_service, "_provider_call", lambda **_kwargs: next(calls))

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert analysis.result_payload["draft"]["focus"]["recommended_stage_key"] == "compare"
    assert analysis.verification_payload["status"] == "approved"
    assert analysis.open_questions == []


@pytest.mark.django_db
@override_settings(
    ACCELERATOR_LLM_MAX_INPUT_CHARS="12000",
    ACCELERATOR_DISCOVERY_MAX_INPUT_CHARS="40000",
)
def test_discovery_verifier_accepts_full_draft_above_generic_input_limit(
    owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    draft = _draft()
    draft["value_stream"]["description"] += "x" * 13000
    calls = iter([_result(draft), _result(_verifier())])
    observed_messages = []

    def fake_call(**kwargs):
        observed_messages.append(kwargs["messages"])
        return next(calls)

    monkeypatch.setattr(architect_service, "_provider_call", fake_call)

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert len(observed_messages[1][1]["content"]) > 12000
    assert len(observed_messages[1][1]["content"]) < 40000


@pytest.mark.django_db
def test_case_b_real_ambiguity_waits_for_one_precise_human_question(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    draft = _draft()
    draft["focus"]["uncertainties"] = [
        "Die Quellen lassen offen, ob der Fokus beim Angebotseingang oder Vergleich beginnen soll."
    ]
    draft["clarifications"] = [
        {
            "question": "Beginnt der verantwortete Prozess erst bei vollständigem Angebotseingang?",
            "impact": "Die Antwort bestimmt die Scope-Startgrenze.",
            "blocking": True,
        }
    ]
    verifier = _verifier(
        "waiting_human",
        human_question=(
            "Beginnt der verantwortete Prozess erst, wenn alle Lieferantenangebote vorliegen?"
        ),
    )
    calls = iter([_result(draft), _result(verifier)])
    monkeypatch.setattr(architect_service, "_provider_call", lambda **_kwargs: next(calls))

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.WAITING_HUMAN
    assert analysis.verification_payload["status"] == "waiting_human"
    assert "alle Lieferantenangebote" in analysis.verification_payload["human_question"]
    assert not ValueStream.objects.exists()


@pytest.mark.django_db
def test_case_c_contradictory_sources_remain_visible(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(
        owner=owner,
        tmp_path=tmp_path,
        contradictory=True,
    )
    draft = _draft(contradiction=True)
    calls = iter([_result(draft), _result(_verifier())])
    monkeypatch.setattr(architect_service, "_provider_call", lambda **_kwargs: next(calls))

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert len(analysis.contradictions) == 1
    assert analysis.contradictions[0]["evidence_refs"] == ["S1", "S2"]


@pytest.mark.django_db
def test_discovery_repairs_one_deterministic_contract_violation(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    invalid = _draft()
    invalid["contradictions"] = [
        {
            "statement": "Die Rollenfolge sei widersprüchlich.",
            "evidence_refs": ["S1"],
        }
    ]
    repaired = copy.deepcopy(invalid)
    repaired["contradictions"] = []
    calls = [
        _result(invalid),
        _result(repaired),
        _result(_verifier()),
    ]
    observed = []

    def fake_call(**kwargs):
        observed.append(kwargs["schema_name"])
        return calls[len(observed) - 1]

    monkeypatch.setattr(architect_service, "_provider_call", fake_call)

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert observed == [
        "autonomous_business_discovery_v1",
        "autonomous_business_discovery_repair_v1",
        "autonomous_business_discovery_verifier_v1",
    ]
    assert analysis.result_payload["draft"]["contradictions"] == []


@pytest.mark.django_db
def test_contract_repair_consumes_the_single_repair_budget(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    invalid = _draft()
    invalid["contradictions"] = [
        {
            "statement": "Die Rollenfolge sei widersprüchlich.",
            "evidence_refs": ["S1"],
        }
    ]
    repaired = copy.deepcopy(invalid)
    repaired["contradictions"] = []
    calls = [
        _result(invalid),
        _result(repaired),
        _result(
            _verifier(
                "repair",
                repair_instructions="Noch eine weitere fachliche Reparatur wäre nötig.",
            )
        ),
    ]
    observed = []

    def fake_call(**kwargs):
        observed.append(kwargs["schema_name"])
        return calls[len(observed) - 1]

    monkeypatch.setattr(architect_service, "_provider_call", fake_call)

    with pytest.raises(DiscoveryAnalysisError, match="einmaligen Repair"):
        execute_autonomous_business_discovery(
            actor=owner,
            session_id=session.pk,
            snapshot_id=snapshot.pk,
        )

    assert observed == [
        "autonomous_business_discovery_v1",
        "autonomous_business_discovery_repair_v1",
        "autonomous_business_discovery_verifier_v1",
    ]
    failed = CaptureAnalysis.objects.get(session=session)
    assert failed.status == CaptureAnalysis.Status.FAILED
    assert failed.error_code == "verification_not_converged"
    assert failed.verification_payload["status"] == "repair"
    assert failed.result_payload["draft"]["contradictions"] == []


@pytest.mark.django_db
def test_verifier_finding_is_retained_if_repair_provider_fails(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    verifier = _verifier(
        "repair",
        repair_instructions="Process Scope enger und quellengebunden formulieren.",
    )
    calls = [_result(_draft()), _result(verifier)]

    def fake_call(**kwargs):
        if len(calls) == 0:
            raise DiscoveryAnalysisError(
                "Die OpenRouter-Anfrage hat das Zeitlimit überschritten.",
                code="timeout",
            )
        return calls.pop(0)

    monkeypatch.setattr(architect_service, "_provider_call", fake_call)

    with pytest.raises(DiscoveryAnalysisError, match="Zeitlimit"):
        execute_autonomous_business_discovery(
            actor=owner,
            session_id=session.pk,
            snapshot_id=snapshot.pk,
        )

    failed = CaptureAnalysis.objects.get(session=session)
    assert failed.status == CaptureAnalysis.Status.FAILED
    assert failed.error_code == "timeout"
    assert failed.verification_payload["status"] == "repair"
    assert (
        failed.verification_payload["repair_instructions"]
        == "Process Scope enger und quellengebunden formulieren."
    )
    assert failed.result_payload["draft"]["process_analysis"]


@pytest.mark.django_db
def test_discovery_has_one_bounded_repair_and_independent_reverification(
    owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    original = _draft()
    repaired = copy.deepcopy(original)
    repaired["hypotheses"][0]["statement"] = (
        "Die Ursache der manuellen Vergleichsarbeit ist noch zu untersuchen."
    )
    calls = [
        _result(original),
        _result(
            _verifier(
                "repair",
                repair_instructions="Unbelegte Ursachenannahme als Hypothese abschwächen.",
            )
        ),
        _result(repaired),
        _result(_verifier()),
    ]
    observed = []

    def fake_call(**kwargs):
        observed.append(kwargs["schema_name"])
        return calls[len(observed) - 1]

    monkeypatch.setattr(architect_service, "_provider_call", fake_call)

    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert len(observed) == 4
    assert observed.count("autonomous_business_discovery_verifier_v1") == 2
    assert analysis.result_payload["draft"]["hypotheses"][0]["statement"] == (
        "Die Ursache der manuellen Vergleichsarbeit ist noch zu untersuchen."
    )


def test_unreported_number_is_rejected_before_materialization():
    draft = _draft()
    draft["process_analysis"]["baseline_metrics"] = "Bearbeitung dauert 37 Minuten."
    with pytest.raises(DiscoveryContractError, match="37"):
        validate_discovery_payload(
            draft,
            allowed_refs={"U0", "S1"},
            evidence_text="Angebote werden manuell verglichen.",
        )


@pytest.mark.django_db
def test_scope_confirmation_materializes_canonical_domain_and_starts_existing_investigation(
    owner, tmp_path
):
    session, discovery_snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    analysis = _approved_analysis(session=session, snapshot=discovery_snapshot)

    result = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )

    session.refresh_from_db()
    stream = ValueStream.objects.get(pk=result.value_stream_id)
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    focus = ValueStreamFocus.objects.get(value_stream=stream)
    stage_focus = StageFocusDecision.objects.get(value_stream=stream)
    run = InvestigationRun.objects.get(pk=result.investigation_run_id)
    investigation_snapshot = InvestigationSourceSnapshot.objects.get(
        pk=result.investigation_snapshot_id
    )

    assert session.status == CaptureSession.Status.COMPLETED
    assert session.target_value_stream == stream
    assert stream.status == ValueStream.Status.ACTIVE
    assert stream.stages.count() == 2
    assert focus.status == ValueStreamFocus.Status.SELECTED
    assert focus.is_selected
    assert stage_focus.selected_stage == process.stage
    for stage in stream.stages.all():
        criteria = stage_focus.criteria_for(stage)
        assert criteria["impact"] in ScreeningLevel.values
        assert criteria["pain_intensity"] in ScreeningLevel.values
        assert criteria["improvement_potential"] in ScreeningLevel.values
        assert criteria["data_accessibility"] in ScreeningLevel.values
        assert criteria["change_effort"] in ScreeningLevel.values
        assert criteria["time_to_value"] in {"unknown", "short", "medium", "long"}
        assert criteria["evidence_basis"] in {"hypothesis", "indicative", "measured"}
    assert process.status == ProcessAnalysis.Status.DRAFT
    assert process.stage.name == "Angebote vergleichen"
    assert run.process_analysis == process
    assert run.source_snapshot == investigation_snapshot
    assert run.execution_requested_at is not None
    assert investigation_snapshot.manifest_hash == discovery_snapshot.manifest_hash
    assert investigation_snapshot.process_context["discovery_snapshot_id"] == str(
        discovery_snapshot.pk
    )
    assert list(
        investigation_snapshot.sources.order_by("filename").values_list(
            "filename", "content_sha256", "content"
        )
    ) == list(
        discovery_snapshot.sources.order_by("filename").values_list(
            "filename", "content_sha256", "content"
        )
    )


@pytest.mark.django_db
def test_materialization_is_idempotent_for_same_confirmed_analysis(owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    revision = session.revision

    first = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=revision,
    )
    second = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=revision,
    )

    assert second.reused is True
    assert second.value_stream_id == first.value_stream_id
    assert second.process_analysis_id == first.process_analysis_id
    assert second.investigation_run_id == first.investigation_run_id
    assert ValueStream.objects.count() == 1
    assert ProcessAnalysis.objects.count() == 1
    assert InvestigationRun.objects.count() == 1


@pytest.mark.django_db
def test_foreign_owner_cannot_open_autonomous_review(client, owner, other_owner):
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement="Manuelle Bearbeitung dauert zu lange.",
    )
    client.force_login(other_owner)

    response = client.get(
        reverse(
            "accelerator:autonomous_discovery_review",
            kwargs={"session_id": session.pk},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_reader_cannot_open_autonomous_start(client, reader):
    client.force_login(reader)

    assert client.get(reverse("accelerator:autonomous_discovery_start")).status_code == 403


@pytest.mark.django_db
def test_start_surface_is_minimal_and_accepts_only_current_source_scope(client, owner):
    client.force_login(owner)

    response = client.get(reverse("accelerator:autonomous_discovery_start"))
    content = response.content.decode()

    assert response.status_code == 200
    assert "Geschäftsproblem oder Ziel" in content
    assert "Zusätzlicher Geschäftskontext" in content
    assert ".md" in content
    assert ".txt" in content
    assert ".csv" in content
    assert "Value-Stream-Phasen" not in content


@pytest.mark.django_db
def test_start_post_creates_capture_snapshot_without_guided_questions(
    client, owner, tmp_path, monkeypatch
):
    monkeypatch.setattr(architect_views, "_run_analysis", lambda *_args, **_kwargs: None)
    client.force_login(owner)

    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        response = client.post(
            reverse("accelerator:autonomous_discovery_start"),
            {
                "problem_statement": "Angebote werden manuell verglichen.",
                "business_context": "Einkauf und Fachbereich entscheiden gemeinsam.",
                "sources": _source_uploads(),
            },
        )

    session = CaptureSession.objects.get(mode=CaptureSession.Mode.AUTONOMOUS)
    assert response.status_code == 302
    assert response.url == reverse(
        "accelerator:autonomous_discovery_review",
        kwargs={"session_id": session.pk},
    )
    assert InvestigationSourceFolder.objects.get(capture_session=session)
    assert InvestigationSourceSnapshot.objects.get(capture_session=session)
    assert session.answered_required_count == 0


@pytest.mark.django_db
def test_case_b_human_clarification_continues_on_same_snapshot(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    ambiguous = _draft()
    ambiguous["clarifications"] = [
        {
            "question": "Beginnt der Prozess erst, wenn alle Angebote vorliegen?",
            "impact": "Die Antwort bestimmt die Scope-Startgrenze.",
            "blocking": True,
        }
    ]
    first_calls = iter(
        [
            _result(ambiguous),
            _result(
                _verifier(
                    "waiting_human",
                    human_question="Beginnt der Prozess erst, wenn alle Angebote vorliegen?",
                )
            ),
        ]
    )
    monkeypatch.setattr(
        architect_service,
        "_provider_call",
        lambda **_kwargs: next(first_calls),
    )

    waiting = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    assert waiting.status == CaptureAnalysis.Status.WAITING_HUMAN

    session = add_autonomous_discovery_correction(
        actor=owner,
        session_id=session.pk,
        expected_revision=session.revision,
        correction="Ja. Der Process Scope beginnt erst, wenn alle Angebote vorliegen.",
    )
    resolved = _draft()
    second_calls = iter([_result(resolved), _result(_verifier())])
    monkeypatch.setattr(
        architect_service,
        "_provider_call",
        lambda **_kwargs: next(second_calls),
    )

    approved = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )

    assert approved.status == CaptureAnalysis.Status.SUCCESS
    assert approved.source_revision == session.revision
    assert approved.result_payload["discovery_snapshot_id"] == str(snapshot.pk)
    stored_snapshot = InvestigationSourceSnapshot.objects.get(pk=snapshot.pk)
    assert stored_snapshot.manifest_hash == snapshot.manifest_hash


@pytest.mark.django_db
def test_materialization_rejects_focus_that_does_not_match_reviewed_process_scope(owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    analysis = _approved_analysis(session=session, snapshot=snapshot)

    with pytest.raises(DiscoveryMaterializationError, match="Process-Scope"):
        materialize_discovery_and_start_investigation(
            actor=owner,
            session_id=session.pk,
            analysis_id=analysis.pk,
            selected_stage_key="offers",
            expected_revision=session.revision,
        )

    assert not ValueStream.objects.exists()
    assert not ProcessAnalysis.objects.exists()
    assert not InvestigationRun.objects.exists()


@pytest.mark.django_db
def test_alternative_focus_in_review_triggers_reanalysis_before_materialization(
    client, owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    _approved_analysis(session=session, snapshot=snapshot)
    observed = {}

    def fake_run(_request, *, session, snapshot):
        observed["revision"] = session.revision
        observed["snapshot_id"] = snapshot.pk
        observed["correction"] = session.answers["corrections"][-1]["text"]
        return None

    monkeypatch.setattr(architect_views, "_run_analysis", fake_run)
    client.force_login(owner)

    response = client.post(
        reverse(
            "accelerator:autonomous_discovery_review",
            kwargs={"session_id": session.pk},
        ),
        {
            "action": "confirm",
            "revision": session.revision,
            "selected_stage_key": "offers",
        },
    )

    session.refresh_from_db()
    assert response.status_code == 302
    assert observed["revision"] == session.revision
    assert observed["snapshot_id"] == snapshot.pk
    assert "Angebote einholen" in observed["correction"]
    assert "Angebote vergleichen" in observed["correction"]
    assert not ValueStream.objects.exists()
    assert not ProcessAnalysis.objects.exists()
    assert not InvestigationRun.objects.exists()


@pytest.mark.django_db
def test_expired_autonomous_capture_can_be_purged_with_temporary_evidence(owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    folder_id = snapshot.folder_id
    snapshot_id = snapshot.pk
    now = timezone.now()
    CaptureSession.objects.filter(pk=session.pk).update(
        status=CaptureSession.Status.EXPIRED,
        expired_at=now - timedelta(days=8),
    )

    deleted = purge_terminal_capture_sessions(now=now)

    assert deleted == 1
    assert not CaptureSession.objects.filter(pk=session.pk).exists()
    assert not InvestigationSourceFolder.objects.filter(pk=folder_id).exists()
    assert not InvestigationSourceSnapshot.objects.filter(pk=snapshot_id).exists()
