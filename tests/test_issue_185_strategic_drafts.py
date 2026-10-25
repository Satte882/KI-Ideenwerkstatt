from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process
from test_issue_178_strategic_discovery import analyze, make_context, materialize
from test_solution_selection_ux import make_option, make_process

from ki_radar.accelerator.models import CaptureSession
from ki_radar.architecture.forms import ProcessAnalysisForm, SolutionOptionForm
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, SolutionSelectionDecision
from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.use_cases.workflow import build_process_analysis_journey

pytestmark = pytest.mark.django_db


@pytest.fixture
def exploration(owner, tmp_path, monkeypatch):
    context = make_context(owner, tmp_path)
    analysis = analyze(owner, context, monkeypatch)
    result = materialize(owner, context[0], analysis)
    return ProcessAnalysis.objects.get(pk=result.process_analysis_id)


def process_data(process):
    return model_to_dict(process, fields=ProcessAnalysisForm.Meta.fields)


def option_data(option):
    return model_to_dict(option, fields=SolutionOptionForm.Meta.fields)


def test_immediate_materialization_edit_save_resume_and_option_drafts(owner, client, exploration):
    process = exploration
    provenance = deepcopy(process.source_snapshot)
    assert not process.discovery_path_decisions.exists()
    assert process.initiative_id is None
    client.force_login(owner)
    edit = reverse("architecture:process_analysis_update", args=[process.pk])
    page = client.get(edit)
    assert page.status_code == 200
    assert not page.context["form"].fields["baseline_metrics"].required
    assert not page.context["form"].fields["bottlenecks"].required
    data = process_data(process)
    data["name"] = "Strategischer Arbeitsentwurf"
    # Server-owned provenance and a path confirmation cannot be submitted through this form.
    data.update(strategic="1", source_snapshot="{}", outcome_contract_version="0")
    saved = client.post(edit, data)
    assert saved.status_code == 302
    process.refresh_from_db()
    assert process.name == data["name"]
    assert process.baseline_metrics == process.bottlenecks == process.confirmed_causes == ""
    assert process.source_snapshot == provenance
    assert process.status == "draft" and process.outcome_contract_version == 1
    assert not process.discovery_path_decisions.exists()
    assert client.get(edit).context["form"].initial["name"] == data["name"]

    create = reverse("architecture:solution_option_create", args=[process.pk])
    assert client.get(create).status_code == 200
    draft = SolutionOption(
        name="Organisatorische Alternative untersuchen",
        option_type="organizational",
        description="Hypothese: Zuständigkeiten im Untersuchungsbereich klären.",
        expected_value="Möglicher Beitrag zu tragfähigen Buchungen; Wirkung unbekannt.",
    )
    response = client.post(create, option_data(draft))
    assert response.status_code == 302, response.context["form"].errors
    option = process.solution_options.get()
    update = reverse("architecture:solution_option_update", args=[option.pk])
    assert client.get(update).status_code == 200
    values = option_data(option)
    values["description"] += " Evidenz und Aufwand noch unbekannt."
    assert client.post(update, values).status_code == 302
    option.refresh_from_db()
    assert option.description == values["description"]
    assert option.evaluation_status == "draft" and option.recommendation != "preferred"
    assert client.get(update).context["form"].initial["description"] == values["description"]
    detail = client.get(process.get_absolute_url())
    assert create in detail.content.decode()
    assert detail.context["journey"].next_action.action_label == "Optionsentwürfe vergleichen"
    assert "Lösungsentscheidung offen." not in detail.content.decode()
    journey = build_process_analysis_journey(process, owner)
    assert journey.next_action.url == reverse(
        "architecture:solution_option_compare", args=[process.pk]
    )
    assert not SolutionSelectionDecision.objects.exists()
    assert_binding_stays_blocked(owner, client, process)


def test_immediate_form_contract_without_path_confirmation(exploration):
    form = ProcessAnalysisForm(process_data(exploration), instance=exploration)
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("role", ["reader", "other_owner"])
def test_unprivileged_get_and_post_remain_forbidden(request, client, exploration, owner, role):
    option = make_option(exploration, owner, name="Entwurf", option_type="no_tech", assessed=False)
    client.force_login(request.getfixturevalue(role))
    for route, pk in [
        ("process_analysis_update", exploration.pk),
        ("solution_option_create", exploration.pk),
        ("solution_option_update", option.pk),
    ]:
        url = reverse(f"architecture:{route}", args=[pk])
        assert client.get(url).status_code == 403
        assert client.post(url, {"strategic": "1"}).status_code == 403


@pytest.mark.parametrize("mutation", ["missing", "malformed", "foreign", "scope", "actor", "stage"])
def test_invalid_provenance_cannot_relax_guards(
    owner, client, exploration, business_unit, mutation
):
    process = exploration
    if mutation == "missing":
        process.source_snapshot = {}
    elif mutation == "malformed":
        process.source_snapshot["strategic_exploration"]["analysis_id"] = "not-a-uuid"
    elif mutation == "foreign":
        foreign = make_process(owner, business_unit)
        foreign.source_snapshot = deepcopy(process.source_snapshot)
        foreign.stage.value_stream.focus.status = "candidate"
        foreign.stage.value_stream.focus.save()
        process = foreign
    elif mutation == "scope":
        process.source_snapshot["strategic_exploration"]["human_scope"]["reason"] = "Invented"
    elif mutation == "actor":
        process.source_snapshot["strategic_exploration"]["scope_confirmed_by"] = -1
    else:
        process.stage = process.stage.value_stream.stages.exclude(pk=process.stage_id).first()
    process.save()
    option = make_option(process, owner, name="Entwurf", option_type="no_tech", assessed=False)
    client.force_login(owner)
    for route, pk in [
        ("process_analysis_update", process.pk),
        ("solution_option_create", process.pk),
        ("solution_option_update", option.pk),
    ]:
        url = reverse(f"architecture:{route}", args=[pk])
        assert client.get(url + "?strategic=1").status_code == 302
        assert (
            client.post(url, {"strategic": "1", "allow_unknown_diagnosis": "1"}).status_code == 302
        )
    form = ProcessAnalysisForm(instance=process)
    assert form.fields["baseline_metrics"].required


def test_binding_stays_blocked_and_preserves_inputs(owner, client, exploration):
    assert_binding_stays_blocked(owner, client, exploration)


def assert_binding_stays_blocked(owner, client, process):
    # Only after the immediate form path was tested above: isolate the still-binding focus gate.
    bind_process(owner, process, path="strategic")
    option = make_option(
        process, owner, name="Non-KI-Hypothese", option_type="no_tech", assessed=False
    )
    with pytest.raises(ValidationError, match="Fokusentscheidung"):
        select_preferred_solution(
            process_analysis=process,
            selected_option=option,
            rationale="Noch kein belastbarer Vergleich",
            actor=owner,
        )
    client.force_login(owner)
    data = {
        "selected_option": str(option.pk),
        "process_version": process.version,
        "rationale": "Organisatorische Hypothese, keine bewiesene Überlegenheit",
    }
    response = client.post(reverse("architecture:solution_option_compare", args=[process.pk]), data)
    assert response.status_code == 200
    assert "Fokusentscheidung" in str(response.context["form"].errors)
    assert response.context["form"].data["rationale"] == data["rationale"]
    assert response.context["form"].data["selected_option"] == str(option.pk)
    assert not SolutionSelectionDecision.objects.exists()
    process.refresh_from_db()
    assert process.baseline_metrics == process.bottlenecks == process.confirmed_causes == ""
    assert process.stage.value_stream.focus.status == "candidate"


def test_journey_offers_edit_before_any_option(owner, exploration):
    journey = build_process_analysis_journey(exploration, owner)
    assert journey.next_action.url == reverse(
        "architecture:process_analysis_update", args=[exploration.pk]
    )
    assert "entwurf" in journey.next_action.action_label


def test_resume_after_capture_retention(owner, client, exploration):
    CaptureSession.objects.all().delete()
    client.force_login(owner)
    edit = reverse("architecture:process_analysis_update", args=[exploration.pk])
    assert client.get(edit).status_code == 200
    response = client.post(edit, process_data(exploration))
    assert response.status_code == 302
    assert (
        client.get(
            reverse("architecture:solution_option_create", args=[exploration.pk])
        ).status_code
        == 200
    )


def test_saved_materialization_without_durable_copy_still_resumes(
    owner, tmp_path, monkeypatch, client
):
    from ki_radar.architecture import discovery_materialization

    original = discovery_materialization.bind_discovery_snapshot_to_process

    def historical_binding(**kwargs):
        kwargs.pop("strategic_exploration")
        return original(**kwargs)

    monkeypatch.setattr(
        discovery_materialization, "bind_discovery_snapshot_to_process", historical_binding
    )
    context = make_context(owner, tmp_path)
    result = materialize(owner, context[0], analyze(owner, context, monkeypatch))
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    context[0].refresh_from_db()
    context[0].status = CaptureSession.Status.EXPIRED
    context[0].save(update_fields=["status"])
    client.force_login(owner)
    edit = reverse("architecture:process_analysis_update", args=[process.pk])
    assert client.get(edit).status_code == 200
    assert client.post(edit, process_data(process)).status_code == 302


@pytest.mark.parametrize("status", ["deferred", "not_selected"])
def test_explicit_global_deferral_still_blocks_draft_exception(owner, client, exploration, status):
    focus = exploration.stage.value_stream.focus
    focus.status = status
    focus.save()
    client.force_login(owner)
    url = reverse("architecture:process_analysis_update", args=[exploration.pk])
    assert client.get(url).status_code == 302


def test_draft_cannot_self_validate(owner, client, exploration):
    client.force_login(owner)
    data = process_data(exploration)
    data["status"] = "validated"
    response = client.post(
        reverse("architecture:process_analysis_update", args=[exploration.pk]), data
    )
    assert response.status_code == 200 and "status" in response.context["form"].errors
    exploration.refresh_from_db()
    assert exploration.status == "draft" and not exploration.validations.exists()
