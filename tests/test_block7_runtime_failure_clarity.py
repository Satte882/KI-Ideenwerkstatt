from types import SimpleNamespace

import pytest

from ki_radar.accelerator.solution_generation_service import SolutionGenerationError
from ki_radar.accelerator.solution_generation_views import _generation_error_message
from ki_radar.architecture.solution_selection import comparison_blockers


def test_contract_failure_detail_is_preserved_for_user_feedback():
    error = SolutionGenerationError(
        "Die KI-Antwort hat die fachlichen Sicherheitsregeln nicht erfüllt und wurde vollständig "
        "verworfen. Validierungsgrund: $.options.assistant.risks: Unbekannte Source-ID.",
        code="invalid_generation_payload",
    )

    assert _generation_error_message(error) == str(error)
    assert "Validierungsgrund:" in _generation_error_message(error)


@pytest.mark.parametrize(
    "code",
    [
        "not_configured",
        "unauthorized",
        "provider_schema_unsupported",
        "provider_unavailable",
        "provider_error",
        "invalid_response",
        "empty_response",
        "response_too_large",
        "unavailable",
    ],
)
def test_known_provider_failures_preserve_specific_safe_message(code):
    error = SolutionGenerationError(f"Sichere Providerdiagnose: {code}", code=code)

    assert _generation_error_message(error) == str(error)
    assert "derzeit nicht verfügbar" not in _generation_error_message(error)


def test_minimum_two_options_message_belongs_to_persisted_selection_comparison():
    existing_option = SimpleNamespace(name="Manuelle Option", comparison_complete=True)

    blockers = comparison_blockers([existing_option])

    assert blockers == [
        "Für die spätere Auswahl sind mindestens zwei unterschiedliche, gespeicherte "
        "Lösungsoptionen erforderlich."
    ]
