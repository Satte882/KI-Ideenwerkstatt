from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from test_guided_intake_hard_gates import complete_intake_data
from test_issue_146_outcome_contract import outcome_process
from test_issue_160_outcome_presentation import form_data, prep_url

from ki_radar.accelerator.analysis_service import canonical_answer_hash
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from ki_radar.use_cases.context_adoption import CAPTURE_SOURCE_KEY, capture_context
from ki_radar.use_cases.initiative_models import ImprovementInitiative
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


@pytest.fixture
def source(owner):
    session = CaptureSession.objects.create(
        owner=owner,
        capture_type="use_case",
        catalog_version="1.0",
        schema_version="1.0",
        working_title="Wissensantworten",
        status="completed",
        revision=5,
        answers={"uc_problem_context": "Entwürfe aus Handbüchern"},
        expires_at=timezone.now() + timedelta(days=90),
        completed_at=timezone.now(),
    )
    analysis = CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status="success",
        capture_type="use_case",
        source_revision=5,
        source_hash=canonical_answer_hash(session.answers),
        catalog_version="1.0",
        answer_schema_version="1.0",
        extraction_schema_version="1.0",
        prompt_version="1.1",
        finished_at=timezone.now(),
    )
    for field, value in {
        "title": "KI-Wissensentwurf",
        "summary": "Quellengebundene Antwortentwürfe",
        "metric.type": "duration",
        "human_oversight": "Jede Antwort fachlich prüfen",
        "benefit_category": "Qualitätsnutzen (Hypothese)",
    }.items():
        CaptureFieldSuggestion.objects.create(
            analysis=analysis,
            target_object_type="use_case",
            target_field=f"use_case.{field}",
            suggested_value=value,
            field_type="enum" if field == "metric.type" else "text",
            source_question="uc_problem_context",
            source_excerpt="Entwürfe aus Handbüchern",
            uncertainty="low",
            uncertainty_reason="Direkte Angabe",
        )
    return analysis


def test_capture_get_is_read_only_and_explicit_import_preserves_existing_input(
    client, owner, source
):
    client.force_login(owner)
    state = client.session
    state["use_case_intake"] = {"title": "Eigene Überschrift"}
    state.save()
    response = client.get(reverse("use_cases:create"), {"analysis": source.pk})
    assert response.status_code == 200
    assert client.session["use_case_intake"] == {"title": "Eigene Überschrift"}
    assert not UseCase.objects.exists()
    response = client.post(
        reverse("use_cases:create"),
        {"analysis_id": source.pk, "action": "import_analysis", "title": "Noch nicht gespeichert"},
    )
    assert response.context["form"]["title"].value() == "Noch nicht gespeichert"
    stored = client.session["use_case_intake"]
    assert stored["title"] == "Eigene Überschrift"
    assert stored["summary"] == "Quellengebundene Antwortentwürfe"
    assert stored["metric_type"] == "duration"
    assert "metric_baseline" not in stored
    assert "business_owner" not in stored
    assert "title" not in client.session["use_case_intake"][CAPTURE_SOURCE_KEY]["fields"]


@pytest.mark.parametrize("change", ["expired", "discarded", "revision", "answers", "prompt"])
def test_capture_rejects_unusable_sources(owner, source, change):
    session = source.session
    if change == "expired":
        session.expires_at = timezone.now() - timedelta(seconds=1)
    elif change == "discarded":
        session.status = "discarded"
    elif change == "revision":
        session.revision += 1
    elif change == "answers":
        session.answers = {"uc_problem_context": "Geändert"}
    else:
        source.prompt_version = "9.9"
        source.save(update_fields=["prompt_version"])
    session.save()
    with pytest.raises(ValidationError):
        capture_context(actor=owner, analysis_id=source.pk)


def test_other_actor_cannot_import_capture(client, other_owner, source):
    client.force_login(other_owner)
    assert client.get(reverse("use_cases:create"), {"analysis": source.pk}).status_code == 403


def test_intake_save_records_edits_and_repeated_source_does_not_duplicate(
    client, owner, business_unit, source
):
    client.force_login(owner)
    client.post(
        reverse("use_cases:create"), {"analysis_id": source.pk, "action": "import_analysis"}
    )
    state = client.session
    provenance = state["use_case_intake"][CAPTURE_SOURCE_KEY]
    state["use_case_intake"] = complete_intake_data(
        business_unit,
        owner,
        title="Fachlich bearbeitet",
        metric_baseline="",
        metric_target="",
        human_oversight="Jede Antwort fachlich prüfen",
        benefit_category="Qualitätsnutzen (Hypothese)",
    )
    state["use_case_intake"][CAPTURE_SOURCE_KEY] = provenance
    state.save()
    saved = client.post(reverse("use_cases:intake_step", args=[6]))
    assert saved.status_code == 302
    case = UseCase.objects.get()
    assert case.status == "idea" and case.decision_status == "ready"
    assert case.metric_baseline is None and case.metric_target is None
    assert case.human_oversight == "Jede Antwort fachlich prüfen"
    record = case.context_provenance[0]
    assert record["source_hash"] == source.source_hash
    title = next(field for field in record["fields"] if field["field"] == "title")
    assert title["proposed"] == "KI-Wissensentwurf" and title["saved"] == "Fachlich bearbeitet"
    assert "Entwürfe aus Handbüchern" not in str(record)
    assert case.history.first().context_provenance == case.context_provenance
    source.session.refresh_from_db()
    assert source.session.target_use_case_id == case.pk
    assert (
        client.get(reverse("use_cases:create"), {"analysis": source.pk}).url
        == case.get_absolute_url()
    )
    assert UseCase.objects.count() == 1


def test_source_changed_before_final_save_preserves_intake_and_creates_nothing(
    client, owner, business_unit, source
):
    client.force_login(owner)
    client.post(
        reverse("use_cases:create"), {"analysis_id": source.pk, "action": "import_analysis"}
    )
    state = client.session
    provenance = state["use_case_intake"][CAPTURE_SOURCE_KEY]
    state["use_case_intake"] = complete_intake_data(business_unit, owner, title="Nicht verlieren")
    state["use_case_intake"][CAPTURE_SOURCE_KEY] = provenance
    state.save()
    source.session.revision += 1
    source.session.save()
    response = client.post(reverse("use_cases:intake_step", args=[6]))
    assert response.status_code == 200
    assert not UseCase.objects.exists()
    assert client.session["use_case_intake"]["title"] == "Nicht verlieren"


def test_outcome_import_is_explicit_editable_and_keeps_business_outcome_open(
    client, owner, business_unit
):
    process = outcome_process(owner, business_unit)
    client.force_login(owner)
    first = client.get(prep_url(process))
    assert not first.context["form"]["contribution"].value()
    data = form_data(first)
    data.update(action="load_context", title="Eigener Titel", evidence_level="hypothesis")
    loaded = client.post(prep_url(process), data)
    form = loaded.context["form"]
    assert form["title"].value() == "Eigener Titel"
    assert form["contribution"].value().startswith("Zu prüfender Prozessbeitrag:")
    assert not form["business_outcome"].value()
    assert not form["confirmation_reason"].value()
    assert not ImprovementInitiative.objects.exists()
    data = form_data(loaded)
    data.update(
        action="save_draft",
        context_ticket=loaded.context["context_ticket"],
        contribution="Bearbeiteter Prozessbeitrag",
    )
    saved = client.post(prep_url(process), data)
    assert saved.status_code == 302
    initiative = ImprovementInitiative.objects.get()
    assert initiative.contribution == "Bearbeiteter Prozessbeitrag"
    assert initiative.hypothesis_origin == "ai" and not initiative.confirmed_at
    assert initiative.context_provenance[0]["fields"][0]["source_field"] == "process.outcome"
    assert initiative.history.first().context_provenance == initiative.context_provenance
    process.refresh_from_db()
    assert not process.initiative_id
    assert not process.discovery_path_decisions.exists()
    assert client.post(prep_url(process), data).status_code == 302
    assert ImprovementInitiative.objects.count() == 1


def test_high_uncertainty_is_not_prefilled(owner, source):
    source.suggestions.filter(target_field="use_case.summary").update(uncertainty="high")
    _, context = capture_context(actor=owner, analysis_id=source.pk)
    assert "summary" not in {item["field"] for item in context["items"]}


def test_source_deleted_before_final_save_is_a_visible_error(client, owner, business_unit, source):
    client.force_login(owner)
    client.post(
        reverse("use_cases:create"), {"analysis_id": source.pk, "action": "import_analysis"}
    )
    state = client.session
    provenance = state["use_case_intake"][CAPTURE_SOURCE_KEY]
    state["use_case_intake"] = complete_intake_data(business_unit, owner)
    state["use_case_intake"][CAPTURE_SOURCE_KEY] = provenance
    state.save()
    source.delete()
    response = client.post(reverse("use_cases:intake_step", args=[6]))
    assert response.status_code == 200
    assert "nicht mehr verfügbar" in response.content.decode()
    assert not UseCase.objects.exists()


def test_changed_suggestion_rejects_final_save(client, owner, business_unit, source):
    client.force_login(owner)
    client.post(
        reverse("use_cases:create"), {"analysis_id": source.pk, "action": "import_analysis"}
    )
    state = client.session
    provenance = state["use_case_intake"][CAPTURE_SOURCE_KEY]
    state["use_case_intake"] = complete_intake_data(business_unit, owner)
    state["use_case_intake"][CAPTURE_SOURCE_KEY] = provenance
    state.save()
    source.suggestions.filter(target_field="use_case.title").update(
        suggested_value="Anderer Vorschlag"
    )
    response = client.post(reverse("use_cases:intake_step", args=[6]))
    assert response.status_code == 200
    assert not UseCase.objects.exists()


def test_changed_outcome_source_rejects_save_and_keeps_user_edits(client, owner, business_unit):
    process = outcome_process(owner, business_unit)
    client.force_login(owner)
    data = form_data(client.get(prep_url(process)))
    data.update(action="load_context", evidence_level="hypothesis")
    loaded = client.post(prep_url(process), data)
    data = form_data(loaded)
    data.update(
        action="save_draft",
        context_ticket=loaded.context["context_ticket"],
        title="Nicht verlieren",
    )
    process.outcome = "Anderer Prozessoutput"
    process.save()
    response = client.post(prep_url(process), data)
    assert response.status_code == 200
    assert "inzwischen geändert" in response.content.decode()
    assert response.context["form"]["title"].value() == "Nicht verlieren"
    assert not ImprovementInitiative.objects.exists()
