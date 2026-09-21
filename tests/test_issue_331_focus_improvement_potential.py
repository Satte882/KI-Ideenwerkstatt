import pytest

from ki_radar.architecture.models import EvidenceBasis, TimeToValue, ValueStream, ValueStreamStage
from ki_radar.architecture.stage_focus import ensure_single_stage_focus
from ki_radar.architecture.stage_focus_forms import StageFocusForm
from ki_radar.core.taxonomy import ScreeningLevel


def _stream(*, owner, business_unit, name="Value Stream"):
    return ValueStream.objects.create(
        name=name,
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Bedarf liegt vor.",
        outcome="Ergebnis liegt vor.",
        scope_in="Vom Bedarf bis zum Ergebnis.",
        status=ValueStream.Status.ACTIVE,
    )


def _stage(value_stream, sequence, name):
    return ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=sequence,
        name=name,
        description=f"Aktivitäten in {name}.",
        actors="Fachbereich",
        systems="Fachanwendung",
        documents="Vorgangsdaten",
        pain_points="Manuelle Nacharbeit",
        baseline_metrics="Baseline vorhanden",
    )


@pytest.mark.django_db
def test_improvement_potential_is_persisted_separately_from_change_effort(owner, business_unit):
    value_stream = _stream(owner=owner, business_unit=business_unit)
    stage_one = _stage(value_stream, 1, "Prüfen")
    stage_two = _stage(value_stream, 2, "Entscheiden")

    data = {
        "selected_stage": str(stage_two.pk),
        "rationale": "Die zweite Phase bietet das größte realistische Verbesserungspotenzial.",
    }
    for stage in (stage_one, stage_two):
        data.update(
            {
                f"impact_{stage.pk.hex}": ScreeningLevel.HIGH,
                f"pain_intensity_{stage.pk.hex}": ScreeningLevel.HIGH,
                f"improvement_potential_{stage.pk.hex}": (
                    ScreeningLevel.HIGH if stage == stage_two else ScreeningLevel.LOW
                ),
                f"data_accessibility_{stage.pk.hex}": ScreeningLevel.MEDIUM,
                f"change_effort_{stage.pk.hex}": (
                    ScreeningLevel.HIGH if stage == stage_two else ScreeningLevel.LOW
                ),
                f"time_to_value_{stage.pk.hex}": TimeToValue.MEDIUM,
                f"evidence_basis_{stage.pk.hex}": EvidenceBasis.HYPOTHESIS,
            }
        )

    form = StageFocusForm(data=data, value_stream=value_stream)

    assert form.is_valid(), form.errors
    snapshot = form.criteria_snapshot()
    selected = snapshot[str(stage_two.pk)]
    assert selected["improvement_potential"] == ScreeningLevel.HIGH
    assert selected["change_effort"] == ScreeningLevel.HIGH
    assert "improvement_potential" in selected
    assert "change_effort" in selected


@pytest.mark.django_db
def test_legacy_short_path_keeps_improvement_potential_unknown(owner, business_unit):
    value_stream = _stream(owner=owner, business_unit=business_unit, name="Legacy Stream")
    stage = _stage(value_stream, 1, "Einzige Phase")

    assert ensure_single_stage_focus(stage=stage, actor=owner) is True

    criteria = value_stream.stage_focus_decision.criteria_for(stage)
    assert criteria["improvement_potential"] == ""
    assert criteria["change_effort"] == ""
