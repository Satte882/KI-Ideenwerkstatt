"""Synthetic B acceptance: real routes, frozen sources, no model or business claims."""

from copy import deepcopy
from hashlib import sha256

import pytest
from django.core.exceptions import ValidationError
from django.forms.models import model_to_dict
from django.urls import reverse
from django.utils import timezone
from test_issue_146_outcome_contract import bind_process, outcome_process
from test_issue_178_strategic_discovery import analyze, make_context, materialize
from test_issue_185_strategic_drafts import option_data, process_data

from ki_radar.accelerator.models import CaptureSession
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import ProcessAnalysis, SolutionOption
from ki_radar.architecture.solution_selection import (
    focus_readiness_blockers,
    select_preferred_solution,
)
from ki_radar.architecture.strategic_exploration import strategic_binding_basis
from ki_radar.use_cases.impact_review_views import ImpactReviewForm
from ki_radar.use_cases.impact_reviews import save_impact_review
from ki_radar.use_cases.initiative_views import InitiativeForm
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.models import UseCase
from ki_radar.use_cases.outcome_contract import confirm_initiative, set_discovery_path
from ki_radar.use_cases.workflow import build_process_analysis_journey

pytestmark = pytest.mark.django_db
QUALITY = {
    "difference_reason": "Verbindlichkeit an einer Quelle organisatorisch klären gegenüber "
    "Assistenz zur Anzeige von Quellen und Widersprüchen; beide adressieren Servicequalität.",
    "uncertainty_reason": "Globales Screening offen: Potenzial, Datenzugang und Aufwand unbekannt. "
    "Begrenzter menschlicher Rahmen statt erfundener Ratings. Non-KI klärt Verbindlichkeit "
    "direkt; Adoption, Schulungsaufwand und Kosten unbewiesen. Nach vier Wochen prüfen.",
}


@pytest.fixture
def exploration(owner, tmp_path, monkeypatch, client):
    context = make_context(owner, tmp_path)
    analysis = analyze(owner, context, monkeypatch)
    result = materialize(owner, context[0], analysis)
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert not process.initiative_id and not process.discovery_path_decisions.exists()
    client.force_login(owner)
    url = reverse("architecture:process_analysis_update", args=[process.pk])
    assert client.get(url).status_code == 200
    assert client.post(url, process_data(process)).status_code == 302
    assert client.get(url).status_code == 200
    assert not process.discovery_path_decisions.exists()
    return process


def bind(owner, process):
    initiative = save_initiative(
        actor=owner,
        data={
            "title": "Synthetischer B-Fall: tragfähige Buchungen und verlässliche Betreuung",
            "business_outcome": "Mehr tragfähige Buchungen bei verlässlicher Betreuung",
            "contribution": "Begrenzte Klärung von Kundenanfragen bis zur verantworteten Antwort",
            "impact_hypothesis": "Klare Verbindlichkeit könnte Rückfragen und Aufwand senken.",
            "evaluation_criteria": "Buchungsvolumen und Servicequalität getrennt von Prozesszeit",
            "outcome_owner": "Serviceleitung",
            "measurement_method": "Buchungs- und Qualitätsprotokolle im begrenzten Servicebereich",
            "measurement_period": "Vier Wochen nach organisatorischer Umstellung",
            "measurement_population": "Anfragen im menschlich gewählten Untersuchungsrahmen",
            "measurement_reference": "Vergleich mit Vorperiode; Referenzwerte noch unbekannt",
            "measurement_unknowns": "Ist-Werte fehlen; Owner klärt Vergleichbarkeit vor Auswertung",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Begrenzte prüfbare Hypothese annehmen; keine gemessene Wirkung",
        expected_revision=initiative.revision,
    )
    bind_process(owner, process, path="strategic", initiative=initiative)
    return initiative


def options(owner, process, client):
    client.force_login(owner)
    made = []
    for kind, name, description in [
        (
            "organizational",
            "Verbindliche Quelle und Zuständigkeit",
            "Reiseorganisation bestätigt Änderungen an einer verantworteten Quelle",
        ),
        (
            "assistant",
            "Assistierte Quellenanzeige",
            "Assistenz zeigt Quellen und Widersprüche; Service prüft Verbindlichkeit",
        ),
    ]:
        draft = SolutionOption(
            name=name,
            option_type=kind,
            description=description,
            expected_value="Weniger Klärarbeit könnte Servicekapazität schaffen; Wirkung offen",
        )
        response = client.post(
            reverse("architecture:solution_option_create", args=[process.pk]), option_data(draft)
        )
        assert response.status_code == 302, response.context["form"].errors
        option = process.solution_options.get(name=name)
        data = option_data(option)
        data.update(
            evaluation_status="assessed",
            feasibility="medium",
            integration_effort="medium",
            time_to_value="unknown",
            bottleneck_coverage="Strategisches Servicepotenzial; kein Engpassbeleg",
            data_requirements="Buchungsnotiz und Änderungsnachricht; Datenzugang ungeklärt",
            application_impact="Bestehender Servicearbeitsplatz",
            integration_impact="Quellenzugriff klären",
            technology_constraints="Keine automatische verbindliche Kundenzusage",
            architecture_fit="Menschliche Zuständigkeit bleibt führend; Anschlussfähigkeit prüfen",
            risks="Adoption und Verbindlichkeitsfehler; Geschäftswirkung unbekannt",
            effort_assessment="Einmalig: Umstellung; laufend: Quellenpflege bzw. Betrieb; "
            "organisatorisch: Schulung. Beträge unknown; keine kostenfreie Alternative",
            outcome_effect="Weniger Rückfragen könnten zusätzliche Buchungen ermöglichen",
        )
        response = client.post(
            reverse("architecture:solution_option_update", args=[option.pk]), data
        )
        assert response.status_code == 302, response.context["form"].errors
        option.refresh_from_db()
        made.append(option)
    return made


def choose(owner, process, option, **changes):
    return select_preferred_solution(
        process_analysis=process,
        selected_option=option,
        actor=owner,
        expected_process_version=process.version,
        rationale="Non-KI klärt Verbindlichkeit; technische Anzeige schafft keine Autorität. "
        "Begrenzte Umstellung mit menschlicher Prüfung und bewusst offenen Kosten.",
        **(QUALITY | changes),
    )


def assert_unknowns(process):
    process.refresh_from_db()
    assert process.baseline_metrics == process.confirmed_causes == process.bottlenecks == ""
    focus = ValueStreamFocus.objects.get(value_stream=process.stage.value_stream)
    assert focus.status == "candidate"
    assert all(
        not getattr(focus, field)
        for field in (
            "strategic_impact",
            "economic_potential",
            "pain_intensity",
            "data_accessibility",
            "change_effort",
        )
    )


def test_complete_b_routes_external_non_ai_record_review_and_honest_completion(
    owner,
    exploration,
    client,
    tmp_path,
):
    process = exploration
    # Immediate draft options precede any later path/outcome confirmation.
    alternatives = options(owner, process, client)
    assert not process.discovery_path_decisions.exists()
    initiative = bind(owner, process)
    url = reverse("architecture:solution_option_compare", args=[process.pk])
    page = client.get(url)
    assert not page.context["selection_blocked"]
    assert "Offene globale Screeningfragen" in page.content.decode()
    data = {
        "selected_option": str(alternatives[0].pk),
        "process_version": process.version,
        "rationale": "Verbindlichkeit direkt organisatorisch klären; Adoption bewusst prüfen",
        **QUALITY,
    }
    assert client.post(url, data).status_code == 302
    decision = process.solution_selection_decisions.get()
    frozen = deepcopy(decision.outcome_snapshot)
    assert frozen["strategic_binding"]["scope"]["human_scope"]["explicit_strategic"]
    assert frozen["strategic_binding"]["open_screening_fields"]
    assert (
        decision.quality_snapshot["strategic_screening_acceptance"] == QUALITY["uncertainty_reason"]
    )
    assert not decision.outcome_review_required
    assert_unknowns(process)
    assert not UseCase.objects.exists()
    assert build_process_analysis_journey(process, owner).next_action.key == "impact"

    # Deterministic stand-in for a human-owned external organizational rollout,
    # explicitly synthetic, not a claimed intervention at a real company.
    rollout_at = timezone.now()
    external_record = tmp_path / "synthetic_external_rollout.md"
    external_record.write_text(
        "SYNTHETISCHER EXTERNER UMSETZUNGSBELEG - kein realer Unternehmensvorgang.\n"
        f"Entscheidung {decision.pk}; Umsetzung {rollout_at.isoformat()}; Serviceleitung.\n"
        "Verantwortete Quelle und Vertretung benannt; Änderung im Testteam erklärt.\n"
        "Abnahme: Testanfrage mit Quellenverantwortung beantwortet.\n"
        "Rückfall: bisherige Rückfrage; Buchungs-/Qualitätsmessung noch ausstehend.\n",
        encoding="utf-8",
    )
    digest = sha256(external_record.read_bytes()).hexdigest()
    assert rollout_at >= decision.decided_at
    review_url = reverse("use_cases:initiative_impact", args=[initiative.pk])
    data = {name: "" for name in ImpactReviewForm.Meta.fields}
    initiative.refresh_from_db()
    data.update(
        selection=decision.pk,
        process_result="unknown",
        attribution="unclear",
        process_measurement=f"Synthetische externe Umstellung: {external_record.name}; "
        f"SHA256 {digest}. Kein gemessener Prozessnutzen.",
        criteria_assessment="Geschäftskriterien nicht beurteilbar; Messung fehlt",
        assessment_basis="original",
        effect_status="unclear",
        effect_reason="Organisatorische Umstellung dokumentiert; Buchungswirkung nicht gemessen",
        attribution_reason="Keine kausale Zuordnung ohne Geschäftsmessung und Vergleich",
        expected_revision=initiative.revision,
        action="review",
    )
    assert client.post(review_url, data).status_code == 302
    initiative.refresh_from_db()
    review = initiative.impact_review
    assert not review.review_required and review.attribution == "unclear"
    assert review.criteria_snapshot["original"]["id"] == decision.pk
    assert review.criteria_snapshot["original"]["outcome"] == frozen
    form_data = model_to_dict(initiative, fields=InitiativeForm.Meta.fields)
    form_data = {key: value if value is not None else "" for key, value in form_data.items()}
    form_data.update(status="completed", expected_revision=initiative.revision)
    assert client.post(initiative.get_absolute_url(), form_data).status_code == 302
    initiative.refresh_from_db()
    review.refresh_from_db()
    assert initiative.status == "completed" and initiative.effect_status == "unclear"
    assert not review.review_required
    assert build_process_analysis_journey(process, owner).next_action is None
    decision.refresh_from_db()
    assert decision.outcome_snapshot == frozen
    assert_unknowns(process)
    assert not UseCase.objects.exists()


@pytest.mark.parametrize(
    "missing",
    [
        "provenance",
        "path",
        "outcome",
        "confirmation",
        "deferred",
        "not_selected",
        "selected_incomplete",
    ],
)
def test_missing_strategic_basis_never_replaces_global_gate(owner, exploration, client, missing):
    process = exploration
    initiative = bind(owner, process)
    alternatives = options(owner, process, client)
    if missing == "provenance":
        process.source_snapshot = {}
        process.save()
    elif missing == "path":
        set_discovery_path(
            process=process,
            actor=owner,
            path="problem",
            origin_basis="Neuer Befund",
            change_reason="Bewusste Umordnung",
        )
    elif missing == "outcome":
        initiative = save_initiative(
            actor=owner, initiative=initiative, data={"business_outcome": ""}
        )
    elif missing == "confirmation":
        save_initiative(
            actor=owner, initiative=initiative, data={"impact_hypothesis": "Andere Hypothese"}
        )
    else:
        focus = process.stage.value_stream.focus
        focus.status = "selected" if missing == "selected_incomplete" else missing
        focus.save()
    process.refresh_from_db()
    assert not strategic_binding_basis(process)
    with pytest.raises(ValidationError):
        choose(owner, process, alternatives[0])
    assert not process.solution_selection_decisions.exists()


@pytest.mark.parametrize("field", ["difference_reason", "uncertainty_reason"])
def test_human_comparison_and_unknown_acceptance_cannot_be_omitted(
    owner, exploration, client, field
):
    bind(owner, exploration)
    alternatives = options(owner, exploration, client)
    with pytest.raises(ValidationError, match="begründet"):
        choose(owner, exploration, alternatives[0], **{field: ""})
    client.force_login(owner)
    data = {
        "selected_option": str(alternatives[0].pk),
        "process_version": exploration.version,
        "rationale": "Eingabe behalten",
        **QUALITY,
        field: "",
    }
    response = client.post(
        reverse("architecture:solution_option_compare", args=[exploration.pk]), data
    )
    assert response.status_code == 200 and field in response.context["form"].errors
    assert response.context["form"]["rationale"].value() == "Eingabe behalten"
    assert not exploration.solution_selection_decisions.exists()


@pytest.mark.parametrize("role", ["reader", "other_owner"])
def test_selection_permission_unchanged(owner, exploration, client, request, role):
    bind(owner, exploration)
    alternatives = options(owner, exploration, client)
    actor = request.getfixturevalue(role)
    with pytest.raises(ValidationError):
        choose(actor, exploration, alternatives[0])
    client.force_login(actor)
    assert (
        client.post(
            reverse("architecture:solution_option_compare", args=[exploration.pk]), {}
        ).status_code
        == 403
    )


def test_scope_retention_metadata_and_material_changes_share_freshness(owner, exploration, client):
    initiative = bind(owner, exploration)
    alternatives = options(owner, exploration, client)
    decision = choose(owner, exploration, alternatives[0])
    frozen = deepcopy(decision.outcome_snapshot)
    CaptureSession.objects.all().delete()
    assert not decision.outcome_review_required
    save_initiative(actor=owner, initiative=initiative, data={"title": "Nur anderer Titel"})
    decision.refresh_from_db()
    assert not decision.outcome_review_required
    focus = exploration.stage.value_stream.focus
    focus.status = "deferred"
    focus.save()
    decision.refresh_from_db()
    assert decision.outcome_review_required
    assert decision.outcome_snapshot == frozen


def test_problem_and_legacy_keep_global_screening_gate(owner, business_unit):
    process = outcome_process(owner, business_unit)
    bind_process(owner, process)
    focus = process.stage.value_stream.focus
    focus.status = "candidate"
    focus.save()
    assert focus_readiness_blockers(process)
    assert not strategic_binding_basis(process)
    # The legacy-cohort constructor in the selection UX helper remains unchanged.
    from test_solution_selection_ux import make_process

    legacy = make_process(owner, business_unit)
    legacy.stage.value_stream.focus.status = "candidate"
    legacy.stage.value_stream.focus.save()
    assert not legacy.outcome_contract_version and not legacy.comparison_contract_version
    assert focus_readiness_blockers(legacy)


def test_optimistic_process_conflict_preserved(owner, exploration, client):
    bind(owner, exploration)
    alternatives = options(owner, exploration, client)
    with pytest.raises(ValidationError, match="geändert"):
        select_preferred_solution(
            process_analysis=exploration,
            selected_option=alternatives[0],
            actor=owner,
            rationale="Veralteter Stand",
            expected_process_version=exploration.version - 1,
            **QUALITY,
        )
    assert not exploration.solution_selection_decisions.exists()


def test_legacy_strategic_materialization_does_not_gain_binding_exception(
    owner,
    tmp_path,
    monkeypatch,
    client,
):
    # Simulate construction in the historical cohort; never downgrade a stored process.
    monkeypatch.setattr(
        ProcessAnalysis._meta.get_field("comparison_contract_version"), "default", 0
    )
    context = make_context(owner, tmp_path)
    result = materialize(owner, context[0], analyze(owner, context, monkeypatch))
    process = ProcessAnalysis.objects.get(pk=result.process_analysis_id)
    assert not process.comparison_contract_version
    bind(owner, process)
    alternatives = options(owner, process, client)
    assert not strategic_binding_basis(process)
    with pytest.raises(ValidationError, match="Fokusentscheidung"):
        choose(owner, process, alternatives[0])


def test_partial_screening_knowledge_requires_new_interpretation(owner, exploration, client):
    initiative = bind(owner, exploration)
    alternatives = options(owner, exploration, client)
    decision = choose(owner, exploration, alternatives[0])
    initiative.refresh_from_db()
    review = save_impact_review(
        initiative=initiative,
        actor=owner,
        expected_revision=initiative.revision,
        data={"selection": decision, "effect_status": "unclear", "effect_reason": "Messung offen"},
        finalize=True,
    )
    assert not review.review_required
    focus = ValueStreamFocus.objects.get(value_stream=exploration.stage.value_stream)
    focus.strategic_impact = "high"
    focus.save()
    review.refresh_from_db()
    assert review.review_required
    assert (
        decision.outcome_snapshot["strategic_binding"]["screening_values"]["strategic_impact"] == ""
    )


def test_real_scope_without_confirmed_phase_cannot_bind(owner, exploration, client):
    from test_issue_189_measurement_plan import planned

    from ki_radar.use_cases.initiatives import bind_initiative

    initiative = planned(owner)
    bind_initiative(initiative=initiative, artifact=exploration, actor=owner)
    exploration.refresh_from_db()
    set_discovery_path(
        process=exploration,
        actor=owner,
        path="strategic",
        origin_basis="Menschlicher Rahmen",
        strategic_potential="Servicekapazität prüfen",
        validation_step="Begrenzte organisatorische Umstellung prüfen",
    )
    alternatives = options(owner, exploration, client)
    assert not strategic_binding_basis(exploration)
    with pytest.raises(ValidationError, match="Vorhabensfokus"):
        choose(owner, exploration, alternatives[0])
