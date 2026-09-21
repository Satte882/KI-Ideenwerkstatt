from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any

from django.conf import settings

from .evidence_composer import compose_delivery_fields
from .evidence_mapper import map_direct_delivery_fields
from .evidence_mapping_contract import V1_DELIVERY_FIELD_MAPPINGS
from .evidence_snapshot import build_delivery_evidence_snapshot
from .mapping_refresh import (
    BLOCK8_MAPPING_MANIFEST_KEY,
    MappingRefreshPlan,
    RefreshAction,
    plan_mapping_refresh,
)

ARCHITECTURE_MAPPING_FIELDS = frozenset({"system_landscape", "data_flows"})
PACKAGE_MAPPING_FIELDS = frozenset(V1_DELIVERY_FIELD_MAPPINGS) - ARCHITECTURE_MAPPING_FIELDS
ARCHITECTURE_TEXT_FIELDS = frozenset(
    {
        "system_landscape",
        "system_responsibilities",
        "data_flows",
        "data_quality_and_access",
        "integration_contracts",
        "integration_operations",
    }
)
MAPPING_TRACKING_SECTION = "problem_and_target"


@dataclass(frozen=True, slots=True)
class DeliveryMappingSeed:
    package_values: dict[str, str]
    architecture_values: dict[str, str]
    source_manifest: dict[str, Any]
    plan: MappingRefreshPlan


def block8_mapper_enabled() -> bool:
    configured = getattr(settings, "DELIVERY_EVIDENCE_MAPPER_ENABLED", None)
    if configured is not None:
        return bool(configured)
    raw = os.environ.get("DELIVERY_EVIDENCE_MAPPER_ENABLED", "")
    return raw.strip().casefold() in {"1", "true", "yes", "on"}


def build_delivery_mapping_candidates(use_case, approval_decision):
    snapshot = build_delivery_evidence_snapshot(
        use_case,
        approval_decision=approval_decision,
    )
    direct = map_direct_delivery_fields(snapshot)
    composed = compose_delivery_fields(snapshot)
    return (*direct, *composed)


def delivery_mapping_manifest(package) -> dict[str, Any] | None:
    review = package.section_reviews.filter(section_key=MAPPING_TRACKING_SECTION).first()
    if review is None:
        return None
    raw = (review.source_manifest or {}).get(BLOCK8_MAPPING_MANIFEST_KEY)
    if not isinstance(raw, dict) or not raw:
        return None
    return dict(raw)


def delivery_mapping_is_legacy(package) -> bool:
    return delivery_mapping_manifest(package) is None


def block8_mapping_source_differences(package) -> list[dict[str, Any]]:
    manifest = delivery_mapping_manifest(package)
    if manifest is None or package.generated_from_decision_id is None:
        return []

    candidates = build_delivery_mapping_candidates(
        package.use_case,
        package.generated_from_decision,
    )
    candidate_index = {candidate.target_field: candidate for candidate in candidates}
    previous_fields = dict(manifest.get("fields") or {})
    differences = []
    for target_field, previous in previous_fields.items():
        candidate = candidate_index.get(target_field)
        if candidate is None:
            continue
        snapshot_hash = str(previous.get("evidence_hash") or "")
        current_hash = candidate.evidence_hash
        changed = snapshot_hash != current_hash
        differences.append(
            {
                "package_field": target_field,
                "section_key": candidate.section_key,
                "previous_status": str(previous.get("status") or ""),
                "snapshot_evidence_hash": snapshot_hash,
                "current_evidence_hash": current_hash,
                "changed": changed,
                "stale": changed,
                "current_gap": candidate.is_gap,
                "current_sources": [asdict(source) for source in candidate.sources],
            }
        )
    return differences


def build_mapped_delivery_seed(
    *,
    use_case,
    approval_decision,
    fallback_package_values: dict[str, str],
    fallback_architecture_values: dict[str, str],
    source_manifest: dict[str, Any],
) -> DeliveryMappingSeed:
    package_values = _empty_package_values_for_mapping(fallback_package_values)
    architecture_values = _empty_unsupported_architecture_values(fallback_architecture_values)
    current_values = {}
    for field_name in PACKAGE_MAPPING_FIELDS:
        current_values[field_name] = package_values.get(field_name, "")
    for field_name in ARCHITECTURE_MAPPING_FIELDS:
        current_values[field_name] = architecture_values.get(field_name, "")

    candidates = build_delivery_mapping_candidates(use_case, approval_decision)
    plan = plan_mapping_refresh(
        current_values=current_values,
        candidates=candidates,
        source_manifest=source_manifest,
    )
    _apply_plan_values(package_values, architecture_values, plan.values)
    return DeliveryMappingSeed(
        package_values=package_values,
        architecture_values=architecture_values,
        source_manifest=plan.source_manifest,
        plan=plan,
    )


def build_existing_package_refresh_plan(package) -> MappingRefreshPlan:
    review = package.section_reviews.filter(section_key=MAPPING_TRACKING_SECTION).first()
    source_manifest = dict(review.source_manifest or {}) if review is not None else {}
    current_values = {}
    for field_name in PACKAGE_MAPPING_FIELDS:
        current_values[field_name] = getattr(package, field_name)
    artifacts = package.architecture_artifacts
    for field_name in ARCHITECTURE_MAPPING_FIELDS:
        current_values[field_name] = getattr(artifacts, field_name)

    candidates = build_delivery_mapping_candidates(
        package.use_case,
        package.generated_from_decision,
    )
    return plan_mapping_refresh(
        current_values=current_values,
        candidates=candidates,
        source_manifest=source_manifest,
    )


def apply_refresh_plan(package, plan: MappingRefreshPlan) -> tuple[str, ...]:
    package_fields = []
    architecture_fields = []
    changed_sections = set()
    artifacts = package.architecture_artifacts
    for decision in plan.decisions:
        if decision.action is RefreshAction.WRITE:
            changed_sections.add(decision.section_key)
    for field_name in plan.changed_fields:
        if field_name in PACKAGE_MAPPING_FIELDS:
            setattr(package, field_name, plan.values[field_name])
            package_fields.append(field_name)
        elif field_name in ARCHITECTURE_MAPPING_FIELDS:
            setattr(artifacts, field_name, plan.values[field_name])
            architecture_fields.append(field_name)

    if package_fields:
        package.save(update_fields=[*package_fields, "updated_at"])
    if architecture_fields:
        artifacts.save(update_fields=[*architecture_fields, "updated_at"])
    for review in package.section_reviews.all():
        if review.source_manifest != plan.source_manifest:
            review.source_manifest = plan.source_manifest
            review.save(update_fields=["source_manifest", "updated_at"])
    if changed_sections:
        from .services import reset_section_reviews

        reset_section_reviews(package, changed_sections)
    return plan.changed_fields


def _empty_package_values_for_mapping(values: dict[str, str]) -> dict[str, str]:
    prepared = dict(values)
    for field_name in prepared:
        if field_name != "external_delivery_url":
            prepared[field_name] = ""
    return prepared


def _empty_unsupported_architecture_values(values: dict[str, str]) -> dict[str, str]:
    prepared = dict(values)
    for field_name in ARCHITECTURE_TEXT_FIELDS:
        prepared[field_name] = ""
    return prepared


def _apply_plan_values(package_values, architecture_values, mapped_values) -> None:
    for field_name, value in mapped_values.items():
        if field_name in PACKAGE_MAPPING_FIELDS:
            package_values[field_name] = value
        elif field_name in ARCHITECTURE_MAPPING_FIELDS:
            architecture_values[field_name] = value
