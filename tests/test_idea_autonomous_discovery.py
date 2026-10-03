import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from test_issue_98_autonomous_business_discovery import (
    _approved_analysis,
    _draft,
    _result,
    _session_and_snapshot,
    _source_uploads,
    _verifier,
)
from test_issue_422_idea_inbox import set_intake_session

from ki_radar.accelerator import architect_service, architect_views
from ki_radar.accelerator.investigation_models import InvestigationSourceSnapshot
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.retention import (
    expire_due_capture_sessions,
    purge_terminal_capture_sessions,
)
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


def test_invalid_correction_stays_visible_and_preserves_input(client, idea, owner, tmp_path):
    session, _analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    revision = session.revision
    client.force_login(owner)
    correction = "x" * 4001
    response = client.post(
        reverse("accelerator:autonomous_discovery_review", args=[session.pk]),
        {"action": "correct", "revision": session.revision, "correction": correction},
    )
    assert response.status_code == 200
    form = response.context["correction_form"]
    assert form.is_bound
    assert "correction" in form.errors
    assert form["correction"].value() == correction
    assert 'role="alert"' in response.content.decode()
    session.refresh_from_db()
    assert session.revision == revision


def test_discovery_and_process_sidebar_keep_current_location(client, idea, owner, tmp_path):
    client.force_login(owner)
    start = client.get(
        reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": idea.pk}
    )
    assert start.context["nav_is_analysis"]
    assert start.context["nav_is_discovery"]
    assert 'aria-current="page"' in start.content.decode()
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    review = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert review.context["nav_is_discovery"]
    result = materialize(owner, session, analysis)
    process = client.get(
        reverse("architecture:process_analysis_detail", args=[result.process_analysis_id])
    )
    assert process.context["nav_is_analysis"]
    assert process.context["latest_investigation_activity"]["execution_state"] == "pending"
    content = process.content.decode()
    assert "Untersuchungsstart angefordert" in content
    assert "Die Untersuchung läuft im Hintergrund" not in content
    assert "Zur Ursprungsidee" in content
    activity = client.get(
        reverse("accelerator:investigation_activity", args=[result.investigation_run_id])
    )
    assert 'sidebar-local-active" aria-current="page"' in activity.content.decode()


def test_completed_intake_can_return_directly_to_review_after_edit(client, idea, owner):
    from ki_radar.use_cases.intake_views import SESSION_KEY, _wizard_step_states

    client.force_login(owner)
    set_intake_session(client, owner.business_unit, owner, idea=idea)
    stored = client.session[SESSION_KEY]
    for current_step in range(1, 6):
        states = _wizard_step_states(stored=stored, current_step=current_step)
        assert all(state["is_reachable"] for state in states)


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
def test_discovery_start_defaults_to_idea_unit_without_account_restriction(idea, owner, unit):
    if unit == "empty":
        idea.business_unit = None
    elif unit == "different":
        idea.business_unit = BusinessUnit.objects.create(name="Andere Organisation")
    idea.save()
    session = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    assert idea_origin_id(session.answers) == idea.pk
    assert session.answers["business_unit"]["id"] == (
        idea.business_unit_id or owner.business_unit_id
    )
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


def start_from_idea(client, idea, owner, tmp_path, monkeypatch, *, uploads=()):
    monkeypatch.setattr(architect_views, "_run_analysis", lambda *args, **kwargs: None)
    client.force_login(owner)
    data = {
        "idea_candidate": str(idea.pk),
        "business_unit": owner.business_unit_id,
        "problem_statement": "Bestätigte Korrektur: Angebote werden manuell verglichen.",
        "business_context": "Einkauf und Fachbereich bereiten die Entscheidung vor.",
    }
    if uploads:
        data["sources"] = list(uploads)
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        response = client.post(reverse("accelerator:autonomous_discovery_start"), data)
    assert response.status_code == 302
    session = CaptureSession.objects.get()
    return session, session.discovery_source_snapshots.get()


def test_idea_cta_and_prefill_are_permission_guarded_and_read_only(
    client, idea, owner, reader, tmp_path
):
    client.force_login(owner)
    detail = client.get(idea.get_absolute_url())
    assert "Geschäftsproblem untersuchen" in detail.content.decode()
    assert "Direkt als Use Case übernehmen" in detail.content.decode()
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        response = client.get(
            reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": str(idea.pk)}
        )
    assert response.status_code == 200
    assert response.context["form"].initial == {
        "problem_statement": idea.description,
        "business_unit": idea.business_unit_id,
    }
    assert set(response.context["form"].fields) == {
        "problem_statement",
        "business_context",
        "business_unit",
    }
    assert idea.title in response.content.decode()
    assert idea.source_note in response.content.decode()
    assert not CaptureSession.objects.exists()
    assert not CaptureAnalysis.objects.exists()
    assert not ProcessAnalysis.objects.exists()
    assert not (tmp_path / "managed").exists()
    client.force_login(reader)
    assert (
        "Geschäftsproblem untersuchen" not in client.get(idea.get_absolute_url()).content.decode()
    )
    for method in [client.get, client.post]:
        response = method(
            reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": str(idea.pk)}
        )
        assert response.status_code == 403


@pytest.mark.parametrize("extra_source", [False, True])
def test_idea_source_is_frozen_but_only_real_uploads_are_independent_evidence(
    client, idea, owner, tmp_path, monkeypatch, extra_source
):
    uploads = (
        [SimpleUploadedFile("interview.md", b"Zusatzquelle aus dem Interview.")]
        if extra_source
        else []
    )
    session, snapshot = start_from_idea(client, idea, owner, tmp_path, monkeypatch, uploads=uploads)
    origin = session.answers["origin"]
    source = snapshot.sources.get(filename=origin["origin_source_filename"])
    assert source.content_sha256 == origin["origin_source_sha256"]
    assert len(snapshot.manifest_hash) == 64
    assert "nicht unabhängig bestätigt" in source.content
    assert session.answers["problem_statement"] in source.content
    assert session.answers["business_context"] in source.content
    assert idea.title in source.content
    assert idea.source_note in source.content
    assert idea.description not in source.content
    assert snapshot.sources.count() == (2 if extra_source else 1)
    assert set(origin) == {
        "type",
        "idea_candidate_id",
        "title",
        "source_note",
        "captured_at",
        "idea_updated_at",
        "origin_source_filename",
        "origin_source_sha256",
    }
    assert not any(key in session.answers for key in ["impact", "confidence", "ease", "focus"])
    document, refs, evidence = architect_service._source_document(
        session=session, snapshot=snapshot
    )
    assert document["input_ref"] == "U0"
    assert document["problem_statement"] == session.answers["problem_statement"]
    assert origin["origin_source_filename"] not in str(document)
    assert evidence.count(session.answers["problem_statement"]) == 1
    assert refs == ({"U0", "S1"} if extra_source else {"U0"})
    if extra_source:
        assert document["sources"][0]["filename"] == "interview.md"
        assert document["sources"][0]["ref"] == "S1"
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN


def test_repeat_start_and_detail_resume_existing_or_materialized_discovery(
    client, idea, owner, tmp_path, monkeypatch
):
    session, snapshot = start_from_idea(client, idea, owner, tmp_path, monkeypatch)
    review_url = reverse("accelerator:autonomous_discovery_review", args=[session.pk])
    start_url = reverse("accelerator:autonomous_discovery_start")
    for method in [client.get, client.post]:
        response = method(start_url, {"idea_candidate": str(idea.pk)})
        assert response.url == review_url
    assert CaptureSession.objects.count() == 1
    assert InvestigationSourceSnapshot.objects.count() == 1
    assert "Discovery fortsetzen" in client.get(idea.get_absolute_url()).content.decode()
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    result = materialize(owner, session, analysis)
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert "Analyse fortsetzen" in client.get(idea.get_absolute_url()).content.decode()
    for method in [client.get, client.post]:
        response = method(start_url, {"idea_candidate": str(idea.pk)})
        assert response.url == process.get_absolute_url()
    investigation_snapshot = InvestigationSourceSnapshot.objects.get(
        pk=result.investigation_snapshot_id
    )
    assert list(snapshot.sources.values_list("filename", "content_sha256", "content")) == list(
        investigation_snapshot.sources.values_list("filename", "content_sha256", "content")
    )


def test_long_idea_description_is_not_truncated_and_requires_confirmation(client, idea, owner):
    idea.description = "x" * 4001
    idea.save()
    client.force_login(owner)
    url = reverse("accelerator:autonomous_discovery_start")
    response = client.get(url, {"idea_candidate": str(idea.pk)})
    assert response.context["form"].initial["problem_statement"] == idea.description
    response = client.post(
        url,
        {
            "idea_candidate": str(idea.pk),
            "problem_statement": idea.description,
        },
    )
    assert response.status_code == 200
    assert response.context["form"].errors["problem_statement"]
    assert not CaptureSession.objects.exists()


@pytest.mark.parametrize("uploads", [False, True])
def test_complete_idea_discovery_uses_existing_review_and_investigation(
    client, idea, owner, tmp_path, monkeypatch, uploads
):
    draft = _draft()
    if not uploads:
        for item in [
            draft["value_stream"],
            draft["focus"],
            draft["process_analysis"],
            *draft["stages"],
            *draft["facts"],
            *draft["hypotheses"],
        ]:
            item["evidence_refs"] = ["U0"]
    provider_results = iter([_result(draft), _result(_verifier())])
    observed = []

    def provider(**kwargs):
        observed.append(json.loads(kwargs["messages"][1]["content"]))
        return next(provider_results)

    monkeypatch.setattr(architect_service, "_provider_call", provider)
    client.force_login(owner)
    data = {
        "idea_candidate": str(idea.pk),
        "business_unit": owner.business_unit_id,
        "problem_statement": (
            "Ein freigegebener Beschaffungsbedarf startet die Lieferantenauswahl. "
            "Angebote werden per E-Mail eingeholt und manuell verglichen. "
            "Einkauf und Fachbereich bereiten die Entscheidung vor."
        ),
        "business_context": "Der manuelle Angebotsvergleich dauert zu lange.",
    }
    if uploads:
        data["sources"] = _source_uploads()
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        response = client.post(reverse("accelerator:autonomous_discovery_start"), data)
    session = CaptureSession.objects.get()
    assert response.url == reverse("accelerator:autonomous_discovery_review", args=[session.pk])
    analysis = session.analyses.get()
    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert len(observed) == 2
    assert observed[0]["input_ref"] == "U0"
    assert len(observed[0]["sources"]) == int(uploads)
    assert analysis.result_payload["source_labels"].keys() == ({"U0", "S1"} if uploads else {"U0"})
    review = client.get(response.url)
    assert review.status_code == 200
    assert review.context["can_confirm"]
    assert "Discovery verwerfen" in review.content.decode()
    assert not ProcessAnalysis.objects.exists()
    response = client.post(
        response.url,
        {
            "action": "confirm",
            "revision": session.revision,
            "selected_stage_key": "compare",
        },
    )
    assert response.status_code == 302
    idea.refresh_from_db()
    session.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN
    process = idea.discovery_process_analysis
    assert process.stage.value_stream.business_unit == owner.business_unit
    assert session.status == CaptureSession.Status.COMPLETED
    snapshot = InvestigationSourceSnapshot.objects.get(process_analysis=process)
    source = snapshot.sources.get(filename=session.answers["origin"]["origin_source_filename"])
    assert data["problem_statement"] in source.content
    assert (Path(snapshot.folder.root_path) / source.filename).is_file()
    assert response.url == reverse(
        "accelerator:investigation_activity",
        args=[session.answers["materialization"]["investigation_run_id"]],
    )


def test_capture_retention_preserves_durable_idea_origin_and_process_source(
    client, idea, owner, tmp_path, monkeypatch
):
    session, snapshot = start_from_idea(client, idea, owner, tmp_path, monkeypatch)
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    result = materialize(owner, session, analysis)
    process_snapshot = InvestigationSourceSnapshot.objects.get(pk=result.investigation_snapshot_id)
    source = process_snapshot.sources.get()
    source_path = Path(process_snapshot.folder.root_path) / source.filename
    source_bytes = source_path.read_bytes()
    now = timezone.now()
    CaptureSession.objects.filter(pk=session.pk).update(
        status=CaptureSession.Status.EXPIRED, expired_at=now - timedelta(days=8)
    )
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path / "managed"):
        assert purge_terminal_capture_sessions(now=now) == 1
    assert not CaptureSession.objects.filter(pk=session.pk).exists()
    assert not CaptureAnalysis.objects.filter(pk=analysis.pk).exists()
    assert not InvestigationSourceSnapshot.objects.filter(pk=snapshot.pk).exists()
    idea.refresh_from_db()
    assert idea.discovery_process_analysis_id == result.process_analysis_id
    assert idea.discovery_process_analysis.stage.value_stream_id == result.value_stream_id
    assert source_path.read_bytes() == source_bytes
    assert process_snapshot.sources.get().content_sha256 == source.content_sha256
    assert "Analyse fortsetzen" in client.get(idea.get_absolute_url()).content.decode()
    response = client.post(
        reverse("accelerator:autonomous_discovery_start"),
        {
            "idea_candidate": str(idea.pk),
        },
    )
    assert response.url == idea.discovery_process_analysis.get_absolute_url()
    assert not CaptureSession.objects.exists()


@pytest.mark.parametrize("outcome", ["waiting_human", "failed", "discard", "expiry"])
def test_discovery_lifecycle_keeps_idea_open_and_only_terminal_drafts_release_intake(
    client, idea, owner, tmp_path, monkeypatch, outcome
):
    session, snapshot = start_from_idea(
        client, idea, owner, tmp_path, monkeypatch, uploads=_source_uploads()
    )
    if outcome in {"waiting_human", "failed"}:

        def provider(**kwargs):
            if outcome == "failed":
                raise architect_service.DiscoveryAnalysisError(
                    "Provider fehlgeschlagen", code="test_failure"
                )
            if kwargs["schema_name"] == "autonomous_business_discovery_v1":
                return _result(_draft())
            return _result(_verifier("waiting_human", human_question="Wo beginnt der Prozess?"))

        monkeypatch.setattr(architect_service, "_provider_call", provider)
        if outcome == "failed":
            with pytest.raises(architect_service.DiscoveryAnalysisError):
                architect_service.execute_autonomous_business_discovery(
                    actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
                )
        else:
            architect_service.execute_autonomous_business_discovery(
                actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
            )
        assert session.analyses.get().status == outcome
    elif outcome == "discard":
        response = client.post(
            reverse("accelerator:capture_discard", args=[session.pk]),
            {
                "revision": session.revision,
            },
        )
        assert response.status_code == 302
    else:
        CaptureSession.objects.filter(pk=session.pk).update(
            expires_at=timezone.now() - timedelta(seconds=1)
        )
        assert expire_due_capture_sessions() == 1
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.discovery_process_analysis_id is None
    client.post(reverse("use_cases:idea_promote", args=[idea.pk]))
    assert bool(client.session.get("use_case_intake")) == (outcome in {"discard", "expiry"})


def test_other_owner_cannot_create_second_session_or_open_first_owner_review(
    client, idea, owner, other_owner, tmp_path, monkeypatch
):
    session, _ = start_from_idea(client, idea, owner, tmp_path, monkeypatch)
    client.force_login(other_owner)
    response = client.post(
        reverse("accelerator:autonomous_discovery_start"),
        {
            "idea_candidate": str(idea.pk),
            "problem_statement": idea.description,
        },
    )
    assert response.url == idea.get_absolute_url()
    assert CaptureSession.objects.count() == 1
    response = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert response.status_code == 404
    with pytest.raises(ValidationError, match="jemand anderem"):
        create_autonomous_capture_session(
            actor=other_owner, problem_statement=idea.description, idea_candidate_id=idea.pk
        )


def test_changed_idea_unit_does_not_redirect_existing_discovery_or_change_materialization(
    client, idea, owner, tmp_path
):
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    idea.business_unit = BusinessUnit.objects.create(name="Abweichende Organisation")
    idea.save()
    client.force_login(owner)
    response = client.post(
        reverse("accelerator:autonomous_discovery_start"),
        {
            "idea_candidate": str(idea.pk),
            "problem_statement": idea.description,
        },
    )
    assert response.url == reverse("accelerator:autonomous_discovery_review", args=[session.pk])
    result = materialize(owner, session, analysis)
    value_stream = ValueStream.objects.get(pk=result.value_stream_id)
    assert value_stream.business_unit_id == session.answers["business_unit"]["id"]
    assert value_stream.business_unit_id != idea.business_unit_id


@pytest.mark.parametrize("state", ["dismissed", "missing", "invalid_origin", "expired"])
def test_stale_discovery_cannot_materialize_invalid_or_terminal_origin(
    idea, owner, tmp_path, state
):
    session, analysis = idea_draft(idea=idea, owner=owner, tmp_path=tmp_path)
    if state == "dismissed":
        idea.state = IdeaCandidate.State.DISMISSED
        idea.decision_note = "Kein Bedarf"
        idea.save()
    elif state == "missing":
        idea.delete()
    elif state == "invalid_origin":
        session.answers["origin"]["idea_candidate_id"] = "invalid"
        session.save()
    else:
        session.expires_at = timezone.now() - timedelta(seconds=1)
        session.save()
    with pytest.raises(DiscoveryMaterializationError):
        materialize(owner, session, analysis)
    assert not ProcessAnalysis.objects.exists()
    assert not ValueStream.objects.exists()


def test_running_analysis_keeps_due_draft_active_like_existing_capture_retention(idea, owner):
    session = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    CaptureAnalysis.objects.create(
        session=session,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        prompt_version="test",
        extraction_schema_version="test",
    )
    CaptureSession.objects.filter(pk=session.pk).update(
        expires_at=timezone.now() - timedelta(seconds=1)
    )
    assert expire_due_capture_sessions() == 0
    repeated = create_autonomous_capture_session(
        actor=owner, problem_statement=idea.description, idea_candidate_id=idea.pk
    )
    assert repeated.pk == session.pk
    assert CaptureSession.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_origin_migration_preserves_existing_idea_data(owner):
    target = ("use_cases", "0013_alter_decisionassessment_assessed_by")
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    executor.migrate([target])
    try:
        old_apps = executor.loader.project_state([target]).apps
        OldIdea = old_apps.get_model("use_cases", "IdeaCandidate")
        OldUseCase = old_apps.get_model("use_cases", "UseCase")
        use_case = OldUseCase.objects.create(
            title="Bestehender Use Case",
            business_unit_id=owner.business_unit_id,
            business_owner_id=owner.pk,
        )
        for state in ["open", "dismissed", "promoted"]:
            OldIdea.objects.create(
                title=f"Bestehende Idee {state}",
                description="Originalbeschreibung",
                state=state,
                decision_note="Originalbegründung" if state == "dismissed" else "",
                promoted_use_case_id=use_case.pk if state == "promoted" else None,
                impact=4,
                confidence=3,
                ease=2,
                source_note="Originalquelle",
            )
        before = list(OldIdea.objects.order_by("pk").values())
    finally:
        MigrationExecutor(connection).migrate(leaves)
    after = list(IdeaCandidate.objects.order_by("pk").values())
    assert after == [{**row, "discovery_process_analysis_id": None} for row in before]
