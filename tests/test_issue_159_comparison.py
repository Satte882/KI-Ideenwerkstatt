from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process, outcome_process, select
from test_solution_selection_ux import make_option, make_process

from ki_radar.architecture.comparison_policy import COVERAGE_LABEL
from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import SolutionOption
from ki_radar.architecture.solution_retirement import retire_solution_option
from ki_radar.architecture.solution_selection import comparison_blockers, ordered_solution_options
from ki_radar.architecture.templatetags.architecture_focus import comparison_technical_value

pytestmark = pytest.mark.django_db

COMMON = (
    "description",
    "expected_value",
    "bottleneck_coverage",
    "risks",
    "architecture_fit",
    "feasibility",
    "time_to_value",
)
TECHNICAL = ("data_requirements", "application_impact", "integration_impact", "integration_effort")


@pytest.mark.parametrize("option_type", SolutionOption.OptionType.values)
@pytest.mark.parametrize("status", SolutionOption.EvaluationStatus.values)
def test_assessment_contract_across_model_form_and_gate(owner, business_unit, option_type, status):
    process = make_process(owner, business_unit)
    option = make_option(process, owner, name="Prüfoption", option_type=option_type, assessed=True)
    second = make_option(
        process, owner, name="Zweite Option", option_type="assistant", assessed=True
    )
    option.evaluation_status = status
    baseline = {field: getattr(option, field) for field in SolutionOptionForm.Meta.fields}
    for field in (*COMMON, *TECHNICAL):
        option.refresh_from_db()
        option.evaluation_status = status
        empty = (
            "not_assessed"
            if field in {"feasibility", "time_to_value", "integration_effort"}
            else ""
        )
        setattr(option, field, empty)
        required = field in COMMON or option_type not in {"organizational", "no_tech"}
        assert (field in option.missing_assessment_field_names) == required
        complete = status == "assessed" and not required
        assert option.comparison_complete == complete
        assert bool(comparison_blockers([option, second])) == (not complete)
        if status == "assessed" and required:
            with pytest.raises(ValidationError) as error:
                option.clean()
            assert field in error.value.message_dict
        else:
            option.clean()
        form = SolutionOptionForm(
            {**baseline, field: empty}, instance=option, process_analysis=process
        )
        form_required = (status == "assessed" and required) or field in {
            "description",
            "expected_value",
        }
        assert form.is_valid() == (not form_required), form.errors
        if form_required:
            assert field in form.errors
        assert form.fields["bottleneck_coverage"].label == COVERAGE_LABEL


@pytest.mark.parametrize("option_type", ["organizational", "no_tech"])
@pytest.mark.parametrize("path", ["problem", "strategic"])
def test_binding_non_technical_option_without_technical_fillers(
    owner, business_unit, option_type, path
):
    process = outcome_process(owner, business_unit)
    option = process.solution_options.get(option_type="organizational")
    option.option_type = option_type
    for field in TECHNICAL:
        setattr(option, field, "not_assessed" if field == "integration_effort" else "")
    option.bottleneck_coverage = "Begründetes Potenzial: Klärung durch benannte Verantwortliche"
    option.full_clean()
    option.save()
    if path == "strategic":
        process.confirmed_causes = process.diagnostic_observations = ""
        process.save()
    bind_process(owner, process, path=path)
    from ki_radar.architecture.solution_selection import select_preferred_solution

    decision = select_preferred_solution(
        process_analysis=process,
        selected_option=option,
        actor=owner,
        rationale="Technologieoffener Vergleich des gemeinsamen Beitrags",
    )
    frozen = deepcopy(decision.comparison_snapshot)
    snapshot_option = next(item for item in frozen if item["id"] == str(option.pk))
    assert snapshot_option["integration_effort"] == "not_assessed"
    assert snapshot_option["data_requirements"] == ""
    assert decision.diagnosis_snapshot["confirmed_causes"] == process.confirmed_causes
    option.description = "Später bearbeiteter Entwurf"
    option.save()
    decision.refresh_from_db()
    assert decision.comparison_snapshot == frozen


@pytest.mark.parametrize(
    "option_type", ["organizational", "no_tech", "assistant", "rule_automation"]
)
def test_outcome_effects_block_all_active_options_before_submit(
    client, owner, business_unit, option_type
):
    process = outcome_process(owner, business_unit)
    bind_process(owner, process)
    options = list(process.solution_options.all())
    options[0].option_type = option_type
    for option in options:
        option.outcome_effect = "   "
        option.save()
    retired = make_option(
        process, owner, name="Nicht weiterverfolgt", option_type="no_tech", assessed=True
    )
    retire_solution_option(option=retired, actor=owner)
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    response = client.get(url)
    assert response.context["selection_blocked"]
    assert {option.pk for option in response.context["missing_outcome_effect_options"]} == {
        option.pk for option in options
    }
    html = response.content.decode()
    assert 'data-testid="selection-option-outcome-blocker"' in html
    for option in options:
        assert f"Wirkung für {option.name} ergänzen" in html
        assert (
            reverse("architecture:solution_option_update", args=[option.pk])
            + "?return_to=comparison"
            in html
        )
    assert f"Wirkung für {retired.name} ergänzen" not in html
    assert (
        len(comparison_blockers(ordered_solution_options(process), process_analysis=process)) == 2
    )
    post = client.post(
        url,
        {
            "selected_option": options[0].pk,
            "process_version": process.version,
            "rationale": "Vollständiger Effekt fehlt",
        },
    )
    assert post.status_code == 200 and not process.solution_selection_decisions.exists()
    assert "Wirkung auf das gemeinsame Geschäftsergebnis fehlt" in str(post.context["form"].errors)
    # Editing and draft saves remain possible. Both classes use exactly the same gate.
    for option in options:
        option.outcome_effect = "Beitrag bleibt eine explizite Wirkannahme"
        option.save()
    assert not client.get(url).context["selection_blocked"]
    process.outcome_contract_version = (
        0  # Read-only legacy projection, no persisted cohort downgrade.
    )
    for option in options:
        option.outcome_effect = ""
    assert comparison_blockers(options, process_analysis=process) == []


@pytest.mark.parametrize("option_type", SolutionOption.OptionType.values)
def test_comparison_display_preserves_actual_technical_entries(option_type):
    option = SolutionOption(option_type=option_type)
    for field in (*TECHNICAL, "technology_constraints"):
        setattr(option, field, "not_assessed" if field == "integration_effort" else "")
        if option_type in {"organizational", "no_tech"}:
            assert comparison_technical_value(option, field) == "Nicht relevant"
        else:
            assert comparison_technical_value(option, field) != "Nicht relevant"
        setattr(
            option, field, "low" if field == "integration_effort" else "Tatsächliche Auswirkung"
        )
        assert comparison_technical_value(option, field) == (
            "Niedrig" if field == "integration_effort" else "Tatsächliche Auswirkung"
        )


def test_problem_diagnosis_remains_required(owner, business_unit):
    process = outcome_process(owner, business_unit)
    bind_process(owner, process, path="problem")
    process.confirmed_causes = ""
    process.save()
    with pytest.raises(ValidationError, match="bestätigte Ursache"):
        select(owner, process)
