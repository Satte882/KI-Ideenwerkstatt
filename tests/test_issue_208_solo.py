"""Technical local solo rehearsal only; never independent human acceptance."""

import copy
import json
import secrets
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import include, path, reverse
from test_issue_146_outcome_contract import bind_process, direct
from test_solution_selection_ux import make_option

from config.urls import urlpatterns as normal_urls
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.core.openrouter import OpenRouterUnavailable, request_openrouter
from ki_radar.solo import access
from ki_radar.solo.offline import draft
from ki_radar.solo.scenarios import PACKETS, SCOPE, source_text
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_contract import confirm_initiative

pytestmark = pytest.mark.django_db
urlpatterns = [*normal_urls, path("solo/", include("ki_radar.solo.urls"))]


@pytest.fixture
def solo(monkeypatch, tmp_path, client):
    # pytest owns a separate disposable PostgreSQL DB. Test the production isolation
    # predicate separately; only this fixture substitutes its required name prefix.
    monkeypatch.setattr(access, "require_isolation", lambda: None)
    password = secrets.token_urlsafe(24)
    file = tmp_path / "password.txt"
    file.write_text(password, encoding="utf-8")
    with override_settings(
        SOLO_TEST_MODE=True,
        SETTINGS_MODULE="config.settings.solo",
        DEBUG=True,
        ROOT_URLCONF=__name__,
        MIDDLEWARE=[*settings.MIDDLEWARE, "ki_radar.solo.access.LocalSoloMiddleware"],
        INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "sources",
    ):
        # Existing migration infrastructure is already applied by pytest-django.
        monkeypatch.setattr(
            "ki_radar.core.management.commands.prepare_solo_test.call_command", Mock()
        )
        call_command("prepare_solo_test", password_file=str(file))
        master = get_user_model().objects.get(username=access.MASTER)
        client.defaults["HTTP_HOST"] = "localhost"
        client.force_login(master)
        assert client.get("/solo/").status_code == 200
        yield master, password, file


def switch(client, role):
    response = client.post("/solo/switch/", {"role": role})
    assert response.status_code == 302
    return get_user_model().objects.get(pk=client.session["_auth_user_id"])


def test_actual_identity_switch_preserves_rights_and_master_is_not_domain_actor(solo, client):
    master = solo[0]
    assert client.post(reverse("use_cases:create"), {}).status_code == 403
    seen = set()
    for key, (username, _, group) in access.ROLES.items():
        actor = switch(client, key)
        seen.add(actor.pk)
        assert actor.pk != master.pk and actor.username == username
        assert not actor.is_superuser and not actor.is_staff and not actor.has_usable_password()
        assert set(actor.groups.values_list("name", flat=True)) == {group}
    assert len(seen) == len(access.ROLES)
    assert switch(client, "master").pk == master.pk
    assert client.post("/solo/switch/", {"role": "arbitrary-user"}).status_code == 403
    assert client.get("/solo/switch/").status_code == 405


def test_intake_draft_returns_only_to_its_own_identity(solo, client):
    owner = switch(client, "owner")
    assert (
        client.post(
            reverse("use_cases:create"),
            {
                "title": "SOLO-C-Entwurf",
                "business_unit": owner.business_unit_id,
                "business_owner": owner.pk,
                "problem_statement": "Synthetische interne Regelsuche",
            },
        ).status_code
        == 302
    )
    assert client.session["use_case_intake"]["title"] == "SOLO-C-Entwurf"
    switch(client, "reader")
    assert "use_case_intake" not in client.session
    switch(client, "coordination")
    assert "use_case_intake" not in client.session
    switch(client, "owner")
    assert client.session["use_case_intake"]["title"] == "SOLO-C-Entwurf"
    page = client.get(reverse("use_cases:create"))
    assert page.status_code == 200
    assert "SOLO-C-Entwurf" in page.content.decode()
    # Clearing the current intake must not resurrect an older cached version.
    session = client.session
    session.pop("use_case_intake")
    session.save()
    switch(client, "master")
    switch(client, "owner")
    assert "use_case_intake" not in client.session


def test_switch_does_not_remove_independent_approval_gate(solo, client):
    owner = switch(client, "owner")
    coordinator = get_user_model().objects.get(username="solo_coordination")
    case = direct(owner, coordinator, owner.business_unit)
    switch(client, "owner")
    assessment_url = reverse("use_cases:assessment_create", args=[case.pk])
    assert client.get(assessment_url).status_code == 403
    switch(client, "coordination")
    url = reverse("use_cases:approval_decision_create", args=[case.pk])
    data = {
        "decision_status": "approved",
        "rationale": "Synthetische Fachprüfung",
        "governance_confirmed": "on",
    }
    assert client.post(url, data).status_code == 200
    assert not case.approval_decisions.exists()
    switch(client, "owner")
    initiative = save_initiative(
        actor=owner,
        data={
            "title": "Synthetische SOLO-C-Regelsuche",
            "business_outcome": "Verlässliche interne Auskünfte bei mehr Anfragen",
            "contribution": "Gültige Regelfundstellen für die menschliche Quellenprüfung finden",
            "impact_hypothesis": "Weniger Suchaufwand könnte Kapazität bei korrekten "
            "Auskünften schaffen",
            "outcome_owner": "Serviceleitung",
            "evaluation_criteria": "Anfragevolumen und Quellenrichtigkeit getrennt "
            "von Suchzeit prüfen",
            "measurement_unknowns": "Messdesign, Baseline und Zielwerte vor Versuch klären",
        },
    )
    initiative = confirm_initiative(
        actor=owner,
        initiative=initiative,
        rationale="Synthetischen Beitrag bewusst zuordnen",
        expected_revision=initiative.revision,
    )
    bind_initiative(actor=owner, initiative=initiative, artifact=case)
    switch(client, "coordination")
    assert client.post(url, data).status_code == 200
    assert not case.approval_decisions.exists()  # Now only the independent-actor gate remains.
    reviewer = switch(client, "review")
    assert client.post(url, data).status_code == 302
    assert case.approval_decisions.get().decided_by_id == reviewer.pk
    assert case.approval_decisions.get().outcome_snapshot["initiative_id"] == str(initiative.pk)
    switch(client, "reader")
    assert client.post(url, data).status_code == 403


@pytest.mark.parametrize("change", ["tamper", "expired", "password", "target-rights", "logout"])
def test_grant_cannot_survive_revocation_or_rights_change(solo, client, change, monkeypatch):
    master = solo[0]
    actor = switch(client, "owner")
    if change == "tamper":
        session = client.session
        session[access.GRANT] = "forged"
        session.save()
    elif change == "expired":
        session = client.session
        claim = signing.loads(session[access.GRANT], salt=access.GRANT)
        with monkeypatch.context() as patch:
            patch.setattr(signing.TimestampSigner, "timestamp", lambda self: "0")
            session[access.GRANT] = signing.dumps(claim, salt=access.GRANT)
        session.save()
    elif change == "password":
        master.set_unusable_password()
        master.save()
    elif change == "target-rights":
        actor.groups.add(Group.objects.get_or_create(name="Technischer Administrator")[0])
    else:
        client.post(reverse("accounts:logout"))
    assert client.post("/solo/switch/", {"role": "technical"}).status_code in {302, 403}
    assert "_auth_user_id" not in client.session


def test_nonlocal_anonymous_and_csrf_requests_cannot_switch(solo, client):
    assert client.get("/solo/", REMOTE_ADDR="192.0.2.1").status_code == 403
    assert client.post("/solo/switch/", {"role": "owner"}, HTTP_HOST="example.com").status_code in {
        400,
        403,
    }
    csrf = Client(enforce_csrf_checks=True, HTTP_HOST="localhost")
    csrf.force_login(solo[0])
    assert csrf.post("/solo/switch/", {"role": "owner"}).status_code == 403
    anonymous = Client(HTTP_HOST="localhost")
    assert anonymous.post("/solo/switch/", {"role": "owner"}).status_code == 302


def test_preparation_is_idempotent_and_does_not_overwrite_credentials(solo, client):
    master, _, file = solo
    count = get_user_model().objects.count()
    original = master.password
    call_command("prepare_solo_test", password_file=str(file))
    assert get_user_model().objects.count() == count
    master.refresh_from_db()
    assert master.password == original
    assert not ProcessAnalysis.objects.exists()


@pytest.mark.parametrize("case", ["A", "B"])
def test_discovery_real_routes_use_offline_packets_and_preserve_human_decisions(
    solo, client, monkeypatch, case
):
    network = Mock(side_effect=AssertionError("No network allowed"))
    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", network)
    switch(client, "owner")
    response = client.post(f"/solo/discovery/{case}/")
    assert response.status_code == 302
    session = CaptureSession.objects.get()
    assert not ProcessAnalysis.objects.exists()
    assert client.post(response.url, {"action": "retry"}).status_code == 302
    analysis = session.analyses.latest("created_at")
    assert analysis.status == CaptureAnalysis.Status.SUCCESS, analysis.error_message
    assert "solo/offline" in analysis.model_name
    assert not ProcessAnalysis.objects.exists()
    session.refresh_from_db()
    result = client.post(
        response.url,
        {
            "action": "confirm",
            "selected_stage_key": "clarify",
            "revision": session.revision,
        },
    )
    assert result.status_code == 302
    process = ProcessAnalysis.objects.get()
    assert not process.solution_selection_decisions.exists() and not process.initiative_id
    assert process.confirmed_causes == "" and process.baseline_metrics == ""
    if case == "B":
        assert process.diagnostic_observations == process.bottlenecks == ""
    assert (
        client.get(reverse("architecture:process_analysis_update", args=[process.pk])).status_code
        == 200
    )
    network.assert_not_called()
    with pytest.raises(OpenRouterUnavailable, match="nicht verfügbar"):
        request_openrouter(messages=[], max_tokens=10, timeout_seconds=1)
    owner = get_user_model().objects.get(username="solo_owner")
    initiative = save_initiative(
        actor=owner,
        data={
            "title": f"Synthetische SOLO-{case}-Kundenbetreuung",
            "business_outcome": "Verlässliche Kundenbetreuung bei mehr Anfragen",
            "contribution": "Anfragenklärung bis zur verantworteten Antwortvorbereitung",
            "impact_hypothesis": "Weniger Klärarbeit könnte Kapazität bei verlässlicher "
            "Betreuung schaffen",
            "outcome_owner": "Serviceleitung",
            "evaluation_criteria": "Anfragevolumen und Antwortqualität getrennt "
            "von Klärzeit prüfen",
            "measurement_unknowns": "Messdesign, Baseline und Zielwerte vor Versuch "
            "mit Owner klären",
        },
    )
    initiative = confirm_initiative(
        actor=owner,
        initiative=initiative,
        rationale="Begrenzte synthetische Hypothese prüfen",
        expected_revision=initiative.revision,
    )
    bind_process(
        owner,
        process,
        initiative=initiative,
        path="strategic" if case == "B" else "problem",
        path_context={
            "origin_basis": f"Synthetischer SOLO-{case}-Untersuchungsauftrag",
            "strategic_potential": "Verlässliche Betreuung bei mehr Anfragen",
            "validation_step": "Anfragevolumen und Antwortqualität getrennt prüfen",
        },
    )
    for kind, label, description in [
        ("organizational", "Verbindliche Quelle", "Zuständigkeit und Vertretung klären"),
        ("assistant", "Assistierte Zuordnung", "Freie Formulierungen aufbereiten; Mensch prüft"),
    ]:
        option = make_option(process, owner, name=label, option_type=kind, assessed=True)
        option.description = description
        option.expected_value = "Weniger Klärarbeit; Geschäftswirkung noch unbekannt"
        option.bottleneck_coverage = "Zuordnung klären; im strategischen Fall kein Ursachenbeleg"
        option.data_requirements = "Synthetische Anfragen und freigegebene Zuständigkeitsregeln"
        option.application_impact = "Servicearbeitsplatz"
        option.integration_impact = "Quellenanzeige, Zugang vor Realversuch prüfen"
        option.technology_constraints = "Keine automatische verbindliche Kundenzusage"
        option.risks = "Adoption, fehlerhafte Zuordnung und Betriebskosten unbekannt"
        option.outcome_effect = "Kapazität für verlässliche Betreuung könnte steigen"
        option.effort_assessment = (
            "Einführung, Quellenpflege und Schulung; bei KI Betrieb "
            "und menschliche Einzelprüfung; Kosten noch offen"
        )
        option.save()
    selected = process.solution_options.get(
        option_type="organizational" if case == "B" else "assistant"
    )
    response = client.post(
        reverse("architecture:solution_option_compare", args=[process.pk]),
        {
            "selected_option": selected.pk,
            "process_version": process.version,
            "confirmed_causes": process.cause_hypotheses,
            "rationale": "Verbindlichkeit direkt organisatorisch klären; Adoption offen"
            if case == "B"
            else "Freie Formulierungen begrenzt assistieren; Prüfaufwand akzeptiert",
            "difference_reason": "Verantwortlichkeit an der Quelle ändern gegenüber "
            "Aufbereitung freier Formulierungen; Mensch bleibt verantwortlich",
            "uncertainty_reason": "Globale Screeningfragen bei Strategie offen; "
            "Adoption, Kosten und Geschäftswirkung sind nicht gemessen",
            "diagnosis_basis": "assumption",
            "diagnosis_note": "Synthetische fachliche Hypothese; kein empirischer Ursachenbeweis",
        },
    )
    assert response.status_code == 302, response.context["form"].errors
    process.refresh_from_db()
    decision = process.solution_selection_decisions.get()
    assert not decision.outcome_review_required
    assert UseCase.objects.count() == (1 if case == "A" else 0)
    network.assert_not_called()


@pytest.mark.parametrize("invalid", ["mode", "module", "debug", "database", "host"])
def test_isolation_fails_closed_even_with_mode_flag(invalid):
    databases = copy.deepcopy(settings.DATABASES)
    databases["default"].update(NAME="ki_radar_solo_guard", HOST="127.0.0.1")
    values = dict(
        SOLO_TEST_MODE=True, SETTINGS_MODULE="config.settings.solo", DEBUG=True, DATABASES=databases
    )
    if invalid == "mode":
        values["SOLO_TEST_MODE"] = False
    elif invalid == "module":
        values["SETTINGS_MODULE"] = "config.settings.prod"
    elif invalid == "debug":
        values["DEBUG"] = False
    elif invalid == "database":
        databases["default"]["NAME"] = "ki_radar"
    else:
        databases["default"]["HOST"] = "db.example.com"
    with override_settings(**values), pytest.raises(PermissionDenied):
        access.require_isolation()


def test_solo_routes_absent_in_normal_application(client):
    assert client.get("/solo/").status_code == 404


@pytest.mark.parametrize("changed", ["input", "extra-source", "scope", "verifier"])
def test_offline_rejects_changed_packets_and_foreign_verification(solo, monkeypatch, changed):
    network = Mock(side_effect=AssertionError("No network allowed"))
    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", network)
    document = {
        **{key: PACKETS["B"][key] for key in ("problem_statement", "business_context")},
        "sources": [{"content": source_text("B")}],
        "human_scope": dict(SCOPE),
    }
    name = "autonomous_business_discovery_v3"
    if changed == "input":
        document["problem_statement"] = "Unrelated input"
    elif changed == "extra-source":
        document["sources"].append({"content": "Foreign source"})
    elif changed == "scope":
        document["human_scope"]["scope_start"] = "Other start"
    else:
        payload = draft("B", "ap1-discovery-v3", dict(SCOPE))
        payload["process_analysis"]["baseline_metrics"] = "Invented measurement"
        document = {"input": document, "draft": payload}
        name = "autonomous_business_discovery_verifier_v2"
    response_format = {
        "json_schema": {
            "name": name,
            "schema": {
                "properties": {"schema_version": {"enum": ["ap1-discovery-v3"]}},
            },
        }
    }
    with pytest.raises(OpenRouterUnavailable):
        request_openrouter(
            messages=[{"content": json.dumps(document)}],
            max_tokens=10,
            timeout_seconds=1,
            response_format=response_format,
        )
    network.assert_not_called()


def test_mode_flag_alone_never_enables_offline_transport(monkeypatch):
    network = Mock(side_effect=AssertionError("No network allowed"))
    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", network)
    with override_settings(SOLO_TEST_MODE=True), pytest.raises(PermissionDenied):
        request_openrouter(messages=[], max_tokens=10, timeout_seconds=1)
    network.assert_not_called()
