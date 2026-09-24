from __future__ import annotations

PLANNER_PROMPT_VERSION = "vs1-planner-v14"
SYNTHESIS_PROMPT_VERSION = "vs1-synthesis-v6"
VERIFIER_PROMPT_VERSION = "vs1-verifier-v4"
PLANNER_SCHEMA_VERSION = "vs1-planner-schema-v14"
SYNTHESIS_SCHEMA_VERSION = "vs1-synthesis-schema-v4"
VERIFIER_SCHEMA_VERSION = "vs1-verifier-schema-v5"

PLANNER_TOOL_NAMES = (
    "list_sources",
    "search_sources",
    "read_source",
    "profile_csv",
    "compare_groups",
)

# The parameter names and enums are also used by runtime validation. Keep this
# small, portable contract in the frozen run snapshot and planner context.
TOOL_PARAMETER_CONTRACTS = {
    "list_sources": {"required": [], "optional": []},
    "search_sources": {"required": ["query"], "optional": ["cursor", "limit"]},
    "read_source": {
        "required": ["source_id"],
        "optional": ["cursor", "limit", "columns"],
    },
    "profile_csv": {"required": ["source_id"], "optional": []},
    "compare_groups": {
        "required": ["source_id", "group_by", "aggregation"],
        "optional": ["value_column", "filters", "unit_column"],
        "aggregations": ["count", "sum", "mean", "median", "min", "max"],
        "value_column_required_except": ["count"],
        "filter_fields": ["column", "operator", "value"],
        "filter_operators": [
            "eq",
            "neq",
            "gt",
            "gte",
            "lt",
            "lte",
            "in",
            "not_in",
            "is_null",
            "not_null",
        ],
    },
}

_SYNTHESIS_DOMAIN_RULES = """claim_register enthält ausschließlich Evidence Claims:
Aussagen, die wahr, falsch, widersprüchlich oder offen sein können und dafür Evidenz
benötigen. Jeder Eintrag ist ein Objekt mit nichtleerer claim_id (maximal 100 Zeichen),
einem nichtleeren statement, area aus
problem_context|competing_hypotheses|constraints_risks|recommendation_validation,
einem nichtleeren claim_kind und status aus open|supported|refuted|conflicting.
Nutze evidence_refs/counterevidence_refs nur als Arrays reproduzierbarer Referenzobjekte.
Criticality wird serverseitig aus der Claim-Semantik abgeleitet; erfinde oder steuere
kein critical-Feld. Kritische bestehende Evidence Claims dürfen nicht gelöscht,
umbenannt, inhaltlich unter derselben claim_id umgeschrieben oder herabgestuft werden.
Konkurrierende Hypothesen sollen als eigene Evidence Claims mit
area=competing_hypotheses und claim_kind=hypothesis geführt werden, wenn die Evidenzlage
mehr als eine plausible Erklärung trägt.

Solution Options sind Kandidaten und gehören ausschließlich in brief_payload.options, nicht
in claim_register. Der zukünftige Validation Plan gehört ausschließlich in
brief_payload.validation_step und ist kein Evidence Claim. Dass ein Pilot oder Messschritt
noch nicht ausgeführt wurde, ist daher kein Evidenzmangel. Eine Empfehlung kann als
Evidence Claim geführt werden, wenn ihre Evidenzbasis explizit referenziert wird.
Unbekannte Punkte werden ehrlich als offen bzw. in risks_unknowns ausgewiesen und dürfen
nicht als bestätigte Tatsachen oder Empfehlungspremissen verwendet werden.

Wenn der Run einen Decision Brief verlangt, pflege brief_payload als möglichst vollständigen
prüfbaren Arbeitsstand. Methodische Qualitätsmerkmale wie mehrere competing hypotheses,
Berechnungen, Non-AI-/Status-quo-Optionen und validation_step sind erwünscht und werden
separat im Benchmark gemessen; sie sind aber keine universellen technischen READY-Gates.
question_scope, problem und recommendation müssen die tatsächlich verwendete Evidenz korrekt
referenzieren. Vorschläge sind keine bestätigten Tatsachen. Eine fehlende
entscheidungskritische Größe bleibt unbekannt und führt zu einer präzisen clarification
statt zu einer erfundenen Zahl.

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
jeder Wert benötigt mindestens {relevant:boolean}. reason und reference sind optional.
Eine Quelle mit relevant=true muss tatsächlich gelesen oder analysiert worden sein;
relevant=false benötigt keine künstliche Fundstellenprüfung.
Verarbeite Gegenbelege, wenn sie für die Entscheidung relevant sind.
"""

PLANNER_INSTRUCTION = """Untersuche die Entscheidungsfrage anhand des freigegebenen Quellenraums.
Wähle genau den nächsten fachlich sinnvollen Schritt: Werkzeug, Synthese oder eine wirklich
entscheidungskritische Rückfrage. Wenn die vorhandene Evidenz für einen reviewfähigen
Entscheidungsstand genügt, wähle action=synthesize mit leerem tool_name und "{}" als
parameters. Der Server besitzt Quellen, Werkzeugergebnisse, Claims und Brief; schreibe
diese Zustände nicht zurück. Nutze nur die Werkzeugnamen,
Source-IDs und Parameter aus dem Kontext. Für read_source und profile_csv ist genau
eine source_id erlaubt. Für compare_groups gelten die angegebenen Pflichtfelder.
Bevor du action=synthesize wählst: Wenn eine tragende Hypothese oder Empfehlung auf einer
quantitativen Beziehung zwischen strukturierten Feldern beruht und die dafür nötigen Werte
im freigegebenen Quellenraum vorhanden sind, führe die passende reproduzierbare Analyse mit
einem erlaubten Werkzeug aus, insbesondere compare_groups. Verschiebe einen solchen intern
lösbaren Analysecheck nicht nur in validation_step; bloßes Lesen der Rohzeilen ersetzt ihn nicht.
parameters und clarification_payload sind serialisierte JSON-Objekte; leer ist "{}".
Wenn synthesis_investigation_request gesetzt ist, schließe diese vom Synthesizer erkannte
Evidenzlücke mit einem erlaubten Werkzeug, sofern sie innerhalb des freigegebenen Quellenraums
lösbar ist; frage den Menschen nicht, eine interne Toolarbeit auszuführen.
Eine Suche nach möglichen Gegenbelegen gehört zur Untersuchung. Erfinde keine Fakten,
Messwerte, Freigaben oder zusätzlichen Scope. Nutze clarification nur für eine echte externe
entscheidungskritische Evidenzlücke, Permission/Scope oder einen Value-Trade-off; technische
Fehler, Budget und Verifikation gehören dem Server. Begründe knapp den Prüfpunkt."""

SYNTHESIS_INSTRUCTION = (
    """Erzeuge aus dem serverseitig gespeicherten Werkzeugverlauf
genau ein vollständiges Decision Package: Claim Register, Decision Brief und
Relevanzentscheidung für jede Manifestquelle. Verwende nur nachprüfbare Fundstellen.
Kennzeichne Fakten, Hypothesen, Gegenbelege und Unbekanntes getrennt; erfinde keine
Fakten oder Messwerte. Bei einer Reparatur bleiben vorhandene Claim-IDs und
Briefabschnitte erhalten. Antworte als ein einziges JSON-Objekt. claim_register ist
ein echtes JSON-Array; brief_payload, source_relevance und clarification_payload
sind echte JSON-Objekte. Diese Felder dürfen niemals als JSON-Text in Strings
serialisiert werden.
Wenn eine entscheidungskritische Evidenzlücke mit den bereits freigegebenen Quellen
und erlaubten Werkzeugen selbst geschlossen werden kann, setze clarification_reason auf
den leeren String und liefere investigation_request={goal,reason}; frage den Menschen dafür
nicht. Der Planner übernimmt danach wieder genau den nächsten Werkzeugschritt. Nur wenn die
fehlende Information außerhalb des freigegebenen Quellenraums liegt oder eine echte menschliche
Entscheidung erfordert, setze clarification_reason=missing_evidence, investigation_request={},
claim_register=[], brief_payload={}, source_relevance={} und formuliere in
clarification_payload die konkrete Frage und ihren Einfluss auf die Entscheidung.
Bei einem vollständigen Package setze clarification_reason auf den leeren String,
investigation_request={} und clarification_payload auf {}.
"""
    + _SYNTHESIS_DOMAIN_RULES
)

VERIFIER_INSTRUCTION = """Du bist ein frischer unabhängiger Verifier. Prüfe
Entscheidungsfrage, Evidence Claims, reale Quellen-/Analysefundstellen, Gegenbelege,
Empfehlung und denselben versionierten Decision-Brief-Stand. Solution Options sind
Kandidaten, keine Evidence Claims; ein zukünftiger validation_step ist ein konkreter
Messplan und muss noch nicht ausgeführt sein. Fordere daher weder Options-Claims noch
Evidenz für die bereits erfolgte Durchführung des Validation Plans.

Prüfe insbesondere, ob Aussagen als bestätigte Daten, berichtete Meinung, Hypothese oder
unbekannt korrekt getrennt sind, ob die Empfehlung durch Evidenz getragen wird und ob
vorhandene Berechnungen Population, Grenzen und reproduzierbare Tool-Referenzen enthalten.
Berücksichtige Gegenbelege und relevante offene Punkte. Prüfe jeden als kritisch markierten
Evidence Claim ausdrücklich und liste seine ID in checked_critical_claims. Fordere zusätzliche
read_requests nur an, wenn eine konkrete Fundstelle für diese Integritätsprüfung wirklich
fehlt. Nichtkritische Caveats dürfen READY nicht verhindern: Wenn kein konkreter kritischer
Evidenz-/Integritätsfehler verbleibt, liefere ausschließlich noncritical Findings und
source_references_valid=true. Erfinde keine Evidenz und triff keine fachliche Freigabe.
Verwende nur den rekonstruierbaren Arbeitsstand."""


def planner_response_format() -> dict:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "vs1_planner_action",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["tool", "synthesize", "clarify"]},
                    "target_claim_id": {"type": "string"},
                    "expected_discriminating_finding": {"type": "string"},
                    "rationale": {"type": "string"},
                    "tool_name": {
                        "type": "string",
                        "enum": ["", *PLANNER_TOOL_NAMES],
                    },
                    "parameters": {
                        "type": "string",
                        "description": (
                            "Serialisiertes JSON-Objekt mit Parametern für tool_name "
                            "gemäß tool_parameter_contracts im Kontext; leer exakt {}."
                        ),
                    },
                    "clarification_reason": {
                        "type": "string",
                        "enum": [
                            "",
                            "missing_evidence",
                            "permission_or_scope",
                            "value_tradeoff",
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
                    "clarification_reason",
                    "clarification_payload",
                ],
                "additionalProperties": False,
            },
        },
    }


def synthesis_response_format() -> dict:
    # The synthesis package is deliberately not double-encoded into string fields.
    # JSON object mode keeps the provider contract simple while the server performs
    # the authoritative domain/provenance validation of the native package.
    return {"type": "json_object"}


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
