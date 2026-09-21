from dataclasses import dataclass

from ki_radar.delivery.mapping_refresh import (
    BLOCK8_MAPPING_MANIFEST_KEY,
    MappingStatus,
    RefreshAction,
    is_legacy_placeholder,
    plan_mapping_refresh,
)


@dataclass(frozen=True, slots=True)
class Source:
    source_kind: str = "use_case"
    source_id: str = "use-case-1"
    source_field: str = "problem_statement"
    source_version: str = "v1"
    semantic_version: str = "semantic-v1"
    priority: int = 1


@dataclass(frozen=True, slots=True)
class Candidate:
    target_field: str
    section_key: str
    value: str
    evidence_hash: str
    is_gap: bool = False
    sources: tuple[Source, ...] = (Source(),)


def candidate(value="Neuer Wert", evidence_hash="hash-2", *, gap=False):
    return Candidate(
        target_field="problem_context",
        section_key="problem_and_target",
        value="" if gap else value,
        evidence_hash=evidence_hash,
        is_gap=gap,
        sources=() if gap else (Source(),),
    )


def manifest_entry(*, status="mapped", evidence_hash="hash-1", mapped_value="Alter Wert"):
    return {
        BLOCK8_MAPPING_MANIFEST_KEY: {
            "contract_version": "block8.v1",
            "fields": {
                "problem_context": {
                    "status": status,
                    "section_key": "problem_and_target",
                    "evidence_hash": evidence_hash,
                    "mapped_value": mapped_value,
                    "sources": [],
                }
            },
        }
    }


def only_decision(plan):
    assert len(plan.decisions) == 1
    return plan.decisions[0]


def test_new_empty_field_accepts_first_valid_evidence():
    plan = plan_mapping_refresh(
        current_values={"problem_context": ""},
        candidates=(candidate(),),
    )
    decision = only_decision(plan)

    assert decision.status is MappingStatus.MAPPED
    assert decision.action is RefreshAction.WRITE
    assert plan.values["problem_context"] == "Neuer Wert"
    assert plan.changed_fields == ("problem_context",)


def test_missing_evidence_stays_visible_gap_without_write():
    plan = plan_mapping_refresh(
        current_values={"problem_context": ""},
        candidates=(candidate(gap=True),),
    )
    decision = only_decision(plan)

    assert decision.status is MappingStatus.GAP
    assert decision.action is RefreshAction.NOOP
    assert plan.values["problem_context"] == ""


def test_known_legacy_placeholder_is_replaceable_but_manual_text_is_not():
    assert is_legacy_placeholder("Menschliche Kontrolle konkretisieren.") is True
    placeholder_plan = plan_mapping_refresh(
        current_values={"problem_context": "Menschliche Kontrolle konkretisieren."},
        candidates=(candidate(),),
    )
    manual_plan = plan_mapping_refresh(
        current_values={"problem_context": "Bewusst manuell dokumentierter Kontext"},
        candidates=(candidate(),),
    )

    assert only_decision(placeholder_plan).action is RefreshAction.WRITE
    assert only_decision(manual_plan).status is MappingStatus.CONFLICT
    assert manual_plan.values["problem_context"] == "Bewusst manuell dokumentierter Kontext"


def test_first_evidence_after_recorded_gap_is_applied_directly():
    plan = plan_mapping_refresh(
        current_values={"problem_context": ""},
        candidates=(candidate(),),
        source_manifest=manifest_entry(status="gap", evidence_hash="gap-hash", mapped_value=""),
    )

    assert only_decision(plan).action is RefreshAction.WRITE
    assert plan.values["problem_context"] == "Neuer Wert"


def test_unchanged_evidence_never_overwrites_manual_delivery_edit():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Manuelle Präzisierung"},
        candidates=(candidate(value="Alter Wert", evidence_hash="hash-1"),),
        source_manifest=manifest_entry(),
    )
    decision = only_decision(plan)

    assert decision.status is MappingStatus.MAPPED
    assert decision.action is RefreshAction.NOOP
    assert plan.values["problem_context"] == "Manuelle Präzisierung"


def test_changed_evidence_updates_when_delivery_still_matches_last_mapping():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Alter Wert"},
        candidates=(candidate(value="Neuer Wert", evidence_hash="hash-2"),),
        source_manifest=manifest_entry(),
    )

    assert only_decision(plan).action is RefreshAction.WRITE
    assert plan.values["problem_context"] == "Neuer Wert"


def test_changed_evidence_conflicts_with_manual_divergence_without_overwrite():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Manuelle Präzisierung"},
        candidates=(candidate(value="Neuer Wert", evidence_hash="hash-2"),),
        source_manifest=manifest_entry(),
    )
    decision = only_decision(plan)

    assert decision.status is MappingStatus.CONFLICT
    assert decision.action is RefreshAction.CONFLICT
    assert plan.values["problem_context"] == "Manuelle Präzisierung"
    assert decision.conflict.previous_mapped_value == "Alter Wert"
    assert decision.conflict.current_value == "Manuelle Präzisierung"
    assert decision.conflict.candidate_value == "Neuer Wert"
    assert plan.conflict_fields == ("problem_context",)


def test_same_evidence_hash_ignores_render_only_candidate_change():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Alter Wert"},
        candidates=(candidate(value="Alter\nWert", evidence_hash="hash-1"),),
        source_manifest=manifest_entry(),
    )

    assert only_decision(plan).action is RefreshAction.NOOP
    assert plan.values["problem_context"] == "Alter Wert"


def test_disappearing_source_marks_previous_mapping_stale_without_erasing_value():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Alter Wert"},
        candidates=(candidate(evidence_hash="gap-hash", gap=True),),
        source_manifest=manifest_entry(),
    )

    assert only_decision(plan).status is MappingStatus.STALE
    assert only_decision(plan).action is RefreshAction.NOOP
    assert plan.values["problem_context"] == "Alter Wert"


def test_explicit_stale_source_never_writes_candidate():
    plan = plan_mapping_refresh(
        current_values={"problem_context": "Alter Wert"},
        candidates=(candidate(),),
        source_manifest=manifest_entry(),
        stale_fields={"problem_context"},
    )

    assert only_decision(plan).status is MappingStatus.STALE
    assert only_decision(plan).action is RefreshAction.NOOP
    assert plan.values["problem_context"] == "Alter Wert"


def test_second_refresh_is_idempotent_and_preserves_non_block8_manifest_data():
    first = plan_mapping_refresh(
        current_values={"problem_context": "Alter Wert"},
        candidates=(candidate(),),
        source_manifest={"use_case": {"id": "use-case-1"}, **manifest_entry()},
    )
    second = plan_mapping_refresh(
        current_values=first.values,
        candidates=(candidate(),),
        source_manifest=first.source_manifest,
    )

    assert first.values == second.values
    assert first.source_manifest == second.source_manifest
    assert second.changed_fields == ()
    assert second.source_manifest["use_case"] == {"id": "use-case-1"}
    entry = second.source_manifest[BLOCK8_MAPPING_MANIFEST_KEY]["fields"]["problem_context"]
    assert entry["status"] == "mapped"
    assert entry["evidence_hash"] == "hash-2"
    assert entry["mapped_value"] == "Neuer Wert"
