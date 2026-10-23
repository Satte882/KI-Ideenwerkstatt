from copy import deepcopy

import pytest
from django.forms import HiddenInput
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process, outcome_process, select

from ki_radar.architecture.models import ValueStreamStage
from ki_radar.architecture.stage_focus import get_phase_focus_decision
from ki_radar.use_cases.initiatives import save_initiative

pytestmark = pytest.mark.django_db


def prep_url(process):
    return reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": process.pk})


def form_data(response):
    form = response.context["form"]
    return {name: form[name].value() or "" for name in form.fields}


def confirmation_block(response):
    return (
        response.content.decode()
        .split('data-testid="outcome-confirmation">', 1)[1]
        .split("</div>", 1)[0]
    )


@pytest.fixture
def process(owner, business_unit):
    return outcome_process(owner, business_unit)


def test_first_entry_hides_special_fields_and_resumes_draft(client, owner, process):
    client.force_login(owner)
    first = client.get(prep_url(process))
    for field in ("change_reason", "correction_reason", "adopt_contract"):
        assert isinstance(first.context["form"].fields[field].widget, HiddenInput)
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(first)
    data = form_data(first)
    data.update(
        title="Unfertiger Entwurf",
        evidence_level="hypothesis",
        action="save_draft",
        origin_basis="Noch offener Auftrag",
        focus_reason="Ungesicherter Fokusgrund",
    )
    saved = client.post(prep_url(process), data, follow=True)
    assert saved.status_code == 200
    assert saved.context["form"]["focus_reason"].value() == "Ungesicherter Fokusgrund"
    client.logout()
    client.force_login(owner)
    resumed = client.get(saved.request["PATH_INFO"], {"initiative": saved.context["initiative"].pk})
    assert resumed.context["form"]["origin_basis"].value() == "Noch offener Auftrag"
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(resumed)
    process.refresh_from_db()
    assert not process.initiative_id and not process.discovery_path_decisions.exists()


@pytest.mark.parametrize("state", ["new", "confirmed", "changed"])
def test_all_surfaces_show_only_actual_confirmation(client, owner, reader, process, state):
    initiative = bind_process(owner, process)
    if state == "new":
        # A genuinely never-confirmed initiative is linked only for exploration.
        second = outcome_process(owner, process.stage.value_stream.business_unit)
        initiative = save_initiative(actor=owner, data={"title": "Noch nicht angenommen"})
        from ki_radar.use_cases.initiatives import bind_initiative

        bind_initiative(actor=owner, initiative=initiative, artifact=second)
        process = second
    elif state == "changed":
        initiative = save_initiative(
            actor=owner, initiative=initiative, data={"impact_hypothesis": "Andere Wirkannahme"}
        )
    else:
        initiative = save_initiative(actor=owner, initiative=initiative, data={"status": "active"})
    client.force_login(owner)
    urls = [
        prep_url(process),
        initiative.get_absolute_url(),
        reverse("architecture:solution_option_compare", args=[process.pk]),
    ]
    for url in urls:
        response = client.get(url)
        assert response.status_code == 200
        block = confirmation_block(response)
        assert "Fachlich angenommen ist kein Geschäftserfolgsnachweis." in block
        assert f"Outcome-Revision {initiative.outcome_revision}" in block
        assert ("Wirkannahme dieser Revision fachlich angenommen." in block) == (
            state == "confirmed"
        )
        assert ("Entwurf / fachlich noch nicht angenommen." in block) == (state != "confirmed")
        if state == "confirmed":
            assert str(owner) in block and "<time datetime=" in block
            assert "Vorhabensstatus: Aktiv" in block
    client.force_login(reader)
    readonly = client.get(initiative.get_absolute_url())
    assert readonly.status_code == 200
    assert ("Wirkannahme dieser Revision fachlich angenommen." in confirmation_block(readonly)) == (
        state == "confirmed"
    )


def test_failed_path_switch_keeps_values_and_stored_confirmation(client, owner, process):
    initiative = bind_process(owner, process)
    frozen = deepcopy(select(owner, process).outcome_snapshot)
    client.force_login(owner)
    data = form_data(client.get(prep_url(process)))
    data.update(
        action="confirm",
        path="strategic",
        change_reason="",
        business_outcome="Nicht gespeichertes Ziel",
        strategic_potential="Sichtbares neues Potenzial",
        validation_step="Fachlich prüfen",
        confirmation_reason="Annahme",
        correction_reason="Ungesicherte Korrektur",
    )
    failed = client.post(prep_url(process), data)
    assert failed.status_code == 200
    assert "Pfadwechsel benötigt" in failed.content.decode()
    for field in ("change_reason", "correction_reason"):
        assert not isinstance(failed.context["form"].fields[field].widget, HiddenInput)
    for field in ("business_outcome", "strategic_potential", "correction_reason"):
        assert failed.context["form"][field].value() == data[field]
    block = confirmation_block(failed)
    assert "Wirkannahme dieser Revision fachlich angenommen." in block
    assert "Ungesicherte Eingaben" in block
    initiative.refresh_from_db()
    assert initiative.business_outcome != data["business_outcome"]
    assert process.discovery_path_decisions.count() == 1
    assert process.solution_selection_decisions.first().outcome_snapshot == frozen
    data["change_reason"] = "Strategisches Potenzial nach fachlicher Prüfung"
    assert client.post(prep_url(process), data).status_code == 302
    assert process.discovery_path_decisions.count() == 2


def test_formal_correction_preserves_confirmation_and_remains_accessible_after_material_change(
    client, owner, process
):
    initiative = bind_process(owner, process)
    before = (initiative.outcome_revision, initiative.confirmed_revision, initiative.confirmed_at)
    client.force_login(owner)
    initial = client.get(prep_url(process))
    assert not isinstance(initial.context["form"].fields["correction_reason"].widget, HiddenInput)
    data = form_data(initial)
    data.update(
        action="save_draft",
        business_outcome=initiative.business_outcome + ".",
        correction_reason="Nur Satzpunkt ergänzt",
    )
    saved = client.post(prep_url(process), data, follow=True)
    assert saved.status_code == 200
    initiative.refresh_from_db()
    assert (
        initiative.outcome_revision,
        initiative.confirmed_revision,
        initiative.confirmed_at,
    ) == before
    assert saved.context["form"]["correction_reason"].value() == "Nur Satzpunkt ergänzt"
    save_initiative(
        actor=owner,
        initiative=initiative,
        data={"impact_hypothesis": "Tatsächlich anderer Mechanismus"},
    )
    current = client.get(prep_url(process))
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(current)
    assert not isinstance(current.context["form"].fields["correction_reason"].widget, HiddenInput)


@pytest.mark.parametrize("action", ["load", "cancel_load", "save_draft"])
def test_special_post_values_survive_context_switches(client, owner, process, action):
    target = save_initiative(actor=owner, data={"title": "Unbestätigter Entwurf"})
    client.force_login(owner)
    first = client.get(prep_url(process), {"initiative": target.pk})
    data = form_data(first)
    data.update(
        action=action,
        change_reason="Noch ungesicherter Wechsel",
        correction_reason="Noch ungesicherte Korrektur",
    )
    response = client.post(prep_url(process), data, follow=True)
    assert response.status_code == 200
    for field in ("change_reason", "correction_reason"):
        assert response.context["form"][field].value() == data[field]
        assert not isinstance(response.context["form"].fields[field].widget, HiddenInput)
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(response)


def test_hidden_revision_error_is_visible_and_input_not_lost(client, owner, process):
    bind_process(owner, process)
    client.force_login(owner)
    data = form_data(client.get(prep_url(process)))
    data.update(action="save_draft", expected_revision="invalid", focus_reason="Nicht verlieren")
    rejected = client.post(prep_url(process), data)
    assert rejected.status_code == 200
    assert "Geprüfter Vorhabensstand" in rejected.content.decode()
    assert 'role="alert"' in rejected.content.decode()
    assert rejected.context["form"]["focus_reason"].value() == "Nicht verlieren"


def test_phase_rationale_is_read_only_and_comparison_blockers_stay_visible(
    client, owner, process, business_unit
):
    initiative = bind_process(owner, process)
    focus = get_phase_focus_decision(process.stage, initiative=initiative)
    decision = select(owner, process)
    frozen = deepcopy(decision.outcome_snapshot)
    stage = ValueStreamStage.objects.create(
        value_stream=process.stage.value_stream, sequence=2, name="Phase B"
    )
    second = outcome_process(owner, business_unit, stage=stage)
    bind_process(owner, second, initiative=initiative)
    ids = list(initiative.stage_focus_decisions.values_list("pk", flat=True))
    client.force_login(owner)
    for _ in range(2):
        response = client.get(prep_url(process))
        assert response.context["phase_focus"].pk == focus.pk
        html = response.content.decode()
        assert 'data-testid="phase-focus-rationale"' in html and focus.rationale in html
    assert list(initiative.stage_focus_decisions.values_list("pk", flat=True)) == ids
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen and not decision.outcome_review_required
    option = process.solution_options.first()
    option.outcome_effect = ""
    option.save()
    save_initiative(
        actor=owner, initiative=initiative, data={"business_outcome": "Wesentlich anderes Ziel"}
    )
    comparison = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))
    assert comparison.context["selection_blocked"]
    assert 'data-testid="selection-option-outcome-blocker"' in comparison.content.decode()
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(comparison)


def test_unbound_comparison_and_direct_case_use_actual_status(
    client, owner, coordinator, business_unit, process
):
    from test_issue_146_outcome_contract import direct

    client.force_login(owner)
    comparison = client.get(reverse("architecture:solution_option_compare", args=[process.pk]))
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(comparison)
    case = direct(owner, coordinator, business_unit)
    url = reverse("use_cases:prepare_outcome", kwargs={"kind": "usecase", "pk": case.pk})
    initial = client.get(url)
    for field in ("change_reason", "correction_reason", "focus_reason"):
        assert isinstance(initial.context["form"].fields[field].widget, HiddenInput)
    assert "Entwurf / fachlich noch nicht angenommen." in confirmation_block(initial)
    data = form_data(initial)
    data.update(
        action="save_draft",
        title="Direkter Entwurf",
        evidence_level="hypothesis",
        correction_reason="Nicht verlorene Eingabe",
    )
    saved = client.post(url, data, follow=True)
    assert saved.status_code == 200
    assert saved.context["form"]["correction_reason"].value() == "Nicht verlorene Eingabe"
    assert not isinstance(saved.context["form"].fields["correction_reason"].widget, HiddenInput)
