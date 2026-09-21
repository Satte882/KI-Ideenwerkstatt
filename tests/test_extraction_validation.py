import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator import analysis_service, extraction_validation
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from ki_radar.core.openrouter import OpenRouterResult

LIMITS = {
    "ACCELERATOR_LLM_TIMEOUT_SECONDS": "15",
    "ACCELERATOR_LLM_MAX_INPUT_CHARS": "50000",
    "ACCELERATOR_LLM_MAX_OUTPUT_TOKENS": "700",
    "ACCELERATOR_LLM_MAX_CALLS_PER_CONTEXT": "3",
    "ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY": "20",
    "ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY": "100",
}


def _completed_session(owner, capture_type=CaptureSession.CaptureType.VALUE_STREAM):
    catalog = get_capture_catalog(capture_type, "1.0")
    answers = {
        question.key: f"Fachliche Antwort für {question.key}" for question in catalog.questions
    }
    now = timezone.now()
    return CaptureSession.objects.create(
        owner=owner,
        capture_type=capture_type,
        catalog_version="1.0",
        schema_version="1.0",
        answers=answers,
        status=CaptureSession.Status.COMPLETED,
        completed_at=now,
        expires_at=now + timedelta(days=90),
    )


def _payload(suggestions):
    return {
        "schema_version": "1.0",
        "prompt_version": "1.0",
        "suggestions": suggestions,
        "open_questions": [],
        "contradictions": [],
    }


def _suggestion(**overrides):
    value = {
        "target_object_type": "value_stream",
        "target_field": "value_stream.scope_in",
        "target_group_key": None,
        "field_type": "text",
        "suggested_value": "Fachliche Antwort für vs_scope_in",
        "source_question": "vs_scope_in",
        "source_excerpt": "Fachliche Antwort für vs_scope_in",
        "uncertainty": "low",
        "uncertainty_reason": "Die Aussage ist ausdrücklich genannt.",
    }
    value.update(overrides)
    return value


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_source_excerpt_must_be_contained_in_the_actual_answer(owner):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    with pytest.raises(extraction_validation.ExtractionValidationError, match="nicht belegt"):
        extraction_validation.validate_extraction_document(
            _payload([_suggestion(source_excerpt="Erfundener Ausschnitt")]),
            prepared=prepared,
        )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_question_or_help_text_echo_is_rejected_as_degenerate(owner):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)
    question = prepared.catalog.question_map["vs_scope_in"]
    session.answers["vs_scope_in"] = question.label
    session.save(update_fields=["answers", "updated_at"])
    prepared.answers["vs_scope_in"] = question.label

    with pytest.raises(extraction_validation.ExtractionValidationError, match="wiederholt nur"):
        extraction_validation.validate_extraction_document(
            _payload(
                [
                    _suggestion(
                        suggested_value=question.label,
                        source_excerpt=question.label,
                    )
                ]
            ),
            prepared=prepared,
        )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_invented_repeated_group_is_rejected(owner):
    session = _completed_session(owner)
    session.answers["vs_stages"] = "Phase Angebot prüfen und anschließend Freigabe dokumentieren."
    session.save(update_fields=["answers", "updated_at"])
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    with pytest.raises(extraction_validation.ExtractionValidationError, match="Gruppe ist"):
        extraction_validation.validate_extraction_document(
            _payload(
                [
                    _suggestion(
                        target_object_type="value_stream_stage",
                        target_field="value_stream.stages[].name",
                        target_group_key="erfundene-phase",
                        suggested_value="Erfundene Phase",
                        source_question="vs_stages",
                        source_excerpt="Phase Angebot prüfen",
                    )
                ]
            ),
            prepared=prepared,
        )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_real_repeated_group_is_accepted_when_excerpt_contains_slug(owner):
    session = _completed_session(owner)
    session.answers["vs_stages"] = "Phase Angebot prüfen und anschließend Freigabe dokumentieren."
    session.save(update_fields=["answers", "updated_at"])
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    _document, suggestions = extraction_validation.validate_extraction_document(
        _payload(
            [
                _suggestion(
                    target_object_type="value_stream_stage",
                    target_field="value_stream.stages[].name",
                    target_group_key="phase-angebot-prufen",
                    suggested_value="Angebot prüfen",
                    source_question="vs_stages",
                    source_excerpt="Phase Angebot prüfen",
                )
            ]
        ),
        prepared=prepared,
    )

    assert suggestions[0]["target_group_key"] == "phase-angebot-prufen"


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_german_decimal_and_unit_are_normalized(owner):
    session = _completed_session(owner, CaptureSession.CaptureType.USE_CASE)
    session.answers["uc_metric"] = "Die Baseline beträgt 1.234,50 Minuten."
    session.save(update_fields=["answers", "updated_at"])
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    _document, suggestions = extraction_validation.validate_extraction_document(
        _payload(
            [
                _suggestion(
                    target_object_type="use_case",
                    target_field="use_case.metric.baseline",
                    field_type="decimal",
                    suggested_value="1.234,50 min",
                    source_question="uc_metric",
                    source_excerpt="1.234,50 Minuten",
                )
            ]
        ),
        prepared=prepared,
    )

    assert suggestions[0]["suggested_value"] == {"value": "1234.50", "unit": "min"}


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_enum_is_checked_against_blueprint_contract(owner):
    session = _completed_session(owner, CaptureSession.CaptureType.USE_CASE)
    session.answers["uc_solution_context"] = "Die Priorität ist dringend."
    session.save(update_fields=["answers", "updated_at"])
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    with pytest.raises(
        extraction_validation.ExtractionValidationError, match="Ungültiger Enumwert"
    ):
        extraction_validation.validate_extraction_document(
            _payload(
                [
                    _suggestion(
                        target_object_type="use_case",
                        target_field="use_case.priority",
                        field_type="enum",
                        suggested_value="urgent",
                        source_question="uc_solution_context",
                        source_excerpt="Priorität ist dringend",
                    )
                ]
            ),
            prepared=prepared,
        )


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_one_invalid_item_rejects_the_entire_result(owner):
    session = _completed_session(owner)
    prepared = analysis_service.prepare_capture_analysis(actor=owner, session_id=session.pk)

    with pytest.raises(extraction_validation.ExtractionValidationError):
        extraction_validation.validate_extraction_document(
            _payload(
                [
                    _suggestion(),
                    _suggestion(
                        source_excerpt="nicht vorhanden",
                        target_field="value_stream.scope_out",
                        source_question="vs_scope_out",
                    ),
                ]
            ),
            prepared=prepared,
        )

    assert CaptureFieldSuggestion.objects.count() == 0


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_execute_stores_all_suggestions_and_provider_metadata_atomically(owner, monkeypatch):
    session = _completed_session(owner)
    provider_payload = _payload([_suggestion()])
    provider_result = OpenRouterResult(
        content=json.dumps(provider_payload),
        model="provider/model",
        usage={
            "prompt_tokens": 20,
            "completion_tokens": 10,
            "total_tokens": 30,
            "cost": 0.002,
        },
        output_chars=200,
    )
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: provider_result,
    )

    analysis = extraction_validation.execute_capture_analysis(actor=owner, session_id=session.pk)

    assert analysis.status == CaptureAnalysis.Status.SUCCESS
    assert analysis.model_name == "provider/model"
    assert analysis.total_tokens == 30
    assert analysis.suggestions.count() == 1
    suggestion = analysis.suggestions.get()
    assert suggestion.target_field == "value_stream.scope_in"
    assert suggestion.target_object_id is None


@pytest.mark.django_db
@override_settings(**LIMITS)
def test_execute_marks_invalid_result_failed_without_partial_suggestions(owner, monkeypatch):
    session = _completed_session(owner)
    provider_payload = _payload(
        [
            _suggestion(),
            _suggestion(
                target_field="value_stream.scope_out",
                source_question="vs_scope_out",
                source_excerpt="nicht vorhanden",
            ),
        ]
    )
    monkeypatch.setattr(
        analysis_service,
        "request_openrouter",
        lambda **kwargs: OpenRouterResult(
            content=json.dumps(provider_payload),
            model="provider/model",
            usage={},
            output_chars=200,
        ),
    )

    with pytest.raises(analysis_service.CaptureAnalysisError) as exc_info:
        extraction_validation.execute_capture_analysis(actor=owner, session_id=session.pk)

    analysis = CaptureAnalysis.objects.get()
    assert exc_info.value.code == "invalid_extraction"
    assert analysis.status == CaptureAnalysis.Status.FAILED
    assert CaptureFieldSuggestion.objects.count() == 0
