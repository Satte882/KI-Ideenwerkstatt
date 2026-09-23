from __future__ import annotations

PLANNER_PROMPT_VERSION = "vs1-planner-v6"
VERIFIER_PROMPT_VERSION = "vs1-verifier-v2"
PLANNER_SCHEMA_VERSION = "vs1-planner-schema-v8"
VERIFIER_SCHEMA_VERSION = "vs1-verifier-schema-v4"

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
Halte den werkzeugspezifischen Parametervertrag exakt ein. read_source und profile_csv
akzeptieren genau eine source_id pro Aufruf; mehrere Quellen werden in getrennten Schritten
gelesen. Verwende ausschließlich Source-IDs aus dem bereitgestellten Quellenmanifest.
Die Felder parameters, claim_register, brief_payload, source_relevance, progress_payload und
clarification_payload werden als Strings transportiert, müssen aber IMMER serialisiertes JSON
enthalten. Verwende für ein leeres Objekt exakt "{}" und für eine leere Liste exakt "[]".
Verwende niemals einen leeren String, "unverändert" oder sonstigen Freitext als Ersatz für JSON.
Jeder Eintrag in claim_register ist ein Objekt mit einer nichtleeren claim_id (maximal 100
Zeichen), area aus problem_context|competing_hypotheses|solution_options|constraints_risks|
recommendation_validation, einem nichtleeren claim_kind und status aus
open|supported|refuted|conflicting. Nutze evidence_refs/counterevidence_refs nur als Arrays
reproduzierbarer Referenzobjekte; kritische bestehende Claims dürfen nicht gelöscht,
umbenannt oder herabgestuft werden.
Führe mindestens zwei konkurrierende Hypothesen als eigene Claims mit
area=competing_hypotheses und claim_kind=hypothesis. Options-Claims verwenden
area=solution_options, claim_kind=option und metadata.non_ai bzw.
metadata.status_quo als boolesche Kennzeichen. Empfehlung und Validierung sind
eigene Claims mit area=recommendation_validation und claim_kind=recommendation
bzw. validation. Ein unbelegter Vorschlag bleibt offen und darf nicht als
bestätigte Tatsache verwendet werden.

Wenn der Run einen vollständigen Decision Brief verlangt, pflege brief_payload als prüfbaren
Arbeitsstand mit genau diesen fachlichen Bausteinen: question_scope, problem mit echten
references, mindestens zwei competing hypotheses mit Evidenz/Gegenbelegen, calculations mit
Tool-Resultat/Population/Grenzen, mindestens zwei options einschließlich Non-AI und Status quo,
recommendation mit Evidenz, risks_unknowns sowie validation_step. Vorschläge sind keine
bestätigten Tatsachen. Eine fehlende entscheidungskritische Größe bleibt unbekannt und führt
zu einer präzisen clarification statt zu einer erfundenen Zahl oder READY.

Verwende exakt die folgenden Feldnamen des Decision-Brief-Vertrags:
question_scope={question,scope}, problem={statement,references}, hypotheses als Liste
mit {statement,status,references,counterevidence_refs}, calculations als Liste mit
{summary,reference,population,limits}, options als Liste mit
{name,description,expected_value,option_type,non_ai,status_quo},
recommendation={summary,rationale,references}, risks_unknowns als Liste und
validation_step={step,measurement}. population ist ein Objekt, kein Freitext.
option_type ist ein gültiger Produkttyp wie no_tech, organizational oder generative_ai;
non_ai und status_quo sind separate boolesche Felder. Gib die aktuelle Entscheidungsfrage
im Feld question exakt wieder.

Eine Quellenreferenz hat {source_id,locator,revision_hash}; locator verwendet bei Text
{line} und bei CSV {row} mit optionaler column. Ein Analyseergebnis hat
{tool_result_id,revision_hash}. Verwende nur IDs und Hashes aus Manifest oder
Werkzeugresultaten. Für quantitative Vergleiche verwende compare_groups und referenziere
das Ergebnis; berechne keine prüfpflichtige Gruppenkennzahl nur aus gelesenen Zeilen.
source_relevance ist ein JSON-Objekt mit genau einer Source-ID pro Manifestquelle;
jeder Wert hat {relevant:boolean,reason:string,reference:Referenzobjekt}.
Solange noch nicht jede Quelle eine gültige Referenz hat, verwende hierfür "{}".
Suche vor dem Abschluss ausdrücklich nach Gegenbelegen und verarbeite Treffer.
Ein unveränderter Arbeitsstand braucht keine erneute identische Werkzeuganfrage."""

VERIFIER_INSTRUCTION = """Du bist ein frischer unabhängiger Verifier. Prüfe Entscheidungsfrage,
fünf Pflichtbereiche, Claims, reale Quellen-/Analysefundstellen, Gegenbelege, Empfehlung
und denselben versionierten Decision-Brief-Stand. Prüfe insbesondere, ob Aussagen als
bestätigte Daten, berichtete Meinung, Hypothese oder unbekannt korrekt getrennt sind und ob
Berechnungen Population, Grenzen und reproduzierbare Tool-Referenzen tragen. Liefere
strukturierte Findings statt einer bloßen Freigabe. Erfinde keine Evidenz und triff keine
fachliche Freigabe. Verwende nur den rekonstruierbaren Arbeitsstand."""


def planner_response_format(
    *,
    allowed_source_ids: tuple[str, ...] = (),
    csv_source_ids: tuple[str, ...] = (),
) -> dict:
    del allowed_source_ids, csv_source_ids
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "vs1_planner_action",
            "strict": True,
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
                    "parameters": {
                        "type": "string",
                        "description": (
                            "Serialisiertes JSON-Objekt mit Parametern für tool_name; "
                            "leer exakt {}."
                        ),
                    },
                    "claim_register": {
                        "type": "string",
                        "description": (
                            "Serialisiertes JSON-Array des vollständigen Claim-Registers; "
                            "leer exakt []. Jeder Eintrag benötigt claim_id, area, "
                            "claim_kind und status gemäß Planner-Vertrag."
                        ),
                    },
                    "brief_payload": {
                        "type": "string",
                        "description": (
                            "Serialisiertes JSON-Objekt des aktuellen Decision-Brief-"
                            "Arbeitsstands; leer exakt {}."
                        ),
                    },
                    "source_relevance": {
                        "type": "string",
                        "description": (
                            "Serialisiertes JSON-Objekt der Relevanz je Source-ID; leer exakt {}."
                        ),
                    },
                    "progress_kind": {
                        "type": "string",
                        "enum": ["none", "evidence", "refutation", "contradiction", "coverage"],
                    },
                    "progress_payload": {
                        "type": "string",
                        "description": "Serialisiertes JSON-Objekt zum Fortschritt; leer exakt {}.",
                    },
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
                    "clarification_payload": {
                        "type": "string",
                        "description": "Serialisiertes JSON-Objekt zur Klärung; leer exakt {}.",
                    },
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
                "additionalProperties": False,
            },
        },
    }


def verifier_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "vs1_verifier_report",
            "strict": True,
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
                            "required": ["source_id", "cursor", "limit", "columns", "claim_id"],
                            "additionalProperties": False,
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
                            "required": ["severity", "code", "claim_id", "message"],
                            "additionalProperties": False,
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
                "additionalProperties": False,
            },
        },
    }
