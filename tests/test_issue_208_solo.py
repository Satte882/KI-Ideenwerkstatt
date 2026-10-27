"""Technical local solo rehearsal only; never independent human acceptance."""

import copy
import io
import json
import secrets
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, override_settings
from django.urls import include, path, reverse
from test_issue_98_autonomous_business_discovery import _approved_analysis, _session_and_snapshot
from test_issue_146_outcome_contract import direct

from config.urls import urlpatterns as normal_urls
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.architecture.models import ProcessAnalysis
from ki_radar.core.openrouter import request_openrouter
from ki_radar.solo import access
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
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


@pytest.mark.parametrize("solo_mode", [False, True])
def test_solo_uses_the_same_configured_model_transport(monkeypatch, solo_mode):
    payload = json.dumps(
        {
            "model": "configured/model",
            "choices": [
                {
                    "message": {"content": "transport response"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }
    ).encode()
    network = Mock(side_effect=lambda *args, **kwargs: io.BytesIO(payload))
    monkeypatch.setattr("ki_radar.core.openrouter.urllib.request.urlopen", network)
    with override_settings(
        SOLO_TEST_MODE=solo_mode,
        OPENROUTER_API_KEY="configured-test-key",
        OPENROUTER_MODEL="configured/model",
        OPENROUTER_API_URL="https://example.invalid/api",
    ):
        result = request_openrouter(
            messages=[{"role": "user", "content": "arbitrary synthetic context"}],
            max_tokens=100,
            timeout_seconds=5,
            response_format={"type": "json_schema", "json_schema": {"name": "ordinary-schema"}},
            provider={"require_parameters": True},
        )
    assert result.model == "configured/model" and result.content == "transport response"
    request = network.call_args.args[0]
    assert request.full_url == "https://example.invalid/api"
    body = json.loads(request.data)
    assert body["model"] == "configured/model"
    assert body["response_format"]["json_schema"]["name"] == "ordinary-schema"
    assert body["provider"]["require_parameters"]


@pytest.mark.parametrize("strategic", [False, True])
def test_own_scenario_enters_normal_discovery_without_solo_response(
    solo, client, monkeypatch, strategic
):
    actor = switch(client, "owner")
    analysis = Mock(return_value=None)
    monkeypatch.setattr("ki_radar.accelerator.architect_views._run_analysis", analysis)
    url = reverse("accelerator:autonomous_discovery_start")
    data = {
        "business_unit": actor.business_unit_id,
        "problem_statement": "Synthetische Laboraufträge bis zur freigegebenen Befundauskunft",
        "business_context": (
            "Eigener Testkontext; keine Baseline und keine reale Patienteninformation"
        ),
        "sources": SimpleUploadedFile("eigene-quelle.md", b"Synthetic laboratory process context"),
    }
    if strategic:
        data.update(
            strategic="1",
            scope_start="Auftragseingang",
            scope_end="Freigegebene Auskunft",
            reason="Begrenztes Lernziel",
            validation_step="Testquellen mit Verantwortlichen prüfen",
        )
    assert client.post(url, data).status_code == 302
    session = CaptureSession.objects.get()
    assert session.answers["problem_statement"] == data["problem_statement"]
    assert session.catalog_version == ("3.0" if strategic else "2.0")
    analysis.assert_called_once()
    assert not CaptureAnalysis.objects.exists()
    assert not ProcessAnalysis.objects.exists()
    page = client.get("/solo/")
    assert reverse("accelerator:autonomous_discovery_start") in page.content.decode()
    assert "Offline-Testentwürfe" not in page.content.decode()
    assert client.post("/solo/discovery/A/").status_code == 404


def test_old_fixed_outputs_remain_visible_but_are_not_current_quality_evidence(
    solo, client, tmp_path
):
    actor = switch(client, "owner")
    session, snapshot = _session_and_snapshot(owner=actor, tmp_path=tmp_path)
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    analysis.model_name = "solo/offline-fixture-v1"
    analysis.save(update_fields=["model_name"])
    original = copy.deepcopy((analysis.result_payload, analysis.verification_payload))
    url = reverse("accelerator:autonomous_discovery_review", args=[session.pk])
    response = client.get(url)
    assert response.status_code == 200
    assert "Historischer fester Solo-Testentwurf" in response.content.decode()
    assert not response.context["can_confirm"]
    assert client.post(
        url, {"action": "confirm", "selected_stage_key": "compare", "revision": session.revision}
    ).status_code in {200, 302}
    assert not ProcessAnalysis.objects.exists()
    analysis.refresh_from_db()
    assert (analysis.result_payload, analysis.verification_payload) == original
