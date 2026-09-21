from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ObjectDoesNotExist

from .architecture_artifacts import get_delivery_architecture_artifacts
from .models import DELIVERY_SECTION_DEFINITIONS, DeliveryPackage, DeliverySectionReview


@dataclass(frozen=True)
class ReadinessFinding:
    section_key: str
    code: str
    severity: str
    message: str


@dataclass(frozen=True)
class DeliveryStatusSnapshot:
    code: str
    label: str
    handover_complete: bool


SECTION_LABELS = dict(DELIVERY_SECTION_DEFINITIONS)
READY_REQUIRED_FIELDS = {
    "problem_and_target": (
        "problem_context",
        "target_outcome",
    ),
    "scope_and_users": (
        "in_scope",
        "out_of_scope",
        "users_and_scenarios",
        "mvp_scope",
    ),
    "solution_direction": (
        "solution_outline",
        "architecture_decisions",
    ),
    "architecture_and_data": (
        "system_context",
        "data_context",
        "integrations",
    ),
    "requirements_and_governance": (
        "functional_requirements",
        "non_functional_requirements",
        "security_privacy_requirements",
        "human_oversight",
        "logging_and_audit",
        "operations_and_support",
    ),
    "acceptance_and_measurement": (
        "acceptance_criteria",
        "test_scenarios",
        "measurement_plan",
    ),
    "delivery_control": (
        "dependencies",
        "risks",
        "assumptions",
        "initial_backlog",
        "external_delivery_url",
        "handover_notes",
    ),
}

ARCHITECTURE_REQUIRED_FIELDS = {
    "system_landscape": "Ist-/Ziel-Systemlandschaft",
    "system_responsibilities": "Systemverantwortung und Zielkomponenten",
    "data_flows": "Daten- und Informationsflüsse",
    "data_quality_and_access": "Datenqualität, Zugriff und Schutzbedarf",
    "integration_contracts": "Integrationsverträge und Verantwortlichkeiten",
    "integration_operations": "Integrationsbetrieb und Fehlerbehandlung",
}

GENERIC_PLACEHOLDER_FRAGMENTS = (
    "im delivery package konkretisieren",
    "konkretisieren.",
    "explizit ergänzen",
    "ergänzen.",
    "kleinsten ende-zu-ende-ablauf",
    "kernablauf aus dem freigegebenen use case umsetzen",
    "fachliche entscheidung und ergebnis nachvollziehbar darstellen",
    "happy path, datenfehler, fachliche ausnahme",
    "epic 1: kernprozess und nutzerfluss",
    "keine zusätzlichen prüfungen markiert",
    "fachliche verantwortlichkeiten bestätigen",
)

_PERCENT_THRESHOLD_RE = re.compile(
    r"(?:[<>]=?|≤|≥|mindestens|maximal|unter|über)?\s*\d+(?:[.,]\d+)?\s*(?:%|prozent)",
    re.IGNORECASE,
)
_SEMANTIC_PLACEHOLDER_RE = re.compile(
    r"(?:\[[^\]]*(?:konkret|frist|zweck|ergänz|festleg)[^\]]*\]|"
    r"\b(?:tbd|todo|später)\b|noch\s+(?:festlegen|definieren|ergänzen)|"
    r"(?:festlegen|definieren|konkretisieren|benennen|ergänzen)\s*[.!]?$)",
    re.IGNORECASE,
)
_POPULATION_CONTEXT_RE = re.compile(
    r"(?:testpopulation|population|grundgesamtheit|testset|evaluationsset|goldstandard)"
    r"(?:\s+(?:der|für|aus|mit|umfasst))?\s*(?::|=|-)?\s*[a-zäöüß][^;\n]{2,}",
    re.IGNORECASE,
)
_SAMPLE_SIZE_RE = re.compile(
    r"(?:\bn\s*=\s*\d+|(?:stichprobengröße|stichprobe|testset|evaluationsset|goldstandard)"
    r"[^\d;\n]{0,30}\d+|\b\d+\s*(?:fälle|vorgänge|beispiele|dokumente|ausgaben|outputs))",
    re.IGNORECASE,
)
_UNCERTAINTY_CONTEXT_RE = re.compile(
    r"(?:konfidenzintervall|fehlerspanne|statistische unsicherheit|aussagekraft)",
    re.IGNORECASE,
)
_CRITICAL_CLASS_RE = re.compile(
    r"(?:seltene?|kritische?|fehlerklass|edge cases?|randfälle)", re.IGNORECASE
)
_TARGETED_TEST_SIZE_RE = re.compile(
    r"(?:\b\d+\s*(?:gezielte[nr]?\s+)?(?:testfälle|tests|fälle|beispiele)|"
    r"(?:testset|negativtest|randfalltest)[^\d;\n]{0,30}\d+)",
    re.IGNORECASE,
)
_RECALL_TARGET_RE = re.compile(
    r"\brecall\b[^\d;\n]{0,30}\d+(?:[.,]\d+)?\s*(?:%|prozent)?", re.IGNORECASE
)
_POSITIVE_CASE_COUNT_RE = re.compile(
    r"(?:\b\d+\s*positive\s+(?:fälle|beispiele|treffer)|"
    r"(?:positive\s+(?:fälle|beispiele)|n[_ -]?pos)\s*(?::|=|von)?\s*\d+)",
    re.IGNORECASE,
)
_NUMERIC_CONFIDENCE_RE = re.compile(
    r"(?:"
    r"(?:confidence|konfidenz)(?:\s*score)?\s*(?::|=|>|<|von)?\s*\d+(?:[.,]\d+)?\s*%?"
    r"|\d+(?:[.,]\d+)?\s*%?\s*(?:confidence|konfidenz)(?:\s*score)?"
    r")",
    re.IGNORECASE,
)
_PREDICTIVE_OUTPUT_RE = re.compile(
    r"(?:extraktion|klassifikation|classifier|klassifikator)", re.IGNORECASE
)
_GENERATIVE_OUTPUT_RE = re.compile(
    r"(?:generativ|freitext|textentwurf|kommunikationsentwurf|llm-ausgabe|antwortentwurf)",
    re.IGNORECASE,
)
_RULE_BASED_OUTPUT_RE = re.compile(r"(?:regelbasiert|regelprüfung)", re.IGNORECASE)
_CONFIDENCE_JUSTIFICATION_RE = re.compile(
    r"(?:kalibrier|dokumentierte? semantik|fachlich definiert|interpretierbar)",
    re.IGNORECASE,
)
_NEGATED_JUSTIFICATION_RE = re.compile(
    r"(?:nicht|un|ohne(?:\s+eine)?)\s*"
    r"(?:kalibrier\w*|dokumentierte?\s+semantik|fachlich\s+definiert|interpretierbar)",
    re.IGNORECASE,
)
_OUTPUT_NOT_APPLICABLE_RE = re.compile(
    r"(?:"
    r"(?:kein(?:e|en|er|es)?|nicht\s+anwendbar(?:e|en|er|es)?)\s+[^.;\n]{0,24}"
    r"(?:extraktion|klassifikation|generativ|freitext|textentwurf|regelbasiert|regelprüfung)"
    r"|(?:extraktion|klassifikation|generativ\w*|freitext|textentwurf|regelbasiert|regelprüfung)"
    r"[^.;\n]{0,30}(?:nicht\s+anwendbar|nicht\s+vorgesehen|entfällt)"
    r")",
    re.IGNORECASE,
)
_GROUNDING_RE = re.compile(r"(?:grounding|quelle|beleg|nachweis)", re.IGNORECASE)
_UNCERTAIN_BASIS_RE = re.compile(
    r"(?:unsicher|fehlende\s+(?:grundlagen?|quellen?|informationen?)|"
    r"unbelegt|nicht\s+ableitbar|kenntnislücke)",
    re.IGNORECASE,
)
_RULE_REFERENCE_RE = re.compile(
    r"(?:regelreferenz|regel[- ]?(?:id|version|nummer)|policy[- ]?(?:id|version))",
    re.IGNORECASE,
)
_RULE_RESULT_RE = re.compile(
    r"(?:prüfergebnis|regelresultat|bestanden|nicht\s+bestanden|erfüllt|verletzt)",
    re.IGNORECASE,
)
_NEGATED_GROUNDING_RE = re.compile(
    r"(?:kein(?:e|en)?|ohne)\s+(?:grounding|quellen?(?:bezug)?|belege?|nachweise?)"
    r"|(?:grounding|quellen?(?:bezug)?|belege?|nachweise?)"
    r"[^.;\n]{0,24}(?:deaktiviert|fehlt\b|fehlen\b|nicht\s+(?:vorhanden|verwendet|dokumentiert))",
    re.IGNORECASE,
)
_NEGATED_UNCERTAIN_BASIS_RE = re.compile(
    r"(?:keine|ohne)\s+(?:kennzeichnung|anzeige|darstellung)[^.;\n]{0,24}"
    r"(?:unsicher|fehlende\s+(?:grundlagen?|quellen?|informationen?)|kenntnislücke)"
    r"|(?:unsicherheit|unsichere\s+(?:grundlagen?|quellen?|informationen?)|kenntnislücken?)"
    r"[^.;\n]{0,30}(?:nicht\s+(?:angezeigt|gekennzeichnet|dargestellt)|fehlt\b|fehlen\b)",
    re.IGNORECASE,
)
_NEGATED_RULE_REFERENCE_RE = re.compile(
    r"(?:kein(?:e)?|ohne)\s+(?:regelreferenz|regel[- ]?(?:id|version|nummer)|"
    r"policy[- ]?(?:id|version))"
    r"|(?:regelreferenz|regel[- ]?(?:id|version|nummer)|policy[- ]?(?:id|version))"
    r"[^.;\n]{0,24}(?:fehlt\b|nicht\s+(?:vorhanden|dokumentiert))",
    re.IGNORECASE,
)
_NEGATED_RULE_RESULT_RE = re.compile(
    r"(?:kein(?:e)?|ohne)\s+(?:prüfergebnis|regelresultat)"
    r"|(?:prüfergebnis|regelresultat)[^.;\n]{0,24}"
    r"(?:fehlt\b|nicht\s+(?:vorhanden|dokumentiert))",
    re.IGNORECASE,
)
_NEGATED_CRITICAL_TEST_RE = re.compile(
    r"(?:nicht|nie|ohne)\s+(?:gezielt\s+)?(?:getestet|geprüft|abgedeckt)"
    r"|(?:wird|werden|ist|sind)\s+[^.;\n]{0,20}nicht\s+"
    r"(?:gezielt\s+)?(?:getestet|geprüft|abgedeckt)"
    r"|keine\s+(?:gezielten?\s+)?(?:testfälle|tests|testabdeckung)",
    re.IGNORECASE,
)
_LATENCY_BUDGET_RE = re.compile(
    r"(?:p95|ende-zu-ende|e2e|nutzer(?:seitig)?(?:es)?\s+(?:latenz|budget))"
    r"[^\d]{0,30}(?:<|≤|max(?:imal)?\.?|unter)?\s*(\d+(?:[.,]\d+)?)\s*(ms|sekunden?|s\b)",
    re.IGNORECASE,
)
_TIMEOUT_RE = re.compile(
    r"(?:request-|provider-|komponenten-)?timeout[^\d]{0,20}(\d+(?:[.,]\d+)?)\s*(ms|sekunden?|s\b)",
    re.IGNORECASE,
)
_RETRY_RE = re.compile(r"(?:retr(?:y|ies)|wiederholung(?:en)?)", re.IGNORECASE)
_SYNC_RE = re.compile(r"\bsynchron\w*", re.IGNORECASE)
_ASYNC_RE = re.compile(
    r"(?:\basynchron\w*|außerhalb\s+des\s+(?:synchronen\s+)?nutzerpfads)", re.IGNORECASE
)
_RETRY_COUNT_RE = re.compile(
    r"(?:maximal\s+)?(?P<count>\d+|ein(?:e|en|er|es)?|zwei|drei)\s+"
    r"(?:synchron\w*\s+)?(?:retr(?:y|ies)|wiederholung(?:en)?)",
    re.IGNORECASE,
)
_ATTEMPT_COUNT_RE = re.compile(
    r"(?:maximal\s+)?(?P<count>\d+|ein(?:e|en|er|es)?|zwei|drei)\s+"
    r"synchron\w*\s+versuch(?:e|en)?",
    re.IGNORECASE,
)
_TOTAL_SYNC_DURATION_RE = re.compile(
    r"(?:maximale?\s+)?(?:gesamtdauer|gesamtlatenz|gesamtzeit)"
    r"[^\d]{0,60}(\d+(?:[.,]\d+)?)\s*(ms|sekunden?|s\b)",
    re.IGNORECASE,
)

_RETENTION_CATEGORIES = {
    "Audit-/Traceability-Metadaten": re.compile(
        r"(?:audit|traceability)[-/ ]*metadaten", re.IGNORECASE
    ),
    "Prompt-/Input-Rohinhalte": re.compile(
        r"(?:prompt|input)[-/ ]*(?:roh)?inhalt(?:e|en)?", re.IGNORECASE
    ),
    "Dokumentinhalte": re.compile(r"dokumentinhalt(?:e|en)?", re.IGNORECASE),
    "personenbezogene oder besonders schutzbedürftige Daten": re.compile(
        r"(?:personenbezogene|besonders\s+schutzbedürftige|sensible)\s+daten", re.IGNORECASE
    ),
    "technische Logs/Betriebsdaten": re.compile(
        r"(?:technische\s+logs?|betriebsdaten)", re.IGNORECASE
    ),
}
_PURPOSE_RE = re.compile(r"(?:zweck|zweckbindung)\s*(?::|=|-|ist)\s*[^;\n.]{3,}", re.IGNORECASE)
_RETENTION_DURATION_RE = re.compile(
    r"(?:aufbewahr|speicher|lösch|retention|frist)[^;\n]{0,35}"
    r"\d+\s*(?:stunden?|tage?|wochen?|monate?|jahre?)",
    re.IGNORECASE,
)
_EVENT_DELETION_RE = re.compile(
    r"(?:nach\s+(?:verarbeitung|abschluss|zweckfortfall|vertragsende|freigabe)|"
    r"bei\s+(?:widerruf|zweckfortfall))[^;\n]{0,40}(?:lösch|entfern|vernicht)|"
    r"(?:lösch|entfern|vernicht)[^;\n]{0,40}"
    r"(?:nach\s+(?:verarbeitung|abschluss|zweckfortfall|vertragsende|freigabe)|"
    r"bei\s+(?:widerruf|zweckfortfall))",
    re.IGNORECASE,
)
_NON_PERSISTENCE_RE = re.compile(
    r"(?:nicht\s+(?:gespeichert|persistiert|aufbewahrt)|keine\s+(?:speicherung|persistierung)|"
    r"nur\s+transient|sofort\s+gelöscht)",
    re.IGNORECASE,
)
_INVALID_RETENTION_RE = re.compile(
    r"(?:keine\s+löschung|nicht\s+gelöscht|unbegrenzt|dauerhaft\s+gespeichert|"
    r"frist\s+(?:benennen|festlegen|ergänzen)|löschfrist\s+(?:offen|tbd))",
    re.IGNORECASE,
)
_INVALID_PURPOSE_RE = re.compile(
    r"(?:keine\s+zweckbindung|zweck\s+(?:benennen|festlegen|ergänzen|offen|tbd))",
    re.IGNORECASE,
)


def _seconds(match: re.Match[str]) -> float:
    value = float(match.group(1).replace(",", "."))
    return value / 1000 if match.group(2).casefold() == "ms" else value


def _statements(value: str) -> list[str]:
    return [
        statement.strip()
        for statement in re.split(r"(?:[;\n]+|(?<=[.!?])\s+)", value)
        if statement.strip()
    ]


def _has_concrete_match(value: str, pattern: re.Pattern[str]) -> bool:
    return any(
        pattern.search(statement) and not _SEMANTIC_PLACEHOLDER_RE.search(statement)
        for statement in _statements(value)
    )


def _has_affirmative_match(
    value: str,
    pattern: re.Pattern[str],
    negated_pattern: re.Pattern[str],
) -> bool:
    return any(
        pattern.search(negated_pattern.sub("", statement))
        and not _SEMANTIC_PLACEHOLDER_RE.search(statement)
        for statement in _statements(value)
    )


def _affirmative_confidence_semantics(statement: str) -> bool:
    without_negated_claims = _NEGATED_JUSTIFICATION_RE.sub("", statement)
    return bool(_CONFIDENCE_JUSTIFICATION_RE.search(without_negated_claims))


def _output_semantic_findings(confidence_text: str) -> list[ReadinessFinding]:
    findings: list[ReadinessFinding] = []
    statements = _statements(confidence_text)
    output_patterns = (_PREDICTIVE_OUTPUT_RE, _GENERATIVE_OUTPUT_RE, _RULE_BASED_OUTPUT_RE)
    active_output_statements = [
        statement
        for statement in statements
        if any(pattern.search(statement) for pattern in output_patterns)
        and not _OUTPUT_NOT_APPLICABLE_RE.search(statement)
        and not _SEMANTIC_PLACEHOLDER_RE.search(statement)
    ]
    if not active_output_statements:
        findings.append(
            ReadinessFinding(
                "requirements_and_governance",
                "OUTPUT_TYPE_SEMANTICS_MISSING",
                "blocker",
                (
                    "Die Confidence- und Unsicherheitsdarstellung ist noch keinem konkreten "
                    "Output-Typ zugeordnet."
                ),
            )
        )
        return findings

    predictive_numeric_without_semantics = any(
        _PREDICTIVE_OUTPUT_RE.search(statement)
        and _NUMERIC_CONFIDENCE_RE.search(statement)
        and not _affirmative_confidence_semantics(statement)
        for statement in active_output_statements
    )
    if predictive_numeric_without_semantics:
        findings.append(
            ReadinessFinding(
                "requirements_and_governance",
                "PREDICTIVE_CONFIDENCE_SEMANTICS_INCOMPLETE",
                "blocker",
                (
                    "Numerische Confidence für Extraktion oder Klassifikation benötigt eine "
                    "ausdrücklich dokumentierte fachliche Semantik."
                ),
            )
        )

    generative_statements = [
        statement
        for statement in active_output_statements
        if _GENERATIVE_OUTPUT_RE.search(statement)
    ]
    if generative_statements:
        unjustified_numeric_confidence = any(
            _NUMERIC_CONFIDENCE_RE.search(statement)
            and not _affirmative_confidence_semantics(statement)
            for statement in generative_statements
        )
        if unjustified_numeric_confidence:
            findings.append(
                ReadinessFinding(
                    "requirements_and_governance",
                    "GENERATIVE_NUMERIC_CONFIDENCE_UNJUSTIFIED",
                    "blocker",
                    (
                        "Für generative Texte wird ein numerischer Confidence Score verlangt, "
                        "ohne eine belastbare, kalibrierte Semantik zu dokumentieren."
                    ),
                )
            )
        if not (
            _has_affirmative_match(confidence_text, _GROUNDING_RE, _NEGATED_GROUNDING_RE)
            and _has_affirmative_match(
                confidence_text,
                _UNCERTAIN_BASIS_RE,
                _NEGATED_UNCERTAIN_BASIS_RE,
            )
        ):
            findings.append(
                ReadinessFinding(
                    "requirements_and_governance",
                    "GENERATIVE_GROUNDING_INCOMPLETE",
                    "blocker",
                    (
                        "Generative Ausgaben benötigen Quellenbezug oder Grounding sowie eine "
                        "Kennzeichnung fehlender oder unsicherer Grundlagen."
                    ),
                )
            )

    has_rule_based_output = any(
        _RULE_BASED_OUTPUT_RE.search(statement) for statement in active_output_statements
    )
    has_rule_based_evidence = _has_affirmative_match(
        confidence_text,
        _RULE_REFERENCE_RE,
        _NEGATED_RULE_REFERENCE_RE,
    ) and _has_affirmative_match(
        confidence_text,
        _RULE_RESULT_RE,
        _NEGATED_RULE_RESULT_RE,
    )
    if has_rule_based_output and not has_rule_based_evidence:
        findings.append(
            ReadinessFinding(
                "requirements_and_governance",
                "RULE_BASED_OUTPUT_EVIDENCE_INCOMPLETE",
                "blocker",
                "Regelbasierte Prüfungen benötigen Regelreferenz und Prüfergebnis.",
            )
        )
    return findings


def _count_value(value: str) -> int:
    normalized = value.casefold()
    if normalized.startswith("ein"):
        return 1
    return {"zwei": 2, "drei": 3}.get(normalized, int(value) if value.isdigit() else 0)


def _latency_semantic_findings(latency_text: str) -> list[ReadinessFinding]:
    statements = _statements(latency_text)
    synchronous_retry_statements: list[str] = []
    for index, statement in enumerate(statements):
        if not _RETRY_RE.search(statement) or _ASYNC_RE.search(statement):
            continue
        context = statement
        if not _SYNC_RE.search(context):
            adjacent_statements = [
                statements[adjacent_index]
                for adjacent_index in (index - 1, index + 1)
                if 0 <= adjacent_index < len(statements)
                and _SYNC_RE.search(statements[adjacent_index])
                and not _ASYNC_RE.search(statements[adjacent_index])
            ]
            if adjacent_statements:
                context = f"{statement} {adjacent_statements[0]}"
        if _SYNC_RE.search(context):
            synchronous_retry_statements.append(context)
    if not synchronous_retry_statements:
        return []

    budget_matches = list(_LATENCY_BUDGET_RE.finditer(latency_text))
    if not budget_matches:
        message = "Für synchrone Retries fehlt ein nutzerseitiges Ende-zu-Ende-Latenzbudget."
    else:
        budget_seconds = min(_seconds(match) for match in budget_matches)
        total_matches = list(_TOTAL_SYNC_DURATION_RE.finditer(latency_text))
        total_seconds = [_seconds(match) for match in total_matches]
        timeout_matches = list(_TIMEOUT_RE.finditer(latency_text))
        retry_counts = {
            _count_value(match.group("count"))
            for statement in synchronous_retry_statements
            for match in _RETRY_COUNT_RE.finditer(statement)
        }
        attempt_counts = {
            _count_value(match.group("count"))
            for statement in synchronous_retry_statements
            for match in _ATTEMPT_COUNT_RE.finditer(statement)
        }
        total_attempts: int | None = None
        if len(attempt_counts) == 1 and not retry_counts:
            total_attempts = next(iter(attempt_counts))
        elif len(retry_counts) == 1 and not attempt_counts:
            total_attempts = next(iter(retry_counts)) + 1
        elif len(retry_counts) == 1 and len(attempt_counts) == 1:
            retry_attempts = next(iter(retry_counts)) + 1
            stated_attempts = next(iter(attempt_counts))
            if retry_attempts == stated_attempts:
                total_attempts = stated_attempts

        if len(timeout_matches) == 1 and total_attempts:
            calculated_seconds = _seconds(timeout_matches[0]) * total_attempts
            if total_seconds and any(
                abs(declared_seconds - calculated_seconds) > 0.001
                for declared_seconds in total_seconds
            ):
                message = (
                    "Die dokumentierte maximale Gesamtdauer widerspricht der aus Timeout und "
                    "Versuchszahl berechneten synchronen Retry-Dauer."
                )
            elif calculated_seconds > budget_seconds:
                message = (
                    f"Die maximale synchrone Retry-Dauer von {calculated_seconds:g} Sekunden "
                    "überschreitet das nutzerseitige Ende-zu-Ende-Latenzbudget."
                )
            else:
                return []
        elif total_seconds:
            if max(total_seconds) <= budget_seconds:
                return []
            message = (
                "Die dokumentierte maximale Gesamtdauer aller synchronen Versuche "
                "überschreitet das nutzerseitige Ende-zu-Ende-Latenzbudget."
            )
        else:
            message = (
                "Für die synchronen Retries ist keine eindeutig ableitbare oder ausdrücklich "
                "dokumentierte maximale Gesamtdauer aller Versuche vorhanden."
            )

    return [
        ReadinessFinding(
            "requirements_and_governance",
            "LATENCY_RETRY_BUDGET_CONFLICT",
            "blocker",
            message,
        )
    ]


def _retention_segments(retention_text: str) -> dict[str, str]:
    occurrences: list[tuple[int, str]] = []
    for label, pattern in _RETENTION_CATEGORIES.items():
        occurrences.extend((match.start(), label) for match in pattern.finditer(retention_text))
    occurrences.sort()
    segments: dict[str, list[str]] = {label: [] for label in _RETENTION_CATEGORIES}
    for index, (start, label) in enumerate(occurrences):
        end = occurrences[index + 1][0] if index + 1 < len(occurrences) else len(retention_text)
        segments[label].append(retention_text[start:end].strip())
    return {label: "\n".join(values) for label, values in segments.items()}


def _retention_semantic_findings(retention_text: str) -> list[ReadinessFinding]:
    segments = _retention_segments(retention_text)
    problems: list[str] = []
    for label, segment in segments.items():
        if not segment:
            problems.append(f"{label}: Kategorie fehlt")
            continue
        purpose_complete = bool(_PURPOSE_RE.search(segment)) and not (
            _INVALID_PURPOSE_RE.search(segment) or _SEMANTIC_PLACEHOLDER_RE.search(segment)
        )
        has_retention_rule = bool(
            _RETENTION_DURATION_RE.search(segment)
            or _EVENT_DELETION_RE.search(segment)
            or _NON_PERSISTENCE_RE.search(segment)
        )
        has_invalid_retention = bool(
            _INVALID_RETENTION_RE.search(segment) or _SEMANTIC_PLACEHOLDER_RE.search(segment)
        )
        retention_complete = has_retention_rule and not has_invalid_retention
        if not purpose_complete:
            problems.append(f"{label}: Zweck fehlt oder ist noch ein Platzhalter")
        if not retention_complete:
            problems.append(f"{label}: konkrete Lösch-/Aufbewahrungsregel fehlt")
    if not problems:
        return []
    return [
        ReadinessFinding(
            "requirements_and_governance",
            "RETENTION_SEMANTICS_INCOMPLETE",
            "blocker",
            "Retention unvollständig: " + "; ".join(problems) + ".",
        )
    ]


def _quality_semantic_findings(package: DeliveryPackage) -> list[ReadinessFinding]:
    findings: list[ReadinessFinding] = []
    evaluation_text = "\n".join(
        _text(value)
        for value in (
            package.acceptance_criteria,
            package.test_scenarios,
            package.measurement_plan,
        )
    )
    if _PERCENT_THRESHOLD_RE.search(evaluation_text):
        if not _has_concrete_match(evaluation_text, _POPULATION_CONTEXT_RE):
            findings.append(
                ReadinessFinding(
                    "acceptance_and_measurement",
                    "EVALUATION_POPULATION_MISSING",
                    "warning",
                    (
                        "Prozentuale Qualitätsgrenzen benötigen eine benannte Testpopulation "
                        "und eine nachvollziehbare Stichprobengröße."
                    ),
                )
            )
        if not _has_concrete_match(evaluation_text, _SAMPLE_SIZE_RE):
            findings.append(
                ReadinessFinding(
                    "acceptance_and_measurement",
                    "EVALUATION_SAMPLE_SIZE_MISSING",
                    "warning",
                    "Für die prozentualen Qualitätsgrenzen fehlt eine numerische Stichprobengröße.",
                )
            )
        if not _has_concrete_match(evaluation_text, _UNCERTAINTY_CONTEXT_RE):
            findings.append(
                ReadinessFinding(
                    "acceptance_and_measurement",
                    "EVALUATION_UNCERTAINTY_UNDOCUMENTED",
                    "warning",
                    (
                        "Für die prozentualen Qualitätsgrenzen ist die statistische "
                        "Aussagekraft beziehungsweise Unsicherheit noch nicht dokumentiert."
                    ),
                )
            )
        critical_class_covered = any(
            _CRITICAL_CLASS_RE.search(statement)
            and _TARGETED_TEST_SIZE_RE.search(statement)
            and not _NEGATED_CRITICAL_TEST_RE.search(statement)
            and not _SEMANTIC_PLACEHOLDER_RE.search(statement)
            for statement in _statements(evaluation_text)
        )
        if not critical_class_covered:
            findings.append(
                ReadinessFinding(
                    "acceptance_and_measurement",
                    "CRITICAL_ERROR_CLASSES_UNDOCUMENTED",
                    "warning",
                    (
                        "Seltene oder kritische Fehlerklassen sollten mit gezielten "
                        "Testfällen beziehungsweise Testsets abgedeckt werden."
                    ),
                )
            )
    if _RECALL_TARGET_RE.search(evaluation_text) and not _has_concrete_match(
        evaluation_text, _POSITIVE_CASE_COUNT_RE
    ):
        findings.append(
            ReadinessFinding(
                "acceptance_and_measurement",
                "RECALL_POSITIVE_CASES_MISSING",
                "warning",
                "Ein Recall-Ziel benötigt die numerische Anzahl positiver Fälle im Testset.",
            )
        )

    confidence_text = "\n".join(
        _text(value)
        for value in (
            package.acceptance_criteria,
            package.human_oversight,
            package.non_functional_requirements,
        )
    )
    findings.extend(_output_semantic_findings(confidence_text))

    artifacts = get_delivery_architecture_artifacts(package)
    latency_text = "\n".join(
        _text(value)
        for value in (
            package.non_functional_requirements,
            package.operations_and_support,
            getattr(artifacts, "integration_operations", ""),
        )
    )
    findings.extend(_latency_semantic_findings(latency_text))

    retention_text = "\n".join(
        _text(value)
        for value in (
            package.logging_and_audit,
            package.security_privacy_requirements,
            package.operations_and_support,
        )
    )
    findings.extend(_retention_semantic_findings(retention_text))
    return findings


def _text(value) -> str:
    return str(value or "").strip()


def _field_label(package: DeliveryPackage, field_name: str) -> str:
    return str(package._meta.get_field(field_name).verbose_name)


def _is_generic_placeholder(value: str) -> bool:
    normalized = value.casefold()
    return any(fragment in normalized for fragment in GENERIC_PLACEHOLDER_FRAGMENTS)


def _parse_manifest_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _source_staleness_findings(
    package: DeliveryPackage,
    reviews_by_key,
) -> list[ReadinessFinding]:
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        # The handed-over version is an immutable snapshot. Later source changes belong to a
        # new package version and must not retroactively invalidate the completed handover.
        return []
    review = reviews_by_key.get("problem_and_target")
    if review is None or not review.source_manifest:
        return []

    try:
        origin = package.use_case.architecture_origin
    except ObjectDoesNotExist:
        origin = None
    objects = {
        "use_case": package.use_case,
        "value_stream": origin.stage.value_stream if origin is not None else None,
        "value_stream_stage": origin.stage if origin is not None else None,
        "process_analysis": origin.process_analysis if origin is not None else None,
        "solution_option": origin.solution_option if origin is not None else None,
    }
    findings: list[ReadinessFinding] = []
    role_source = (review.source_manifest.get("role_sources") or {}).get("technical_owner")
    if role_source is not None:
        snapshot_id = str(role_source.get("id") or "")
        current_id = str(package.use_case.technical_owner_id or "")
        if snapshot_id != current_id:
            findings.append(
                ReadinessFinding(
                    "architecture_and_data",
                    "TECHNICAL_OWNER_SOURCE_CHANGE_UNRESOLVED",
                    "blocker",
                    (
                        "Der Technical Owner wurde am Use Case geändert. Alter Package-Wert, "
                        "neuer Quellwert und Übernahmeentscheidung müssen vor der Übergabe "
                        "nachvollziehbar geklärt werden."
                    ),
                )
            )
    for package_field, source in (review.source_manifest.get("field_sources") or {}).items():
        obj = objects.get(source.get("kind"))
        source_field = source.get("field")
        if obj is None or not source_field:
            continue
        current = getattr(obj, source_field, None)
        current_text = "" if current is None else str(current)
        snapshot_text = str(source.get("value") or "")
        if current_text == snapshot_text:
            continue
        label = str(package._meta.get_field(package_field).verbose_name)
        findings.append(
            ReadinessFinding(
                "delivery_control",
                "SOURCE_CHANGED_AFTER_SNAPSHOT",
                "warning",
                (
                    f"Quelle für „{label}“ geändert: "
                    f"„{snapshot_text or '-'}“ → „{current_text or '-'}“."
                ),
            )
        )
    return findings


def evaluate_delivery_readiness(package: DeliveryPackage) -> list[ReadinessFinding]:
    if package.readiness_schema_version < 2:
        return []

    findings: list[ReadinessFinding] = []
    if package.technical_owner_id is None:
        findings.append(
            ReadinessFinding(
                "architecture_and_data",
                "TECHNICAL_OWNER_MISSING",
                "blocker",
                "Vor der Übergabe muss ein Technical Owner benannt sein.",
            )
        )
    elif not package.technical_owner.is_active:
        findings.append(
            ReadinessFinding(
                "architecture_and_data",
                "TECHNICAL_OWNER_INACTIVE",
                "blocker",
                (
                    "Der zugeordnete Technical Owner ist nicht aktiv und kann die technische "
                    "Verantwortung nicht wahrnehmen."
                ),
            )
        )

    reviews = {review.section_key: review for review in package.section_reviews.all()}
    for section_key, section_label in DELIVERY_SECTION_DEFINITIONS:
        review = reviews.get(section_key)
        if review is None:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "SECTION_REVIEW_MISSING",
                    "blocker",
                    f"Für „{section_label}“ fehlt die strukturierte Sektionsprüfung.",
                )
            )
            continue
        if not review.source_manifest:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "SOURCE_MANIFEST_MISSING",
                    "blocker",
                    f"Für „{section_label}“ fehlt der Quellenstand.",
                )
            )
        if review.review_status == DeliverySectionReview.ReviewStatus.BLOCKED:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "SECTION_BLOCKED",
                    "blocker",
                    review.review_note or f"Die Sektion „{section_label}“ ist blockiert.",
                )
            )
        elif review.review_status == DeliverySectionReview.ReviewStatus.NEEDS_REVIEW:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "SECTION_NEEDS_REVIEW",
                    "blocker",
                    f"Die Sektion „{section_label}“ wurde noch nicht vollständig bestätigt.",
                )
            )
        elif review.review_status == DeliverySectionReview.ReviewStatus.NOT_APPLICABLE:
            if not _text(review.review_note):
                findings.append(
                    ReadinessFinding(
                        section_key,
                        "NOT_APPLICABLE_REASON_MISSING",
                        "blocker",
                        f"Für „{section_label}“ fehlt die Begründung der Nichtanwendbarkeit.",
                    )
                )
        elif not review.confirmations_complete:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "REQUIRED_CONFIRMATION_MISSING",
                    "blocker",
                    (
                        f"Für „{section_label}“ fehlen erforderliche fachliche oder "
                        "technische Bestätigungen."
                    ),
                )
            )
        elif review.has_role_collapse:
            findings.append(
                ReadinessFinding(
                    section_key,
                    "INDEPENDENT_CONFIRMATION_MISSING",
                    "blocker",
                    (
                        f"Für „{section_label}“ wurden fachliche und technische "
                        "Bestätigung durch dieselbe Person erteilt. Vor der Übergabe "
                        "ist eine unabhängige Bestätigung durch eine zweite Person "
                        "erforderlich."
                    ),
                )
            )

    for section_key, field_names in READY_REQUIRED_FIELDS.items():
        for field_name in field_names:
            value = _text(getattr(package, field_name, ""))
            label = _field_label(package, field_name)
            if not value:
                findings.append(
                    ReadinessFinding(
                        section_key,
                        f"{field_name.upper()}_MISSING",
                        "blocker",
                        f"Pflichtangabe fehlt: {label}.",
                    )
                )
            elif _is_generic_placeholder(value):
                findings.append(
                    ReadinessFinding(
                        section_key,
                        f"{field_name.upper()}_GENERIC",
                        "blocker",
                        (
                            f"Die Angabe „{label}“ ist noch eine generische Vorlage und "
                            "muss konkretisiert werden."
                        ),
                    )
                )

    artifacts = get_delivery_architecture_artifacts(package)
    if artifacts is None:
        findings.append(
            ReadinessFinding(
                "architecture_and_data",
                "ARCHITECTURE_ARTIFACTS_MISSING",
                "blocker",
                "Die umsetzungsbezogenen Architekturartefakte fehlen.",
            )
        )
    else:
        for field_name, label in ARCHITECTURE_REQUIRED_FIELDS.items():
            value = _text(getattr(artifacts, field_name, ""))
            if not value:
                findings.append(
                    ReadinessFinding(
                        "architecture_and_data",
                        f"{field_name.upper()}_MISSING",
                        "blocker",
                        f"Pflichtangabe fehlt: {label}.",
                    )
                )
            elif _is_generic_placeholder(value):
                findings.append(
                    ReadinessFinding(
                        "architecture_and_data",
                        f"{field_name.upper()}_GENERIC",
                        "blocker",
                        (
                            f"Die Angabe „{label}“ ist noch eine generische Vorlage und "
                            "muss konkretisiert werden."
                        ),
                    )
                )

    decision = package.generated_from_decision
    if _text(decision.conditions):
        if decision.condition_owner_id is None:
            findings.append(
                ReadinessFinding(
                    "delivery_control",
                    "CONDITION_OWNER_MISSING",
                    "blocker",
                    "Die Freigabe enthält Auflagen, aber keinen verantwortlichen Condition Owner.",
                )
            )
        if decision.condition_due_date is None:
            findings.append(
                ReadinessFinding(
                    "delivery_control",
                    "CONDITION_DUE_DATE_MISSING",
                    "blocker",
                    "Die Freigabe enthält Auflagen, aber keine Fälligkeit.",
                )
            )
        if decision.conditions.casefold() not in package.handover_notes.casefold():
            findings.append(
                ReadinessFinding(
                    "delivery_control",
                    "APPROVAL_CONDITIONS_NOT_TRANSFERRED",
                    "blocker",
                    (
                        "Die verbindlichen Freigabeauflagen wurden nicht vollständig in die "
                        "Übergabehinweise übernommen."
                    ),
                )
            )

    findings.extend(_source_staleness_findings(package, reviews))
    findings.extend(_quality_semantic_findings(package))
    return findings


def blocking_findings(package: DeliveryPackage) -> list[ReadinessFinding]:
    return [
        finding for finding in evaluate_delivery_readiness(package) if finding.severity == "blocker"
    ]


def delivery_status_snapshot(package: DeliveryPackage) -> DeliveryStatusSnapshot:
    if package.status == DeliveryPackage.Status.HANDED_OVER:
        if package.handed_over_at is None or blocking_findings(package):
            return DeliveryStatusSnapshot(
                code="handover_inconsistent",
                label="Übergabe blockiert (inkonsistenter Bestand)",
                handover_complete=False,
            )
        return DeliveryStatusSnapshot(
            code=package.status,
            label=package.get_status_display(),
            handover_complete=package.handed_over_at is not None,
        )
    if package.status == DeliveryPackage.Status.READY and blocking_findings(package):
        return DeliveryStatusSnapshot(
            code="readiness_blocked",
            label="Readiness blockiert",
            handover_complete=False,
        )
    return DeliveryStatusSnapshot(
        code=package.status,
        label=package.get_status_display(),
        handover_complete=False,
    )


def _legacy_missing_ready_fields(package: DeliveryPackage) -> list[str]:
    legacy_fields = (
        "problem_context",
        "target_outcome",
        "in_scope",
        "out_of_scope",
        "users_and_scenarios",
        "solution_outline",
        "system_context",
        "data_context",
        "functional_requirements",
        "non_functional_requirements",
        "security_privacy_requirements",
        "human_oversight",
        "logging_and_audit",
        "operations_and_support",
        "mvp_scope",
        "acceptance_criteria",
        "test_scenarios",
        "measurement_plan",
        "initial_backlog",
        "integrations",
        "dependencies",
        "risks",
        "assumptions",
        "architecture_decisions",
    )
    missing = [
        _field_label(package, field_name)
        for field_name in legacy_fields
        if not _text(getattr(package, field_name, ""))
    ]
    artifacts = get_delivery_architecture_artifacts(package)
    if artifacts is None:
        missing.extend(
            [
                "Ist-/Ziel-Systemlandschaft",
                "Daten- und Informationsflüsse",
                "Integrationsverträge und Verantwortlichkeiten",
            ]
        )
    else:
        legacy_artifact_fields = {
            "system_landscape": "Ist-/Ziel-Systemlandschaft",
            "data_flows": "Daten- und Informationsflüsse",
            "integration_contracts": "Integrationsverträge und Verantwortlichkeiten",
        }
        for field_name, label in legacy_artifact_fields.items():
            if not _text(getattr(artifacts, field_name, "")):
                missing.append(label)
    return list(dict.fromkeys(missing))


def missing_ready_fields(package: DeliveryPackage) -> list[str]:
    if package.readiness_schema_version < 2:
        return _legacy_missing_ready_fields(package)
    return [finding.message for finding in blocking_findings(package)]


def render_delivery_markdown(package: DeliveryPackage) -> str:
    """Compatibility wrapper for callers of the former readiness export."""

    from .exports import render_delivery_markdown as render

    return render(package)
