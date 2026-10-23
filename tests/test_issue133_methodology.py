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


def test_accepted_a_replay_nominal_side_cause_is_now_rejected():
    record = json.loads(
        (
            Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology/A-replay-v7.json"
        ).read_text(encoding="utf-8")
    )
    draft = record["analyses"][-1]["result_payload"]["draft"]
    assert any("pain_points" in error for error in discovery_methodical_findings(draft))


def test_a_source_review_still_contains_an_unqualified_secondary_cause():
    path = Path(__file__).resolve().parents[1] / (
        "artifacts/issue133/methodology/A-revalidate-v12.json"
    )
    draft = json.loads(path.read_text(encoding="utf-8"))["analyses"][-1]["result_payload"]["draft"]
    assert any(
        "stages[0].pain_points" in finding for finding in discovery_methodical_findings(draft)
    )


@pytest.mark.parametrize(
    ("case", "path"), [("A", "stages[0].pain_points"), ("B", "focus.rationale")]
)
def test_real_source_repairs_preserve_all_unaffected_fields_and_decision_gaps(case, path):
    evidence = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"
    record = json.loads((evidence / f"{case}-revalidate-v13.json").read_text(encoding="utf-8"))
    analysis = record["analyses"][-1]
    history = analysis["result_payload"]["review_history"]
    assert len(history) == 2
    assert history[1]["incoming_repair"]["allowed_fields"] == [path]
    # Independently remove only the allowed leaf and compare the complete drafts.
    before, after = copy.deepcopy(history[0]["draft"]), copy.deepcopy(history[1]["draft"])
    if case == "A":
        assert "unbestätigte" in after["stages"][0]["pain_points"]
        before["stages"][0].pop("pain_points")
        after["stages"][0].pop("pain_points")
    else:
        assert "erste Kundenkontakt" not in after["focus"]["rationale"]
        before["focus"].pop("rationale")
        after["focus"].pop("rationale")
    assert before == after
    assert analysis["status"] == "waiting_human"
    assert blocking_discovery_questions(history[-1]["draft"])
    assert not discovery_methodical_findings(history[-1]["draft"])


@pytest.mark.parametrize("version", ["v14", "v15"])
def test_real_c_solution_repair_does_not_turn_unknown_reachability_into_an_outage(version):
    evidence = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"
    record = json.loads((evidence / f"C-solutions-{version}.json").read_text(encoding="utf-8"))
    runs = {run["step_type"]: run for run in record["quality_runs"]}
    assert runs["initial_critic"]["result_payload"]["findings"][0]["repairable"]
    patches = record["solution_preview"]["machine_repair"]["patches"]
    assert {patch["option"] for patch in patches} == {
        "organizational",
        "rule_automation",
        "assistant",
    }
    for patch in patches:
        assert patch["field"] == "bottleneck_coverage"
        assert "offene Voraussetzung" in patch["statement"]["text"]
        assert "bestätigte Ursache: keine" in patch["statement"]["text"]
    assert runs["final_critic"]["status"] == "success"
    assert not record["cause_confirmed"]
    assert not record["scope_confirmed"]


def test_real_d_solution_repair_leaves_integration_need_explicitly_unknown():
    evidence = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"
    record = json.loads((evidence / "D-solutions-v15.json").read_text(encoding="utf-8"))
    patches = record["solution_preview"]["machine_repair"]["patches"]
    assert len(patches) == 1
    assert patches[0]["option"] == "assistant"
    assert patches[0]["field"] == "integration_impact"
    assert "ist offen, ob" in patches[0]["statement"]["text"]
    runs = {run["step_type"]: run for run in record["quality_runs"]}
    assert runs["initial_critic"]["result_payload"]["findings"][0]["repairable"]
    assert runs["final_critic"]["status"] == "success"
    assert not record["cause_confirmed"]
    assert not record["scope_confirmed"]


def test_v15_c_late_finding_is_not_mistaken_for_semantic_acceptance():
    evidence = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"
    record = json.loads((evidence / "C-solutions-v15.json").read_text(encoding="utf-8"))
    final = next(run for run in record["quality_runs"] if run["step_type"] == "final_critic")
    assert final["status"] == "success"  # transport success is not semantic acceptance
    assert any(
        item["repairable"] and item["field"] == "technology_constraints"
        for item in final["result_payload"]["findings"]
    )


def test_current_c_critic_collects_the_complete_cross_field_correction_before_repair():
    evidence = Path(__file__).resolve().parents[1] / "artifacts/issue133/methodology"
    record = json.loads((evidence / "C-solutions-v16.json").read_text(encoding="utf-8"))
    patches = record["solution_preview"]["machine_repair"]["patches"]
    assert {(patch["option"], patch["field"]) for patch in patches} == {
        ("organizational", "bottleneck_coverage"),
        ("organizational", "technology_constraints"),
        ("rule_automation", "bottleneck_coverage"),
        ("rule_automation", "technology_constraints"),
        ("assistant", "bottleneck_coverage"),
    }
    for patch in patches:
        assert "ungeprüft" in patch["statement"]["text"]
        assert "Engpässe sind" not in patch["statement"]["text"]
        assert "ist ein Engpass" not in patch["statement"]["text"]
    final = next(run for run in record["quality_runs"] if run["step_type"] == "final_critic")
    assert final["status"] == "success"
    assert final["result_payload"]["findings"] == []


def test_targeted_discovery_repair_cannot_regress_other_fields():
    base = _draft()
    proposed = copy.deepcopy(base)
    proposed["process_analysis"]["business_rules"] = "Unbekannt"
    proposed["focus"]["rationale"] = "Die Suche verursacht sicher alle Verzögerungen."
    review = _verifier("repair", repair_instructions="Regel unbelegt")
    review["critical_findings"] = [
        {"code": "unsupported_rule", "message": "process_analysis.business_rules ist unbelegt."}
    ]
    targets = architect_service._repair_field_targets(base, review)
    assert targets == ("process_analysis.business_rules",)
    result = architect_service._apply_discovery_field_repair(base, proposed, targets)
    assert result["process_analysis"]["business_rules"] == "Unbekannt"
    assert result["focus"] == base["focus"]
    assert base["process_analysis"]["business_rules"] != "Unbekannt"


@pytest.mark.django_db
def test_late_semantic_finding_is_corrected_and_review_history_is_retained(
    owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    first, second, final = _draft(), _draft(), _draft()
    second["process_analysis"]["current_flow"] = "Unbelegter Arbeitsschritt"
    final["process_analysis"]["current_flow"] = "Unbekannt"
    final["clarifications"] = [
        {"question": "Wie läuft es tatsächlich ab?", "impact": "Scope ungeklärt", "blocking": True}
    ]
    responses = iter(
        [
            _result(first),
            _result(_verifier("repair", repair_instructions="Modalität korrigieren")),
            _result(second),
            _result(_verifier("repair", repair_instructions="Arbeitsschritt unbelegt")),
            _result(final),
            _result(_verifier()),
        ]
    )
    monkeypatch.setattr(architect_service, "_provider_call", lambda **kwargs: next(responses))
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
    )
    assert analysis.status == "waiting_human"
    history = analysis.result_payload["review_history"]
    assert len(history) == 3
    assert history[0]["draft"] == first
    assert history[1]["draft"] == second
    assert history[2]["draft"] == final
    assert history[1]["verifier"]["status"] == "repair"
    assert not ValueStream.objects.exists()


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

    source = build_solution_generation_source_context(
        make_process(owner, business_unit), source_schema_version="block7_sources_v1"
    )
    historical = valid_generation_payload()
    historical["schema_version"] = "1.0"
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
    assert "draft" not in repair_document
    assert repair_document["input"]["problem_statement"]
    outline = repair_document["untrusted_proposal_outline"]
    assert outline["recommended_stage_key"] == original["focus"]["recommended_stage_key"]
    assert all(set(stage) == {"key", "name"} for stage in outline["stages"])
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
