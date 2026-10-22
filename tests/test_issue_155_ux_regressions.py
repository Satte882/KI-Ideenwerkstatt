"""Outcome preparation and explicit AI planning must preserve human commands."""

import socket
from types import SimpleNamespace

import pytest
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process
from test_issue_146_outcome_contract import direct as direct_case
from test_issue_146_outcome_contract import process as process_fixture

from ki_radar.architecture.stage_focus import get_stage_focus_decision
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_contract import outcome_blockers

pytestmark = pytest.mark.django_db
process = process_fixture


@pytest.fixture(autouse=True)
def no_external_models(monkeypatch, settings):
    settings.OPENROUTER_API_KEY = ""
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    database_port = int(settings.DATABASES["default"].get("PORT") or 5432)

    def guarded(original):
        def connect(sock, address):
            if (
                settings.DATABASES["default"]["ENGINE"].endswith("postgresql")
                and isinstance(address, tuple)
                and address[0] in {"127.0.0.1", "::1", "localhost"}
                and address[1] == database_port
            ):
                return original(sock, address)
            return blocked()

        return connect

    def blocked():
        raise AssertionError("External network is forbidden in UX155 regressions")

    monkeypatch.setattr(socket.socket, "connect", guarded(original_connect))
    monkeypatch.setattr(socket.socket, "connect_ex", guarded(original_connect_ex))


def preparation_url(process):
    return reverse("use_cases:prepare_outcome", kwargs={"kind": "process", "pk": process.pk})


def form_data(response):
    form = response.context["form"]
    return {name: form[name].value() or "" for name in form.fields}


def test_load_requires_explicit_replace_and_cancel_preserves_incomplete_input(
    client, owner, process
):
    initiative = bind_process(owner, process)
    client.force_login(owner)
    url = preparation_url(process)
    data = form_data(client.get(url))
    data.update(title="", business_outcome="UNSAVED-155", origin_basis="Unbestätigte Herkunft")
    pending = client.post(url, {**data, "action": "load"})
    assert pending.status_code == 200
    assert pending.context["load_pending"]
    assert pending.context["form"]["business_outcome"].value() == "UNSAVED-155"
    assert "Eingaben ersetzen und Vorhaben laden" in pending.content.decode()
    kept = client.post(url, {**data, "action": "cancel_load"})
    assert not kept.context["load_pending"]
    assert kept.context["form"]["origin_basis"].value() == "Unbestätigte Herkunft"
    assert kept.context["form"]["title"].value() == ""
    initiative.refresh_from_db()
    assert initiative.business_outcome != "UNSAVED-155"
    assert process.discovery_path_decisions.count() == 1
    replaced = client.post(url, {**data, "action": "confirm_load"}, follow=True)
    assert replaced.context["form"]["business_outcome"].value() == initiative.business_outcome
    assert not replaced.context["load_pending"]


def test_outcome_blockers_are_visible_before_selection_and_server_still_rejects(
    client, owner, process
):
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    before = client.get(url)
    assert before.context["selection_blocked"]
    assert before.context["outcome_blockers"] == [
        "Vorhaben mit Geschäftsergebnis und Wirkannahme bewusst zuordnen"
    ]
    assert 'data-testid="selection-outcome-blocker"' in before.content.decode()
    assert preparation_url(process) in before.content.decode()
    rejected = client.post(
        url,
        {
            "selected_option": process.solution_options.first().pk,
            "process_version": process.version,
            "rationale": "Eingabe bleibt erhalten",
        },
    )
    assert rejected.status_code == 200
    assert "Eingabe bleibt erhalten" in rejected.content.decode()
    assert not process.solution_selection_decisions.exists()
    bind_process(owner, process)
    assert not client.get(url).context["selection_blocked"]


@pytest.mark.parametrize(
    "route,label",
    [
        ("initiative_edit", "Vorhaben"),
        ("initiative_impact", "Wirkungsprüfung"),
        ("capability_experiment_create", "Capability-Test"),
    ],
)
def test_shared_outcome_pages_have_one_active_main_and_local_area(
    client, owner, process, route, label
):
    initiative = bind_process(owner, process)
    client.force_login(owner)
    kwargs = {"initiative_id" if route == "capability_experiment_create" else "pk": initiative.pk}
    response = client.get(reverse(f"use_cases:{route}", kwargs=kwargs))
    assert response.status_code == 200
    assert response.context["nav_is_analysis"]
    assert response.context["nav_outcome_label"] == label
    content = response.content.decode()
    assert content.count('aria-current="page"') == 1
    assert 'aria-current="location"' in content


def test_reader_cannot_load_or_save_outcome_or_start_ai_planning(client, reader, process):
    client.force_login(reader)
    for action in ("load", "confirm_load", "save_draft", "confirm"):
        assert client.post(preparation_url(process), {"action": action}).status_code == 403
    compare = reverse("architecture:solution_option_compare", args=[process.pk])
    assert client.post(compare, {"continue_ai_handoff": "1"}).status_code == 403
    assert not ImprovementInitiative.objects.exists()


def test_direct_outcome_stays_in_use_case_context(client, owner, coordinator, business_unit):
    case = direct_case(owner, coordinator, business_unit)
    client.force_login(owner)
    response = client.get(
        reverse("use_cases:prepare_outcome", kwargs={"kind": "usecase", "pk": case.pk})
    )
    assert response.status_code == 200
    assert not response.context["nav_is_analysis"]
    assert response.context["nav_outcome_label"] == "Outcome-Bezug vorbereiten"
    assert response.content.decode().count('aria-current="page"') == 1
    assert 'aria-label="Lokaler Use-Case-Bereich"' in response.content.decode()


def test_ai_selection_has_zero_generation_side_effects_and_explicit_planning_uses_existing_services(
    client,
    owner,
    process,
    monkeypatch,
):
    bind_process(owner, process)
    calls = []

    def metric(*, use_case, actor):
        calls.append("metric")
        use_case.ap2_planning_provenance = {"generated_by": "mock"}
        use_case.save(update_fields=["ap2_planning_provenance", "updated_at"])
        return SimpleNamespace(changed_fields=("metric_name",))

    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_and_apply_ap2_metric_pilot", metric
    )
    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_ap2_architecture_inputs",
        lambda **kw: calls.append("architecture"),
    )
    monkeypatch.setattr(
        "ki_radar.architecture.solution_views.generate_ap2_decision_governance",
        lambda **kw: calls.append("governance"),
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    response = client.post(
        url,
        {
            "selected_option": process.solution_options.get(option_type="assistant").pk,
            "process_version": process.version,
            "rationale": "KI mit manueller Prüfung begründet",
        },
        follow=True,
    )
    assert response.status_code == 200
    assert calls == []
    case = UseCase.objects.get()
    assert case.ap2_planning_provenance == {}
    assert "kostenpflichtige Modellaufrufe" in response.content.decode()
    client.get(url)
    assert calls == []
    generated = client.post(url, {"continue_ai_handoff": "1"}, follow=True)
    assert generated.status_code == 200
    assert calls == ["metric", "architecture", "governance"]
    assert process.solution_selection_decisions.count() == 1
    assert UseCase.objects.count() == 1
    assert "keine Freigabe" in generated.content.decode()


def test_draft_context_survives_redirect_and_login_without_changing_binding(client, owner, process):
    initiative = bind_process(owner, process, path="strategic")
    path = process.discovery_path_decisions.first()
    focus = get_stage_focus_decision(process.stage.value_stream, initiative=initiative)
    confirmation = (
        initiative.confirmed_revision,
        initiative.confirmed_by_id,
        initiative.confirmed_at,
    )
    client.force_login(owner)
    url = preparation_url(process)
    data = form_data(client.get(url))
    context = {
        "path": "problem",
        "origin_basis": "DRAFT-ORIGIN-155",
        "strategic_potential": "DRAFT-POTENTIAL-155",
        "validation_step": "Später prüfen",
        "focus_reason": "Noch unbestätigter Fokus",
        "change_reason": "Wechsel prüfen",
        "confirmation_reason": "Noch unbestätigte Annahme",
    }
    saved = client.post(url, {**data, **context, "action": "save_draft"}, follow=True)
    assert saved.status_code == 200
    for key, value in context.items():
        assert saved.context["form"][key].value() == value
    initiative.refresh_from_db()
    assert (
        initiative.confirmed_revision,
        initiative.confirmed_by_id,
        initiative.confirmed_at,
    ) == confirmation
    assert process.discovery_path_decisions.count() == 1
    assert process.discovery_path_decisions.first().pk == path.pk
    assert (
        get_stage_focus_decision(process.stage.value_stream, initiative=initiative).pk == focus.pk
    )
    client.logout()
    client.force_login(owner)
    resumed = client.get(saved.request["PATH_INFO"], {"initiative": initiative.pk})
    assert resumed.context["has_preparation_draft"]
    for key, value in context.items():
        assert resumed.context["form"][key].value() == value
    # The draft does not replace any gate input or immutable decision context.
    assert not outcome_blockers(process)
    assert process.discovery_path_decisions.first().origin_basis != context["origin_basis"]
    confirmed_data = form_data(resumed)
    accepted = client.post(url, {**confirmed_data, "action": "confirm"})
    assert accepted.status_code == 302
    initiative.refresh_from_db()
    assert initiative.preparation_drafts == {}
    assert process.discovery_path_decisions.first().origin_basis == context["origin_basis"]


def test_new_draft_is_unbound_and_incomplete_confirmation_keeps_context(client, owner, process):
    client.force_login(owner)
    url = preparation_url(process)
    saved = client.post(
        url,
        {
            "title": "Offener Entwurf",
            "evidence_level": "hypothesis",
            "action": "save_draft",
            "path": "strategic",
            "origin_basis": "Offener Auftrag",
            "strategic_potential": "",
            "focus_reason": "",
            "confirmation_reason": "",
        },
        follow=True,
    )
    initiative = ImprovementInitiative.objects.get()
    process.refresh_from_db()
    assert process.initiative_id is None
    assert not process.discovery_path_decisions.exists()
    assert get_stage_focus_decision(process.stage.value_stream, initiative=initiative) is None
    assert initiative.confirmed_by_id is None
    rejected = client.post(url, {**form_data(saved), "action": "confirm"})
    assert rejected.status_code == 200
    initiative.refresh_from_db()
    assert initiative.preparation_drafts
    assert not process.discovery_path_decisions.exists()


def test_stale_draft_cannot_overwrite_another_edit(client, owner, process):
    initiative = bind_process(owner, process)
    client.force_login(owner)
    url = preparation_url(process)
    stale = form_data(client.get(url))
    save_initiative(actor=owner, initiative=initiative, data={"title": "Neuer Stand"})
    rejected = client.post(
        url, {**stale, "origin_basis": "Nicht überschreiben", "action": "save_draft"}
    )
    assert rejected.status_code == 200
    assert "inzwischen geändert" in rejected.content.decode()
    initiative.refresh_from_db()
    assert initiative.title == "Neuer Stand"
    assert initiative.preparation_drafts == {}
