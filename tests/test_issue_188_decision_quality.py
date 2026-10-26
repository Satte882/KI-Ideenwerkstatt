"""Synthetic RSD-like service context: decision quality, not business success."""

from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process, outcome_process

from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import ProcessAnalysis, SolutionSelectionDecision
from ki_radar.architecture.solution_selection import (
    comparison_blockers,
    confirm_diagnosis_and_select_solution,
    select_preferred_solution,
)
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.outcome_contract import confirm_initiative, set_discovery_path
from ki_radar.use_cases.services import approval_check, create_use_case_from_selected_solution

pytestmark = pytest.mark.django_db

QUALITY = {
    "difference_reason": (
        "Organisieren: Reiseorganisation bestätigt Änderungen verbindlich an einer Stelle. "
        "Assistenz: Kundenservice erhält Quellen und Widerspruchshinweise "
        "zur menschlichen Prüfung. "
        "Beide sollen verlässliche Betreuung bei zusätzlichem Buchungsvolumen unterstützen."
    ),
    "uncertainty_reason": (
        "Adoption der Änderungsregel und laufender Prüfaufwand sind unbekannt. "
        "Die begrenzte Auswahl trägt eine zu prüfende Nutzenhypothese, keinen ROI-Nachweis."
    ),
    "diagnosis_basis": "assumption",
    "diagnosis_note": (
        "Synthetische fachliche Annahme: unklare Verbindlichkeit führt zu Rückfragen. "
        "Unabhängiger empirischer Ursachenbeweis und Geschäftswirkung stehen aus."
    ),
}


@pytest.fixture
def comparison(owner, business_unit):
    process = outcome_process(owner, business_unit)
    process.comparison_contract_version = 1
    process.name = "Synthetische RSD-nahe Klärung von Leistungs- und Transferfragen"
    process.scope_start = process.trigger = "Kundenfrage zur gebuchten Leistung"
    process.scope_end = process.outcome = "Fachlich verantwortete Auskunft mit Quelle"
    process.current_flow = "Buchungsmaske, gemeinsames Postfach, Rückfrage bei Reiseorganisation"
    process.roles = "Kundenservice und Reiseorganisation"
    process.systems = "Buchungsmaske und gemeinsames Postfach; Produktnamen unbekannt"
    process.data_objects = "Buchungsnotiz und Änderungsnachricht"
    process.bottlenecks = process.diagnostic_observations = (
        "Synthetischer berichteter Ablauf aus issue133_methodology/A/01_case.md: "
        "Kundenservice prüft mehrere Quellen und fragt bei Unklarheit nach."
    )
    process.cause_hypotheses = process.confirmed_causes = (
        "Für diesen Test fachlich angenommene, nicht empirisch bewiesene Ursache: "
        "Verbindlichkeit von Änderungsangaben ist unklar."
    )
    process.baseline_metrics = ""
    process.save()
    stream = process.stage.value_stream
    stream.name = "Synthetische Reisebuchung bis Betreuung"
    stream.trigger = "Buchung und Rückfrage"
    stream.outcome = "Verlässlich betreuter Kunde"
    stream.scope_in = "Auskünfte zu gebuchten Leistungen"
    stream.save()
    process.stage.name = "Leistungsfragen klären"
    process.stage.save()
    focus = stream.focus
    focus.business_domain = "customer_service"
    focus.capability = "Leistungsfragen klären"
    focus.save()
    initiative = save_initiative(
        actor=owner,
        data={
            "title": "Synthetischer RSD-naher Servicefall; keine realen Unternehmensdaten",
            "business_outcome": "Mehr Buchungen mit verlässlicher Betreuung bewältigen",
            "contribution": "Quellenklärung im Kundenservice vereinfachen",
            "impact_hypothesis": (
                "Weniger Rückfragen könnten Kapazität für zusätzliche Buchungen schaffen."
            ),
            "evaluation_criteria": (
                "Buchungsvolumen und Servicequalität prüfen; Prozesszeit ist kein Nutzenbeweis."
            ),
            "outcome_owner": "Kundenserviceleitung",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Synthetische Hypothese zur Prüfung, keine reale Messung",
        expected_revision=initiative.revision,
    )
    bind_process(owner, process, initiative=initiative)
    for option in process.solution_options.all():
        option.description = (
            "Reiseorganisation bestätigt Änderungen verbindlich in einer gemeinsamen Quelle."
            if option.option_type == "organizational"
            else "Assistenz zeigt Quellen und Widersprüche; Service verantwortet die Auskunft."
        )
        option.outcome_effect = (
            "Weniger Rückfragen könnten Kapazität für zusätzliche Buchungen schaffen; "
            "Geschäftswirkung ist eine offene Hypothese."
        )
        option.expected_value = (
            "Weniger Such- und Klärarbeit; verlässliche Auskunft noch zu prüfen."
        )
        option.bottleneck_coverage = (
            "Unklare Verbindlichkeit adressieren; Ursachenfit bleibt bedingt."
        )
        option.data_requirements = "Buchungsnotiz und Änderungsnachricht mit Quellenstatus"
        option.application_impact = "Quellenanzeige am bestehenden Arbeitsplatz"
        option.integration_impact = "Zugriff auf Buchungsmaske und gemeinsames Postfach ungeklärt"
        option.technology_constraints = "Keine automatische verbindliche Kundenauskunft"
        option.risks = "Falsche Verbindlichkeitsannahme; Servicequalität darf nicht sinken"
        option.architecture_fit = "Synthetische Hypothese; Referenz: issue133_methodology/A und B"
        option.effort_assessment = (
            "Einmalig: Änderungsregel einführen; laufend: Quellenpflege; organisatorisch: "
            "Schulung und Zuständigkeiten. Kosten unknown; Adoption unbewiesen."
            if option.option_type == "organizational"
            else "Einmalig: Integration und Test; laufend: Betrieb und menschliche Prüfung; "
            "organisatorisch: Prüferschulung. Kosten unknown; Prüfaufwand nicht gemessen."
        )
        option.save()
    return process


def choose(process, owner, *, ai=False, **quality):
    return select_preferred_solution(
        process_analysis=process,
        selected_option=process.solution_options.get(
            option_type="assistant" if ai else "organizational"
        ),
        rationale=(
            "Assistenz bevorzugt: vorhandene Quellen werden am Servicearbeitsplatz erschlossen; "
            "menschliche Prüfung und unbekannte Betriebskosten bewusst akzeptiert."
            if ai
            else "Organisatorische Regel bevorzugt: Verbindlichkeit direkt an der Quelle klären; "
            "Adoption und Schulungsaufwand bewusst akzeptiert."
        ),
        actor=owner,
        expected_process_version=process.version,
        **quality,
    )


@pytest.mark.parametrize("ai", [True, False])
def test_coherent_human_choice_freezes_common_effort_and_qualified_diagnosis(comparison, owner, ai):
    decision = choose(comparison, owner, ai=ai, **QUALITY)
    assert decision.selected_option.starts_ai_use_case == ai
    assert decision.quality_snapshot["difference_reason"] == QUALITY["difference_reason"]
    assert decision.quality_snapshot["assessment"] == "human_reasoned_not_independently_verified"
    assert decision.diagnosis_snapshot["confirmation_basis"]["basis"] == "assumption"
    assert all("unknown" in row["effort_assessment"] for row in decision.comparison_snapshot)
    assert not decision.outcome_review_required
    frozen = deepcopy(decision.comparison_snapshot)
    if ai:
        result = create_use_case_from_selected_solution(decision=decision, actor=owner)
        assert result.use_case.initiative_id == comparison.initiative_id
    option = comparison.solution_options.exclude(pk=decision.selected_option_id).get()
    option.effort_assessment = "Andere organisatorische Umstellung; Zusatzaufwand unbekannt."
    option.save()
    decision.refresh_from_db()
    assert decision.outcome_review_required
    assert decision.comparison_snapshot == frozen
    if ai:
        with pytest.raises(ValidationError, match="geändert"):
            create_use_case_from_selected_solution(decision=decision, actor=owner)
        assert (
            "Aktuelle menschliche Lösungsentscheidung der Herkunft"
            in approval_check(
                use_case=result.use_case, target_status="approved", actor=owner
            ).blockers
        )


def test_distinct_ai_levers_do_not_require_a_non_ai_or_status_quo_option(comparison, owner):
    options = list(comparison.solution_options.order_by("name"))
    for option, description in zip(
        options,
        (
            "Assistenz erschließt Quellen für die Suche am Servicearbeitsplatz.",
            "Assistenz markiert widersprüchliche Änderungen für die verantwortliche Klärung.",
        ),
        strict=True,
    ):
        option.option_type = "assistant"
        option.description = description
        option.effort_assessment = (
            "Einmalig Integration, laufend Modellbetrieb; organisatorisch Prüfschulung. "
            "Kosten und Prüfaufwand unknown, menschlich bewusst zu prüfen."
        )
        option.save()
    decision = select_preferred_solution(
        process_analysis=comparison,
        selected_option=options[0],
        actor=owner,
        rationale="Quellensuche priorisiert; Konfliktprüfung als Alternative betrachtet.",
        **{
            **QUALITY,
            "difference_reason": "Quellensuche gegenüber gezielter Widerspruchsprüfung; "
            "unterschiedliche Hebel werden fachlich angenommen, nicht automatisch bewiesen.",
        },
    )
    assert all(row["option_type"] == "assistant" for row in decision.comparison_snapshot)


@pytest.mark.parametrize("field", list(QUALITY))
def test_missing_human_explanation_cannot_bind(comparison, owner, field):
    data = {**QUALITY, field: " "}
    with pytest.raises(ValidationError):
        choose(comparison, owner, **data)
    assert not SolutionSelectionDecision.objects.exists()
    assert not comparison.solution_options.filter(recommendation="preferred").exists()


@pytest.mark.parametrize("kind", ["organizational", "assistant"])
def test_effort_is_binding_only_for_both_solution_classes(comparison, owner, kind):
    option = comparison.solution_options.get(option_type=kind)
    option.effort_assessment = ""
    option.save()
    assert (
        option.comparison_complete
    )  # Existing assessment and frozen generator contracts unchanged.
    assert any(
        option.name in reason and "Aufwand" in reason
        for reason in comparison_blockers(
            list(comparison.solution_options.all()), process_analysis=comparison
        )
    )
    with pytest.raises(ValidationError, match="Aufwand"):
        choose(comparison, owner, **QUALITY)


def test_renamed_ai_copies_do_not_prove_a_distinct_lever(comparison, owner):
    first, second = list(comparison.solution_options.order_by("name"))
    for key in (
        "description",
        "expected_value",
        "bottleneck_coverage",
        "risks",
        "architecture_fit",
    ):
        setattr(second, key, getattr(first, key).upper())
    first.option_type = second.option_type = "assistant"
    first.save()
    second.save()
    with pytest.raises(ValidationError, match="umbenannte"):
        select_preferred_solution(
            process_analysis=comparison,
            selected_option=first,
            actor=owner,
            rationale="Keine automatische wirtschaftliche Siegerbehauptung",
            **QUALITY,
        )
    assert not SolutionSelectionDecision.objects.exists()


def test_problem_diagnosis_confirmation_is_atomic_with_quality_check(comparison, owner):
    comparison.confirmed_causes = ""
    comparison.save()
    version = comparison.version
    with pytest.raises(ValidationError):
        confirm_diagnosis_and_select_solution(
            process_analysis=comparison,
            selected_option=comparison.solution_options.first(),
            confirmed_causes="Fachliche Annahme",
            rationale="Begründung",
            expected_process_version=version,
            actor=owner,
        )
    comparison.refresh_from_db()
    assert comparison.confirmed_causes == "" and comparison.version == version
    assert not comparison.validations.exists()
    decision = confirm_diagnosis_and_select_solution(
        process_analysis=comparison,
        selected_option=comparison.solution_options.first(),
        confirmed_causes="Fachliche Annahme",
        rationale="Begrenzter Vergleich unter Unsicherheit",
        expected_process_version=version,
        actor=owner,
        **QUALITY,
    )
    assert decision.diagnosis_snapshot["confirmation_basis"]["basis"] == "assumption"
    assert decision.diagnosis_snapshot["validation"]["note"]


def test_strategic_choice_needs_no_fictional_cause_or_new_screening_bypass(comparison, owner):
    comparison.confirmed_causes = comparison.diagnostic_observations = ""
    comparison.save()
    set_discovery_path(
        process=comparison,
        actor=owner,
        path="strategic",
        origin_basis="Synthetischer strategischer Untersuchungsauftrag",
        change_reason="Neuer Auftrag",
        strategic_potential="Zusätzliches Buchungsvolumen mit verlässlicher Betreuung",
        validation_step="Akzeptanz der verbindlichen Änderungsregel untersuchen",
    )
    data = {key: QUALITY[key] for key in ("difference_reason", "uncertainty_reason")}
    decision = choose(comparison, owner, **data)
    assert decision.diagnosis_snapshot["confirmed_causes"] == ""
    assert decision.diagnosis_snapshot["confirmation_basis"]["basis"] == "not_required"
    focus = comparison.stage.value_stream.focus
    focus.status = "candidate"
    focus.save()
    with pytest.raises(ValidationError, match="Fokusentscheidung"):
        choose(comparison, owner, **data)


def test_evidence_classification_keeps_source_and_limits_without_claiming_proof(comparison, owner):
    data = {
        **QUALITY,
        "diagnosis_basis": "evidence",
        "diagnosis_note": "Synthetischer Quellenverweis: Prozessbeobachtung A; keine Kausalstudie.",
    }
    decision = choose(comparison, owner, **data)
    assert decision.diagnosis_snapshot["confirmation_basis"]["note"] == data["diagnosis_note"]
    assert "Grenzen" in decision.diagnosis_snapshot["confirmation_basis"]["label"]


def test_regular_view_preserves_input_and_renders_auditable_quality(comparison, owner, client):
    client.force_login(owner)
    url = reverse("architecture:solution_option_compare", args=[comparison.pk])
    base = {
        "selected_option": comparison.solution_options.get(option_type="organizational").pk,
        "process_version": comparison.version,
        "rationale": "Begrenzte menschliche Auswahl",
    }
    response = client.post(url, {**base, **QUALITY, "uncertainty_reason": ""})
    assert response.status_code == 200
    assert response.context["form"].errors["uncertainty_reason"]
    assert QUALITY["difference_reason"] in response.content.decode()
    assert not SolutionSelectionDecision.objects.exists()
    response = client.post(url, {**base, **QUALITY})
    assert response.status_code == 302
    html = client.get(url).content.decode()
    assert "Fachliche Ursachenbestätigung ist kein unabhängiger empirischer Beweis" in html
    assert "Menschlich begründeter Vergleich" in html
    assert "Kosten unknown" not in html  # Existing display translates unknown, storage does not.
    assert "Unbekannt / noch zu klären" in html


def test_combined_view_forwards_quality(comparison, owner, client):
    comparison.confirmed_causes = ""
    comparison.save()
    client.force_login(owner)
    response = client.post(
        reverse("architecture:solution_option_compare", args=[comparison.pk]),
        {
            "selected_option": comparison.solution_options.get(option_type="organizational").pk,
            "process_version": comparison.version,
            "confirmed_causes": "Synthetische fachliche Annahme",
            "rationale": "Vergleich unter offener Evidenz",
            **QUALITY,
        },
    )
    assert response.status_code == 302
    assert SolutionSelectionDecision.objects.get().quality_snapshot["version"] == 1


def test_option_form_keeps_unknowns_and_blank_drafts(comparison, owner):
    option = comparison.solution_options.first()
    data = {field: getattr(option, field) for field in SolutionOptionForm._meta.fields}
    data.update(effort_assessment="", evaluation_status="draft")
    form = SolutionOptionForm(data=data, instance=option, process_analysis=comparison)
    assert form.is_valid(), form.errors
    form.save()
    data["effort_assessment"] = (
        "Einmalig unknown; laufend unknown; Schulung unknown, erst untersuchen."
    )
    form = SolutionOptionForm(data=data, instance=option, process_analysis=comparison)
    assert form.is_valid(), form.errors
    assert form.save().effort_assessment == data["effort_assessment"]


def test_rights_revisions_and_immutable_decisions_stay_enforced(comparison, owner, reader):
    with pytest.raises(ValidationError, match="Berechtigung"):
        choose(comparison, reader, **QUALITY)
    stale = comparison.version
    comparison.version += 1
    comparison.save()
    with pytest.raises(ValidationError, match="geändert"):
        select_preferred_solution(
            process_analysis=comparison,
            selected_option=comparison.solution_options.first(),
            actor=owner,
            rationale="Stale",
            expected_process_version=stale,
            **QUALITY,
        )
    decision = choose(comparison, owner, **QUALITY)
    with pytest.raises(ValidationError, match="unveränderlich"):
        decision.save()
    with pytest.raises(ValidationError):
        SolutionSelectionDecision.objects.filter(pk=decision.pk).update(quality_snapshot={})
    with pytest.raises(ValidationError):
        SolutionSelectionDecision.objects.bulk_create(
            [
                SolutionSelectionDecision(
                    process_analysis=comparison,
                    selected_option=comparison.solution_options.first(),
                    rationale="Bypass",
                    quality_snapshot={"version": 1},
                )
            ]
        )


@pytest.mark.parametrize("method", ["save", "update", "bulk_update"])
def test_new_comparison_contract_cannot_be_downgraded(comparison, method):
    with pytest.raises(ValidationError, match=r"[Kk]ohorte|Entscheidungsfelder"):
        if method == "save":
            comparison.comparison_contract_version = 0
            comparison.save()
        elif method == "update":
            ProcessAnalysis.objects.filter(pk=comparison.pk).update(comparison_contract_version=0)
        else:
            comparison.comparison_contract_version = 0
            ProcessAnalysis.objects.bulk_update([comparison], ["comparison_contract_version"])


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_older_cohort_and_snapshots(owner, business_unit):
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor

    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    target = [("architecture", "0025_allow_unknown_draft_diagnosis")]
    executor.migrate(target)
    try:
        apps = executor.loader.project_state(target).apps
        stream = apps.get_model("architecture", "ValueStream").objects.create(
            name="Bestand", business_unit_id=business_unit.pk
        )
        stage = apps.get_model("architecture", "ValueStreamStage").objects.create(
            value_stream=stream, sequence=1, name="Bestand"
        )
        process = apps.get_model("architecture", "ProcessAnalysis").objects.create(
            stage=stage, name="Bestand", outcome_contract_version=1
        )
        option = apps.get_model("architecture", "SolutionOption").objects.create(
            process_analysis=process, name="Bestand", option_type="organizational"
        )
        decision = apps.get_model("architecture", "SolutionSelectionDecision").objects.create(
            process_analysis=process,
            selected_option=option,
            rationale="Historisch",
            comparison_snapshot=[{"id": str(option.pk), "expected_value": "Historischer Stand"}],
        )
        frozen = deepcopy(decision.comparison_snapshot)
    finally:
        MigrationExecutor(connection).migrate(leaves)
    old = ProcessAnalysis.objects.get(pk=process.pk)
    assert old.comparison_contract_version == 0 and old.outcome_contract_version == 1
    decision = SolutionSelectionDecision.objects.get(pk=decision.pk)
    assert decision.comparison_snapshot == frozen and decision.quality_snapshot == {}
    assert ProcessAnalysis._meta.get_field("comparison_contract_version").default == 1
