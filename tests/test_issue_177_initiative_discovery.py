from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import close_old_connections, connection
from django.urls import reverse
from django.utils import timezone
from test_idea_autonomous_discovery import idea_draft, materialize

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_autonomous_capture_session
from ki_radar.architecture.discovery_materialization import DiscoveryMaterializationError
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.initiative_discovery import initiative_discovery_idea
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative

pytestmark = pytest.mark.django_db


def initiative(owner):
    return save_initiative(
        actor=owner,
        data={
            "title": "Mehr tragfähige Buchungen",
            "business_outcome": "Mehr tragfähige Buchungen.",
        },
    )


def test_minimal_creation_and_editable_prefill(client, owner):
    client.force_login(owner)
    response = client.post(
        reverse("use_cases:initiative_create"),
        {"title": "Wachstum", "business_outcome": "Mehr Buchungen"},
    )
    assert response.status_code == 302
    from ki_radar.use_cases.initiative_models import ImprovementInitiative

    item = ImprovementInitiative.objects.get()
    assert item.status == "draft" and not item.outcome_owner
    url = reverse("use_cases:initiative_discovery_start", args=[item.pk])
    first = client.post(url)
    assert client.post(url).url == first.url
    idea = item.ideas.get()
    assert idea.description == item.business_outcome
    assert "kein unabhängiger Nachweis" in idea.source_note
    start = client.get(first.url)
    assert start.context["form"]["problem_statement"].value() == "Mehr Buchungen"
    assert "Ursprüngliches Geschäftsziel" in start.context["form"]["business_context"].value()
    assert item.get_absolute_url() in start.content.decode()
    assert CaptureSession.objects.count() == 0


@pytest.mark.parametrize("role", ["owner", "coordinator", "other_owner", "reader"])
def test_rights_and_visible_actions(client, owner, coordinator, other_owner, reader, role):
    item = initiative(owner)
    actor = locals()[role]
    client.force_login(actor)
    url = reverse("use_cases:initiative_discovery_start", args=[item.pk])
    page = client.get(item.get_absolute_url())
    allowed = role in {"owner", "coordinator"}
    assert ("Untersuchung starten" in page.content.decode()) == allowed
    assert client.post(url).status_code == (302 if allowed else 403)
    if not allowed:
        with pytest.raises(PermissionDenied):
            initiative_discovery_idea(initiative=item, actor=actor)
        assert not item.ideas.exists()


def test_resume_ownership_expiry_and_existing_origin(client, owner, coordinator):
    item = initiative(owner)
    idea = initiative_discovery_idea(initiative=item, actor=owner)
    session = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    client.force_login(owner)
    assert "Untersuchung fortsetzen" in client.get(item.get_absolute_url()).content.decode()
    client.force_login(coordinator)
    page = client.get(item.get_absolute_url()).content.decode()
    assert "Untersuchung in Bearbeitung" in page
    assert "Untersuchung fortsetzen" not in page
    assert initiative_discovery_idea(initiative=item, actor=coordinator).pk == idea.pk
    session.expires_at = timezone.now() - timedelta(days=1)
    session.save(update_fields=["expires_at"])
    page = client.get(item.get_absolute_url()).content.decode()
    assert "Untersuchung starten" in page
    assert item.ideas.count() == 1


def test_ambiguous_origins_and_conflicting_binding(owner):
    item = initiative(owner)
    idea = initiative_discovery_idea(initiative=item, actor=owner)
    other = initiative(owner)
    with pytest.raises(ValidationError, match="anderen Vorhaben"):
        bind_initiative(initiative=other, artifact=idea, actor=owner)
    another = IdeaCandidate.objects.create(
        title="Andere Herkunft", description="Ziel", submitted_by=owner
    )
    bind_initiative(initiative=item, artifact=another, actor=owner)
    with pytest.raises(ValidationError, match="Mehrere Ideen"):
        initiative_discovery_idea(initiative=item, actor=owner)
    assert item.ideas.count() == 2


def test_materialization_continuity_and_idempotency(client, owner, tmp_path):
    item = initiative(owner)
    idea = initiative_discovery_idea(initiative=item, actor=owner)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    first = materialize(owner, session, analysis)
    second = materialize(owner, session, analysis)
    process = ProcessAnalysis.objects.get(pk=first.process_analysis_id)
    assert second.reused and second.process_analysis_id == process.pk
    assert process.initiative_id == item.pk
    assert ProcessAnalysis.objects.count() == ValueStream.objects.count() == 1
    client.force_login(owner)
    assert "Prozessanalyse öffnen" in client.get(item.get_absolute_url()).content.decode()
    for url in [
        process.get_absolute_url(),
        idea.get_absolute_url(),
        reverse("accelerator:autonomous_discovery_review", args=[session.pk]),
    ]:
        assert item.get_absolute_url() in client.get(url).content.decode()


def test_materialization_cannot_bind_foreign_initiative(owner, other_owner, tmp_path):
    item = initiative(other_owner)
    idea = initiative_discovery_idea(initiative=item, actor=other_owner)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    with pytest.raises(DiscoveryMaterializationError) as error:
        materialize(owner, session, analysis)
    assert error.value.code == "initiative_binding_conflict"
    assert not ProcessAnalysis.objects.exists() and not ValueStream.objects.exists()
    idea.refresh_from_db()
    assert not idea.discovery_process_analysis_id


def test_completed_legacy_discovery_is_not_retroactively_bound(owner, tmp_path):
    idea = IdeaCandidate.objects.create(
        title="Historisch", description="Altbestand", submitted_by=owner
    )
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    first = materialize(owner, session, analysis)
    item = initiative(owner)
    bind_initiative(initiative=item, artifact=idea, actor=owner)
    again = materialize(owner, session, analysis)
    assert again.reused and again.process_analysis_id == first.process_analysis_id
    assert ProcessAnalysis.objects.get(pk=again.process_analysis_id).initiative_id is None


def test_malformed_legacy_origin_stays_readable_but_cannot_materialize(client, owner, tmp_path):
    idea = IdeaCandidate.objects.create(
        title="Altbestand", description="Historisch", submitted_by=owner
    )
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    session.answers["origin"] = []
    session.save(update_fields=["answers"])
    client.force_login(owner)
    response = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert response.status_code == 200
    assert response.context["origin_idea"] is None
    with pytest.raises(DiscoveryMaterializationError) as error:
        materialize(owner, session, analysis)
    assert error.value.code == "idea_origin_conflict"
    assert not ProcessAnalysis.objects.exists()


def test_completed_discovery_rejects_conflicting_process_assignment(owner, tmp_path):
    item = initiative(owner)
    idea = initiative_discovery_idea(initiative=item, actor=owner)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    result = materialize(owner, session, analysis)
    other = initiative(owner)
    # Simulate an inconsistent historical import; normal binding already rejects it.
    ProcessAnalysis.objects.filter(pk=result.process_analysis_id).update(initiative=other)
    with pytest.raises(DiscoveryMaterializationError) as error:
        materialize(owner, session, analysis)
    assert error.value.code == "initiative_binding_conflict"


@pytest.mark.django_db(transaction=True)
def test_concurrent_intake_reuses_one_idea(owner):
    if connection.vendor != "postgresql":
        pytest.skip("Row locks require PostgreSQL")
    item = initiative(owner)

    def start(_):
        close_old_connections()
        try:
            return initiative_discovery_idea(initiative=item, actor=owner).pk
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(start, range(2)))
    assert ids[0] == ids[1]
    assert item.ideas.count() == 1


@pytest.mark.django_db(transaction=True)
def test_concurrent_materialization_reuses_one_process(owner, tmp_path):
    if connection.vendor != "postgresql":
        pytest.skip("Row locks require PostgreSQL")
    item = initiative(owner)
    idea = initiative_discovery_idea(initiative=item, actor=owner)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)

    def confirm(_):
        close_old_connections()
        try:
            return materialize(owner, session, analysis).process_analysis_id
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(confirm, range(2)))
    assert ids[0] == ids[1]
    assert item.process_analyses.count() == 1
