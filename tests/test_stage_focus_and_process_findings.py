import pytest
from django.urls import reverse

from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    EvidenceBasis,
    ProcessAnalysis,
    TimeToValue,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.architecture.process_findings import build_process_findings, humanize_process_text
from ki_radar.architecture.stage_focus import StageFocusDecision
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel


def make_selected_stream(*, owner, business_unit):
    value_stream = ValueStream.objects.create(
        name="Lieferantenauswahl",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf ist freigegeben.",
        outcome="Lieferant ist ausgewählt.",
        scope_in="Angebotsvergleich und Auswahl.",
        status=ValueStream.Status.ACTIVE,
        created_by=owner,
    )
    ValueStreamFocus.objects.create(
        value_stream=value_stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Supplier Sourcing",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Hoher manueller Aufwand rechtfertigt den Deep Dive.",
        updated_by=owner,
    )
    return value_stream


def make_stage(value_stream, sequence, name, pain_points, baseline_metrics):
    return ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=sequence,
        name=name,
        description=f"Aktivitäten der Phase {name}.",
        actors="Einkauf",
        systems="ERP und E-Mail",
        documents="Angebote",
        pain_points=pain_points,
        baseline_metrics=baseline_metrics,
    )


@pytest.mark.django_db
def test_process_analysis_requires_saved_focus_stage_and_uses_selected_stage(
    client,
    owner,
    business_unit,
):
    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    stage_one = make_stage(
        value_stream,
        1,
        "Bedarf klären",
        "Wenige Rückfragen",
        "2 Minuten je Vorgang",
    )
    stage_two = make_stage(
        value_stream,
        2,
        "Angebote vergleichen",
        "Manuelle Prüfung\nMedienbruch",
        "11 Minuten je Vorgang\n18 % Korrekturen",
    )
    client.force_login(owner)

    response = client.get(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": stage_one.pk})
    )
    assert response.status_code == 302
    focus_url = reverse(
        "architecture:stage_focus_select",
        kwargs={"pk": value_stream.pk},
    )
    assert response.url == focus_url

    payload = {
        "selected_stage": str(stage_two.pk),
        "rationale": "Phase 2 bündelt den größten Aufwand und die stärksten Reibungsverluste.",
    }
    for stage in (stage_one, stage_two):
        payload.update(
            {
                f"impact_{stage.pk.hex}": ScreeningLevel.HIGH,
                f"pain_intensity_{stage.pk.hex}": (
                    ScreeningLevel.HIGH if stage == stage_two else ScreeningLevel.LOW
                ),
                f"improvement_potential_{stage.pk.hex}": (
                    ScreeningLevel.HIGH if stage == stage_two else ScreeningLevel.LOW
                ),
                f"data_accessibility_{stage.pk.hex}": ScreeningLevel.MEDIUM,
                f"change_effort_{stage.pk.hex}": ScreeningLevel.MEDIUM,
                f"time_to_value_{stage.pk.hex}": (
                    TimeToValue.SHORT if stage == stage_two else TimeToValue.MEDIUM
                ),
                f"evidence_basis_{stage.pk.hex}": (
                    EvidenceBasis.MEASURED if stage == stage_two else EvidenceBasis.HYPOTHESIS
                ),
            }
        )

    response = client.post(focus_url, payload)
    assert response.status_code == 302
    decision = StageFocusDecision.objects.get(value_stream=value_stream)
    assert decision.selected_stage == stage_two
    assert decision.criteria_for(stage_two)["pain_intensity"] == ScreeningLevel.HIGH
    assert decision.criteria_for(stage_two)["improvement_potential"] == ScreeningLevel.HIGH
    assert decision.criteria_for(stage_two)["change_effort"] == ScreeningLevel.MEDIUM
    assert decision.criteria_for(stage_two)["time_to_value"] == TimeToValue.SHORT
    assert decision.criteria_for(stage_two)["evidence_basis"] == EvidenceBasis.MEASURED
    assert decision.criteria_for(stage_one)["evidence_basis"] == EvidenceBasis.HYPOTHESIS
    assert (
        decision.criteria_for(stage_two)["indicators"]["baseline_metrics"]
        == "11 Minuten je Vorgang\n18 % Korrekturen"
    )

    blocked = client.get(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": stage_one.pk})
    )
    assert blocked.status_code == 302
    assert blocked.url == value_stream.get_absolute_url()

    allowed = client.get(
        reverse("architecture:process_analysis_create", kwargs={"stage_id": stage_two.pk})
    )
    assert allowed.status_code == 200
    content = allowed.content.decode()
    assert "Angebote vergleichen" in content
    assert "novalidate" in content
    assert "Baseline und Prozesskennzahlen *" in content
    assert "Bottlenecks und Ursachen *" in content
    assert 'name="trigger"' in content
    assert allowed.context["form"].initial.get("trigger", "") == ""
    assert allowed.context["form"].initial.get("outcome", "") == ""

    detail = client.get(value_stream.get_absolute_url()).content.decode()
    assert "Verbesserungspotenzial" in detail
    assert "Time-to-Value" in detail
    assert "Evidenzbasis" in detail
    assert "Kurz" in detail
    assert "Gemessen / nachgewiesen" in detail


@pytest.mark.django_db
def test_short_path_is_explicitly_justified_without_full_phase_scoring(
    client,
    owner,
    business_unit,
):
    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    stage = make_stage(
        value_stream,
        1,
        "Einzige sinnvolle Fokusphase",
        "Hoher manueller Aufwand",
        "25 Minuten je Vorgang",
    )
    client.force_login(owner)

    response = client.post(
        reverse("architecture:stage_focus_select", kwargs={"pk": value_stream.pk}),
        {
            "selected_stage": str(stage.pk),
            "rationale": "Nur diese Phase enthält den betrachteten Engpass.",
            "is_short_path": "on",
            "short_path_reason": (
                "Die übrige Wertschöpfung liegt außerhalb des dokumentierten Scopes."
            ),
        },
    )

    assert response.status_code == 302
    decision = StageFocusDecision.objects.get(value_stream=value_stream)
    assert decision.is_short_path is True
    assert decision.criteria_for(stage)["impact"] == ""
    assert decision.criteria_for(stage)["improvement_potential"] == ""
    assert decision.criteria_for(stage)["change_effort"] == ""
    assert decision.criteria_for(stage)["time_to_value"] == ""
    assert decision.criteria_for(stage)["evidence_basis"] == ""
    assert "außerhalb" in decision.short_path_reason


@pytest.mark.django_db
def test_process_decision_basis_is_compact_and_traceable_without_new_facts(
    client,
    owner,
    business_unit,
):
    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    stage = make_stage(
        value_stream,
        1,
        "Angebote vergleichen",
        "Manuelle Prüfung",
        "11 Minuten je Vorgang",
    )
    process_analysis = ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich analysieren",
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Angebote liegen vor.",
        scope_end="Vergleich ist freigegeben.",
        trigger="Angebotsfrist endet.",
        outcome="Nachvollziehbarer Vergleich.",
        current_flow="Angebote werden manuell übertragen und geprüft.",
        roles="Sachbearbeitung\nEinkauf",
        systems="ERP\nE-Mail",
        data_objects="Angebote\nBewertungsmatrix",
        business_rules="Annahme: Freigabegrenze bleibt unverändert.",
        handoffs="Übergabe an den Einkauf.",
        bottlenecks="Manuelle Prüfung\nMedienbruch\nWiederholte Rückfragen",
        exceptions="Offen: Umgang mit unvollständigen Angeboten.",
        baseline_metrics="11 Minuten je Vorgang\n18 % Korrekturen",
        target_state_principles="Nachvollziehbare Bewertung.",
        analyzed_by=owner,
    )

    groups = build_process_findings(process_analysis)
    by_key = {group.key: group for group in groups}
    assert [item.text for item in by_key["problem"].items] == ["Manuelle Prüfung"]
    assert [item.text for item in by_key["scale"].items] == [
        "11 Minuten je Vorgang",
        "18 % Korrekturen",
    ]
    assert set(by_key) == {"problem", "scale"}
    assert "context" not in by_key
    assert not any("Automatisierung" in item.text for group in groups for item in group.items)

    client.force_login(owner)
    response = client.get(process_analysis.get_absolute_url())
    body = response.content.decode()
    assert response.status_code == 200
    assert "Kernbefund" in body
    source_link = 'Quelle: <a href="#analysis-bottlenecks">Bottlenecks und Ursachen</a>'
    assert source_link in body
    findings_index = body.index("Kernbefund")
    solutions_index = body.index("Lösungsoptionen vergleichen")
    assert findings_index < solutions_index


@pytest.mark.django_db
def test_materialized_investigation_text_is_humanized_in_process_core(
    client,
    owner,
    business_unit,
):
    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    stage = make_stage(
        value_stream,
        1,
        "Freigabe",
        "Schwankende Freigabezeiten",
        "Offen",
    )
    raw_metric = (
        "Mittlere approval_hours nach queue_retries: 0=5.5 (n=2), 4=23 (n=1). "
        "| Population: rows_total: 4; included_rows: [1, 2, 3, 4] "
        "| Grenzen: Kleine Stichprobe. "
        "| Nachweis: tool-result:b7630e51-ee87-4ac9-93ac-4d5dae5d44c5 "
        "source-sha256:aaef53e70008ec0a70f4a24f6a894429d66f337faf17b96aa3c434038a8e0782"
    )
    process = ProcessAnalysis.objects.create(
        stage=stage,
        name="Historisch materialisierte Analyse",
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Fall liegt vor.",
        scope_end="Entscheidung liegt vor.",
        trigger="Fall wird eingereicht.",
        outcome="Richtung ist dokumentiert.",
        current_flow="Fall prüfen.",
        roles="Fachbereich",
        systems="Workflow",
        data_objects="Fallunterlagen",
        bottlenecks="Schwankende Freigabezeiten",
        diagnostic_observations="Die Bearbeitungs- und Freigabezeiten schwanken.",
        cause_hypotheses=(
            "[supported] Technische Queue-Fehler verlängern die Durchlaufzeit.\n"
            "[refuted] approver_available erklärt die Verzögerung."
        ),
        baseline_metrics=raw_metric,
        analyzed_by=owner,
    )

    groups = {group.key: group for group in build_process_findings(process)}
    scale_text = " ".join(item.text for item in groups["scale"].items)
    assert "Freigabedauer (Stunden)" in scale_text
    assert "Queue-Wiederholungen" in scale_text
    assert "Population:" not in scale_text
    assert "tool-result:" not in scale_text
    assert "source-sha256:" not in scale_text
    assert humanize_process_text(process.cause_hypotheses).startswith("Durch Evidenz gestützt:")

    client.force_login(owner)
    body = client.get(process.get_absolute_url()).content.decode()
    core_start = body.index("Kernbefund")
    raw_start = body.index("Rohdaten und Herkunft anzeigen")
    visible_core = body[core_start:raw_start]
    assert "Durch Evidenz gestützt:" in visible_core
    assert "Durch Evidenz nicht gestützt:" in visible_core
    assert "[supported]" not in visible_core
    assert "[refuted]" not in visible_core
    assert "approval_hours" not in visible_core
    assert "queue_retries" not in visible_core
    assert "tool-result:" not in visible_core
    assert "source-sha256:" not in visible_core

    raw_audit = body[raw_start:]
    assert "tool-result:" in raw_audit
    assert "source-sha256:" in raw_audit


@pytest.mark.django_db
def test_process_decision_basis_preserves_decimal_metrics_and_prefers_observation(
    owner, business_unit
):
    value_stream = make_selected_stream(owner=owner, business_unit=business_unit)
    stage = make_stage(value_stream, 1, "Freigabe", "Manuelle Prüfung", "1,5 Arbeitstage")
    process_analysis = ProcessAnalysis.objects.create(
        stage=stage,
        name="Freigabe analysieren",
        status=ProcessAnalysis.Status.DRAFT,
        scope_start="Antrag liegt vor.",
        scope_end="Antrag ist entschieden.",
        trigger="Antrag eingereicht.",
        outcome="Schnelle Entscheidung.",
        current_flow="Manuelle Freigabe.",
        diagnostic_observations="Standardfälle warten auf Freigabe.",
        bottlenecks="Anderer alter Freitext.",
        baseline_metrics="1,5 Arbeitstage; 80 Prozent Standardfälle.",
        analyzed_by=owner,
    )

    by_key = {group.key: group for group in build_process_findings(process_analysis)}
    assert by_key["problem"].items[0].text == "Standardfälle warten auf Freigabe."
    assert [item.text for item in by_key["scale"].items] == [
        "1,5 Arbeitstage",
        "80 Prozent Standardfälle.",
    ]
    assert by_key["problem"].items[0].source_anchor == "analysis-diagnostic-observations"
