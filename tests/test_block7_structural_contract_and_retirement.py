from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError

from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
    STRUCTURAL_OUTPUT_RULE,
    build_solution_generation_messages,
)
from ki_radar.accelerator.solution_generation_validation import (
    SolutionGenerationContractError,
    validate_solution_generation_payload,
)
from ki_radar.architecture.models import (
    ProcessAnalysis,
    SolutionOption,
    SolutionSelectionDecision,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.retirement_models import SolutionOptionRetirement
from ki_radar.architecture.solution_retirement import retire_solution_option
from ki_radar.architecture.solution_selection import ordered_solution_options
from ki_radar.use_cases.models import UseCase

SOURCE_ID = "process.current_flow"


class SourceFact:
    source_id = SOURCE_ID
    value = "Manueller Vergleich"


class SourceContext:
    facts = (SourceFact(),)

    @staticmethod
    def provider_payload():
        return {
            "facts": [
                {
                    "source_id": SOURCE_ID,
                    "field": "current_flow",
                    "value": "Manueller Vergleich",
                }
            ]
        }


def source_context():
    return SourceContext()


def statement(text="Qualitative Aussage"):
    return {
        "text": text,
        "source_ids": [SOURCE_ID],
        "assumptions": [],
        "open_evidence": [],
        "uncertainty": {
            "level": "low",
            "reason": "Direkt aus der Quelle abgeleitet.",
        },
    }


def valid_payload():
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "options": {
            lane: {
                field_name: statement(f"{lane} {field_name}")
                for field_name in GENERATED_OPTION_FIELDS
            }
            for lane in OPTION_LANES
        },
    }


def malformed_missing_statement_fields(payload):
    payload["options"]["organizational"]["name"] = {"source_ids": [SOURCE_ID]}


def malformed_wrong_list_type(payload):
    payload["options"]["assistant"]["risks"]["assumptions"] = "keine"


def malformed_missing_empty_array(payload):
    payload["options"]["rule_automation"]["description"].pop("open_evidence")


def malformed_unknown_field(payload):
    payload["options"]["assistant"]["name"]["confidence"] = 0.9


def malformed_mixed_nested_types(payload):
    target = payload["options"]["organizational"]["architecture_fit"]
    target["source_ids"] = SOURCE_ID
    target["uncertainty"] = "low"


@pytest.mark.parametrize(
    "mutator",
    [
        malformed_missing_statement_fields,
        malformed_wrong_list_type,
        malformed_missing_empty_array,
        malformed_unknown_field,
        malformed_mixed_nested_types,
    ],
)
def test_structural_contract_fuzz_rejects_malformed_provider_shapes(mutator):
    payload = deepcopy(valid_payload())
    mutator(payload)

    with pytest.raises(SolutionGenerationContractError):
        validate_solution_generation_payload(payload, source_context())


def test_structural_contract_accepts_complete_shape_and_prompt_repeats_requirement():
    validated = validate_solution_generation_payload(valid_payload(), source_context())
    messages = build_solution_generation_messages(source_context())

    assert validated["prompt_version"] == "1.2"
    assert STRUCTURAL_OUTPUT_RULE in messages[0]["content"]
    assert '"statement_shape"' in messages[1]["content"]
    assert '"assumptions":[]' in messages[1]["content"]
    assert '"open_evidence":[]' in messages[1]["content"]


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Bedarf freigegeben",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=1,
        name="Angebote vergleichen",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell verglichen.",
        roles="Einkauf",
        systems="ERP",
        data_objects="Angebote",
        bottlenecks="Manueller Vergleich",
        baseline_metrics="Elf Minuten",
        analyzed_by=owner,
    )


def make_option(process, owner, name="Option"):
    return SolutionOption.objects.create(
        process_analysis=process,
        name=name,
        option_type=SolutionOption.OptionType.ORGANIZATIONAL,
        description="Beschreibung",
        expected_value="Qualitativer Nutzen",
        created_by=owner,
    )


@pytest.mark.django_db
def test_retirement_keeps_audit_record_and_excludes_option_from_active_selection(
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    retired = make_option(process, owner, "Nicht weiterverfolgen")
    active = make_option(process, owner, "Aktiv")

    retirement = retire_solution_option(option=retired, actor=owner)

    retired.refresh_from_db()
    assert retirement.option == retired
    assert retirement.retired_by == owner
    assert retired.recommendation == SolutionOption.Recommendation.REJECTED
    assert list(ordered_solution_options(process)) == [active]
    assert SolutionOption.objects.filter(pk=retired.pk).exists()


@pytest.mark.django_db
def test_retirement_uses_same_edit_permission(owner, reader, business_unit):
    process = make_process(owner, business_unit)
    option = make_option(process, owner)

    with pytest.raises(ValidationError, match="Bearbeitungsberechtigung"):
        retire_solution_option(option=option, actor=reader)

    assert not SolutionOptionRetirement.objects.filter(option=option).exists()


@pytest.mark.django_db
def test_retirement_blocks_preferred_and_previously_selected_options(owner, business_unit):
    process = make_process(owner, business_unit)
    preferred = make_option(process, owner, "Bevorzugt")
    preferred.recommendation = SolutionOption.Recommendation.PREFERRED
    preferred.save(update_fields=["recommendation", "updated_at"])

    with pytest.raises(ValidationError, match="bevorzugte"):
        retire_solution_option(option=preferred, actor=owner)

    selected = make_option(process, owner, "Historisch ausgewählt")
    SolutionSelectionDecision.objects.create(
        process_analysis=process,
        selected_option=selected,
        rationale="Historischer Vergleich.",
        comparison_snapshot=[],
        decided_by=owner,
    )

    with pytest.raises(ValidationError, match="bereits ausgewählte"):
        retire_solution_option(option=selected, actor=owner)


@pytest.mark.django_db
def test_retirement_blocks_use_case_linked_option(owner, business_unit):
    process = make_process(owner, business_unit)
    option = make_option(process, owner, "Mit Use Case")
    use_case = UseCase.objects.create(
        title="Angebotsvergleich",
        problem_statement="Manueller Vergleich",
        business_unit=business_unit,
        affected_process="Angebotsvergleich",
        submitter=owner,
        business_owner=owner,
        expected_benefit="Weniger manuelle Arbeit",
    )
    UseCaseOrigin.objects.create(
        use_case=use_case,
        stage=process.stage,
        process_analysis=process,
        solution_option=option,
    )

    with pytest.raises(ValidationError, match="Use Case verknüpfte"):
        retire_solution_option(option=option, actor=owner)
