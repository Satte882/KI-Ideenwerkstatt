"""Deterministic synthetic cases; never evidence of real business or model quality."""

from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from test_issue_98_autonomous_business_discovery import (
    _draft,
    _result,
    _session_and_snapshot,
    _verifier,
)
from test_issue_146_outcome_contract import bind_process, confirmed, direct, outcome_process, select
from test_issue_178_strategic_discovery import analyze, make_context, materialize
from test_issue_185_strategic_drafts import option_data, process_data
from test_issue_188_decision_quality import QUALITY, choose
from test_issue_188_decision_quality import comparison as comparison_fixture
from test_solution_selection_ux import make_option

from ki_radar.accelerator import architect_service
from ki_radar.architecture.discovery_materialization import (
    materialize_discovery_and_start_investigation,
)
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption, ValueStreamStage
from ki_radar.architecture.solution_selection import (
    confirm_diagnosis_and_select_solution,
    select_preferred_solution,
)
from ki_radar.delivery.services import create_delivery_package
from ki_radar.governance.models import GovernanceAssessment
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.impact_review_views import ImpactReviewForm
from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiative_models import InitiativeImpactReview
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
from ki_radar.use_cases.models import DecisionAssessment
from ki_radar.use_cases.outcome_contract import confirm_initiative, snapshot_is_stale
from ki_radar.use_cases.services import (
    create_use_case_from_selected_solution,
    submit_approval_decision,
)

pytestmark = pytest.mark.django_db
comparison = comparison_fixture
PLAN = {
    "measurement_method": "Synthetischer Abgleich freigegebener Vorgänge mit Ergebnisprotokoll",
    "measurement_period": "Vier Wochen nach Beginn der Intervention",
    "measurement_population": "Alle Vorgänge des vereinbarten begrenzten Testbereichs",
    "measurement_reference": "Absolutes Ziel: mindestens 18 von 100 termingerechten Abschlüssen",
}


def planned(owner, initiative=None):
    initiative = initiative or confirmed(owner)
    initiative.refresh_from_db()
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            **PLAN,
            "measurement_unknowns": "",
            "measurement_change_reason": "Messabsicht vor Auswahl präzisiert",
        },
    )
    return confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Messabsicht vor Intervention vereinbart",
        expected_revision=initiative.revision,
    )


def save(owner, initiative, data, *, finalize=True):
    initiative.refresh_from_db()
    return save_impact_review(
        initiative=initiative,
        actor=owner,
        data=data,
        expected_revision=initiative.revision,
        finalize=finalize,
    )


def finding(**overrides):
    data = {
        "effect_status": "confirmed",
        "effect_reason": "Synthetisches Geschäftsergebnis geprüft",
        "business_measurement": "18/100 termingerechte Abschlüsse; vier Wochen; Testpopulation",
        "business_evidence": "Synthetisches Ergebnisprotokoll TEST-189, keine Unternehmensmessung",
        "criteria_assessment": "Absolutes Ziel 18/100 erfüllt; keine Vorher-Verbesserung",
        "assessment_basis": "original",
        "attribution": "unclear",
        "attribution_reason": "Kein kausaler Vergleich; externe Einflüsse bleiben unbekannt",
    }
    data.update(overrides)
    return data


@pytest.mark.parametrize("effect", ["confirmed", "refuted", "unclear"])
def test_non_ai_original_plan_absolute_target_without_baseline(owner, business_unit, effect):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    frozen = deepcopy(selection.outcome_snapshot)
    review = save(
        owner,
        initiative,
        finding(
            selection=selection,
            effect_status=effect,
            criteria_assessment="Ziel verfehlt: 12/100" if effect == "refuted" else "Ziel geprüft",
            process_measurement="Andere Prozessgröße: Rückfragen je Vorgang; Protokoll TEST-P",
            process_result="achieved",
        ),
    )
    assert not review.review_required
    assert review.criteria_snapshot["original"]["id"] == selection.pk
    assert review.attribution == "unclear"
    selection.refresh_from_db()
    assert selection.outcome_snapshot == frozen
    assert not initiative.use_cases.exists()


def test_criteria_changed_after_results_cannot_replace_original_measure(owner, business_unit):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    original = select(owner, process)
    frozen = deepcopy(original.outcome_snapshot)
    review = save(owner, initiative, finding(selection=original))
    with pytest.raises(ValidationError, match="begründen"):
        save_initiative(
            actor=owner, initiative=initiative, data={"evaluation_criteria": "Leichteres Ziel"}
        )
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "evaluation_criteria": "Nach Ergebniskenntnis: nur 12/100 erforderlich",
            "measurement_change_reason": "Nach Ergebniskenntnis geändert; keine Vorab-Vereinbarung",
        },
    )
    review.refresh_from_db()
    assert review.review_required and snapshot_is_stale(process, frozen)
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Bewusste neue Interpretation",
        expected_revision=initiative.revision,
    )
    renewed = select(owner, process)
    with pytest.raises(ValidationError, match="Abweichung"):
        save(owner, initiative, finding(selection=renewed))
    review = save(
        owner,
        initiative,
        finding(
            selection=renewed,
            assessment_basis="retrospective",
            criteria_assessment="Neues Ziel erfüllt; ursprüngliches Ziel nicht nachgewiesen",
            criteria_deviation="Nach Ergebniskenntnis geändert; nur nachträgliche Neubewertung",
        ),
    )
    assert not review.review_required
    assert review.criteria_snapshot["original"]["id"] == original.pk
    assert review.criteria_snapshot["original"]["outcome"] == frozen
    assert (
        review.criteria_snapshot["current"]["evaluation_criteria"]
        != frozen["fields"]["evaluation_criteria"]
    )
    assert review.history.count() == 2


def test_missing_historical_plan_is_not_backfilled(owner, business_unit):
    process = outcome_process(owner, business_unit)
    initiative = bind_process(owner, process)
    selection = select(owner, process)
    assert selection.outcome_snapshot["measurement_plan"]["state"] == "open"
    with pytest.raises(ValidationError, match="Vorab-Messplan"):
        save(owner, initiative, finding(selection=selection))
    review = save(
        owner,
        initiative,
        finding(
            selection=selection,
            assessment_basis="retrospective",
            criteria_deviation="Vorab-Beleg fehlt; nachträgliche Auswertung am Reviewdatum",
        ),
    )
    assert not review.review_required
    assert review.criteria_snapshot["original"]["outcome"]["fields"]["measurement_method"] == ""


@pytest.mark.parametrize("field", list(PLAN))
def test_plan_change_uses_existing_materiality_and_preserves_lock(owner, business_unit, field):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    review = save(owner, initiative, finding(selection=selection))
    initiative.refresh_from_db()
    old_revision = initiative.revision
    changed = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            field: "Anderer fachlicher Messbezug",
            "measurement_change_reason": "Neue Population ab Folgephase",
        },
        expected_revision=old_revision,
    )
    review.refresh_from_db()
    assert review.review_required
    assert selection.outcome_review_required
    with pytest.raises(ValidationError, match="inzwischen"):
        save_impact_review(initiative=changed, actor=owner, expected_revision=old_revision, data={})
    assert selection.outcome_snapshot["fields"][field] == PLAN[field]


def test_review_server_fields_and_metadata_and_view_input(owner, business_unit, client):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    review = save(owner, initiative, finding(selection=selection))
    with pytest.raises(ValidationError, match="Serververwaltete"):
        save(owner, initiative, {"criteria_snapshot": {"original": "forged"}})
    initiative = save_initiative(
        actor=owner, initiative=initiative, data={"title": "Nur neuer Titel"}
    )
    review.refresh_from_db()
    assert not review.review_required
    client.force_login(owner)
    url = reverse("use_cases:initiative_impact", args=[initiative.pk])
    data = {
        k: v if v is not None else ""
        for k, v in model_to_dict(review, fields=ImpactReviewForm.Meta.fields).items()
    }
    data.update(
        expected_revision=initiative.revision,
        effect_status="confirmed",
        effect_reason="Synthetische Aussage",
        action="review",
        criteria_assessment="",
    )
    page = client.post(url, data)
    assert page.status_code == 200
    assert page.context["form"]["business_evidence"].value() == review.business_evidence
    assert "historischen Prüfkriterien" in page.content.decode()
    review.refresh_from_db()
    assert not review.review_required
    review.criteria_snapshot = {"forged": True}
    review.save()
    assert review.review_required


def approve(case, coordinator, technical_admin):
    case.refresh_from_db()
    if case.status == "idea":
        create_review(
            use_case=case,
            actor=coordinator,
            data={
                "review_date": timezone.localdate(),
                "decision": "start_review",
                "new_status": "review",
                "rationale": "Synthetischen Intake fachlich prüfen",
            },
        )
        case.refresh_from_db()
    DecisionAssessment.objects.get_or_create(
        use_case=case,
        version=1,
        defaults=dict(
            assessed_by=coordinator,
            recommendation="approved",
            evidence_quality=1,
            evidence_recency=1,
            evidence_coverage=1,
            independent_review=1,
            assumptions_resolved=1,
        ),
    )
    GovernanceAssessment.objects.get_or_create(
        use_case=case,
        defaults=dict(
            assessment_date=timezone.localdate(), basis_version="TEST-189", result="no_flags"
        ),
    )
    return submit_approval_decision(
        use_case=case,
        actor=technical_admin,
        data={"decision_status": "approved", "rationale": "Unabhängige synthetische Fachprüfung"},
    )


def delivery_and_pilot(case, coordinator, client):
    case.refresh_from_db()
    case.technical_owner = coordinator
    case.metric_name = "Prozessdurchlaufzeit"
    case.metric_target = Decimal("3")
    case.metric_unit = "Tage"
    case.metric_direction = "lower"
    case.metric_measurement_method = "Median über alle Testvorgänge"
    case.planned_pilot_end = timezone.localdate() + timedelta(days=28)
    case.next_review_date = case.planned_pilot_end
    case.save()
    package = create_delivery_package(use_case=case, actor=coordinator)
    client.force_login(coordinator)
    assert client.post(reverse("delivery:package_mark_ready", args=[package.pk])).status_code == 302
    assert client.post(reverse("delivery:package_handover", args=[package.pk])).status_code == 302
    package.refresh_from_db()
    assert package.status == "handed_over"
    create_review(
        use_case=case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "pilot_start": timezone.localdate(),
            "decision": "start_pilot",
            "new_status": "pilot",
            "rationale": "Begrenzten synthetischen Pilot starten",
            "funding_status": "satisfied",
            "funding_evidence": "TEST-189-Freigabe, keine realen Mittel",
            "next_review_date": case.planned_pilot_end,
        },
    )
    case.refresh_from_db()
    assert case.status == "pilot"
    return package


def end(case, coordinator):
    return create_review(
        use_case=case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "decision": "end",
            "new_status": "ended",
            "rationale": "Test beenden; Geschäftswirkung ausdrücklich getrennt bewerten",
            "ending_reason": "Befristeter synthetischer Versuch abgeschlossen",
            "data_and_access_handling": "Testzugänge deaktiviert; synthetische Evidenz archiviert",
            "final_assessment": "Kein realer Nutzen- oder Kausalitätsnachweis",
        },
    )


def test_c_direct_ai_missing_baseline_unclear_end(
    owner,
    coordinator,
    technical_admin,
    business_unit,
    client,
):
    initiative = planned(owner)
    case = direct(owner, coordinator, business_unit)
    bind_initiative(initiative=initiative, artifact=case, actor=owner)
    approval = approve(case, coordinator, technical_admin)
    assert approval.outcome_snapshot["measurement_plan"]["use_case_history_id"]
    original = deepcopy(approval.outcome_snapshot)
    package = delivery_and_pilot(case, coordinator, client)
    assert case.metric_baseline is None
    assert package.business_context_snapshot["original"]["id"] == str(approval.pk)
    with pytest.raises(ValidationError):
        create_review(
            use_case=case,
            actor=coordinator,
            data={
                "review_date": timezone.localdate(),
                "decision": "go_live",
                "new_status": "operation",
                "rationale": "Keine erfundenen Messwerte",
                "funding_status": "satisfied",
                "funding_evidence": "TEST-189",
            },
        )
    review = save(
        owner,
        initiative,
        {
            "use_case": case,
            "effect_status": "unclear",
            "effect_reason": "Geschäftsergebnis nicht gemessen",
        },
    )
    assert not review.review_required and review.attribution == "unclear"
    closure = end(case, coordinator)
    assert closure.scale_readiness_snapshot["business_context"]["effect_status"] == "unclear"
    approval.refresh_from_db()
    assert approval.outcome_snapshot == original
    assert not ProcessAnalysis.objects.exists()


def test_b_actual_strategy_stops_at_unchanged_binding_gate(owner, tmp_path, monkeypatch, client):
    context = make_context(owner, tmp_path)
    analysis = analyze(owner, context, monkeypatch)
    result = materialize(owner, context[0], analysis)
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    client.force_login(owner)
    url = reverse("architecture:process_analysis_update", args=[process.pk])
    assert client.get(url).status_code == 200
    assert client.post(url, process_data(process)).status_code == 302
    assert client.get(url).status_code == 200
    assert not process.discovery_path_decisions.exists()
    option = SolutionOption(
        name="Organisatorische Klärung",
        option_type="organizational",
        description="Zuständigkeit menschlich klären; Nutzen und Kosten offen",
        expected_value="Hypothese; Potenzial noch ungeprüft",
    )
    assert (
        client.post(
            reverse("architecture:solution_option_create", args=[process.pk]), option_data(option)
        ).status_code
        == 302
    )
    initiative = planned(owner)
    bind_process(owner, process, path="strategic", initiative=initiative)
    with pytest.raises(ValidationError, match="Fokus"):
        select_preferred_solution(
            process_analysis=process,
            selected_option=process.solution_options.get(),
            actor=owner,
            rationale="Kein erfundenes Screening",
        )
    assert not process.solution_selection_decisions.exists()
    assert not initiative.use_cases.exists()
    assert not InitiativeImpactReview.objects.filter(initiative=initiative).exists()


def test_a_actual_discovery_to_ai_pilot_and_separate_business_review(
    owner,
    coordinator,
    technical_admin,
    tmp_path,
    monkeypatch,
    client,
):
    session, snapshot = _session_and_snapshot(owner=owner, tmp_path=tmp_path)
    responses = iter([_result(_draft()), _result(_verifier())])
    monkeypatch.setattr(architect_service, "_provider_call", lambda **_: next(responses))
    analysis = architect_service.execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    result = materialize_discovery_and_start_investigation(
        actor=owner,
        session_id=session.pk,
        analysis_id=analysis.pk,
        selected_stage_key="compare",
        expected_revision=session.revision,
    )
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert process.solution_options.count() == 0
    # Human interpretation of the synthetic source, not a prebuilt process/option fixture.
    process.diagnostic_observations = (
        "Synthetisches Interview: uneinheitliche Angebote, manueller Vergleich"
    )
    process.cause_hypotheses = "Formatunterschiede können Übertragungsaufwand verursachen"
    process.save()
    initiative = planned(owner)
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "business_outcome": "Termingerechte belastbare Beschaffungsentscheidungen",
            "contribution": "Angebotsvergleich im begrenzten Einkaufsbereich",
            "evaluation_criteria": "Mindestens 18/100 termingerechte Beschaffungsabschlüsse",
            "measurement_change_reason": "Synthetischen Einkaufsauftrag vor Auswahl präzisieren",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Prüfbaren begrenzten Einkaufsbeitrag bestätigen",
        expected_revision=initiative.revision,
    )
    bind_process(owner, process, initiative=initiative)
    for name, kind, description, effort in [
        (
            "Lieferantenformat vereinheitlichen",
            "organizational",
            "Lieferanten liefern einheitliche Vorlage; Einkauf prüft Adoption",
            "Schulung und Lieferantenumstellung; Durchsetzung unbekannt",
        ),
        (
            "Assistierter Angebotsvergleich",
            "assistant",
            "Assistenz extrahiert verschiedene Formate; Einkauf prüft jeden Vergleich",
            "Integration, Betrieb und menschliche Prüfung; Kosten unknown",
        ),
    ]:
        option = make_option(process, owner, name=name, option_type=kind, assessed=True)
        option.description = description
        option.expected_value = "Weniger Vergleichsaufwand; termingerechte Entscheidung prüfen"
        option.outcome_effect = "Weniger Übertragung könnte termingerechte Beschaffung unterstützen"
        option.effort_assessment = effort
        option.save()
    decision = confirm_diagnosis_and_select_solution(
        process_analysis=process,
        selected_option=process.solution_options.get(option_type="assistant"),
        actor=owner,
        confirmed_causes=process.cause_hypotheses,
        rationale="Test: Formate kurzfristig erschließen; Kostenunsicherheit akzeptiert",
        difference_reason="Lieferantenverhalten ändern gegenüber Extraktion bestehender Dokumente",
        uncertainty_reason="Lieferantenadoption ungesichert; Assistenzrisiken menschlich prüfen",
        diagnosis_basis="assumption",
        diagnosis_note="Fachliche Hypothese aus Interview, kein Kausalbeweis",
        expected_process_version=process.version,
    )
    case = create_use_case_from_selected_solution(decision=decision, actor=owner).use_case
    approve(case, coordinator, technical_admin)
    package = delivery_and_pilot(case, coordinator, client)
    case.metric_actual = Decimal("2")
    case.metric_measurement_period = "Vier Wochen, synthetisches Testprotokoll"
    case.metric_measurement_population = "Testvorgänge Einkaufsbereich"
    case.metric_measured_at = timezone.localdate()
    case.metric_evidence_url = "https://example.invalid/test-189-process"
    case.save()
    review = save(
        owner,
        initiative,
        finding(
            selection=decision,
            use_case=case,
            measurement_difference="Beschaffungsabschlüsse statt Prozessdurchlaufzeit",
        ),
    )
    assert not review.review_required and case.metric_result == "achieved"
    assert review.attribution == "unclear"
    assert package.business_context_snapshot["original"]["kind"] == "selection"
    closure = end(case, coordinator)
    assert closure.scale_readiness_snapshot["business_context"]["effect_status"] == "confirmed"


def test_multiple_process_contributions_keep_single_review_boundary(owner, business_unit):
    initiative = planned(owner)
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "business_outcome": "Termingerechte Beschaffungsabschlüsse",
            "contribution": "Angebotsvergleich und nachgelagerte Beschaffungsfreigabe",
            "evaluation_criteria": "18/100 termingerechte Abschlüsse im Testbereich",
            "measurement_change_reason": "Synthetischen Einkaufsbeitrag vorab abgrenzen",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Zwei eigene Beiträge zum selben Geschäftsergebnis",
        expected_revision=initiative.revision,
    )
    first = outcome_process(owner, business_unit)
    second_stage = ValueStreamStage.objects.create(
        value_stream=first.stage.value_stream, sequence=2, name="Beschaffung freigeben"
    )
    second = outcome_process(owner, business_unit, stage=second_stage)
    second.name = "Beschaffungsfreigabe"
    second.current_flow = "Einkauf legt Vergleich vor; Fachbereich bestätigt Freigabe"
    second.diagnostic_observations = "Synthetisch berichtete unklare Freigabeverantwortung"
    second.confirmed_causes = "Fachliche Hypothese: unklare Zuständigkeit erzeugt Rückfragen"
    second.save()
    for option in second.solution_options.all():
        option.description = (
            "Verantwortung und Vertretung im Fachbereich festlegen"
            if option.option_type == "organizational"
            else "Assistenz ordnet Freigabenachweise; Fachbereich entscheidet weiterhin"
        )
        option.outcome_effect = "Weniger Freigaberückfragen könnten Abschlüsse ermöglichen"
        option.save()
    decisions = []
    for process in [first, second]:
        bind_process(owner, process, initiative=initiative)
        decisions.append(select(owner, process))
    assert all(not decision.outcome_review_required for decision in decisions)
    review = save(
        owner,
        initiative,
        finding(
            selection=decisions[0],
            contribution_boundary=(
                "Vergleich und Freigabe teilen Ressourcen; Wechselwirkung nicht isoliert gemessen. "
                "Nur Vergleich strukturiert referenziert; kein separater ROI der Freigabe."
            ),
        ),
    )
    assert InitiativeImpactReview.objects.filter(initiative=initiative).count() == 1
    assert review.selection_id == decisions[0].pk
    assert decisions[1].process_analysis.initiative_id == initiative.pk
    assert not review.review_required
    assert "nicht isoliert" in review.contribution_boundary


def test_rsd_like_service_case_records_plan_and_honest_unclear(owner, comparison):
    initiative = planned(owner, comparison.initiative)
    decision = choose(comparison, owner, **QUALITY)
    review = save(
        owner,
        initiative,
        {
            "selection": decision,
            "process_measurement": "RSD-Test: Quellenregel eingeführt, Wirkung offen",
            "effect_status": "unclear",
            "effect_reason": "Buchungsvolumen und Servicequalität noch nicht gemessen",
            "criteria_assessment": "Geschäftskriterien unklar; kein Prozesszeit-ROI",
        },
    )
    assert not review.review_required
    assert review.criteria_snapshot["original"]["outcome"]["fields"]["measurement_method"]
    assert review.attribution == "unclear"


def test_new_binding_needs_plan_or_explicit_unknowns_but_draft_remains_free(owner, business_unit):
    process = outcome_process(owner, business_unit)
    initiative = confirmed(owner)
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "measurement_unknowns": "",
            "measurement_change_reason": "Offene Angaben noch nicht begründet",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Wirkannahme bleibt Hypothese",
        expected_revision=initiative.revision,
    )
    bind_process(owner, process, initiative=initiative)
    with pytest.raises(ValidationError, match="Messabsicht"):
        select(owner, process)
    assert not process.solution_selection_decisions.exists()
    assert initiative.measurement_method == ""
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "measurement_unknowns": "Zeitpunkt offen; vor externem Start mit Owner klären",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Offene Messabsicht bewusst akzeptiert",
        expected_revision=initiative.revision,
    )
    assert select(owner, process).outcome_snapshot["measurement_plan"]["state"] == "open"


@pytest.mark.parametrize("effect", ["confirmed", "refuted"])
def test_criteria_text_alone_is_not_business_measurement(owner, business_unit, effect):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    with pytest.raises(ValidationError, match="Messstand und Nachweis"):
        save(
            owner,
            initiative,
            finding(
                selection=selection,
                effect_status=effect,
                business_measurement="",
                business_evidence="",
            ),
        )
    assert (
        save(
            owner,
            initiative,
            {
                "selection": selection,
                "effect_status": "unclear",
                "effect_reason": "Geschäftsmessung fehlt",
            },
        ).attribution
        == "unclear"
    )


def test_saved_draft_criteria_text_is_never_presented_as_reviewed(owner, business_unit, client):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    save(owner, initiative, finding(selection=selection))
    save(owner, initiative, {"criteria_assessment": "Ungeprüfter neuer Abgleich"}, finalize=False)
    client.force_login(owner)
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "Ungeprüfter / historisch nicht erfasster Abgleich" in html
    assert "Geprüfter Abgleich:" not in html
