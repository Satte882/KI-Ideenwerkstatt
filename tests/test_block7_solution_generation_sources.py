import json

import pytest

from ki_radar.accelerator.solution_generation_sources import (
    ALLOWED_SOURCE_IDS,
    REQUIRED_PROCESS_FIELDS,
    VALIDATION_CURRENT,
    VALIDATION_MISSING,
    VALIDATION_STALE,
    SolutionGenerationReadinessError,
    build_solution_generation_source_context,
    require_solution_generation_ready,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    ValueStream,
    ValueStreamStage,
)


def make_process(owner, business_unit, **overrides):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="EU-Datenhaltung und menschliche Freigabe",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=2,
        name="Angebote vergleichen",
        description="Angebote fachlich vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manueller Vergleich",
        baseline_metrics="11 Minuten pro Vergleich",
    )
    data = {
        "stage": stage,
        "name": "Angebotsvergleich",
        "scope_start": "Angebote liegen vor",
        "scope_end": "Auswahl ist dokumentiert",
        "trigger": "Angebotsfrist endet",
        "outcome": "Nachvollziehbare Auswahl",
        "current_flow": "Angebote werden manuell gegenübergestellt.",
        "roles": "Einkauf und Fachbereich",
        "systems": "ERP und Dateiablage",
        "data_objects": "Angebote und Kriterienkatalog",
        "business_rules": "Vier-Augen-Prinzip bei Freigabe",
        "handoffs": "Einkauf übergibt an Fachbereich",
        "bottlenecks": "Manuelle Übertragung verursacht Wartezeit.",
        "exceptions": "Fehlende Pflichtangaben werden nachgefordert.",
        "baseline_metrics": "11 Minuten pro Vergleich",
        "target_state_principles": "Nachvollziehbar und assistierend",
        "source_snapshot": {"capture_analysis_id": "must-not-leave-the-server"},
        "analyzed_by": owner,
    }
    data.update(overrides)
    return ProcessAnalysis.objects.create(**data)


@pytest.mark.django_db
@pytest.mark.parametrize("missing_field", REQUIRED_PROCESS_FIELDS)
def test_each_required_process_field_blocks_readiness(
    owner,
    business_unit,
    missing_field,
):
    process = make_process(owner, business_unit, **{missing_field: "   "})

    context = build_solution_generation_source_context(process)

    assert context.is_ready is False
    assert context.missing_required == (missing_field,)
    with pytest.raises(SolutionGenerationReadinessError) as exc_info:
        require_solution_generation_ready(process)
    assert exc_info.value.missing_fields == (missing_field,)


@pytest.mark.django_db
def test_optional_process_fields_do_not_create_an_extra_gate(owner, business_unit):
    process = make_process(
        owner,
        business_unit,
        business_rules="",
        handoffs="",
        exceptions="",
        target_state_principles="",
    )

    context = require_solution_generation_ready(process)

    assert context.is_ready is True
    assert context.validation_state == VALIDATION_MISSING


@pytest.mark.django_db
def test_validation_state_distinguishes_missing_current_and_stale(owner, business_unit):
    missing = make_process(owner, business_unit)
    assert build_solution_generation_source_context(missing).validation_state == VALIDATION_MISSING

    current = make_process(owner, business_unit)
    ProcessValidation.objects.create(
        process_analysis=current,
        process_version=current.version,
        validated_by=owner,
        validator_role="Process Owner",
    )
    assert build_solution_generation_source_context(current).validation_state == VALIDATION_CURRENT

    stale = make_process(owner, business_unit, version=2)
    ProcessValidation.objects.create(
        process_analysis=stale,
        process_version=1,
        validated_by=owner,
        validator_role="Process Owner",
    )
    assert build_solution_generation_source_context(stale).validation_state == VALIDATION_STALE


@pytest.mark.django_db
def test_review_required_never_exposes_validation_as_current(owner, business_unit):
    process = make_process(owner, business_unit, status=ProcessAnalysis.Status.REVIEW_REQUIRED)
    ProcessValidation.objects.create(
        process_analysis=process,
        process_version=process.version,
        validated_by=owner,
        validator_role="Process Owner",
    )

    context = require_solution_generation_ready(process)

    assert context.validation_state == VALIDATION_STALE
    assert context.is_ready is True


@pytest.mark.django_db
def test_provider_payload_is_minimized_to_whitelisted_source_facts(owner, business_unit):
    process = make_process(owner, business_unit)

    context = require_solution_generation_ready(process)
    payload = context.provider_payload()
    serialized = json.dumps(payload, ensure_ascii=False)
    source_ids = {fact["source_id"] for fact in payload["facts"]}

    assert source_ids <= set(ALLOWED_SOURCE_IDS)
    assert source_ids == {
        "process.name",
        "process.scope_start",
        "process.scope_end",
        "process.trigger",
        "process.outcome",
        "process.current_flow",
        "process.roles",
        "process.systems",
        "process.data_objects",
        "process.business_rules",
        "process.handoffs",
        "process.bottlenecks",
        "process.exceptions",
        "process.baseline_metrics",
        "process.target_state_principles",
        "stage.name",
        "value_stream.constraints",
    }
    assert "process_analysis_id" not in payload
    assert "analyzed_by" not in serialized
    assert "created_by" not in serialized
    assert "owner" not in serialized
    assert "source_snapshot" not in serialized
    assert "must-not-leave-the-server" not in serialized
    assert "Durchlaufzeit reduzieren" not in serialized
    assert "Angebote fachlich vergleichen" not in serialized


@pytest.mark.django_db
def test_source_hash_is_stable_and_changes_with_relevant_source(owner, business_unit):
    process = make_process(owner, business_unit)

    first = require_solution_generation_ready(process)
    second = require_solution_generation_ready(process)
    assert first.source_hash == second.source_hash

    process.bottlenecks = "Neue fachliche Engpassbeschreibung"
    process.save(update_fields=["bottlenecks", "updated_at"])
    changed = require_solution_generation_ready(process)

    assert changed.source_hash != first.source_hash


@pytest.mark.django_db
def test_formal_validation_is_not_a_readiness_requirement(owner, business_unit):
    process = make_process(owner, business_unit, status=ProcessAnalysis.Status.DRAFT)

    context = require_solution_generation_ready(process)

    assert context.is_ready is True
    assert context.validation_state == VALIDATION_MISSING
