import json

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.urls import reverse
from test_issue_98_autonomous_business_discovery import (
    _approved_analysis,
    _draft,
    _result,
    _session_and_snapshot,
    _verifier,
)

from ki_radar.accelerator import architect_service, architect_views
from ki_radar.accelerator.discovery_context import freeze_legacy_discovery_business_unit
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_autonomous_capture_session
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.discovery_materialization import (
    DiscoveryMaterializationError,
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.idea_models import IdeaCandidate

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("profile", ["missing", "inactive", "different"])
def test_owner_can_choose_unit_independently_of_profile(owner, profile):
    target = BusinessUnit.objects.create(name="Ziel der Untersuchung")
    if profile == "missing":
        owner.business_unit = None
        owner.save()
    elif profile == "inactive":
        owner.business_unit.is_active = False
        owner.business_unit.save()
    session = create_autonomous_capture_session(
        actor=owner, problem_statement="Manuelle Angebote", business_unit_id=target.pk
    )
    assert session.answers["business_unit"] == {"id": target.pk, "name": target.name}


@pytest.mark.parametrize("target", ["inactive", "missing", "invalid"])
def test_service_rejects_unavailable_explicit_target_without_profile_fallback(owner, target):
    unit = BusinessUnit.objects.create(name="Inaktive Einheit", is_active=False)
    unit_id = {"inactive": unit.pk, "missing": unit.pk + 1000, "invalid": "invalid"}[target]
    with pytest.raises(ValidationError):
        create_autonomous_capture_session(
            actor=owner, problem_statement="Manuelle Angebote", business_unit_id=unit_id
        )
    assert not CaptureSession.objects.exists()


@pytest.mark.parametrize("idea_unit", ["active", "inactive", "empty", "no_profile"])
def test_start_defaults_are_visible_and_do_not_create_a_session(client, owner, idea_unit):
    unit = BusinessUnit.objects.create(name="Einheit der Idee", is_active=idea_unit != "inactive")
    idea = IdeaCandidate.objects.create(
        title="Angebote",
        description="Manuelle Angebote",
        submitted_by=owner,
        business_unit=unit if idea_unit in {"active", "inactive"} else None,
    )
    if idea_unit == "no_profile":
        owner.business_unit = None
        owner.save()
    client.force_login(owner)
    response = client.get(
        reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": idea.pk}
    )
    assert response.status_code == 200
    expected = (
        unit.pk
        if idea_unit == "active"
        else (owner.business_unit_id if idea_unit == "empty" else None)
    )
    assert response.context["form"].initial["business_unit"] == expected
    assert "Ihre persönliche Zuordnung" in response.content.decode()
    assert "Organisationseinheit der Idee" in response.content.decode()
    assert not CaptureSession.objects.exists()


@pytest.mark.parametrize("selected", ["", "inactive", "invalid"])
def test_invalid_selection_is_an_inline_error_and_preserves_text(client, owner, selected):
    inactive = BusinessUnit.objects.create(name="Inaktiv", is_active=False)
    client.force_login(owner)
    response = client.post(
        reverse("accelerator:autonomous_discovery_start"),
        {
            "problem_statement": "Mein unbearbeiteter Problemtext",
            "business_unit": inactive.pk if selected == "inactive" else selected,
        },
    )
    assert response.status_code == 200
    assert response.context["form"].errors["business_unit"]
    assert (
        response.context["form"]["problem_statement"].value() == "Mein unbearbeiteter Problemtext"
    )
    assert not CaptureSession.objects.exists()


def test_cross_unit_idea_start_without_profile_needs_no_extra_confirmation(
    client, owner, tmp_path, monkeypatch
):
    origin = BusinessUnit.objects.create(name="Ursprungsbereich")
    target = BusinessUnit.objects.create(name="Untersuchungsbereich")
    idea = IdeaCandidate.objects.create(
        title="Angebote", description="Manuelle Angebote", submitted_by=owner, business_unit=origin
    )
    owner.business_unit = None
    owner.save()
    client.force_login(owner)
    monkeypatch.setattr(architect_views, "_run_analysis", lambda *args, **kwargs: None)
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=tmp_path):
        response = client.post(
            reverse("accelerator:autonomous_discovery_start"),
            {
                "idea_candidate": idea.pk,
                "problem_statement": idea.description,
                "business_unit": target.pk,
            },
        )
    assert response.status_code == 302
    session = CaptureSession.objects.get()
    assert session.answers["business_unit"]["id"] == target.pk
    assert session.discovery_source_snapshots.get().sources.count() == 1
    idea.refresh_from_db()
    assert idea.business_unit_id == origin.pk
    assert idea.state == "open"


def test_prompt_review_and_materialization_use_frozen_context_after_profile_changes(
    client, owner, tmp_path, monkeypatch
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    context = session.answers["business_unit"].copy()
    BusinessUnit.objects.filter(pk=context["id"]).update(name="Umbenannter Bereich")
    owner.business_unit = None
    owner.save()
    results = iter([_result(_draft()), _result(_verifier())])
    documents = []

    def provider(**kwargs):
        documents.append(json.loads(kwargs["messages"][1]["content"]))
        return next(results)

    monkeypatch.setattr(architect_service, "_provider_call", provider)
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
    )
    assert documents[0]["business_unit"] == context["name"]
    client.force_login(owner)
    review = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert review.context["business_unit_context"] == context
    assert "Wird angelegt in:" in review.content.decode()
    assert review.context["can_confirm"]
    result = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )
    assert ValueStream.objects.get(pk=result.value_stream_id).business_unit_id == context["id"]


@pytest.mark.parametrize("change", ["inactive", "deleted", "malformed"])
def test_invalid_frozen_target_never_falls_back_and_does_not_materialize(
    client, owner, tmp_path, change
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    analysis = _approved_analysis(session=session, snapshot=snapshot)
    old_unit = owner.business_unit
    owner.business_unit = BusinessUnit.objects.create(name="Andere aktive Einheit")
    owner.save()
    if change == "inactive":
        old_unit.is_active = False
        old_unit.save()
    elif change == "deleted":
        old_unit.delete()
    else:
        session.answers["business_unit"] = None
        session.save()
    client.force_login(owner)
    review = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert review.context["business_unit_error"]
    assert not review.context["can_confirm"]
    assert "Discovery verwerfen" in review.content.decode()
    with pytest.raises(DiscoveryMaterializationError) as error:
        materialize_discovery_and_start_investigation(
            actor=owner,
            session_id=session.pk,
            analysis_id=analysis.pk,
            selected_stage_key="compare",
            expected_revision=session.revision,
        )
    assert error.value.code == "missing_business_unit"
    assert not ValueStream.objects.exists()


def test_legacy_context_freezes_on_first_write_and_review_get_is_read_only(client, owner, tmp_path):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    del session.answers["business_unit"]
    session.save()
    _approved_analysis(session=session, snapshot=snapshot)
    client.force_login(owner)
    review = client.get(reverse("accelerator:autonomous_discovery_review", args=[session.pk]))
    assert review.context["legacy_business_unit"]
    session.refresh_from_db()
    assert "business_unit" not in session.answers
    freeze_legacy_discovery_business_unit(session)
    context = session.answers["business_unit"].copy()
    owner.business_unit = None
    owner.save()
    freeze_legacy_discovery_business_unit(session)
    assert session.answers["business_unit"] == context


def test_discarded_review_has_direct_restart_link(client, owner):
    session = create_autonomous_capture_session(actor=owner, problem_statement="Manuelle Angebote")
    client.force_login(owner)
    response = client.post(
        reverse("accelerator:capture_discard", args=[session.pk]),
        {
            "revision": session.revision,
        },
        follow=True,
    )
    assert response.status_code == 200
    assert "Neue Untersuchung starten" in response.content.decode()
    assert not response.context["can_confirm"]
