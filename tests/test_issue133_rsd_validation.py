"""Scenario A: real Django views, no fabricated model responses or approvals.

Run via scripts/validate_rsd_issue133.py to prohibit network access process-wide.
RSD_REPORT_DIR optionally exports the observed request/response/state transcript.
"""

import copy
import json
import os
from pathlib import Path

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse

from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.delivery.models import DeliveryPackage
from ki_radar.reviews.models import Review
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.models import UseCase

INITIAL = (
    "Wenn jemand wegen seiner gebuchten Reise anruft, suche ich oft erst in der Buchung "
    "und dann noch in alten E-Mails. Manchmal muss ich im Büro nachfragen. "
    "Die Person wartet am Telefon, und ich kann ihr nicht gleich sagen, was gerade gilt."
)


@pytest.mark.django_db
def test_scenario_a_offline_with_explicit_manual_continuation(client, owner, settings, tmp_path):
    settings.OPENROUTER_API_KEY = ""
    settings.INVESTIGATION_SOURCE_UPLOAD_ROOT = tmp_path / "sources"
    settings.ALLOWED_HOSTS = ["testserver"]
    transcript = []

    def request(step, name, data=None, **kwargs):
        url = reverse(name, kwargs=kwargs)
        response = client.get(url) if data is None else client.post(url, data)
        form = response.context.get("form") if response.context else None
        transcript.append(
            {
                "step": step,
                "method": "GET" if data is None else "POST",
                "url": url,
                "input": copy.deepcopy(data),
                "status": response.status_code,
                "redirect": response.get("Location"),
                "messages": [str(m) for m in get_messages(response.wsgi_request)],
                "form_errors": form.errors.get_json_data() if form else {},
            }
        )
        return response

    client.force_login(owner)
    # Only the natural statement enters the initial Inbox; no context cards yet.
    response = request(
        "01 Inbox: initial statement only",
        "use_cases:idea_create",
        {
            "title": "[SYNTHETISCH #133 A] Rückfragen zur gebuchten Reise",
            "description": INITIAL,
            "business_unit": owner.business_unit_id,
            "source_note": "Synthetische Testperson Kundenservice; keine RSD-Aussage",
        },
    )
    assert response.status_code == 302, transcript[-1]
    idea = IdeaCandidate.objects.get()
    assert idea.description == INITIAL
    assert not ValueStream.objects.exists()
    response = client.get(
        reverse("accelerator:autonomous_discovery_start"), {"idea_candidate": str(idea.pk)}
    )
    assert response.context["form"].initial["problem_statement"] == INITIAL
    transcript.append(
        {
            "step": "02 Discovery entry prefill",
            "status": response.status_code,
            "prefilled_problem": response.context["form"].initial["problem_statement"],
        }
    )
    response = request(
        "03 Autonomous Discovery: no later context, no provider",
        "accelerator:autonomous_discovery_start",
        {
            "idea_candidate": str(idea.pk),
            "business_unit": owner.business_unit_id,
            "problem_statement": INITIAL,
            "business_context": "",
        },
    )
    assert response.status_code == 302, transcript[-1]
    session = CaptureSession.objects.get()
    assert session.answers["problem_statement"] == INITIAL
    assert not ValueStream.objects.exists()
    response = request(
        "04 Actual Discovery review",
        "accelerator:autonomous_discovery_review",
        session_id=session.pk,
    )
    assert response.status_code == 200
    transcript.append(
        {
            "session_status": session.status,
            "analysis": list(CaptureAnalysis.objects.values("status", "error_code")),
            "automatic_value_stream_count": ValueStream.objects.count(),
        }
    )
    assert list(CaptureAnalysis.objects.values_list("error_code", flat=True)) == ["not_configured"]

    # Manual branch: test-author proposals, not app discoveries. No binding approval.
    transcript.append(
        {
            "step": "K1 released by test author before manual continuation",
            "asked_by": "test author, not the application",
            "question": "Was wird gefragt, wie gehen Sie vor und wer hilft bei Unklarheit?",
            "card": "A-K1",
            "answer": "Synthetisch: Transferzeit oder Leistung; Buchung und gemeinsames Postfach "
            "prüfen, bei Unklarheit Reiseorganisation fragen. Produktnamen und Frist unbekannt.",
            "targets": ["manual stream/stage proposal", "later process fields with A-K1 prefix"],
            "status": "synthetic report, not validated",
        }
    )
    stream_data = {
        "name": "[SYNTHETISCH #133 A] Reiseanliegen bis geklärte Antwort",
        "business_unit": owner.business_unit_id,
        "owner": owner.pk,
        "status": "draft",
        "description": "Testautor-Entwurf aus A-K1; unbestätigt",
        "trigger": "Rückfrage zu einer bereits gebuchten Reise geht ein",
        "outcome": "Kunde erhält eine geprüfte Antwort; offene Klärfälle bleiben offen",
        "scope_in": "Anliegen aufnehmen, Angaben klären, Antwort prüfen und mitteilen",
        "scope_out": "Neue Buchung, Reiseausführung und Erstattungsentscheidung",
        "strategic_objective": "Hypothese: verlässlichere Antworten; Wirkung unbekannt",
        "stakeholders": "Kunde, Kundenservice, Reiseorganisation",
        "constraints": "Nur berechtigte Einsicht; widersprüchliche Angaben vor Auskunft klären",
        "business_domain": "customer_service",
        "capability": "Kundenanliegen klären",
        "focus_status": "not_screened",
    }
    response = request("05 Manual stream draft", "architecture:value_stream_create", stream_data)
    assert response.status_code == 302, transcript[-1]
    stream = ValueStream.objects.get()
    stages = [
        ("Anliegen zugeordnet", "Aus der Rückfrage entsteht ein zugeordnetes Buchungsanliegen."),
        (
            "Antwortgrundlage geklärt",
            "Aus den Angaben entsteht eine geprüfte Antwortgrundlage; "
            "Widersprüche bleiben bis zur Rückfrage offen.",
        ),
        ("Antwort mitgeteilt", "Aus der geprüften Grundlage erhält der Kunde eine Antwort."),
    ]
    for sequence, (name, description) in enumerate(stages, 1):
        response = request(
            f"06.{sequence} Manual stage proposal",
            "architecture:stage_create",
            {
                "sequence": sequence,
                "name": name,
                "description": "Testautoren-Hypothese aus A-K1: " + description,
            },
            value_stream_id=stream.pk,
        )
        assert response.status_code == 302, transcript[-1]
    stage = ValueStreamStage.objects.get(sequence=2)
    response = request(
        "07 Guard before screening", "architecture:process_analysis_create", stage_id=stage.pk
    )
    assert response.status_code == 302 and not ProcessAnalysis.objects.exists()
    stream_data.update(
        {
            "status": "active",
            "focus_status": "selected",
            "strategic_impact": "medium",
            "economic_potential": "medium",
            "pain_intensity": "medium",
            "data_accessibility": "medium",
            "change_effort": "medium",
            "focus_rationale": (
                "Synthetische Testautoren-Einschätzung, keine Messung oder RSD-Freigabe; "
                "begrenzte Klärung im Kundenservice, wirtschaftliche Relevanz offen."
            ),
        }
    )
    response = request(
        "08 Provisional manual screening",
        "architecture:value_stream_update",
        stream_data,
        pk=stream.pk,
    )
    assert response.status_code == 302, transcript[-1]
    focus = {
        "selected_stage": str(stage.pk),
        "rationale": "Unbestätigter Testfokus: hier berichtet A die Suche; keine Ursache belegt.",
    }
    for candidate in stream.stages.all():
        for criterion in (
            "impact",
            "pain_intensity",
            "improvement_potential",
            "data_accessibility",
            "change_effort",
        ):
            focus[f"{criterion}_{candidate.pk.hex}"] = "medium"
        focus[f"time_to_value_{candidate.pk.hex}"] = "unknown"
        focus[f"evidence_basis_{candidate.pk.hex}"] = "hypothesis"
    response = request(
        "09 Manual phase comparison", "architecture:stage_focus_select", focus, pk=stream.pk
    )
    assert response.status_code == 302, transcript[-1]
    transcript.append(
        {
            "step": "K2-K3 released during manual clarification before process draft",
            "asked_by": "test author, not the application",
            "question": "Gibt es einen konkreten Fall, Gegenbeispiele und gemessene Zeiten?",
            "cards": ["A-K2", "A-K3"],
            "answers": [
                "SYN-A-01: Buchungsnotiz 09:00, spätere Transfernachricht 10:00; "
                "Zustellung und endgültige Gültigkeit nicht dokumentiert.",
                "SYN-A-02: Leistungsfrage mit übereinstimmenden Angaben beantwortbar; "
                "keine Zeitstichprobe, Mengen, Fehlerquote oder Kostendaten.",
            ],
            "targets": ["data_objects", "exceptions", "cause_hypotheses", "baseline_metrics"],
            "status": "synthetic examples, no causal proof",
        }
    )
    process_data = {
        "name": "[SYNTHETISCH #133 A] Antwortgrundlage klären",
        "status": "draft",
        "scope_start": "Zugeordnete Rückfrage zur bestehenden Buchung",
        "scope_end": "Grundlage für Antwort oder benannter offener Klärbedarf",
        "trigger": "Kunde fragt nach aktuellem Stand",
        "outcome": "Prüfbare Antwortgrundlage",
        "current_flow": "A-K1, synthetisch berichtet: Buchung öffnen, E-Mails prüfen, "
        "bei Unklarheit Reiseorganisation fragen; keine beobachtete Prozessaufnahme.",
        "roles": "A-K1: Kundenservice, Reiseorganisation",
        "systems": "A-K1: Buchungsmaske und gemeinsames Postfach; Produktnamen unbekannt",
        "data_objects": (
            "A-K2, synthetisch: SYN-A-01 Buchungsnotiz Transfer 09:00, spätere Nachricht 10:00; "
            "Zustellung an Kunden und endgültige Gültigkeit nicht dokumentiert."
        ),
        "business_rules": "A-K1: unklaren Reisestand vor verbindlicher Auskunft rückfragen",
        "handoffs": "A-K1: Kundenservice fragt Reiseorganisation; Antwortfrist unbekannt",
        "bottlenecks": "Nur berichtetes lokales Suchproblem; systemweiter Engpass unbekannt",
        "diagnostic_observations": INITIAL,
        "cause_hypotheses": "H1: Standangaben widersprechen sich. H2: Zugriffsrechte fehlen. "
        "H3: Rückmeldungen kommen spät. Alle unbestätigt; A-K2 nur ein Fall.",
        "confirmed_causes": "",
        "constraints": "",
        "exceptions": "A-K2: widersprechende Transferzeit; A-K3: Standardfall ohne Widerspruch",
        "baseline_metrics": "Nicht erhoben. Geplant: Such- und Wartezeit getrennt, "
        "Antwortkorrektheit und Wiederholkontakte; keine Zielwerte bekannt.",
        "target_state_principles": "Berechtigte, aktuelle, nachvollziehbare Auskunft; Lösung offen",
    }
    response = request(
        "10 Manual discovery cards K1-K3",
        "architecture:process_analysis_create",
        process_data,
        stage_id=stage.pk,
    )
    assert response.status_code == 302, json.dumps(transcript[-1], ensure_ascii=False)
    process = ProcessAnalysis.objects.get()
    for name, kind, description in [
        (
            "Klärweg und zuständige Person festhalten",
            "organizational",
            "Hypothese: Zuständigkeit und aktueller Stand werden nach Rückfrage festgehalten.",
        ),
        (
            "Vorhandene Buchungsansicht mit Verweisen prüfen",
            "standard_software",
            "Hypothese: vorhandene Ansicht kann freigegebene Informationen erreichbar machen.",
        ),
        (
            "Quellengebundene Suchhilfe prüfen",
            "assistant",
            "Hypothese: Suchhilfe zeigt Quellen und Widersprüche; keine verbindliche Auskunft.",
        ),
    ]:
        response = request(
            "11 Manual solution hypothesis",
            "architecture:solution_option_create",
            {
                "name": name,
                "option_type": kind,
                "evaluation_status": "draft",
                "evidence_basis": "hypothesis",
                "description": description,
                "expected_value": (
                    "Nutzen unbewiesen; Vergleich mit unverändertem Ablauf erforderlich"
                ),
                "time_to_value": "unknown",
                "feasibility": "not_assessed",
                "integration_effort": "not_assessed",
            },
            process_analysis_id=process.pk,
        )
        assert response.status_code == 302, transcript[-1]
    response = request(
        "12 Actual comparison and blockers", "architecture:solution_option_compare", pk=process.pk
    )
    assert response.status_code == 200
    transcript.append(
        {
            "comparison_blockers": response.context["blockers"],
            "diagnosis_blockers": response.context["diagnosis_blockers"],
        }
    )
    response = request(
        "13 Selection without cause confirmation is rejected",
        "architecture:solution_option_compare",
        {
            "selected_option": str(SolutionOption.objects.first().pk),
            "process_version": process.version,
            "rationale": "Negativprobe: keine verbindliche Auswahl zulässig",
            "confirmed_causes": "",
        },
        pk=process.pk,
    )
    assert response.status_code == 200
    assert "confirmed_causes" in response.context["form"].errors
    response = request(
        "14 Actual process decision surface", "architecture:process_analysis_detail", pk=process.pk
    )
    assert response.status_code == 200
    transcript.append({"process_decision_surface": response.context["process_decision_surface"]})
    process.refresh_from_db()
    idea.refresh_from_db()
    final = {
        "idea_description": idea.description,
        "idea_state": idea.state,
        "idea_discovery_process_analysis_id": idea.discovery_process_analysis_id,
        "process_status": process.status,
        "confirmed_causes": process.confirmed_causes,
        "baseline_metrics": process.baseline_metrics,
        "process_source_snapshot": process.source_snapshot,
        "options": list(
            SolutionOption.objects.values(
                "name", "option_type", "evidence_basis", "evaluation_status", "recommendation"
            )
        ),
        "process_validations": ProcessValidation.objects.count(),
        "selection_decisions": SolutionSelectionDecision.objects.count(),
        "use_cases": UseCase.objects.count(),
        "delivery_packages": DeliveryPackage.objects.count(),
        "lifecycle_reviews": Review.objects.count(),
    }
    assert final["confirmed_causes"] == ""
    assert final["idea_discovery_process_analysis_id"] is None
    assert all(
        final[key] == 0
        for key in (
            "process_validations",
            "selection_decisions",
            "use_cases",
            "delivery_packages",
            "lifecycle_reviews",
        )
    )
    transcript.append({"final_state": final})
    if report_dir := os.environ.get("RSD_REPORT_DIR"):
        destination = Path(report_dir)
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "scenario-a-transcript.json").write_text(
            json.dumps(transcript, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
