"""Binding prerequisites use the same rules in preparation, real routes and services."""

from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import direct
from test_issue_183_strategic_binding import QUALITY as STRATEGIC_QUALITY
from test_issue_183_strategic_binding import bind, options
from test_issue_183_strategic_binding import exploration as exploration_fixture
from test_issue_185_strategic_drafts import option_data
from test_issue_188_decision_quality import QUALITY, choose
from test_issue_188_decision_quality import comparison as comparison_fixture
from test_issue_189_measurement_plan import PLAN
from test_solution_selection_ux import make_option, make_process

from ki_radar.architecture.solution_selection import select_preferred_solution
from ki_radar.use_cases.initiatives import PLAN_FIELDS, save_initiative
from ki_radar.use_cases.outcome_contract import (
    build_outcome_snapshot,
    confirm_initiative,
    outcome_blockers,
    set_discovery_path,
)
from ki_radar.use_cases.services import approval_check, submit_approval_decision

pytestmark = pytest.mark.django_db
comparison = comparison_fixture
exploration = exploration_fixture


def form_data(client, url):
    form = client.get(url).context["form"]
    return {name: form[name].value() or "" for name in form.fields}


def without_plan(owner, initiative):
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={**dict.fromkeys(PLAN_FIELDS, ""), "measurement_change_reason": "Messdesign offen"},
    )
    return confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Hypothese bleibt angenommen; Messdesign fehlt noch",
        expected_revision=initiative.revision,
    )


def test_only_effort_missing_has_named_blocker_and_working_correction(client, owner, comparison):
    process = comparison
    option = process.solution_options.get(option_type="organizational")
    option.effort_assessment = ""
    option.save()
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    page = client.get(url)
    assert page.context["selection_blocked"]
    assert not page.context["outcome_blockers"]
    assert not page.context["incomplete_options"]
    blocker = f"Aufwand, Kosten und Umstellung fehlen: {option.name}"
    assert blocker in page.content.decode()
    edit = (
        reverse("architecture:solution_option_update", args=[option.pk]) + "?return_to=comparison"
    )
    assert edit in page.content.decode()
    assert client.get(edit).status_code == 200
    with pytest.raises(ValidationError, match="Aufwand, Kosten und Umstellung"):
        choose(process, owner, **QUALITY)
    payload = {
        "selected_option": option.pk,
        "process_version": process.version,
        "rationale": "Eingabe trotz manipulierter Freigabe behalten",
        **QUALITY,
    }
    rejected = client.post(url, payload)
    assert rejected.status_code == 200
    assert payload["rationale"] in rejected.content.decode()
    assert blocker in rejected.content.decode()
    assert not process.solution_selection_decisions.exists()
    data = option_data(option)
    data["effort_assessment"] = "Einmalige Schulung; laufende Pflege; Kosten offen"
    assert client.post(edit, data).url == url
    assert not client.get(url).context["selection_blocked"]
    assert client.post(url, payload).status_code == 302


@pytest.mark.parametrize("resolution", ["plan", "unknowns"])
@pytest.mark.parametrize("path", ["problem", "strategic"])
def test_missing_measurement_matches_service_and_is_fixed_in_existing_route(
    client, owner, comparison, resolution, path
):
    process = comparison
    if path == "strategic":
        set_discovery_path(
            process=process,
            actor=owner,
            path=path,
            origin_basis="Strategischer synthetischer Auftrag",
            change_reason="Explizite neue fachliche Einordnung",
            strategic_potential="Mehr tragfaehige Buchungen",
            validation_step="Qualitaet und Volumen vor Versuch abgrenzen",
        )
    initiative = without_plan(owner, process.initiative)
    process.refresh_from_db()
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    page = client.get(url)
    blockers = page.context["outcome_blockers"]
    assert len(blockers) == 1 and "Messabsicht" in blockers[0]
    assert blockers[0] in page.content.decode()
    assert page.context["selection_blocked"]
    with pytest.raises(ValidationError) as exc:
        build_outcome_snapshot(process)
    assert exc.value.messages == ["Outcome-Bezug offen: " + blockers[0]]
    # Read-only preflight must never alter confirmation or historical snapshots.
    assert build_outcome_snapshot(process, require_measurement_plan=False)
    option = process.solution_options.get(option_type="organizational")
    payload = {
        "selected_option": option.pk,
        "process_version": process.version,
        "rationale": "Synthetische Abwaegung behalten",
        **QUALITY,
    }
    rejected = client.post(url, payload)
    assert blockers[0] in rejected.content.decode()
    assert rejected.context["form"]["rationale"].value() == payload["rationale"]
    assert not process.solution_selection_decisions.exists()
    prepare = reverse("use_cases:prepare_outcome", args=["process", process.pk])
    assert prepare in page.content.decode()
    data = form_data(client, prepare)
    assert all(name in data for name in (*PLAN_FIELDS, "measurement_change_reason"))
    data.update(
        PLAN
        if resolution == "plan"
        else {
            "measurement_unknowns": "Referenzdaten fehlen; Owner klaert Vergleich vor Pilotstart."
        }
    )
    data.update(action="confirm", confirmation_reason="Messabsicht bewusst angenommen")
    response = client.post(prepare, data)
    assert response.status_code == 302, response.context and response.context["form"].errors
    assert response.url == url
    initiative.refresh_from_db()
    assert initiative.business_outcome == data["business_outcome"]
    assert initiative.measurement_unknowns == data["measurement_unknowns"]
    assert not client.get(url).context["selection_blocked"]
    assert client.post(url, payload).status_code == 302
    frozen = deepcopy(process.solution_selection_decisions.get().outcome_snapshot)
    assert frozen["fields"]["measurement_method"] == data["measurement_method"]
    assert frozen["fields"]["measurement_unknowns"] == data["measurement_unknowns"]


def test_real_strategic_materialization_missing_plan_keeps_only_measurement_blocker(
    client, owner, exploration
):
    process = exploration
    initiative = bind(owner, process)
    option = options(owner, process, client)[0]
    without_plan(owner, initiative)
    process.refresh_from_db()
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    page = client.get(url)
    assert len(page.context["outcome_blockers"]) == 1
    assert "Messabsicht" in page.context["outcome_blockers"][0]
    assert not page.context["focus_blockers"]
    prepare = reverse("use_cases:prepare_outcome", args=["process", process.pk])
    data = form_data(client, prepare)
    data.update(
        measurement_unknowns="Ist-Daten fehlen; Serviceleitung klaert vor Versuch.",
        measurement_change_reason="Offene Messabsicht konkretisieren",
        confirmation_reason="Begrenzte Hypothese bewusst annehmen",
        action="confirm",
    )
    assert client.post(prepare, data).status_code == 302
    assert not client.get(url).context["selection_blocked"]
    assert (
        client.post(
            url,
            {
                "selected_option": option.pk,
                "process_version": process.version,
                "rationale": "Organisatorisch begrenzt pruefen",
                **STRATEGIC_QUALITY,
            },
        ).status_code
        == 302
    )
    assert not process.confirmed_causes


def test_direct_approval_preflight_matches_service_and_preparation_returns_to_decision(
    client, owner, coordinator, technical_admin, business_unit
):
    case = direct(owner, coordinator, business_unit)
    client.force_login(technical_admin)
    prepare = reverse("use_cases:prepare_outcome", args=["usecase", case.pk])
    data = form_data(client, prepare)
    data.update(
        title="Synthetischer Buchungsbeitrag",
        business_outcome="Tragfaehige Buchungen",
        contribution="Rueckfragen begrenzen",
        impact_hypothesis="Freie Kapazitaet koennte helfen",
        evaluation_criteria="Buchungen und Qualitaet pruefen",
        outcome_owner="Serviceleitung",
        confirmation_reason="Hypothese annehmen",
        action="confirm",
    )
    assert client.post(prepare, data).status_code == 302
    case.refresh_from_db()
    blockers = approval_check(
        use_case=case, target_status="approved", actor=technical_admin
    ).blockers
    assert len(blockers) == 1 and "Messabsicht" in blockers[0]
    approval = reverse("use_cases:approval_decision_create", args=[case.pk])
    assert blockers[0] in client.get(approval).content.decode()
    with pytest.raises(ValidationError, match="Messabsicht"):
        submit_approval_decision(
            use_case=case,
            actor=technical_admin,
            data={"decision_status": "approved", "rationale": "Pruefen"},
        )
    data = form_data(client, prepare)
    data.update(PLAN, action="confirm", confirmation_reason="Messabsicht vor Freigabe angenommen")
    assert client.post(prepare, data).url == approval
    case.refresh_from_db()
    assert not approval_check(
        use_case=case, target_status="approved", actor=technical_admin
    ).blockers
    assert (
        client.post(
            approval,
            {"decision_status": "approved", "rationale": "Unabhaengige synthetische Freigabe"},
        ).status_code
        == 302
    )
    assert case.approval_decisions.count() == 1


def test_preparation_errors_revisions_and_rights_preserve_measurement_input(
    client, owner, comparison, reader
):
    process = comparison
    initiative = process.initiative
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", args=["process", process.pk])
    data = form_data(client, url)
    data.update(
        PLAN,
        measurement_unknowns="Offene Vergleichbarkeit vor Versuch klaeren",
        measurement_change_reason="Plan konkretisieren",
        action="confirm",
        confirmation_reason="Neue Absicht annehmen",
    )
    # A stale write is refused with every field retained.
    save_initiative(actor=owner, initiative=initiative, data={"title": "Neuer gespeicherter Titel"})
    page = client.post(url, data)
    assert page.status_code == 200 and "inzwischen" in page.content.decode()
    for name in (*PLAN_FIELDS, "measurement_change_reason", "business_outcome"):
        assert page.context["form"][name].value() == data[name]
    initiative.refresh_from_db()
    assert not initiative.measurement_method
    # Missing change rationale cannot silently rewrite an already documented open plan.
    data["expected_revision"] = initiative.revision
    data["measurement_change_reason"] = ""
    page = client.post(url, data)
    assert "Messplan-/Kriterienänderung bitte begründen" in page.content.decode()
    assert page.context["form"]["measurement_reference"].value() == PLAN["measurement_reference"]
    client.force_login(reader)
    assert client.get(url).status_code == 403
    assert client.post(url, data).status_code == 403
    initiative.refresh_from_db()
    assert not initiative.measurement_method


def test_incomplete_measurement_draft_roundtrip_and_reconfirmation(client, owner, comparison):
    process = comparison
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", args=["process", process.pk])
    data = form_data(client, url)
    data.update(
        measurement_method="Methode als frueher Entwurf",
        measurement_unknowns="",
        measurement_change_reason="Plan schrittweise vorbereiten",
        action="save_draft",
    )
    response = client.post(url, data)
    assert response.status_code == 302
    restored = form_data(client, response.url)
    for name in (*PLAN_FIELDS, "business_outcome", "impact_hypothesis"):
        assert restored[name] == data[name]
    initiative = process.initiative
    initiative.refresh_from_db()
    assert initiative.confirmed_by_id is None
    assert not initiative.measurement_period
    assert outcome_blockers(process, require_measurement_plan=True)
    restored.update(PLAN, action="confirm", confirmation_reason="Vollstaendigen Plan annehmen")
    assert client.post(url, restored).status_code == 302
    process.refresh_from_db()
    assert not outcome_blockers(process, require_measurement_plan=True)
    original_revision = process.initiative.outcome_revision
    # Unchanged return through preparation must preserve current confirmation.
    restored = form_data(client, url)
    restored.update(action="confirm", confirmation_reason="Unveraendert")
    assert client.post(url, restored).status_code == 302
    process.refresh_from_db()
    assert process.initiative.outcome_revision == original_revision
    assert process.initiative.confirmed_revision == original_revision


def test_legacy_has_no_new_measurement_gate(owner, business_unit):
    process = make_process(owner, business_unit)
    for name in ("Organisieren", "Standardsoftware"):
        make_option(process, owner, name=name, option_type="organizational", assessed=True)
    assert outcome_blockers(process, require_measurement_plan=True) == []
    option = process.solution_options.first()
    decision = select_preferred_solution(
        process_analysis=process,
        selected_option=option,
        actor=owner,
        rationale="Historischer Vertrag",
    )
    assert decision.outcome_snapshot == {}
