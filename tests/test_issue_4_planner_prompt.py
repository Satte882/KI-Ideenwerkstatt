from ki_radar.accelerator.investigation_prompts import (
    PLANNER_INSTRUCTION,
    PLANNER_PROMPT_VERSION,
)


def test_planner_requires_reproducible_quantitative_check_before_synthesis():
    assert PLANNER_PROMPT_VERSION == "vs1-planner-v14"
    assert "Bevor du action=synthesize wählst" in PLANNER_INSTRUCTION
    assert "quantitativen Beziehung zwischen strukturierten Feldern" in PLANNER_INSTRUCTION
    assert "insbesondere compare_groups" in PLANNER_INSTRUCTION
    assert "nicht nur in validation_step" in PLANNER_INSTRUCTION
    assert "bloßes Lesen der Rohzeilen ersetzt ihn nicht" in PLANNER_INSTRUCTION


def test_quantitative_check_rule_stays_domain_generic():
    assert "queue_retries" not in PLANNER_INSTRUCTION
    assert "approver_available" not in PLANNER_INSTRUCTION
