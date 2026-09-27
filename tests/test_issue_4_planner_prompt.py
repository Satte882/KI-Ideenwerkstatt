from ki_radar.accelerator.investigation_prompts import (
    PLANNER_INSTRUCTION,
    PLANNER_PROMPT_VERSION,
    SYNTHESIS_INSTRUCTION,
    SYNTHESIS_PROMPT_VERSION,
)


def test_planner_requires_reproducible_quantitative_check_before_synthesis():
    assert PLANNER_PROMPT_VERSION == "vs1-planner-v17"
    assert "Bevor du action=synthesize wählst" in PLANNER_INSTRUCTION
    assert "quantitativen Beziehung zwischen strukturierten Feldern" in PLANNER_INSTRUCTION
    assert "insbesondere compare_groups" in PLANNER_INSTRUCTION
    assert "nicht nur in validation_step" in PLANNER_INSTRUCTION
    assert "bloßes Lesen der Rohzeilen ersetzt ihn nicht" in PLANNER_INSTRUCTION


def test_quantitative_check_rule_stays_domain_generic():
    assert "queue_retries" not in PLANNER_INSTRUCTION
    assert "approver_available" not in PLANNER_INSTRUCTION


def test_repair_synthesis_requires_explicit_critical_claim_replacement():
    assert SYNTHESIS_PROMPT_VERSION == "vs1-synthesis-v9"
    assert "Bei einer Reparatur bleiben unveränderte Claims" in SYNTHESIS_INSTRUCTION
    assert "metadata.replaces_claim_id=<alte claim_id>" in SYNTHESIS_INSTRUCTION
    assert "führe den alten Claim" in SYNTHESIS_INSTRUCTION
    assert "nicht zusätzlich weiter" in SYNTHESIS_INSTRUCTION
    assert "stale und korrigierter widersprüchlicher Claim" in SYNTHESIS_INSTRUCTION


def test_planner_requires_native_json_transport():
    assert "parameters und" in PLANNER_INSTRUCTION
    assert "clarification_payload sind echte JSON-Objekte" in PLANNER_INSTRUCTION
    assert "niemals als JSON-Text in Strings" in PLANNER_INSTRUCTION


def test_planner_action_specific_fields_may_be_omitted():
    assert "action ist immer Pflicht" in PLANNER_INSTRUCTION
    assert "Bei action=tool sind" in PLANNER_INSTRUCTION
    assert "Bei action=clarify sind" in PLANNER_INSTRUCTION
    assert "Bei action=synthesize genügt action" in PLANNER_INSTRUCTION
    assert "inaktive Felder dürfen" in PLANNER_INSTRUCTION


def test_synthesis_binds_existing_solution_candidates_explicitly():
    assert "existing_solution_options" in SYNTHESIS_INSTRUCTION
    assert "existing_option_id" in SYNTHESIS_INSTRUCTION
    assert "übernimm dessen id exakt" in SYNTHESIS_INSTRUCTION
    assert "erfinde keine ID" in SYNTHESIS_INSTRUCTION


def test_planner_clarification_contract_names_exact_reason_codes():
    assert "missing_evidence" in PLANNER_INSTRUCTION
    assert "permission_or_scope" in PLANNER_INSTRUCTION
    assert "value_tradeoff" in PLANNER_INSTRUCTION
    assert "Verwende keine Synonyme" in PLANNER_INSTRUCTION
    assert "keinen entscheidungsrelevanten Bezug" in PLANNER_INSTRUCTION
    assert "clarification_reason=missing_evidence" in PLANNER_INSTRUCTION
