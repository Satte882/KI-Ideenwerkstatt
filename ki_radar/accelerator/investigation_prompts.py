from __future__ import annotations

PLANNER_PROMPT_VERSION = "vs1-planner-v2"
VERIFIER_PROMPT_VERSION = "vs1-verifier-v2"
PLANNER_SCHEMA_VERSION = "vs1-planner-schema-v3"
VERIFIER_SCHEMA_VERSION = "vs1-verifier-schema-v2"

PLANNER_TOOL_NAMES = (
    "list_sources",
    "search_sources",
    "read_source",
    "profile_csv",
    "compare_groups",
)

PLANNER_INSTRUCTION = """Du planst genau den nächsten prüfbaren Untersuchungsschritt.
Arbeite nur mit den serverseitig erlaubten Werkzeugen und dem freigegebenen Quellenraum.
Begründe knapp Ziel-Prüfpunkt und unterscheidenden erwarteten Befund; liefere keine
verborgene Gedankenkette. Erfinde keine Fakten, erweitere weder Scope noch Budget und
triff keine fachliche Freigabe. Nutze vorhandene Evidenz vor einer menschlichen Rückfrage.

Wenn der Run einen vollständigen Decision Brief verlangt, pflege brief_payload als prüfbaren
Arbeitsstand mit genau diesen fachlichen Bausteinen: question_scope, problem mit echten
references, mindestens zwei competing hypotheses mit Evidenz/Gegenbelegen, calculations mit
Tool-Resultat/Population/Grenzen, mindestens zwei options einschließlich Non-AI und Status quo,
recommendation mit Evidenz, risks_unknowns sowie validation_step. Vorschläge sind keine
bestätigten Tatsachen. Eine fehlende entscheidungskritische Größe bleibt unbekannt und führt
zu einer präzisen clarification statt zu einer erfundenen Zahl oder READY."""

VERIFIER_INSTRUCTION = """Du bist ein frischer unabhängiger Verifier. Prüfe Entscheidungsfrage,
fünf Pflichtbereiche, Claims, reale Quellen-/Analysefundstellen, Gegenbelege, Empfehlung
und denselben versionierten Decision-Brief-Stand. Prüfe insbesondere, ob Aussagen als
bestätigte Daten, berichtete Meinung, Hypothese oder unbekannt korrekt getrennt sind und ob
Berechnungen Population, Grenzen und reproduzierbare Tool-Referenzen tragen. Liefere
strukturierte Findings statt einer bloßen Freigabe. Erfinde keine Evidenz und triff keine
fachliche Freigabe. Verwende nur den rekonstruierbaren Arbeitsstand."""


def planner_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "vs1_planner_action",
            "strict": False,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["tool", "verify", "clarify"]},
                    "target_claim_id": {"type": "string"},
                    "expected_discriminating_finding": {"type": "string"},
                    "rationale": {"type": "string"},
                    "tool_name": {
                        "type": "string",
                        "enum": list(PLANNER_TOOL_NAMES),
                    },
                    "parameters": {"type": "object"},
                    "claim_register": {"type": "array", "items": {"type": "object"}},
                    "brief_payload": {"type": "object"},
                    "source_relevance": {"type": "object"},
                    "progress_kind": {
                        "type": "string",
                        "enum": ["none", "evidence", "refutation", "contradiction", "coverage"],
                    },
                    "progress_payload": {"type": "object"},
                    "clarification_reason": {
                        "type": "string",
                        "enum": [
                            "",
                            "missing_evidence",
                            "permission_or_scope",
                            "value_tradeoff",
                            "budget_exhausted",
                            "no_progress",
                            "verification_failed",
                            "technical_failure",
                        ],
                    },
                    "clarification_payload": {"type": "object"},
                },
                "required": [
                    "action",
                    "target_claim_id",
                    "expected_discriminating_finding",
                    "rationale",
                    "tool_name",
                    "parameters",
                    "claim_register",
                    "brief_payload",
                    "source_relevance",
                    "progress_kind",
                    "progress_payload",
                    "clarification_reason",
                    "clarification_payload",
                ],
            },
        },
    }


def verifier_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "vs1_verifier_report",
            "strict": False,
            "schema": {
                "type": "object",
                "properties": {
                    "read_requests": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "source_id": {"type": "string"},
                                "cursor": {"type": "integer"},
                                "limit": {"type": "integer"},
                                "columns": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "claim_id": {"type": "string"},
                            },
                        },
                    },
                    "findings": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "severity": {
                                    "type": "string",
                                    "enum": ["critical", "noncritical"],
                                },
                                "code": {"type": "string"},
                                "claim_id": {"type": "string"},
                                "message": {"type": "string"},
                            },
                        },
                    },
                    "source_references_valid": {"type": "boolean"},
                    "checked_critical_claims": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "read_requests",
                    "findings",
                    "source_references_valid",
                    "checked_critical_claims",
                ],
            },
        },
    }
