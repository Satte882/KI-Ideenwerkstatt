from copy import deepcopy

import pytest

from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_effective import (
    SolutionGenerationEffectivePayloadError,
    build_validated_effective_solution_payload,
)
from ki_radar.accelerator.solution_generation_sources import (
    SOURCE_SCHEMA_VERSION,
    SolutionGenerationSourceContext,
    SourceFact,
)
from ki_radar.accelerator.solution_quality_snapshot import build_solution_quality_snapshot
from ki_radar.accelerator.solution_quality_versions import (
    CRITIC_PROMPT_VERSION,
    CRITIC_SCHEMA_VERSION,
    QUALITY_CONTRACT_VERSION,
    REPAIR_PROMPT_VERSION,
    REPAIR_SCHEMA_VERSION,
)


def source_context(*, source_hash: str = "a" * 64) -> SolutionGenerationSourceContext:
    return SolutionGenerationSourceContext(
        process_analysis_id="00000000-0000-0000-0000-000000000212",
        process_version=7,
        validation_state="current_validated",
        source_hash=source_hash,
        missing_required=(),
        facts=(
            SourceFact(
                source_id="process.current_flow",
                field="current_flow",
                value="Angebote werden manuell geprüft und gegenübergestellt.",
            ),
        ),
    )


def statement(text: str) -> dict[str, object]:
    return {
        "text": text,
        "source_ids": ["process.current_flow"],
        "assumptions": [],
        "open_evidence": [],
        "uncertainty": {
            "level": "low",
            "reason": "Aus dem dokumentierten Ist-Ablauf abgeleitet.",
        },
    }


def preview_payload() -> dict[str, object]:
    options: dict[str, dict[str, object]] = {}
    for lane in OPTION_LANES:
        options[lane] = {
            field_name: statement(f"{lane} {field_name} fachlich eigenständig")
            for field_name in GENERATED_OPTION_FIELDS
        }
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": options,
        "edits": {},
    }


def test_effective_preview_applies_human_edits_without_mutating_original() -> None:
    payload = preview_payload()
    original = deepcopy(payload)
    payload["edits"] = {
        "assistant": {
            "description": "Menschlich präzisierter Assistenzentwurf.",
        },
    }

    effective = build_validated_effective_solution_payload(payload, source_context())

    assert (
        effective["options"]["assistant"]["description"]["text"]
        == "Menschlich präzisierter Assistenzentwurf."
    )
    assert payload["options"] == original["options"]


def test_effective_preview_rejects_unknown_human_edit_field() -> None:
    payload = preview_payload()
    payload["edits"] = {"assistant": {"feasibility": "high"}}

    with pytest.raises(SolutionGenerationEffectivePayloadError) as exc_info:
        build_validated_effective_solution_payload(payload, source_context())

    assert exc_info.value.code == "invalid_preview"


def test_effective_preview_revalidates_human_edit_against_block7_contract() -> None:
    payload = preview_payload()
    payload["edits"] = {
        "assistant": {
            "description": "Der Assistenzentwurf verbessert den Ablauf um 50 Prozent.",
        },
    }

    with pytest.raises(SolutionGenerationEffectivePayloadError) as exc_info:
        build_validated_effective_solution_payload(payload, source_context())

    assert exc_info.value.code == "invalid_preview_edit"


def test_quality_snapshot_is_canonical_across_input_key_order() -> None:
    payload = preview_payload()
    reordered = deepcopy(payload)
    reordered["options"] = dict(reversed(list(reordered["options"].items())))
    for lane in OPTION_LANES:
        reordered["options"][lane] = dict(reversed(list(reordered["options"][lane].items())))

    first = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(),
    )
    second = build_solution_quality_snapshot(
        preview_payload=reordered,
        source_context=source_context(),
    )

    assert first.snapshot_hash == second.snapshot_hash
    assert first.document == second.document


def test_quality_snapshot_changes_when_effective_preview_changes() -> None:
    payload = preview_payload()
    changed = deepcopy(payload)
    changed["edits"] = {
        "assistant": {
            "description": "Menschlich geänderter Assistenzentwurf.",
        },
    }

    original_snapshot = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(),
    )
    changed_snapshot = build_solution_quality_snapshot(
        preview_payload=changed,
        source_context=source_context(),
    )

    assert original_snapshot.snapshot_hash != changed_snapshot.snapshot_hash


def test_quality_snapshot_changes_when_source_hash_changes() -> None:
    payload = preview_payload()

    first = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(source_hash="a" * 64),
    )
    second = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(source_hash="b" * 64),
    )

    assert first.snapshot_hash != second.snapshot_hash


def test_quality_snapshot_binds_all_v1_contract_versions() -> None:
    snapshot = build_solution_quality_snapshot(
        preview_payload=preview_payload(),
        source_context=source_context(),
    )

    assert snapshot.document["quality_contract_version"] == QUALITY_CONTRACT_VERSION
    assert snapshot.document["source_schema_version"] == SOURCE_SCHEMA_VERSION
    assert snapshot.document["generation_prompt_version"] == GENERATION_PROMPT_VERSION
    assert snapshot.document["generation_schema_version"] == GENERATION_SCHEMA_VERSION
    assert snapshot.document["critic_prompt_version"] == CRITIC_PROMPT_VERSION
    assert snapshot.document["critic_schema_version"] == CRITIC_SCHEMA_VERSION
    assert snapshot.document["repair_prompt_version"] == REPAIR_PROMPT_VERSION
    assert snapshot.document["repair_schema_version"] == REPAIR_SCHEMA_VERSION
    assert "model_name" not in snapshot.document


def test_quality_snapshot_becomes_stale_when_critic_contract_version_changes(monkeypatch) -> None:
    payload = preview_payload()
    before = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(),
    )

    monkeypatch.setattr(
        "ki_radar.accelerator.solution_quality_snapshot.CRITIC_PROMPT_VERSION",
        "2.0",
    )
    after = build_solution_quality_snapshot(
        preview_payload=payload,
        source_context=source_context(),
    )

    assert before.snapshot_hash != after.snapshot_hash
    assert before.document["critic_prompt_version"] == CRITIC_PROMPT_VERSION
    assert after.document["critic_prompt_version"] == "2.0"
