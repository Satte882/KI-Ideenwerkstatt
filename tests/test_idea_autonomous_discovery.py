from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone
from test_issue_98_autonomous_business_discovery import _approved_analysis, _session_and_snapshot
from test_issue_422_idea_inbox import set_intake_session

from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_autonomous_capture_session
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream
from ki_radar.use_cases.idea_discovery import build_idea_origin, idea_origin_id
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


@pytest.fixture
def idea(owner):
    return IdeaCandidate.objects.create(
        title="Angebote vergleichen",
        description="Der manuelle Angebotsvergleich dauert zu lange.",
        source_note="Workshop Einkauf",
        business_unit=owner.business_unit,
        submitted_by=owner,
        impact=5,
        confidence=2,
        ease=4,
    )


def idea_draft(*, idea, owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    session.answers["origin"] = build_idea_origin(idea)
    session.save(update_fields=["answers"])
    return session, _approved_analysis(session=session, snapshot=snapshot)


def materialize(owner, session, analysis):
    return materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )


def test_origin_parser_is_explicit_and_rejects_invalid_idea_ids(idea):
    assert idea_origin_id({}) is None
    assert idea_origin_id({"origin": {"type": "other"}}) is None
    assert idea_origin_id({"origin": build_idea_origin(idea)}) == idea.pk
    for origin in [
        [],
        {"type": "idea_candidate"},
        {"type": "idea_candidate", "idea_candidate_id": "x"},
    ]:
        with pytest.raises(ValidationError):
            idea_origin_id({"origin": origin})


def test_discovery_binds_origin_once_without_promoting(idea, owner, tmp_path):
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    first = materialize(owner, session, analysis)
    second = materialize(owner, session, analysis)
    idea.refresh_from_db()
    assert second.reused
    assert first.process_analysis_id == second.process_analysis_id
    assert idea.discovery_process_analysis_id == first.process_analysis_id
    assert idea.discovery_process_analysis.stage.value_stream_id == first.value_stream_id
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.promoted_use_case_id is None
    assert ProcessAnalysis.objects.count() == ValueStream.objects.count() == 1
    with transaction.atomic(), pytest.raises(IntegrityError):
        IdeaCandidate.objects.filter(pk=idea.pk).update(state=IdeaCandidate.State.PROMOTED)


def test_second_session_of_same_idea_cannot_materialize(idea, owner, tmp_path):
    first, first_analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    second, second_analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    materialize(owner, first, first_analysis)
    with pytest.raises(DiscoveryMaterializationError, match="Abschluss oder eine Analyse"):
        materialize(owner, second, second_analysis)
    assert ProcessAnalysis.objects.count() == ValueStream.objects.count() == 1


def test_discovery_wins_against_prepared_intake(client, idea, owner, tmp_path):
    client.force_login(owner)
    set_intake_session(client, owner.business_unit, owner, idea=idea)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    result = materialize(owner, session, analysis)
    response = client.post(reverse("use_cases:intake_step", args=[6]))
    assert response.status_code == 200
    assert "bereits in eine Prozessanalyse" in response.content.decode()
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.discovery_process_analysis_id == result.process_analysis_id
    assert not UseCase.objects.exists()


def test_intake_wins_against_prepared_discovery(client, idea, owner, tmp_path):
    client.force_login(owner)
    set_intake_session(client, owner.business_unit, owner, idea=idea)
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    response = client.post(reverse("use_cases:intake_step", args=[6]))
    assert response.status_code == 302
    with pytest.raises(DiscoveryMaterializationError, match="Abschluss oder eine Analyse"):
        materialize(owner, session, analysis)
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.PROMOTED
    assert idea.promoted_use_case_id == UseCase.objects.get().pk
    assert idea.discovery_process_analysis_id is None
    assert not ProcessAnalysis.objects.exists()
    assert not ValueStream.objects.exists()


@pytest.mark.parametrize("status", ["draft", "discarded", "expired", "overdue"])
def test_active_discovery_blocks_new_intake_only_until_discard_or_expiry(
    client, idea, owner, status
):
    session = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    if status == "overdue":
        session.expires_at = timezone.now() - timedelta(seconds=1)
    else:
        session.status = status
    session.save()
    client.force_login(owner)
    response = client.post(reverse("use_cases:idea_promote", args=[idea.pk]))
    assert response.status_code == 302
    assert bool(client.session.get("use_case_intake")) == (status != "draft")
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN


@pytest.mark.parametrize("unit", ["empty", "same", "different"])
def test_discovery_start_checks_business_unit_server_side(idea, owner, unit):
    if unit == "empty":
        idea.business_unit = None
    elif unit == "different":
        idea.business_unit = BusinessUnit.objects.create(name="Andere Organisation")
    idea.save()
    if unit == "different":
        with pytest.raises(ValidationError, match="Organisationseinheit"):
            create_autonomous_capture_session(
                actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
            )
        assert not CaptureSession.objects.exists()
    else:
        session = create_autonomous_capture_session(
            actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
        )
        assert idea_origin_id(session.answers) == idea.pk
        assert session.owner.business_unit_id == owner.business_unit_id
    idea.refresh_from_db()
    assert (idea.business_unit_id is None) == (unit == "empty")


def test_repeated_service_start_reuses_active_session(idea, owner):
    first = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    second = create_autonomous_capture_session(
        actor=owner, problem_statement="Andere Eingabe", idea_candidate_id=idea.pk
    )
    assert first.pk == second.pk
    assert CaptureSession.objects.count() == 1
    assert second.answers["problem_statement"] == idea.description
