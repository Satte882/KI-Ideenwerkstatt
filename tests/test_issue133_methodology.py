"""Methodical boundaries, independent of any real provider response quality."""

import copy
import json
from pathlib import Path

import pytest
from django.urls import reverse
from test_issue_98_autonomous_business_discovery import (
    _approved_analysis,
    _draft,
    _result,
    _session_and_snapshot,
    _verifier,
)

from ki_radar.accelerator import architect_service
from ki_radar.accelerator.architect_contract import (
    DiscoveryContractError,
    blocking_discovery_questions,
    discovery_methodical_findings,
    validate_discovery_payload,
)
from ki_radar.accelerator.models import CaptureAnalysis
from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.models import ValueStream


@pytest.mark.parametrize("case", ["A", "C", "D"])
def test_original_real_provider_faults_are_detected_without_another_call(case):
    path = Path(__file__).resolve().parents[1] / "artifacts" / "issue133" / "live" / f"{case}.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    draft = record["analyses"][0]["result_payload"]["draft"]
    assert discovery_methodical_findings(draft)


def test_qualified_hypothesis_cannot_leak_as_certain_tradeoff():
    draft = _draft()
    draft["hypotheses"] = [
        {"statement": "Der Datenzugang könnte die Ursache sein.", "evidence_refs": ["U0"]}
    ]
    draft["focus"]["tradeoffs"] = ["Der Datenzugang verursacht die Wartezeit."]
    findings = discovery_methodical_findings(draft)
    assert any("tradeoffs[0]" in item for item in findings)
    draft["focus"]["tradeoffs"] = [
        "Unbestätigte Hypothese: Datenzugang könnte Wartezeit verursachen."
    ]
    assert discovery_methodical_findings(draft) == ()


def test_qualitative_change_effect_is_not_an_observed_fact():
    draft = _draft()
    draft["focus"]["tradeoffs"] = ["Intensivere Abstimmung sichert die Informationskette."]
    assert any("tradeoffs[0]" in item for item in discovery_methodical_findings(draft))
    draft["focus"]["tradeoffs"] = [
        "Intensivere Abstimmung könnte die Informationskette sichern; Wirkung nicht belegt."
    ]
    assert not discovery_methodical_findings(draft)


def test_hypothetically_qualified_causality_is_accepted_in_same_sentence():
    draft = _draft()
    draft["focus"]["rationale"] = (
        "Hypothetisch führt der Abstimmungsaufwand zu diesen Unklarheiten."
    )
    assert not discovery_methodical_findings(draft)


@pytest.mark.django_db
def test_historical_solution_preview_is_readable_but_not_a_fresh_provider_contract(
    owner, business_unit
):
    from test_evaluated_solution_workflow_initial_critic import (
        make_process,
        valid_generation_payload,
    )

    from ki_radar.accelerator.solution_generation_effective import (
        build_validated_effective_solution_payload,
    )
    from ki_radar.accelerator.solution_generation_sources import (
        build_solution_generation_source_context,
    )
    from ki_radar.accelerator.solution_generation_validation import (
        SolutionGenerationContractError,
        validate_solution_generation_payload,
    )

    source = build_solution_generation_source_context(make_process(owner, business_unit))
    historical = valid_generation_payload()
    historical["prompt_version"] = "1.2"
    assert build_validated_effective_solution_payload(historical, source)["prompt_version"] == "1.2"
    with pytest.raises(SolutionGenerationContractError, match="Prompt-Version"):
        validate_solution_generation_payload(historical, source)


@pytest.mark.django_db
def test_critic_receives_hypothesis_context_even_when_option_does_not_reference_it(
    owner, business_unit
):
    from test_evaluated_solution_workflow_initial_critic import (
        make_process,
        valid_generation_payload,
    )

    from ki_radar.accelerator.solution_critic_prompt import build_solution_critic_messages
    from ki_radar.accelerator.solution_generation_sources import (
        build_solution_generation_source_context,
    )
    from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot

    process = make_process(owner, business_unit)
    process.cause_hypotheses = "Fehlende Abstimmung könnte die Wartezeit erklären; unbestätigt."
    process.save()
    source = build_solution_generation_source_context(process)
    snapshot = build_solution_quality_snapshot(
        preview_payload=valid_generation_payload(), source_context=source
    )
    document = json.loads(build_solution_critic_messages(snapshot, source)[1]["content"])
    assert "process.cause_hypotheses" not in document["sources"]
    assert document["diagnosis"]["sources"]["process.cause_hypotheses"] == process.cause_hypotheses
    assert document["diagnosis"]["validation_state"] == "not_validated"


@pytest.mark.django_db
@pytest.mark.parametrize("blocking", [True, False])
def test_generator_blocker_survives_approving_verifier(owner, tmp_path, monkeypatch, blocking):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    draft = _draft()
    draft["clarifications"] = [
        {
            "question": "Welcher Untersuchungsbereich ist fachlich begründet?",
            "impact": "Konkurrierende Bereiche sind nicht abgegrenzt.",
            "blocking": blocking,
        }
    ]
    calls = iter([_result(draft), _result(_verifier())])
    monkeypatch.setattr(architect_service, "_provider_call", lambda **kwargs: next(calls))
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    assert analysis.status == ("waiting_human" if blocking else "success")
    assert analysis.result_payload["draft"] == draft
    if blocking:
        assert (
            analysis.verification_payload["human_question"]
            == draft["clarifications"][0]["question"]
        )
    assert not ValueStream.objects.exists()


def test_entire_stage_chain_triggers_existing_contract_repair():
    draft = _draft()
    draft["process_analysis"]["current_flow"] = "offers -> compare"
    with pytest.raises(DiscoveryContractError, match="alle Value-Stream-Phasen"):
        validate_discovery_payload(draft, allowed_refs={"U0", "S1"}, evidence_text="")


@pytest.mark.django_db
def test_methodical_contract_collects_semantic_findings_before_single_repair(
    owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    original = _draft()
    original["process_analysis"]["current_flow"] = "offers -> compare"
    original["facts"][0]["statement"] = "Neueinstellungen sind ausgeschlossen."
    repaired = _draft()
    observed = []
    responses = iter(
        [
            _result(original),
            _result(
                _verifier("repair", repair_instructions="Keine absolute Personalvorgabe erfinden.")
            ),
            _result(repaired),
            _result(_verifier()),
        ]
    )

    def provider(**kwargs):
        observed.append(kwargs)
        return next(responses)

    monkeypatch.setattr(architect_service, "_provider_call", provider)
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
    )
    assert [item["schema_name"] for item in observed] == [
        "autonomous_business_discovery_v1",
        "autonomous_business_discovery_verifier_v1",
        "autonomous_business_discovery_repair_v1",
        "autonomous_business_discovery_verifier_v1",
    ]
    repair_document = json.loads(observed[2]["messages"][1]["content"])
    assert repair_document["contract_errors"]
    assert "Personalvorgabe" in repair_document["verifier"]["repair_instructions"]
    assert analysis.status == "success"
    assert analysis.result_payload["draft"] == repaired


@pytest.mark.django_db
@pytest.mark.parametrize("historical", [False, True])
def test_saved_approved_draft_cannot_bypass_decision_gap(client, owner, tmp_path, historical):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    draft = _draft()
    draft["clarifications"] = [
        {"question": "Ablauf unbekannt?", "impact": "Scope offen", "blocking": True}
    ]
    analysis = _approved_analysis(session=session, snapshot=snapshot, draft=draft)
    if historical:
        analysis.prompt_version = "ap1-discovery-v1"
        analysis.save(update_fields=["prompt_version"])
    client.force_login(owner)
    response = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert response.context["analysis"].pk == analysis.pk
    assert not response.context["can_confirm"]
    assert response.context["waiting_human"]
    assert "Ablauf unbekannt?" in response.content.decode()
    assert response.context["review_outdated"] is historical
    with pytest.raises(DiscoveryMaterializationError) as error:
        materialize_discovery_and_start_investigation(
            actor=owner,
            session_id=session.pk,
            analysis_id=analysis.pk,
            selected_stage_key="compare",
            expected_revision=session.revision,
        )
    assert error.value.code == (
        "analysis_review_outdated" if historical else "decision_blocking_clarification"
    )
    analysis.refresh_from_db()
    assert analysis.status == CaptureAnalysis.Status.SUCCESS  # historical fact not rewritten
    assert not ValueStream.objects.exists()


@pytest.mark.django_db
def test_repair_precedes_missing_evidence_question_and_revalidates(owner, tmp_path, monkeypatch):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    original = _draft()
    repaired = copy.deepcopy(original)
    repaired["focus"]["rationale"] = "Vorläufiger Untersuchungsbereich; Ursache nicht belegt."
    repaired["clarifications"] = [
        {
            "question": "Was belegt die Ursache?",
            "impact": "Keine gesicherte Ursache",
            "blocking": True,
        }
    ]
    calls = iter(
        [
            _result(original),
            _result(
                _verifier(
                    "repair", repair_instructions="Unbelegte Kausalbehauptung im Fokus entfernen."
                )
            ),
            _result(repaired),
            _result(_verifier()),
        ]
    )
    observed = []

    def provider(**kwargs):
        observed.append(kwargs["schema_name"])
        return next(calls)

    monkeypatch.setattr(architect_service, "_provider_call", provider)
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    assert len(observed) == 4
    assert "repair" in observed[2]
    assert "verifier" in observed[3]
    assert analysis.result_payload["draft"] == repaired
    assert analysis.status == "waiting_human"
    assert blocking_discovery_questions(repaired) == ("Was belegt die Ursache?",)
