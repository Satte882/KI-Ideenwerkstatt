import copy

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from test_issue_98_autonomous_business_discovery import _draft, _result, _verifier

from ki_radar.accelerator import architect_service
from ki_radar.accelerator import strategic_discovery as strategic
from ki_radar.accelerator.architect_contract import (
    DISCOVERY_SCHEMA_VERSION_V2,
    DiscoveryContractError,
    build_discovery_json_schema,
    discovery_versions,
    validate_discovery_payload,
)
from ki_radar.accelerator.investigation_ingestion import create_managed_discovery_source_folder
from ki_radar.accelerator.investigation_models import InvestigationSourceSnapshot
from ki_radar.accelerator.investigation_tools import (
    DiscoverySnapshotRequest,
    create_discovery_source_snapshot,
)
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.services import create_autonomous_capture_session, create_capture_session
from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.focus import get_value_stream_focus
from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.architecture.solution_selection import focus_readiness_blockers
from ki_radar.architecture.stage_focus import get_stage_focus_decision

pytestmark = pytest.mark.django_db
SCOPE = {
    "scope_start": "Eingang einer Kundenanfrage",
    "scope_end": "Vorbereitung einer Antwort",
    "scope_out": "Verbindliche Buchung und operative Durchführung",
    "reason": "Menschlich gewählter enger Lernbereich; keine Überlegenheit nachgewiesen.",
    "validation_step": "Mit Verantwortlichen den Ist-Ablauf und verfügbare Daten erheben.",
}


def make_context(owner, tmp_path, scope=None):
    scope = dict(SCOPE) if scope is None else strategic.scope_basis(scope)
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement="Mehr tragfähige Buchungen. Ist-Daten unbekannt.",
        strategic_scope=scope,
    )
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path):
        folder = create_managed_discovery_source_folder(
            actor=owner,
            capture_session_id=session.pk,
            name="Synthetische Quelle",
            uploads=[
                SimpleUploadedFile("input.md", b"Synthetic strategic goal; no observed flow.")
            ],
        )
        result = create_discovery_source_snapshot(
            actor=owner,
            request=DiscoverySnapshotRequest(capture_session_id=session.pk, folder_id=folder.pk),
        )
    snapshot = InvestigationSourceSnapshot.objects.get(pk=result.snapshot_id)
    draft = _draft()
    draft["schema_version"] = strategic.SCHEMA
    draft["scope_basis"] = scope
    draft["process_analysis"].update(
        scope_start=scope["scope_start"],
        scope_end=scope["scope_end"],
        current_flow="Ist-Ablauf unbekannt.",
        bottlenecks="",
        baseline_metrics="",
        roles="",
        systems="",
        data_objects="",
    )
    for stage in draft["stages"]:
        for field in strategic.STAGE_RATINGS:
            stage[field] = ""
        stage["time_to_value"] = "unknown"
        stage["evidence_basis"] = "hypothesis"
    for field in strategic.FOCUS_RATINGS:
        draft["focus"][field] = ""
    for item in [
        draft["value_stream"],
        draft["focus"],
        draft["process_analysis"],
        *draft["stages"],
    ]:
        item["evidence_refs"] = ["U0"]
    draft["focus"]["rationale"] = scope["reason"] or "Untersuchungsgrund noch offen."
    draft["process_analysis"]["observations"] = ""
    draft["process_analysis"]["cause_hypotheses"] = ""
    draft["facts"] = []
    draft["hypotheses"] = []
    draft["clarifications"] = [
        {
            "question": "Welche Daten sind verfügbar?",
            "impact": "Später erheben",
            "blocking": False,
            "kind": "evidence_collection",
        }
    ]
    draft["unknowns"] = [
        {
            "statement": "Ist-Ablauf, Rollen und Messwerte unbekannt.",
            "impact": "Durch Erhebung zu validieren.",
        }
    ]
    return session, snapshot, draft


@pytest.fixture
def context(owner, tmp_path):
    return make_context(owner, tmp_path)


def analyze(owner, context, monkeypatch, *, waiting=False):
    session, snapshot, draft = context
    verifier = _verifier()
    verifier["schema_version"] = strategic.VERIFIER_SCHEMA
    if waiting:
        verifier.update(
            status="waiting_human", human_question="Welche Grenze gilt bei unklarer Zuständigkeit?"
        )
    monkeypatch.setattr(
        architect_service,
        "_provider_call",
        lambda **kwargs: _result(verifier if "verifier" in kwargs["schema_name"] else draft),
    )
    result = architect_service.execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    result.refresh_from_db()
    return result


def materialize(owner, session, analysis):
    return materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )


def test_new_strategy_is_explicit_and_old_routes_unchanged(owner, context):
    session, snapshot, _ = context
    assert session.catalog_version == "3.0" and session.schema_version == "1.1"
    assert snapshot.process_context["human_scope"] == session.answers["human_scope"]
    assert snapshot.process_context["human_scope"]["actor_id"] == owner.pk
    ordinary = create_autonomous_capture_session(actor=owner, problem_statement="Betriebsproblem")
    guided = create_capture_session(actor=owner, capture_type="value_stream")
    assert ordinary.catalog_version == guided.catalog_version == "2.0"
    assert "human_scope" not in ordinary.answers
    assert discovery_versions("1.0") == ("ap1-discovery-v1", "ap1-methodology-v13")
    assert discovery_versions("2.0") == ("ap1-discovery-v2", "ap1-methodology-v14")
    assert build_discovery_json_schema(DISCOVERY_SCHEMA_VERSION_V2)["properties"]["focus"][
        "properties"
    ]["pain_intensity"]["enum"] == ["low", "medium", "high"]


def test_scope_materializes_as_exploration_without_screening_or_gate_changes(
    owner, context, monkeypatch, client
):
    session, _, draft = context
    analysis = analyze(owner, context, monkeypatch)
    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    result = materialize(owner, session, analysis)
    again = materialize(owner, session, analysis)
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    focus = get_value_stream_focus(process.stage.value_stream)
    decision = get_stage_focus_decision(process.stage.value_stream)
    assert again.reused and again.process_analysis_id == process.pk
    assert focus.status == "candidate" and not focus.is_selected
    assert all(getattr(focus, key) == "" for key in strategic.FOCUS_RATINGS)
    assert decision.is_short_path and decision.short_path_reason == SCOPE["reason"]
    assert decision.selected_by == owner
    assert focus_readiness_blockers(process)
    assert process.confirmed_causes == process.baseline_metrics == process.bottlenecks == ""
    assert process.current_flow == "Ist-Ablauf unbekannt."
    assert analysis.result_payload["draft"]["unknowns"] == draft["unknowns"]
    assert process.source_snapshot["strategic_exploration"]["human_scope"]["actor_id"] == owner.pk
    client.force_login(owner)
    assert (
        "Vorläufiger strategischer Untersuchungsrahmen"
        in client.get(process.get_absolute_url()).content.decode()
    )


def test_real_scope_uncertainty_remains_waiting_human(owner, context, monkeypatch):
    analysis = analyze(owner, context, monkeypatch, waiting=True)
    assert analysis.status == "waiting_human"
    with pytest.raises(DiscoveryMaterializationError):
        materialize(owner, context[0], analysis)
    assert not ProcessAnalysis.objects.exists()


def test_model_cannot_replace_human_decision(owner, context, monkeypatch):
    session, snapshot, _draft_payload = context
    analysis = analyze(owner, context, monkeypatch)
    session.answers["human_scope"]["actor_id"] = -1
    session.save(update_fields=["answers"])
    with pytest.raises(DiscoveryMaterializationError, match="quellengebunden"):
        materialize(owner, session, analysis)
    session.answers["human_scope"] = snapshot.process_context["human_scope"]
    session.save(update_fields=["answers"])
    payload = copy.deepcopy(analysis.result_payload)
    payload["draft"]["scope_basis"]["reason"] = "Vom Modell erfundene Zustimmung"
    analysis.result_payload = payload
    analysis.save(update_fields=["result_payload"])
    with pytest.raises(DiscoveryMaterializationError, match="Scopeangaben"):
        materialize(owner, session, analysis)
    assert not ProcessAnalysis.objects.exists()


@pytest.mark.parametrize("mutation", ["rating", "kind", "number", "cause"])
def test_v3_rejects_estimates_misclassified_blockers_and_inventions(context, mutation):
    draft = copy.deepcopy(context[2])
    if mutation == "rating":
        draft["focus"]["data_accessibility"] = "medium"
    elif mutation == "kind":
        draft["clarifications"][0]["blocking"] = True
    elif mutation == "number":
        draft["process_analysis"]["baseline_metrics"] = "Konversion 97 Prozent"
    else:
        draft["focus"]["rationale"] = "Hauptursache ist Datenmangel."
    with pytest.raises(DiscoveryContractError):
        validate_discovery_payload(
            draft, allowed_refs={"U0", "S1"}, evidence_text="Ziel", schema_version=strategic.SCHEMA
        )


def test_v3_never_reinterprets_v2_payload(context):
    with pytest.raises(DiscoveryContractError):
        validate_discovery_payload(
            context[2],
            allowed_refs={"U0", "S1"},
            evidence_text="Ziel",
            schema_version=DISCOVERY_SCHEMA_VERSION_V2,
        )


def test_missing_human_scope_blocks_even_an_approving_model(owner, tmp_path, monkeypatch):
    context = make_context(owner, tmp_path, scope={})
    analysis = analyze(owner, context, monkeypatch)
    assert analysis.status == "waiting_human"
    with pytest.raises(DiscoveryMaterializationError):
        materialize(owner, context[0], analysis)


def test_ownership_and_only_human_fields_are_accepted(owner, other_owner, context):
    with pytest.raises(ValidationError):
        create_autonomous_capture_session(
            actor=owner,
            problem_statement="Ziel",
            strategic_scope={**SCOPE, "actor_id": other_owner.pk},
        )
    with pytest.raises((PermissionDenied, CaptureSession.DoesNotExist)):
        strategic_session = context[0]
        architect_service.execute_autonomous_business_discovery(
            actor=other_owner, session_id=strategic_session.pk, snapshot_id=context[1].pk
        )


def test_actual_provider_wrapper_records_each_call_and_new_versions(owner, context, monkeypatch):
    session, snapshot, draft = context
    prompts = []

    def provider(**kwargs):
        prompts.append(kwargs)
        if "verifier" in kwargs["response_format"]["json_schema"]["name"]:
            result = _verifier()
            result["schema_version"] = strategic.VERIFIER_SCHEMA
            return _result(result)
        return _result(draft)

    monkeypatch.setattr(architect_service, "request_openrouter", provider)
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
    )
    analysis.refresh_from_db()
    assert len(analysis.result_payload["provider_calls"]) == 2
    assert (
        analysis.result_payload["contract_versions"]["verifier_prompt"] == strategic.VERIFIER_PROMPT
    )
    assert all(item["usage"] is not None for item in analysis.result_payload["provider_calls"])
    assert "human_scope" in prompts[0]["messages"][1]["content"]
    assert strategic.RULES in prompts[0]["messages"][0]["content"]


def test_v3_version_reporting_is_cohort_specific():
    from ki_radar.accelerator.ap4_evidence import current_contract_versions

    assert current_contract_versions()["discovery_schema"] == "ap1-discovery-v1"
    assert current_contract_versions("2.0")["discovery_schema"] == "ap1-discovery-v2"
    assert (
        current_contract_versions("3.0")["discovery_verifier_schema"] == strategic.VERIFIER_SCHEMA
    )


def test_scope_change_creates_new_frozen_revision_without_upgrading_old_sessions(owner, context):
    from ki_radar.accelerator.services import CaptureRevisionConflict, replace_strategic_scope

    session, snapshot, _ = context
    old_scope = copy.deepcopy(snapshot.process_context["human_scope"])
    changed = {**SCOPE, "reason": "Neue ausdrückliche menschliche Bereichsentscheidung"}
    changed_session = replace_strategic_scope(
        actor=owner, session_id=session.pk, expected_revision=session.revision, values=changed
    )
    assert changed_session.revision == session.revision + 1
    new_result = create_discovery_source_snapshot(
        actor=owner,
        request=DiscoverySnapshotRequest(
            capture_session_id=session.pk, folder_id=snapshot.folder_id
        ),
    )
    new_snapshot = InvestigationSourceSnapshot.objects.get(pk=new_result.snapshot_id)
    snapshot.refresh_from_db()
    assert snapshot.process_context["human_scope"] == old_scope
    assert new_snapshot.pk != snapshot.pk
    assert (
        strategic.frozen_human_scope(changed_session, new_snapshot)["reason"] == changed["reason"]
    )
    assert new_snapshot.manifest_hash == snapshot.manifest_hash
    with pytest.raises(CaptureRevisionConflict):
        replace_strategic_scope(
            actor=owner, session_id=session.pk, expected_revision=session.revision, values=changed
        )
    old = create_autonomous_capture_session(actor=owner, problem_statement="Betriebsproblem")
    with pytest.raises(PermissionDenied):
        replace_strategic_scope(
            actor=owner, session_id=old.pk, expected_revision=old.revision, values=SCOPE
        )


def test_existing_idea_session_is_reused_without_switching_its_contract(owner):
    from ki_radar.use_cases.idea_models import IdeaCandidate

    idea = IdeaCandidate.objects.create(title="Alt", description="Problem", submitted_by=owner)
    old = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    again = create_autonomous_capture_session(
        actor=owner,
        problem_statement=idea.description,
        idea_candidate_id=idea.pk,
        strategic_scope=SCOPE,
    )
    assert again.pk == old.pk and again.catalog_version == "2.0"
    assert "human_scope" not in again.answers


@override_settings(ACCELERATOR_STRATEGIC_DISCOVERY_ENABLED=False)
def test_rollback_blocks_new_v3_but_keeps_v2_creation(owner):
    with pytest.raises(ValidationError, match="ausgesetzt"):
        create_autonomous_capture_session(
            actor=owner, problem_statement="Ziel", strategic_scope=SCOPE
        )
    assert (
        create_autonomous_capture_session(actor=owner, problem_statement="Problem").catalog_version
        == "2.0"
    )


def test_rollback_keeps_saved_review_readable_without_model_execution(
    owner, context, monkeypatch, client
):
    analysis = analyze(owner, context, monkeypatch)
    with override_settings(ACCELERATOR_STRATEGIC_DISCOVERY_ENABLED=False):
        client.force_login(owner)
        page = client.get(reverse("accelerator:autonomous_discovery_review", args=[context[0].pk]))
        assert page.status_code == 200 and not page.context["can_confirm"]
        with pytest.raises(DiscoveryMaterializationError, match="ausgesetzt"):
            materialize(owner, context[0], analysis)
        with pytest.raises(architect_service.DiscoveryAnalysisError, match="ausgesetzt"):
            architect_service.execute_autonomous_business_discovery(
                actor=owner, session_id=context[0].pk, snapshot_id=context[1].pk
            )


@pytest.mark.parametrize("explicit_strategy,expected_catalog", [(False, "2.0"), (True, "3.0")])
def test_same_start_form_routes_only_explicit_human_strategy(
    owner, client, tmp_path, monkeypatch, explicit_strategy, expected_catalog
):
    from ki_radar.accelerator import architect_views

    monkeypatch.setattr(architect_views, "_run_analysis", lambda *args, **kwargs: None)
    client.force_login(owner)
    url = reverse("accelerator:autonomous_discovery_start")
    page = client.get(url)
    assert page.status_code == 200
    assert b'name="strategic"' in page.content
    assert b'href="?strategic=1' not in page.content
    data = {
        "problem_statement": "Strategisches Ziel. Ist-Daten unbekannt.",
        "business_unit": owner.business_unit_id,
        **SCOPE,
        "sources": SimpleUploadedFile("input.md", b"Synthetic goal; observed data unknown."),
    }
    if explicit_strategy:
        data["strategic"] = "1"
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path):
        # A stale GET parameter must not silently select v3 on an unchecked POST.
        response = client.post(url + "?strategic=1", data)
    assert response.status_code == 302
    session = CaptureSession.objects.get(owner=owner)
    assert session.catalog_version == expected_catalog
    assert ("human_scope" in session.answers) == explicit_strategy
