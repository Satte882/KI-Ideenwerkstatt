"""Fail-closed offline transport for the two explicitly frozen Discovery packets."""

import json

from ki_radar.accelerator import strategic_discovery as strategic
from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable

from . import access
from .scenarios import PACKETS, SCOPE, source_text


def draft(case, schema_version, scope=None):
    strategic_case = case == "B"
    refs = ["U0"]
    rating = "" if strategic_case else "medium"
    stages = []
    for index, (key, name) in enumerate(
        [("receive", "Kundenanfrage aufnehmen"), ("clarify", "Kundenanfrage klären")], start=1
    ):
        stages.append(
            {
                "key": key,
                "sequence": index,
                "name": name,
                "description": "Möglicher Untersuchungsschritt; tatsächlicher Ablauf unbekannt"
                if strategic_case
                else "Kundenanfrage entgegennehmen und für die Klärung bereitstellen"
                if key == "receive"
                else "Anfrage lesen und einer verantwortlichen Stelle zuordnen",
                "roles": "" if strategic_case else "Kundenservice",
                "systems": "",
                "documents": "Synthetische Kundenanfragen",
                "pain_points": ""
                if strategic_case or key == "receive"
                else "Uneinheitliche Zuordnung",
                "baseline_metrics": "",
                "impact": rating,
                "pain_intensity": rating,
                "improvement_potential": rating,
                "data_accessibility": rating,
                "change_effort": rating,
                "time_to_value": "unknown",
                "evidence_basis": "hypothesis" if strategic_case else "indicative",
                "evidence_refs": refs,
            }
        )
    result = {
        "schema_version": schema_version,
        "value_stream": {
            "name": f"[SOLO-{case}] Kundenanfrage bis verantwortete Antwortvorbereitung",
            "description": "Synthetischer Offline-Testentwurf aus festem Quellenpaket",
            "trigger": "Eingang einer Kundenanfrage",
            "outcome": "Verantwortete Antwortvorbereitung",
            "scope_in": "Anfrage aufnehmen und Antwort fachlich vorbereiten",
            "scope_out": "Verbindliche Buchung und operative Durchführung",
            "strategic_objective": "Verlässliche Kundenbetreuung bei mehr Anfragen",
            "stakeholders": "Serviceleitung und Kundenservice",
            "constraints": "",
            "evidence_refs": refs,
        },
        "stages": stages,
        "focus": {
            "recommended_stage_key": "clarify",
            "business_domain": "customer_service",
            "capability": "Kundenanfragen klären",
            "strategic_impact": rating,
            "economic_potential": rating,
            "pain_intensity": rating,
            "data_accessibility": rating,
            "change_effort": rating,
            "rationale": "Begrenzter synthetischer Untersuchungsrahmen, kein Nutzenbeweis",
            "tradeoffs": ["Weitere Beiträge außerhalb des Rahmens bleiben offen"],
            "uncertainties": ["Baseline, Beträge und Geschäftswirkung unbekannt"],
            "evidence_refs": refs,
        },
        "process_analysis": {
            "name": f"[SOLO-{case}] Kundenanfragenklärung",
            "scope_start": "Eingang einer Kundenanfrage",
            "scope_end": "Verantwortete Antwortvorbereitung",
            "trigger": "Kundenanfrage",
            "outcome": "Verantwortete Antwortvorbereitung",
            "current_flow": "Ist-Ablauf unbekannt"
            if strategic_case
            else "Kundenservice liest Anfragen und ordnet sie einer verantwortlichen Stelle zu",
            "roles": "" if strategic_case else "Kundenservice",
            "systems": "",
            "data_objects": "Synthetische Anfragen und Zuständigkeitsregeln",
            "business_rules": "",
            "handoffs": "",
            "bottlenecks": "" if strategic_case else "Uneinheitliche Zuordnung",
            "observations": ""
            if strategic_case
            else "Im Test-Service berichtete Zuordnungsprobleme",
            "cause_hypotheses": ""
            if strategic_case
            else "Unklare Zuständigkeit könnte Klärarbeit verursachen; nicht empirisch belegt",
            "constraints": "",
            "exceptions": "",
            "baseline_metrics": "",
            "evidence_refs": refs,
        },
        "facts": [],
        "hypotheses": [],
        "unknowns": [
            {
                "statement": "Ist-Werte, Kosten und Geschäftswirkung nicht gemessen",
                "impact": "Kein realer Nutzen- oder Kausalitätsnachweis",
            }
        ],
        "clarifications": [],
        "contradictions": [],
    }
    if strategic_case:
        result["scope_basis"] = scope
    return result


def response(*, messages, response_format):
    access.require_isolation()
    name = (response_format or {}).get("json_schema", {}).get("name", "")
    if name not in {
        "autonomous_business_discovery_v1",
        "autonomous_business_discovery_v3",
        "autonomous_business_discovery_verifier_v1",
        "autonomous_business_discovery_verifier_v2",
    }:
        raise OpenRouterUnavailable(
            "Solo-Offline: Dieser KI-Schritt ist nicht verfügbar. Manuelle Fachroute nutzen; "
            "kein echter Modellaufruf wurde ausgeführt.",
            code="solo_offline_unsupported",
        )
    try:
        document = json.loads(messages[-1]["content"])
        source = document.get("input", document)
        case = next(
            key
            for key, packet in PACKETS.items()
            if (
                source.get("problem_statement") == packet["problem_statement"]
                and source.get("business_context") == packet["business_context"]
                and not source.get("corrections")
                and len(source.get("sources", [])) == 1
                and source["sources"][0].get("content") == source_text(key)
            )
        )
    except (KeyError, ValueError, StopIteration, TypeError) as exc:
        raise OpenRouterUnavailable(
            "Solo-Offline unterstützt nur die unveränderten Quellenpakete A/B-v1. "
            "Eine neue Discovery über die Solo-Testseite starten.",
            code="solo_packet_mismatch",
        ) from exc
    scope = strategic.scope_basis(source.get("human_scope")) if case == "B" else None
    if case == "B" and scope != SCOPE:
        raise OpenRouterUnavailable(
            "Solo-Offline: Geänderter Untersuchungsrahmen nicht unterstützt.",
            code="solo_packet_mismatch",
        )
    schema = response_format["json_schema"]["schema"]["properties"]["schema_version"]["enum"][0]
    if "verifier" in name:
        provided = document.get("draft", {})
        if provided != draft(case, provided.get("schema_version"), scope):
            raise OpenRouterUnavailable(
                "Solo-Offline: Fremder Entwurf wird nicht bestätigt.", code="solo_packet_mismatch"
            )
        payload = {
            "schema_version": schema,
            "status": "approved",
            "checks": dict.fromkeys(
                [
                    "source_grounding",
                    "scope_quality",
                    "stage_sequence",
                    "focus_fit",
                    "hypothesis_separation",
                    "unknowns_visible",
                    "contradictions_preserved",
                ],
                True,
            ),
            "critical_findings": [],
            "repair_instructions": "",
            "human_question": "",
        }
    else:
        payload = draft(case, schema, scope)
    content = json.dumps(payload, ensure_ascii=False)
    return OpenRouterResult(
        content=content,
        model="solo/offline-fixture-v1",
        usage={},
        output_chars=len(content),
        finish_reason="stop",
    )
