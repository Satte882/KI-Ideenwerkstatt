from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
)
from ki_radar.accelerator.structured_models import (
    StructuredAdoptionBatch,
    StructuredAdoptionItem,
)
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


PROCESS_FIELDS = {
    "name": "Angebotsprüfung",
    "scope_start": "Angebot liegt vor",
    "scope_end": "Angebot ist freigegeben",
    "trigger": "Ein Einkaufsvorgang benötigt ein Angebot",
    "outcome": "Das wirtschaftlichste Angebot ist ausgewählt",
    "current_flow": "Einkauf vergleicht Angebote manuell.",
    "roles": "Einkauf, Fachbereich",
    "systems": "ERP, Tabellenkalkulation",
    "data_objects": "Angebote, Bestellanforderung",
    "bottlenecks": "Medienbruch und manueller Vergleich",
    "baseline_metrics": "11 Minuten je Vergleich",
}


def _use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Rechnungsprüfung beschleunigen",
        problem_statement="Die Prüfung dauert zu lange.",
        business_unit=business_unit,
        affected_process="Rechnungsprüfung",
        business_owner=owner,
        submitter=owner,
        expected_benefit="Kürzere Bearbeitungszeit",
        metric_name="Bearbeitungszeit",
        metric_type=UseCase.MetricType.DURATION,
        metric_direction=UseCase.MetricDirection.LOWER,
        metric_unit="min",
        metric_baseline=Decimal("10"),
        metric_target=Decimal("8"),
        metric_measurement_method="Zeitmessung in 20 Fällen",
    )


def _value_stream(owner, business_unit):
    return ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf ist freigegeben.",
        outcome="Bestellung ist ausgelöst.",
        scope_in="Von Bedarf bis Bestellung.",
        created_by=owner,
    )


def _session(*, owner, target):
    is_use_case = isinstance(target, UseCase)
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=(
            CaptureSession.CaptureType.USE_CASE
            if is_use_case
            else CaptureSession.CaptureType.VALUE_STREAM
        ),
        working_title="Strukturierter Review",
        catalog_version="1",
        schema_version="1",
        target_use_case=target if is_use_case else None,
        target_value_stream=None if is_use_case else target,
        status=CaptureSession.Status.COMPLETED,
        revision=1,
        expires_at=timezone.now() + timedelta(days=1),
        completed_at=timezone.now(),
    )


def _analysis(session, owner):
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=owner,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash="a" * 64,
        capture_type=session.capture_type,
        catalog_version="1",
        answer_schema_version="1",
        prompt_version="1.0",
        extraction_schema_version="1.0",
        finished_at=timezone.now(),
    )


def _suggestion(
    *,
    analysis,
    target_type,
    target_field,
    field_type,
    value,
    group_key="",
    uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    excerpt=None,
):
    return CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=target_type,
        target_field=target_field,
        target_group_key=group_key,
        field_type=field_type,
        suggested_value=value,
        source_question="test-question",
        source_excerpt=excerpt or f"Original für {target_field}: {value}",
        uncertainty=uncertainty,
        uncertainty_reason="Der Wert wurde aus der Nutzerantwort abgeleitet.",
    )


def _stage_suggestions(analysis, *, key="stage-01", sequence=1, name="Angebot prüfen"):
    _suggestion(
        analysis=analysis,
        target_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].sequence",
        field_type=CaptureFieldSuggestion.FieldType.INTEGER,
        value=sequence,
        group_key=key,
    )
    _suggestion(
        analysis=analysis,
        target_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        value=name,
        group_key=key,
    )


def _process_suggestions(analysis):
    for field_name, value in PROCESS_FIELDS.items():
        _suggestion(
            analysis=analysis,
            target_type=CaptureFieldSuggestion.TargetObjectType.PROCESS_ANALYSIS,
            target_field=f"process_analysis.{field_name}",
            field_type=CaptureFieldSuggestion.FieldType.TEXT,
            value=value,
        )


def test_metric_review_shows_evidence_and_commits_single_decision(
    client,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    analysis = _analysis(_session(owner=owner, target=use_case), owner)
    _suggestion(
        analysis=analysis,
        target_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.baseline",
        field_type=CaptureFieldSuggestion.FieldType.DECIMAL,
        value="12,5 min",
        excerpt="Die Bearbeitung dauert derzeit 12,5 Minuten.",
    )
    client.force_login(owner)

    detail = client.get(reverse("accelerator:analysis_detail", args=[analysis.id]))
    assert "Strukturierte Vorschläge prüfen" in detail.content.decode()

    url = reverse("accelerator:structured_review", args=[analysis.id])
    response = client.get(url)
    page = response.content.decode()
    assert response.status_code == 200
    assert "Die Bearbeitung dauert derzeit 12,5 Minuten." in page
    assert "12.5" in page
    assert "Dezimalzahl" in page
    assert "Aktueller Datenbankwert" in page
    assert "Alle übernehmen" not in page
    assert "<table" not in page

    client.get(url)
    assert StructuredAdoptionBatch.objects.filter(analysis_id_snapshot=analysis.id).count() == 1
    batch = StructuredAdoptionBatch.objects.get(analysis_id_snapshot=analysis.id)
    item = batch.items.get()

    decision_url = reverse(
        "accelerator:structured_review_decide",
        args=[analysis.id, batch.id, item.id],
    )
    response = client.post(decision_url, {"action": "confirm"})
    assert response.status_code == 302
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert item.decision == StructuredAdoptionItem.Decision.CONFIRMED_PROPOSAL

    commit_url = reverse(
        "accelerator:structured_review_commit",
        args=[analysis.id, batch.id],
    )
    response = client.post(commit_url)
    assert response.status_code == 302
    use_case.refresh_from_db()
    batch.refresh_from_db()
    assert use_case.metric_baseline == Decimal("12.5")
    assert batch.status == StructuredAdoptionBatch.Status.COMMITTED


def test_ambiguous_or_uncertain_metric_requires_explicit_edit(
    client,
    owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    analysis = _analysis(_session(owner=owner, target=use_case), owner)
    _suggestion(
        analysis=analysis,
        target_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.baseline",
        field_type=CaptureFieldSuggestion.FieldType.DECIMAL,
        value="1,234",
        uncertainty=CaptureFieldSuggestion.Uncertainty.MEDIUM,
    )
    client.force_login(owner)
    client.get(reverse("accelerator:structured_review", args=[analysis.id]))
    batch = StructuredAdoptionBatch.objects.get(analysis_id_snapshot=analysis.id)
    item = batch.items.get()
    decision_url = reverse(
        "accelerator:structured_review_decide",
        args=[analysis.id, batch.id, item.id],
    )

    client.post(decision_url, {"action": "confirm"})
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.AMBIGUOUS
    assert item.decision == StructuredAdoptionItem.Decision.PENDING

    client.post(decision_url, {"action": "edit", "edited_value": "12,34"})
    item.refresh_from_db()
    assert item.status == StructuredAdoptionItem.Status.CONFIRMED
    assert item.decision == StructuredAdoptionItem.Decision.CONFIRMED_EDITED
    assert item.decision_snapshot == {"edited_value": "12.34"}


def test_stage_rejection_invalidates_process_and_reconfirmation_enables_atomic_commit(
    client,
    owner,
    business_unit,
):
    value_stream = _value_stream(owner, business_unit)
    analysis = _analysis(_session(owner=owner, target=value_stream), owner)
    _stage_suggestions(analysis)
    _process_suggestions(analysis)
    client.force_login(owner)
    review_url = reverse("accelerator:structured_review", args=[analysis.id])
    response = client.get(review_url)
    assert response.status_code == 200
    batch = StructuredAdoptionBatch.objects.get(analysis_id_snapshot=analysis.id)
    stage_item = batch.items.get(
        candidate_kind=StructuredAdoptionItem.CandidateKind.VALUE_STREAM_STAGE
    )
    process_item = batch.items.get(
        candidate_kind=StructuredAdoptionItem.CandidateKind.PROCESS_ANALYSIS
    )

    stage_url = reverse(
        "accelerator:structured_review_decide",
        args=[analysis.id, batch.id, stage_item.id],
    )
    process_url = reverse(
        "accelerator:structured_review_decide",
        args=[analysis.id, batch.id, process_item.id],
    )
    client.post(stage_url, {"action": "confirm"})
    client.post(
        process_url,
        {"action": "confirm", "stage_reference": "local:stage-01"},
    )
    process_item.refresh_from_db()
    assert process_item.depends_on_id == stage_item.id
    assert process_item.status == StructuredAdoptionItem.Status.CONFIRMED

    client.post(stage_url, {"action": "reject"})
    process_item.refresh_from_db()
    assert process_item.status == StructuredAdoptionItem.Status.DEPENDENCY_INVALID
    assert process_item.decision == StructuredAdoptionItem.Decision.PENDING
    page = client.get(review_url).content.decode()
    assert "erneut bestätigt" in page

    client.post(stage_url, {"action": "confirm"})
    client.post(
        process_url,
        {"action": "confirm", "stage_reference": "local:stage-01"},
    )
    batch.refresh_from_db()
    page = client.get(review_url).content.decode()
    assert "Bestätigte Auswahl atomar übernehmen" in page

    commit_url = reverse(
        "accelerator:structured_review_commit",
        args=[analysis.id, batch.id],
    )
    client.post(commit_url)
    batch.refresh_from_db()
    assert batch.status == StructuredAdoptionBatch.Status.COMMITTED
    assert ValueStreamStage.objects.filter(value_stream=value_stream).count() == 1
    process = ProcessAnalysis.objects.get(stage__value_stream=value_stream)
    assert process.status == ProcessAnalysis.Status.DRAFT


def test_proposed_stages_are_presented_in_sequence_order(client, owner, business_unit):
    value_stream = _value_stream(owner, business_unit)
    analysis = _analysis(_session(owner=owner, target=value_stream), owner)
    _stage_suggestions(analysis, key="stage-02", sequence=2, name="Bestellung auslösen")
    _stage_suggestions(analysis, key="stage-01", sequence=1, name="Angebot prüfen")
    client.force_login(owner)

    page = client.get(reverse("accelerator:structured_review", args=[analysis.id])).content.decode()
    assert page.index("Angebot prüfen") < page.index("Bestellung auslösen")


def test_other_user_cannot_open_or_mutate_review(
    client,
    owner,
    other_owner,
    business_unit,
):
    use_case = _use_case(owner, business_unit)
    analysis = _analysis(_session(owner=owner, target=use_case), owner)
    _suggestion(
        analysis=analysis,
        target_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.metric.name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        value="Durchlaufzeit",
    )
    client.force_login(owner)
    client.get(reverse("accelerator:structured_review", args=[analysis.id]))
    batch = StructuredAdoptionBatch.objects.get(analysis_id_snapshot=analysis.id)
    item = batch.items.get()

    client.force_login(other_owner)
    assert (
        client.get(reverse("accelerator:structured_review", args=[analysis.id])).status_code == 404
    )
    assert (
        client.post(
            reverse(
                "accelerator:structured_review_decide",
                args=[analysis.id, batch.id, item.id],
            ),
            {"action": "reject"},
        ).status_code
        == 404
    )
    item.refresh_from_db()
    assert item.decision == StructuredAdoptionItem.Decision.PENDING
