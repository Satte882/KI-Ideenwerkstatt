from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from ki_radar.architecture.models import (
    ProcessAnalysis,
    UseCaseOrigin,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.stage_focus import (
    InitiativeStageFocusDecision,
    StageFocusDecision,
    get_stage_focus_decision,
    save_stage_focus_decision,
    stage_is_selected,
)
from ki_radar.core.models import SystemJobRun
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


@pytest.fixture
def stages(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
    )
    return [
        ValueStreamStage.objects.create(value_stream=stream, name=f"Phase {n}", sequence=n)
        for n in (1, 2)
    ]


def draft(owner, title="Buchungen verbessern"):
    return save_initiative(actor=owner, data={"title": title})


def focus(owner, initiative, stage):
    return save_stage_focus_decision(
        initiative=initiative,
        value_stream=stage.value_stream,
        selected_stage=stage,
        actor=owner,
        rationale="Gezielter Beitrag",
        criteria_snapshot={},
        is_short_path=True,
        short_path_reason="Bewusste fachliche Eingrenzung",
    )


def test_draft_service_and_ui_can_save_and_resume_without_outcome_fields(client, owner):
    initiative = draft(owner)
    assert initiative.outcome_owner == initiative.business_outcome == ""
    assert initiative.next_review_date is None
    assert initiative.evidence_level == "hypothesis"
    assert initiative.confirmed_by is None
    client.force_login(owner)
    response = client.post(
        initiative.get_absolute_url(),
        {
            "title": "Weiterbearbeitet",
            "status": "active",
            "evidence_level": "hypothesis",
            "expected_revision": 1,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert "Review-Termin noch offen" in response.content.decode()
    form_html = response.content.decode().split('<form method="post">')[1].split("</form>")[0]
    assert 'type="submit"' in form_html and "disabled" not in form_html
    initiative.refresh_from_db()
    assert initiative.title == "Weiterbearbeitet" and initiative.status == "active"
    assert initiative.revision == 2 and initiative.history.count() == 2
    assert initiative.history.first().updated_by == owner


def test_create_ui_without_outcome_and_without_related_artifacts(client, owner):
    client.force_login(owner)
    response = client.post(
        reverse("use_cases:initiative_create"),
        {
            "title": "Offener Entwurf",
            "status": "draft",
            "evidence_level": "hypothesis",
        },
    )
    assert response.status_code == 302
    assert ImprovementInitiative.objects.get().next_review_date is None
    assert not UseCase.objects.exists() and not ProcessAnalysis.objects.exists()


def test_independent_append_only_focus(owner, stages):
    one, two = draft(owner), draft(owner, "Anderer Beitrag")
    first, second = focus(owner, one, stages[0]), focus(owner, two, stages[1])
    revised = focus(owner, one, stages[1])
    assert get_stage_focus_decision(stages[0].value_stream, initiative=one) == revised
    assert get_stage_focus_decision(stages[0].value_stream, initiative=two) == second
    assert (first.revision, second.revision, revised.revision) == (1, 1, 2)
    first.refresh_from_db()
    assert first.selected_stage == stages[0] and not StageFocusDecision.objects.exists()
    assert stage_is_selected(stages[1], initiative=one)
    with pytest.raises(ValidationError):
        first.save()
    with pytest.raises(ValidationError):
        InitiativeStageFocusDecision.objects.filter(pk=first.pk).update(rationale="ersetzt")
    with pytest.raises(ValidationError):
        first.delete()
    with pytest.raises(ValidationError):
        InitiativeStageFocusDecision.objects.all().delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        InitiativeStageFocusDecision.objects.bulk_create(
            [
                InitiativeStageFocusDecision(
                    initiative=one,
                    value_stream=stages[0].value_stream,
                    selected_stage=stages[0],
                    selected_by=owner,
                    revision=1,
                )
            ]
        )


def test_no_global_fallback_and_stage_validation(owner, stages, business_unit):
    legacy = save_stage_focus_decision(
        value_stream=stages[0].value_stream,
        selected_stage=stages[0],
        actor=owner,
        criteria_snapshot={},
        rationale="Legacy",
        is_short_path=True,
        short_path_reason="Bestand",
    )
    initiative = draft(owner)
    assert get_stage_focus_decision(stages[0].value_stream) == legacy
    assert get_stage_focus_decision(stages[0].value_stream, initiative=initiative) is None
    focus(owner, initiative, stages[1])
    legacy.refresh_from_db()
    assert legacy.selected_stage == stages[0]
    other = ValueStream.objects.create(name="Anderer", business_unit=business_unit, owner=owner)
    with pytest.raises(ValidationError):
        save_stage_focus_decision(
            value_stream=other,
            selected_stage=stages[0],
            initiative=initiative,
            actor=owner,
            criteria_snapshot={},
            rationale="Ungültig",
        )


def test_bound_process_ui_and_export_use_only_its_own_focus(owner, stages):
    from django.template.loader import render_to_string

    from ki_radar.review_export_architecture import build_process_review_context

    save_stage_focus_decision(
        value_stream=stages[0].value_stream,
        selected_stage=stages[0],
        actor=owner,
        criteria_snapshot={},
        rationale="Globale Legacy-Begründung",
        is_short_path=True,
        short_path_reason="Bestand",
    )
    initiative = draft(owner)
    process = ProcessAnalysis.objects.create(stage=stages[1], initiative=initiative, name="Beitrag")
    html = render_to_string(
        "architecture/includes/process_focus_context.html", {"process_analysis": process}
    )
    assert "Vorhabensfokus noch offen" in html
    assert "Globale Legacy-Begründung" not in html
    decision = focus(owner, initiative, stages[1])
    html = render_to_string(
        "architecture/includes/process_focus_context.html", {"process_analysis": process}
    )
    assert "Gezielter Beitrag" in html and "Globale Legacy-Begründung" not in html
    exported = build_process_review_context(process, owner)
    assert f"Vorhabensfokus: {decision.pk} · Revision 1" in exported.upstream_context


def test_bound_signals_never_seed_global_focus(owner, business_unit, stages):
    initiative = draft(owner)
    process = ProcessAnalysis.objects.create(
        stage=stages[0],
        name="Entwurf",
        initiative=initiative,
        analyzed_by=owner,
    )
    case = UseCase.objects.create(
        title="Direkt",
        business_unit=business_unit,
        business_owner=owner,
        initiative=initiative,
    )
    UseCaseOrigin.objects.create(use_case=case, stage=stages[0], process_analysis=process)
    assert not StageFocusDecision.objects.exists()
    assert not InitiativeStageFocusDecision.objects.exists()
    direct = UseCase.objects.create(
        title="Ungebunden", business_unit=business_unit, business_owner=owner
    )
    UseCaseOrigin.objects.create(use_case=direct, stage=stages[0], process_analysis=process)
    assert not StageFocusDecision.objects.exists()
    ProcessAnalysis.objects.create(
        stage=stages[1], name="Legacy", analyzed_by=owner, outcome_contract_version=0
    )
    assert get_stage_focus_decision(stages[0].value_stream).selected_stage == stages[1]


def test_optional_links_and_explicit_shared_binding(owner, business_unit, stages):
    initiative = draft(owner)
    idea = IdeaCandidate.objects.create(title="Idee", description="Problem", submitted_by=owner)
    process = ProcessAnalysis.objects.create(
        stage=stages[0], name="Untersuchung", analyzed_by=owner
    )
    case = UseCase.objects.create(title="Direkt", business_unit=business_unit, business_owner=owner)
    for artifact in (idea, process, case):
        assert artifact.initiative_id is None
        bound = bind_initiative(initiative=initiative, artifact=artifact, actor=owner)
        assert bound.initiative_id == initiative.pk
    assert process.outcome_contract_version == case.outcome_contract_version == 1
    with pytest.raises(ValidationError):
        bind_initiative(initiative=draft(owner, "Andere"), artifact=process, actor=owner)
    assert (
        initiative.process_analyses.count()
        == initiative.ideas.count()
        == initiative.use_cases.count()
        == 1
    )
    initiative.refresh_from_db()
    assert initiative.history.filter(history_change_reason__startswith="Zuordnung ").count() == 3
    assert initiative.history.first().updated_by == owner


def test_invalid_completion_can_always_be_saved_as_draft(client, owner):
    initiative = draft(owner)
    client.force_login(owner)
    data = {"title": "Offene Wirkung", "status": "completed", "evidence_level": "hypothesis"}
    response = client.post(initiative.get_absolute_url(), data)
    assert response.status_code == 200 and response.context["form"].errors
    response = client.post(initiative.get_absolute_url(), {**data, "action": "save_draft"})
    assert response.status_code == 302
    initiative.refresh_from_db()
    assert initiative.status == "draft" and initiative.title == "Offene Wirkung"


def test_owner_name_does_not_grant_decision_rights(client, owner, reader, other_owner, stages):
    initiative = save_initiative(
        actor=owner, data={"title": "Offen", "outcome_owner": reader.username}
    )
    with pytest.raises(ValidationError):
        focus(other_owner, initiative, stages[0])
    client.force_login(reader)
    assert client.get(initiative.get_absolute_url()).status_code == 200
    assert client.post(initiative.get_absolute_url(), {"title": "Fremd"}).status_code == 403
    assert client.get(reverse("use_cases:initiative_create")).status_code == 403


def test_outcome_change_resets_confirmation_without_overwriting_history(owner):
    initiative = draft(owner)
    initiative.confirmed_by = owner
    initiative.confirmed_at = timezone.now()
    initiative.confirmed_revision = initiative.revision
    initiative.save()
    changed = save_initiative(
        actor=owner, initiative=initiative, data={"impact_hypothesis": "Hypothese"}
    )
    assert changed.confirmed_revision is None and changed.confirmed_by is None
    assert changed.confirmed_at is None
    assert changed.history.filter(confirmed_by=owner, confirmed_revision=1).exists()


@pytest.mark.parametrize("effect", ["confirmed", "refuted", "unclear"])
def test_completion_and_cancellation_are_honest_and_separate(owner, effect):
    initiative = draft(owner)
    with pytest.raises(ValidationError):
        save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})
    requested_completion = {
        "status": "completed",
        "effect_status": effect,
        "effect_reason": "Noch keine Messung möglich",
    }
    if effect != "unclear":
        # #147: proof-free positive/refuted claims cannot be completed.
        with pytest.raises(ValidationError):
            save_initiative(actor=owner, initiative=initiative, data=requested_completion)
        requested_completion["effect_status"] = "unclear"
    completed = save_initiative(actor=owner, initiative=initiative, data=requested_completion)
    assert completed.status == "completed"
    other = draft(owner, "Abbruch")
    with pytest.raises(ValidationError):
        save_initiative(actor=owner, initiative=other, data={"status": "cancelled"})
    cancelled = save_initiative(
        actor=owner,
        initiative=other,
        data={
            "status": "cancelled",
            "cancellation_reason": "Bedarf entfallen",
        },
    )
    assert cancelled.effect_status == "" and cancelled.status != completed.status


def test_permissions_and_stale_writes_preserve_state(owner, reader, other_owner):
    initiative = draft(owner)
    for actor in (reader, other_owner):
        with pytest.raises(PermissionDenied):
            save_initiative(actor=actor, initiative=initiative, data={"title": "Fremd"})
    save_initiative(actor=owner, initiative=initiative, data={"business_outcome": "Mehr Buchungen"})
    with pytest.raises(ValidationError):
        save_initiative(
            actor=owner, initiative=initiative, expected_revision=1, data={"title": "Alt"}
        )
    with pytest.raises(ValidationError):
        save_initiative(actor=owner, initiative=initiative, data={"confirmed_by": owner})
    initiative.refresh_from_db()
    assert initiative.business_outcome == "Mehr Buchungen"
    assert initiative.history.last().business_outcome == ""
    assert initiative.confirmed_by is None


def test_scan_and_dashboard_keep_initiatives_separate(client, owner):
    today = timezone.localdate()
    for title, date in (
        ("Überfällig", today - timedelta(days=1)),
        ("Bald", today + timedelta(days=30)),
        ("Offen", None),
    ):
        save_initiative(actor=owner, data={"title": title, "next_review_date": date})
    save_initiative(
        actor=owner,
        data={"title": "Abgebrochen", "status": "cancelled", "cancellation_reason": "Kein Bedarf"},
    )
    call_command("scan_due_reviews")
    details = SystemJobRun.objects.get(job_name="review_scan").details
    assert details["overdue"] == 0
    assert details["initiatives"] == {
        "overdue": 1,
        "due_within_30_days": 1,
        "missing_review_date": 1,
    }
    client.force_login(owner)
    response = client.get(reverse("reporting:dashboard"))
    assert response.context["initiative_reviews"] == details["initiatives"]
    assert response.context["active_total"] == 0
    assert "Verbesserungsvorhaben · Reviews" in response.content.decode()


def test_process_create_edit_and_resume_without_initiative_or_confirmed_cause(
    client, owner, stages
):
    from ki_radar.architecture.focus import ValueStreamFocus
    from ki_radar.architecture.forms import ProcessAnalysisForm

    stream = stages[0].value_stream
    stream.status = "active"
    stream.save()
    ValueStreamFocus.objects.create(
        value_stream=stream,
        capability="Beschaffung",
        status="selected",
        rationale="Fachlicher Fokus",
        strategic_impact="high",
        economic_potential="high",
        pain_intensity="high",
        data_accessibility="medium",
        change_effort="medium",
    )
    save_stage_focus_decision(
        value_stream=stream,
        selected_stage=stages[0],
        criteria_snapshot={},
        actor=owner,
        rationale="Fokus",
        is_short_path=True,
        short_path_reason="Bewusst abgegrenzt",
    )
    data = {
        name: "Noch offen" for name, field in ProcessAnalysisForm().fields.items() if field.required
    }
    data.update(name="Neue Untersuchung", status="draft")
    client.force_login(owner)
    response = client.post(
        reverse("architecture:process_analysis_create", args=[stages[0].pk]), data
    )
    assert response.status_code == 302
    process = ProcessAnalysis.objects.get()
    assert process.initiative_id is None and process.confirmed_causes == ""
    data["name"] = "Fortgesetzte Untersuchung"
    response = client.post(reverse("architecture:process_analysis_update", args=[process.pk]), data)
    assert response.status_code == 302
    assert client.get(process.get_absolute_url()).status_code == 200
    process.refresh_from_db()
    assert process.name == data["name"] and process.initiative_id is None
    assert process.outcome_contract_version == 1
    assert not ImprovementInitiative.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_concurrent_focus_saves_serialize_revisions(owner, stages):
    if connection.vendor != "postgresql":
        pytest.skip("Row-lock concurrency contract requires PostgreSQL")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from django.db import close_old_connections

    initiative = draft(owner)
    barrier = Barrier(2)

    def save(stage):
        close_old_connections()
        try:
            barrier.wait(timeout=10)
            return focus(owner, initiative, stage).revision
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        revisions = list(pool.map(save, stages))
    assert sorted(revisions) == [1, 2]
    assert initiative.stage_focus_decisions.count() == 2


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_legacy_focus_origin_and_unbound_cases(owner):
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    old_targets = [
        ("architecture", "0022_alter_solutionarchitectureassessment_assessed_by"),
        ("use_cases", "0014_ideacandidate_discovery_process_analysis"),
    ]
    executor.migrate(old_targets)
    try:
        apps = executor.loader.project_state(old_targets).apps
        stream = apps.get_model("architecture", "ValueStream").objects.create(
            name="Historisch",
            business_unit_id=owner.business_unit_id,
        )
        stage = apps.get_model("architecture", "ValueStreamStage").objects.create(
            value_stream=stream,
            name="Phase",
            sequence=1,
        )
        process = apps.get_model("architecture", "ProcessAnalysis").objects.create(
            stage=stage, name="Alt"
        )
        legacy = apps.get_model("architecture", "StageFocusDecision").objects.create(
            value_stream=stream,
            selected_stage=stage,
            rationale="Unverändert",
            criteria_snapshot={"alt": True},
        )
        case = apps.get_model("use_cases", "UseCase").objects.create(
            title="Altfall",
            business_unit_id=owner.business_unit_id,
            business_owner_id=owner.pk,
            status="operation",
            decision_status="approved",
        )
        origin = apps.get_model("architecture", "UseCaseOrigin").objects.create(
            use_case=case,
            stage=stage,
            process_analysis=process,
            source_snapshot={"historisch": True},
        )
    finally:
        MigrationExecutor(connection).migrate(leaves)
    assert StageFocusDecision.objects.get(pk=legacy.pk).criteria_snapshot == {"alt": True}
    assert UseCaseOrigin.objects.get(pk=origin.pk).source_snapshot == {"historisch": True}
    current = UseCase.objects.get(pk=case.pk)
    assert current.initiative_id is None and current.outcome_contract_version == 0
    assert (current.status, current.decision_status) == ("operation", "approved")
    assert ProcessAnalysis.objects.get(pk=process.pk).initiative_id is None
    assert not ImprovementInitiative.objects.exists()
