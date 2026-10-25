from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from test_idea_autonomous_discovery import materialize
from test_issue_98_autonomous_business_discovery import _approved_analysis

from ki_radar.accelerator import architect_service
from ki_radar.accelerator.investigation_ingestion import (
    create_managed_discovery_source_folder,
    idea_origin_upload,
)
from ki_radar.accelerator.investigation_models import InvestigationSourceSnapshot
from ki_radar.accelerator.investigation_tools import (
    DiscoverySnapshotRequest,
    create_discovery_source_snapshot,
)
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_autonomous_capture_session
from ki_radar.architecture.discovery_materialization import DiscoveryMaterializationError
from ki_radar.architecture.models import ProcessDiscoveryPathDecision
from ki_radar.use_cases import topics
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.initiative_discovery import initiative_discovery_idea
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.topic_contract import SCHEMA, validate_intake_context
from ki_radar.use_cases.topics import save_topic, topic_token

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("role", ["owner", "reader", "coordinator"])
def test_inbox_entry_hierarchy_and_old_direct_save(client, request, role):
    actor = request.getfixturevalue(role)
    client.force_login(actor)

    class Links(HTMLParser):
        def __init__(self):
            super().__init__()
            self.links = []
            self.current = None

        def handle_starttag(self, tag, attrs):
            if tag == "a":
                self.current = {**dict(attrs), "text": ""}

        def handle_data(self, data):
            if self.current is not None:
                self.current["text"] += data

        def handle_endtag(self, tag):
            if tag == "a" and self.current is not None:
                self.links.append(self.current)
                self.current = None

    page = client.get(reverse("use_cases:idea_list"))
    assert page.status_code == 200 and page.context["can_create_idea"]
    links = Links()
    links.feed(page.content.decode())
    primary = next(x for x in links.links if x["text"].strip() == "Neues Thema starten")
    direct = next(x for x in links.links if x["text"].strip() == "Idee direkt erfassen")
    assert primary["href"] == reverse("use_cases:topic_start")
    assert "btn-primary" in primary["class"].split()
    assert direct["href"] == reverse("use_cases:idea_create")
    assert "btn-primary" not in direct.get("class", "").split()
    assert len(client.get(primary["href"]).context["occasions"]) == 3
    old_form = client.get(direct["href"])
    assert old_form.status_code == 200
    assert set(old_form.context["form"].fields) == {
        "title",
        "description",
        "business_unit",
        "source_note",
    }
    assert not IdeaCandidate.objects.exists()
    saved = client.post(
        direct["href"], {"title": "Direkt erfasst", "description": "Originale Beschreibung"}
    )
    assert saved.status_code == 302
    idea = IdeaCandidate.objects.get()
    assert saved.url == idea.get_absolute_url()
    assert idea.submitted_by == actor and idea.intake_context == {}
    assert not CaptureSession.objects.exists() and not ImprovementInitiative.objects.exists()


def test_inbox_creation_actions_remain_hidden_without_existing_permission(reader):
    from django.test import RequestFactory
    from django.urls import resolve

    from ki_radar.use_cases.idea_views import idea_list

    reader.is_active = False
    request = RequestFactory().get(reverse("use_cases:idea_list"))
    request.user = reader
    request.resolver_match = resolve(request.path)
    page = idea_list(request)
    html = page.content.decode()
    assert "Neues Thema starten" not in html and "Idee direkt erfassen" not in html


def create(owner, occasion="problem", **kwargs):
    return save_topic(
        actor=owner,
        token=topic_token(actor=owner, occasion=occasion),
        occasion=occasion,
        text="  Kunden warten auf Antworten.\n",
        **kwargs,
    )


@pytest.fixture(autouse=True)
def no_real_model_calls(monkeypatch):
    def forbidden(**kwargs):
        raise AssertionError("No real model calls authorized for issue 179")

    monkeypatch.setattr(architect_service, "request_openrouter", forbidden)


@pytest.mark.parametrize(
    "occasion,perspectives",
    [
        ("problem", ["staff", "customers"]),
        ("goal", ["leadership"]),
        ("explore", ["partners"]),
    ],
)
def test_three_occasions_save_once_without_analysis(client, owner, occasion, perspectives):
    client.force_login(owner)
    page = client.get(reverse("use_cases:topic_capture", args=[occasion]), follow=True)
    data = {
        "token": page.context["form"]["token"].value(),
        "text": "  Originalsatz mit unbekannter Ursache.\n",
        "perspectives": perspectives,
    }
    response = client.post(page.request["PATH_INFO"], data)
    assert response.status_code == 302
    idea = IdeaCandidate.objects.get()
    assert idea.description == data["text"] == idea.intake_context["original_text"]
    assert idea.title == "Originalsatz mit unbekannter Ursache."
    assert idea.intake_context == {
        "schema_version": SCHEMA,
        "occasion": occasion,
        "perspectives": perspectives,
        "original_text": data["text"],
    }
    assert not CaptureSession.objects.exists() and not ProcessDiscoveryPathDecision.objects.exists()
    assert client.post(page.request["PATH_INFO"], data).url == response.url
    back = client.get(page.redirect_chain[-1][0])
    assert back.status_code == 302 and back.url == response.url
    assert client.post(page.request["PATH_INFO"], data).url == response.url
    assert IdeaCandidate.objects.count() == 1
    assert ImprovementInitiative.objects.count() == int(occasion == "goal")
    if occasion == "goal":
        assert idea.initiative.business_outcome == data["text"]
        assert initiative_discovery_idea(initiative=idea.initiative, actor=owner).pk == idea.pk
    detail = client.get(response.url)
    assert "Untersuchung starten" in detail.content.decode()
    assert "Später fortsetzen" in detail.content.decode()


def test_primary_entry_and_existing_secondary_paths(client, owner):
    client.force_login(owner)
    html = client.get(reverse("reporting:dashboard")).content.decode()
    assert f'class="btn btn-primary" href="{reverse("use_cases:topic_start")}"' in html
    for name in ["idea_create", "initiative_create", "create"]:
        assert reverse(f"use_cases:{name}") in html
    page = client.get(reverse("use_cases:topic_start"))
    assert len(page.context["occasions"]) == 3
    assert page.context["nav_is_topic"] and not page.context["nav_is_analysis"]
    assert "Ich habe bereits eine KI-Idee" in page.content.decode()
    assert client.get(reverse("demo-portal")).status_code == 200


def test_reader_can_save_problem_but_cannot_create_goal_or_start_discovery(client, reader):
    client.force_login(reader)
    idea = create(reader)
    assert "Untersuchung starten</a>" not in client.get(idea.get_absolute_url()).content.decode()
    url = reverse("use_cases:topic_capture", args=["goal"])
    page = client.get(url, follow=True)
    assert not page.context["can_submit"]
    assert 'id="id_text"' not in page.content.decode()
    response = client.post(url, {"token": page.context["form"]["token"].value(), "text": "Ziel"})
    assert response.status_code == 200 and response.context["form"].non_field_errors()
    assert IdeaCandidate.objects.count() == 1 and not ImprovementInitiative.objects.exists()
    with pytest.raises(PermissionDenied):
        create(reader, "goal")


def test_coordinator_uses_existing_goal_rights(coordinator):
    assert create(coordinator, "goal").initiative_id


def test_revoked_goal_permission_preserves_input_without_saving(client, owner):
    client.force_login(owner)
    url = reverse("use_cases:topic_capture", args=["goal"])
    page = client.get(url, follow=True)
    token = page.context["form"]["token"].value()
    owner.groups.clear()
    response = client.post(url, {"token": token, "text": "Noch nicht gespeichertes Ziel"})
    assert response.status_code == 200
    assert response.context["form"]["text"].value() == "Noch nicht gespeichertes Ziel"
    assert "Entwurf speichern und fortfahren" not in response.content.decode()
    assert not IdeaCandidate.objects.exists() and not ImprovementInitiative.objects.exists()


def test_token_tampering_foreign_user_and_conflicting_repost(owner, other_owner):
    token = topic_token(actor=owner, occasion="problem")
    with pytest.raises(ValidationError):
        save_topic(actor=owner, token=token + "bad", occasion="problem", text="Input")
    with pytest.raises(PermissionDenied):
        save_topic(actor=other_owner, token=token, occasion="problem", text="Input")
    with pytest.raises(ValidationError):
        save_topic(actor=owner, token=token, occasion="goal", text="Input")
    idea = save_topic(actor=owner, token=token, occasion="problem", text="Input")
    with pytest.raises(ValidationError, match="bereits"):
        save_topic(actor=owner, token=token, occasion="problem", text="Changed")
    assert IdeaCandidate.objects.get().pk == idea.pk


def test_failure_to_bind_rolls_back_both_objects(owner, monkeypatch):
    monkeypatch.setattr(
        topics,
        "bind_initiative",
        lambda **kwargs: (_ for _ in ()).throw(ValidationError("Bind failed")),
    )
    with pytest.raises(ValidationError, match="Bind failed"):
        create(owner, "goal")
    assert not IdeaCandidate.objects.exists() and not ImprovementInitiative.objects.exists()


@pytest.mark.parametrize(
    "changes",
    [
        {"occasion": "ai_classification"},
        {"perspectives": ["customers", "customers"]},
        {"perspectives": ["unverified_cause"]},
        {"original_text": "  "},
        {"schema_version": "other"},
        {"origin_basis": "customers"},
    ],
)
def test_bounded_context_rejects_invalid_or_extra_fields(changes):
    with pytest.raises(ValidationError):
        validate_intake_context(
            {
                "schema_version": SCHEMA,
                "occasion": "problem",
                "perspectives": [],
                "original_text": "Input",
                **changes,
            }
        )


def test_original_context_immutable_while_description_remains_editable(owner):
    idea = create(owner)
    original = dict(idea.intake_context)
    idea.description = "Fachliche Korrektur"
    idea.save()
    idea.refresh_from_db()
    assert idea.intake_context == original
    idea.intake_context = {**original, "original_text": "Ersetzt"}
    with pytest.raises(ValidationError):
        idea.save()
    with pytest.raises(ValidationError):
        IdeaCandidate.objects.filter(pk=idea.pk).update(intake_context={})
    with pytest.raises(ValidationError):
        IdeaCandidate.objects.bulk_update([idea], ["intake_context"])
    legacy = IdeaCandidate.objects.create(title="Historisch", description="Alt")
    assert legacy.intake_context == {}


def test_restart_logout_and_next_day_resume_without_duplication(client, owner):
    idea = create(owner, "goal", perspectives=["customers", "partners"])
    token = topic_token(actor=owner, occasion="explore")
    client.force_login(owner)
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement=idea.description,
        idea_candidate_id=idea.pk,
        business_unit_id=owner.business_unit_id,
    )
    client.logout()
    with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(days=1)):
        client.force_login(owner)
        page = client.get(idea.get_absolute_url())
        assert "Untersuchung fortsetzen" in page.content.decode()
        page = client.get(idea.initiative.get_absolute_url())
        assert str(session.pk) in page.content.decode()
        assert save_topic(actor=owner, token=token, occasion="explore", text="Partner erkunden")
    assert CaptureSession.objects.count() == 1 and ImprovementInitiative.objects.count() == 1


@override_settings(
    ACCELERATOR_DISCOVERY_MODEL="test/strategic",
    OPENROUTER_MODEL="test/fallback",
    OPENROUTER_API_URL="https://openrouter.ai/api/v1/chat/completions",
)
def test_discovery_entry_shows_actual_model_and_cost_without_auto_route(client, owner):
    idea = create(owner, "goal")
    client.force_login(owner)
    page = client.get(
        reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": idea.pk}
    )
    assert not page.context["strategic_start"]
    html = page.content.decode()
    assert "test/strategic" in html and "OpenRouter" in html and "Kosten" in html
    assert "test/fallback" not in html
    assert not CaptureSession.objects.exists()


def test_goal_uses_current_initiative_outcome_without_rewriting_original_input(client, owner):
    from ki_radar.use_cases.initiatives import save_initiative

    idea = create(owner, "goal")
    original = idea.intake_context["original_text"]
    save_initiative(
        actor=owner,
        initiative=idea.initiative,
        data={"business_outcome": "Aktualisiertes Geschäftsergebnis"},
    )
    client.force_login(owner)
    page = client.get(
        reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": idea.pk}
    )
    assert page.context["form"]["problem_statement"].value() == "Aktualisiertes Geschäftsergebnis"
    idea.refresh_from_db()
    assert idea.intake_context["original_text"] == original


@pytest.mark.parametrize("occasion", ["problem", "goal", "explore"])
def test_source_handover_materialization_and_reentry_keep_context(
    owner, tmp_path, client, occasion
):
    idea = create(owner, occasion, perspectives=["customers", "partners"])
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement=idea.description,
        idea_candidate_id=idea.pk,
        business_unit_id=owner.business_unit_id,
    )
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path):
        folder = create_managed_discovery_source_folder(
            actor=owner,
            capture_session_id=session.pk,
            name="Synthetische Themenquelle",
            uploads=[idea_origin_upload(session)],
        )
        captured = create_discovery_source_snapshot(
            actor=owner,
            request=DiscoverySnapshotRequest(
                capture_session_id=session.pk,
                folder_id=folder.pk,
            ),
        )
    snapshot = InvestigationSourceSnapshot.objects.get(pk=captured.snapshot_id)
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    assert session.answers["origin"]["intake_context"] == idea.intake_context
    source = session.discovery_source_snapshots.get().sources.get()
    assert "keine Quelle, Ursache oder Pfadentscheidung" in source.content
    assert idea.intake_context["original_text"].strip() in source.content
    assert session.catalog_version == "2.0"
    first = materialize(owner, session, analysis)
    assert materialize(owner, session, analysis).process_analysis_id == first.process_analysis_id
    idea.refresh_from_db()
    assert idea.discovery_process_analysis_id == first.process_analysis_id
    assert idea.discovery_process_analysis.initiative_id == idea.initiative_id
    assert not ProcessDiscoveryPathDecision.objects.exists()
    client.force_login(owner)
    assert "Prozessanalyse öffnen" in client.get(idea.get_absolute_url()).content.decode()


@pytest.mark.django_db(transaction=True)
def test_concurrent_same_submission_creates_one_idea_and_bound_goal(owner):
    if connection.vendor != "postgresql":
        pytest.skip("Concurrency requires PostgreSQL")
    token = topic_token(actor=owner, occasion="goal")

    def submit(_):
        close_old_connections()
        try:
            return save_topic(actor=owner, token=token, occasion="goal", text="Ziel").pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(submit, range(2)))
    assert ids[0] == ids[1]
    assert IdeaCandidate.objects.count() == ImprovementInitiative.objects.count() == 1


def test_invalid_post_preserves_text_and_has_no_side_effects(client, owner):
    client.force_login(owner)
    url = reverse("use_cases:topic_capture", args=["explore"])
    page = client.get(url, follow=True)
    response = client.post(
        url,
        {
            "token": page.context["form"]["token"].value(),
            "text": "Original",
            "perspectives": ["cause"],
        },
    )
    assert response.status_code == 200 and response.context["form"]["text"].value() == "Original"
    assert not IdeaCandidate.objects.exists()
    assert client.get(reverse("use_cases:topic_capture", args=["invalid"])).status_code == 404


def test_anonymous_entry_requires_login_and_invalid_hidden_token_is_visible(client, owner):
    url = reverse("use_cases:topic_capture", args=["problem"])
    assert client.get(url).status_code == 302
    client.force_login(owner)
    response = client.post(url, {"text": "Original"})
    assert response.status_code == 200
    assert response.context["form"]["token"].errors
    assert b'role="alert"' in response.content
    assert not IdeaCandidate.objects.exists()


def test_unscoped_exploration_keeps_waiting_human_in_existing_discovery(
    client,
    owner,
    tmp_path,
    monkeypatch,
):
    from test_issue_98_autonomous_business_discovery import _draft, _result, _verifier

    idea = save_topic(
        actor=owner,
        token=topic_token(actor=owner, occasion="explore"),
        occasion="explore",
        text="Ich suche Potenziale, der Bereich ist noch offen.",
    )
    draft = _draft()
    draft["schema_version"] = "ap1-discovery-v2"
    for item in [
        draft["value_stream"],
        draft["focus"],
        draft["process_analysis"],
        *draft["stages"],
        *draft["facts"],
        *draft["hypotheses"],
    ]:
        item["evidence_refs"] = ["U0"]
    question = "Welchen vorläufigen Bereich möchten Sie untersuchen?"

    def provider(**kwargs):
        return _result(
            _verifier("waiting_human", human_question=question)
            if "verifier" in kwargs["schema_name"]
            else draft
        )

    monkeypatch.setattr(architect_service, "_provider_call", provider)
    client.force_login(owner)
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path):
        response = client.post(
            reverse("accelerator:autonomous_discovery_start"),
            {
                "idea_candidate": idea.pk,
                "problem_statement": idea.description,
                "business_unit": owner.business_unit_id,
            },
        )
    assert response.status_code == 302
    session = CaptureSession.objects.get()
    analysis = session.analyses.get()
    assert analysis.status == "waiting_human"
    review = client.get(response.url)
    assert not review.context["can_confirm"] and question in review.content.decode()
    with pytest.raises(DiscoveryMaterializationError):
        materialize(owner, session, analysis)
    idea.refresh_from_db()
    assert idea.discovery_process_analysis_id is None
