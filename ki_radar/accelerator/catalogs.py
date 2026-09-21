from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal

CaptureType = Literal["value_stream", "use_case"]
InputType = Literal["text", "textarea"]

ANSWER_SCHEMA_VERSION = "1.0"
CATALOG_VERSION_V1 = "1.0"
QUESTION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
CONTRACT_PATH = (
    Path(__file__).resolve().parents[1] / "core" / "scenario_blueprints" / "contract.v1.json"
)


class UnsupportedCaptureCatalog(ValueError):
    """Raised when a persisted capture references an unavailable catalog."""


class CaptureAnswerValidationError(ValueError):
    """Raised when an answer document violates the versioned capture contract."""

    def __init__(self, errors: list[str] | tuple[str, ...]):
        self.errors = tuple(errors)
        super().__init__("; ".join(self.errors))


@dataclass(frozen=True)
class CaptureQuestion:
    key: str
    label: str
    help_text: str
    required: bool
    input_type: InputType
    max_length: int
    target_paths: tuple[str, ...]
    narrative_area: str
    rows: int = 6


@dataclass(frozen=True)
class CaptureSection:
    key: str
    title: str
    description: str
    questions: tuple[CaptureQuestion, ...]


@dataclass(frozen=True)
class CaptureCatalog:
    capture_type: CaptureType
    version: str
    schema_version: str
    title: str
    sections: tuple[CaptureSection, ...]

    @property
    def questions(self) -> tuple[CaptureQuestion, ...]:
        return tuple(question for section in self.sections for question in section.questions)

    @property
    def question_map(self) -> dict[str, CaptureQuestion]:
        return {question.key: question for question in self.questions}

    @property
    def required_question_keys(self) -> tuple[str, ...]:
        return tuple(question.key for question in self.questions if question.required)


def _question(
    key: str,
    label: str,
    help_text: str,
    *,
    targets: tuple[str, ...],
    area: str,
    required: bool = True,
    max_length: int = 12_000,
    input_type: InputType = "textarea",
    rows: int = 7,
) -> CaptureQuestion:
    return CaptureQuestion(
        key=key,
        label=label,
        help_text=help_text,
        required=required,
        input_type=input_type,
        max_length=max_length,
        target_paths=targets,
        narrative_area=area,
        rows=rows,
    )


VALUE_STREAM_CATALOG_V1 = CaptureCatalog(
    capture_type="value_stream",
    version=CATALOG_VERSION_V1,
    schema_version=ANSWER_SCHEMA_VERSION,
    title="Geführte Value-Stream-Erfassung",
    sections=(
        CaptureSection(
            key="context",
            title="Kontext und Ziel",
            description="Beschreiben Sie den fachlichen Zusammenhang, noch ohne Entscheidung.",
            questions=(
                _question(
                    "vs_context",
                    "Wie heißt der Value Stream und welchen fachlichen Zweck erfüllt er?",
                    (
                        "Beschreiben Sie Ausgangslage, Empfänger des Ergebnisses und "
                        "strategisches Ziel."
                    ),
                    targets=(
                        "value_stream.name",
                        "value_stream.description",
                        "value_stream.strategic_objective",
                        "value_stream.focus.business_domain",
                        "value_stream.focus.capability",
                    ),
                    area="value_stream_context",
                ),
                _question(
                    "vs_trigger_outcome",
                    "Was löst den Value Stream aus und welches Ergebnis soll am Ende vorliegen?",
                    "Trennen Sie das auslösende Ereignis vom fachlichen Ergebnis.",
                    targets=("value_stream.trigger", "value_stream.outcome"),
                    area="value_stream_boundaries",
                ),
            ),
        ),
        CaptureSection(
            key="scope",
            title="Umfang und Leitplanken",
            description="Grenzen und Beteiligte werden ausdrücklich getrennt erfasst.",
            questions=(
                _question(
                    "vs_scope_in",
                    "Welche Aktivitäten und Ergebnisse gehören ausdrücklich zum Umfang?",
                    "Beschreiben Sie ausschließlich den eingeschlossenen Umfang.",
                    targets=("value_stream.scope_in",),
                    area="scope_in",
                ),
                _question(
                    "vs_scope_out",
                    "Welche Aktivitäten und Entscheidungen gehören ausdrücklich nicht zum Umfang?",
                    "Beschreiben Sie ausschließlich die Abgrenzung.",
                    targets=("value_stream.scope_out",),
                    area="scope_out",
                ),
                _question(
                    "vs_stakeholders_constraints",
                    "Welche Stakeholder, Verantwortlichkeiten und Leitplanken sind relevant?",
                    "Nennen Sie beteiligte Gruppen, regulatorische Grenzen und fachliche Vorgaben.",
                    targets=("value_stream.stakeholders", "value_stream.constraints"),
                    area="stakeholders_constraints",
                ),
            ),
        ),
        CaptureSection(
            key="stages",
            title="Phasen des Value Streams",
            description=(
                "Beschreiben Sie die fachliche Reihenfolge und den heutigen Arbeitskontext."
            ),
            questions=(
                _question(
                    "vs_stages",
                    "Welche Phasen durchläuft der Value Stream in welcher Reihenfolge?",
                    (
                        "Beschreiben Sie je Phase einen erkennbaren Wertfortschritt: Was liegt "
                        "vorher vor, was verändert sich fachlich und welcher relevante Zustand "
                        "bzw. welches Ergebnis ist anschließend erreicht? Benennen Sie zusätzlich "
                        "die sinnvolle Reihenfolge."
                    ),
                    targets=(
                        "value_stream.stages[].sequence",
                        "value_stream.stages[].name",
                        "value_stream.stages[].description",
                    ),
                    area="value_stream_stages",
                ),
                _question(
                    "vs_stage_operations",
                    "Welche Rollen, Systeme sowie Daten oder Dokumente werden je Phase genutzt?",
                    "Ordnen Sie die Angaben möglichst den zuvor genannten Phasen zu.",
                    targets=(
                        "value_stream.stages[].actors",
                        "value_stream.stages[].systems",
                        "value_stream.stages[].documents",
                    ),
                    area="stage_operating_context",
                ),
                _question(
                    "vs_stage_pain_metrics",
                    "Welche Probleme, Engpässe und heutigen Kennzahlen bestehen je Phase?",
                    "Nennen Sie beobachtbare Probleme und vorhandene Baselines mit Einheit.",
                    targets=(
                        "value_stream.stages[].pain_points",
                        "value_stream.stages[].baseline_metrics",
                    ),
                    area="stage_pain_metrics",
                ),
            ),
        ),
        CaptureSection(
            key="process",
            title="Fokusprozess",
            description="Vertiefen Sie den wichtigsten Prozess als unbestätigten Entwurf.",
            questions=(
                _question(
                    "process_scope_flow",
                    "Welcher Prozess soll vertieft werden und wie verläuft er heute?",
                    (
                        "Beschreiben Sie Name, Start, Ende, Auslöser, Ergebnis und die "
                        "wesentlichen Schritte."
                    ),
                    targets=(
                        "process_analysis.name",
                        "process_analysis.scope_start",
                        "process_analysis.scope_end",
                        "process_analysis.trigger",
                        "process_analysis.outcome",
                        "process_analysis.current_flow",
                    ),
                    area="process_scope_flow",
                ),
                _question(
                    "process_operating_model",
                    (
                        "Welche Rollen, Systeme, Datenobjekte, Regeln und Übergaben prägen "
                        "den Prozess?"
                    ),
                    (
                        "Beschreiben Sie Verantwortlichkeiten und Schnittstellen, ohne sie "
                        "zu bestätigen."
                    ),
                    targets=(
                        "process_analysis.roles",
                        "process_analysis.systems",
                        "process_analysis.data_objects",
                        "process_analysis.business_rules",
                        "process_analysis.handoffs",
                    ),
                    area="process_operating_model",
                ),
                _question(
                    "process_findings_target",
                    "Welche Ursachen, Ausnahmen und Kennzahlen erklären das Problem?",
                    (
                        "Ergänzen Sie Bottlenecks, Fehlerfälle, Baseline und Prinzipien für "
                        "den Soll-Zustand."
                    ),
                    targets=(
                        "process_analysis.bottlenecks",
                        "process_analysis.exceptions",
                        "process_analysis.baseline_metrics",
                        "process_analysis.target_state_principles",
                    ),
                    area="process_findings_target",
                ),
            ),
        ),
        CaptureSection(
            key="solutions",
            title="Lösungsalternativen",
            description="Erfassen Sie mehrere unbewertete Kandidaten, nicht nur eine KI-Idee.",
            questions=(
                _question(
                    "solution_candidates",
                    (
                        "Welche organisatorischen, regelbasierten, technischen oder "
                        "KI-gestützten Optionen sind denkbar?"
                    ),
                    (
                        "Beschreiben Sie je Kandidat Name, Typ, Nutzen, abgedeckte Bottlenecks, "
                        "Machbarkeit, Daten, Auswirkungen, Integrationsaufwand, Risiken und "
                        "Architecture Fit."
                    ),
                    targets=(
                        "solution_options[].name",
                        "solution_options[].option_type",
                        "solution_options[].description",
                        "solution_options[].expected_value",
                        "solution_options[].bottleneck_coverage",
                        "solution_options[].feasibility",
                        "solution_options[].data_requirements",
                        "solution_options[].application_impact",
                        "solution_options[].integration_effort",
                        "solution_options[].integration_impact",
                        "solution_options[].technology_constraints",
                        "solution_options[].risks",
                        "solution_options[].architecture_fit",
                    ),
                    area="solution_candidates",
                ),
                _question(
                    "vs_open_questions",
                    "Welche Annahmen, Lücken oder Widersprüche müssen später geklärt werden?",
                    "Fehlende Informationen bleiben offen und werden nicht erfunden.",
                    targets=(),
                    area="open_questions",
                    required=False,
                ),
            ),
        ),
    ),
)


USE_CASE_CATALOG_V1 = CaptureCatalog(
    capture_type="use_case",
    version=CATALOG_VERSION_V1,
    schema_version=ANSWER_SCHEMA_VERSION,
    title="Geführte Use-Case-Erfassung",
    sections=(
        CaptureSection(
            key="problem",
            title="Problem und Prozess",
            description="Ausgangspunkt ist ein beobachtbares Problem, nicht eine Technologie.",
            questions=(
                _question(
                    "uc_problem_context",
                    "Wie heißt der Use Case und welches konkrete Problem soll gelöst werden?",
                    (
                        "Beschreiben Sie Auswirkungen, heutigen Ablauf, betroffenen Prozess "
                        "und Zielgruppen."
                    ),
                    targets=(
                        "use_case.title",
                        "use_case.summary",
                        "use_case.problem_statement",
                        "use_case.affected_process",
                        "use_case.target_users",
                        "use_case.classification.business_domain",
                        "use_case.classification.capability",
                        "use_case.classification.process_area",
                    ),
                    area="use_case_problem",
                ),
            ),
        ),
        CaptureSection(
            key="usage_data",
            title="Nutzung, Systeme und Daten",
            description="Beschreiben Sie den zulässigen Einsatz und den bekannten Datenrahmen.",
            questions=(
                _question(
                    "uc_users_purpose",
                    "Wer nutzt die Lösung und wozu darf sie eingesetzt werden?",
                    "Trennen Sie unmittelbare Nutzer, Betroffene und zulässigen Zweck.",
                    targets=("use_case.intended_users", "use_case.intended_purpose"),
                    area="users_purpose",
                ),
                _question(
                    "uc_systems_data",
                    "Welche Systeme, Datenquellen und Schnittstellen sind betroffen?",
                    "Nennen Sie führende Systeme, benötigte Daten und bekannte Übergaben.",
                    targets=(
                        "use_case.source_systems",
                        "use_case.data_sources",
                        "use_case.interface_description",
                    ),
                    area="systems_data",
                ),
            ),
        ),
        CaptureSection(
            key="benefit",
            title="Nutzen und Messung",
            description="Machen Sie die erwartete Wirkung anhand einer primären Metrik prüfbar.",
            questions=(
                _question(
                    "uc_benefit",
                    "Welche messbare Verbesserung wird erwartet?",
                    "Beschreiben Sie Nutzen, Empfänger und Nutzenkategorie.",
                    targets=("use_case.expected_benefit", "use_case.benefit_category"),
                    area="benefit",
                ),
                _question(
                    "uc_metric",
                    "Wie wird die primäre Erfolgsmetrik definiert und gemessen?",
                    (
                        "Nennen Sie Name, Typ, Optimierungsrichtung, Einheit, Baseline, Zielwert "
                        "und Messmethode einschließlich Zeitraum oder Stichprobe."
                    ),
                    targets=(
                        "use_case.metric.name",
                        "use_case.metric.type",
                        "use_case.metric.direction",
                        "use_case.metric.unit",
                        "use_case.metric.baseline",
                        "use_case.metric.target",
                        "use_case.metric.measurement_method",
                    ),
                    area="metric",
                ),
            ),
        ),
        CaptureSection(
            key="solution_risk",
            title="Lösungsrahmen und Verantwortung",
            description=(
                "Erfassen Sie bekannte Rahmenbedingungen, ohne eine Freigabe vorwegzunehmen."
            ),
            questions=(
                _question(
                    "uc_solution_context",
                    "Welcher Lösungs-, Produkt-, Modell- und Hosting-Rahmen ist bereits bekannt?",
                    "Offene Angaben dürfen ausdrücklich als unbekannt benannt werden.",
                    targets=(
                        "use_case.priority",
                        "use_case.solution_type",
                        "use_case.hosting_type",
                        "use_case.provider",
                        "use_case.product_name",
                        "use_case.model_name",
                    ),
                    area="solution_context",
                ),
                _question(
                    "uc_cost_assessment",
                    "Welche Kosten- und Reifeannahmen bestehen derzeit?",
                    (
                        "Beschreiben Sie einmalige und laufende Kosten sowie Geschäftswert, "
                        "Machbarkeit, Datenreife und Risikokomplexität als vorläufige Einschätzung."
                    ),
                    targets=(
                        "use_case.one_time_cost",
                        "use_case.recurring_cost",
                        "use_case.business_value",
                        "use_case.technical_feasibility",
                        "use_case.data_readiness",
                        "use_case.risk_complexity",
                    ),
                    area="cost_assessment",
                    required=False,
                ),
                _question(
                    "uc_oversight_support",
                    "Welche menschliche Aufsicht und Support-Verantwortung sind erforderlich?",
                    "Beschreiben Sie Kontrollpunkte und bekannte Betriebsverantwortung.",
                    targets=("use_case.human_oversight", "use_case.support_responsibility"),
                    area="oversight_support",
                ),
                _question(
                    "uc_open_questions",
                    "Welche Annahmen, Lücken oder Widersprüche müssen später geklärt werden?",
                    "Fehlende Informationen bleiben offen und werden nicht erfunden.",
                    targets=(),
                    area="open_questions",
                    required=False,
                ),
            ),
        ),
    ),
)


CATALOGS: dict[tuple[CaptureType, str], CaptureCatalog] = {
    ("value_stream", CATALOG_VERSION_V1): VALUE_STREAM_CATALOG_V1,
    ("use_case", CATALOG_VERSION_V1): USE_CASE_CATALOG_V1,
}
CURRENT_CATALOG_VERSIONS: dict[CaptureType, str] = {
    "value_stream": CATALOG_VERSION_V1,
    "use_case": CATALOG_VERSION_V1,
}


def get_capture_catalog(capture_type: CaptureType, version: str | None = None) -> CaptureCatalog:
    selected_version = version or CURRENT_CATALOG_VERSIONS.get(capture_type)
    catalog = CATALOGS.get((capture_type, selected_version))
    if catalog is None:
        raise UnsupportedCaptureCatalog(
            f"Der Fragenkatalog {capture_type!r} in Version {selected_version!r} "
            "wird nicht mehr unterstützt."
        )
    return catalog


def is_capture_catalog_supported(capture_type: str, version: str) -> bool:
    return (capture_type, version) in CATALOGS


@lru_cache(maxsize=1)
def allowed_blueprint_target_paths() -> frozenset[str]:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    allowed_fields = contract["allowed_fields"]
    paths: set[str] = set()

    paths.update(
        f"value_stream.{field}"
        for field in allowed_fields["value_stream"]
        if field not in {"focus", "stages"}
    )
    paths.update(f"value_stream.focus.{field}" for field in allowed_fields["value_stream.focus"])
    paths.update(f"value_stream.stages[].{field}" for field in allowed_fields["value_stream.stage"])
    paths.update(f"process_analysis.{field}" for field in allowed_fields["process_analysis"])
    paths.update(f"solution_options[].{field}" for field in allowed_fields["solution_option"])
    paths.update(
        f"use_case.{field}"
        for field in allowed_fields["use_case"]
        if field not in {"metric", "classification"}
    )
    paths.update(f"use_case.metric.{field}" for field in allowed_fields["use_case.metric"])
    paths.update(
        f"use_case.classification.{field}" for field in allowed_fields["use_case.classification"]
    )
    return frozenset(paths)


def catalog_contract_errors(catalog: CaptureCatalog) -> tuple[str, ...]:
    errors: list[str] = []
    question_keys: set[str] = set()
    section_keys: set[str] = set()
    allowed_paths = allowed_blueprint_target_paths()

    for section in catalog.sections:
        if section.key in section_keys:
            errors.append(f"Doppelter Abschnittsschlüssel: {section.key}")
        section_keys.add(section.key)
        for question in section.questions:
            if not QUESTION_ID_PATTERN.fullmatch(question.key):
                errors.append(f"Ungültige Frage-ID: {question.key}")
            if question.key in question_keys:
                errors.append(f"Doppelte Frage-ID: {question.key}")
            question_keys.add(question.key)
            if question.input_type not in {"text", "textarea"}:
                errors.append(f"Unzulässiger Eingabetyp für {question.key}")
            if question.max_length < 1:
                errors.append(f"Ungültige Längengrenze für {question.key}")
            for target_path in question.target_paths:
                if target_path not in allowed_paths:
                    errors.append(f"Unbekannter Blueprint-Zielpfad {target_path} in {question.key}")
    return tuple(errors)


def validate_answer_document(
    catalog: CaptureCatalog,
    answers: object,
    *,
    require_complete: bool = False,
) -> dict[str, str]:
    errors: list[str] = []
    if not isinstance(answers, dict):
        raise CaptureAnswerValidationError(["Antworten müssen ein JSON-Objekt sein."])

    questions = catalog.question_map
    normalized: dict[str, str] = {}
    for key, value in answers.items():
        if key not in questions:
            errors.append(f"Unbekannte Frage-ID: {key}")
            continue
        if not isinstance(value, str):
            errors.append(f"Antwort für {key} muss Text sein.")
            continue
        cleaned = value.strip()
        if len(cleaned) > questions[key].max_length:
            errors.append(f"Antwort für {key} überschreitet {questions[key].max_length} Zeichen.")
            continue
        normalized[key] = cleaned

    if require_complete:
        for key in catalog.required_question_keys:
            if not normalized.get(key):
                errors.append(f"Pflichtantwort fehlt: {key}")

    if errors:
        raise CaptureAnswerValidationError(errors)
    return normalized


def catalog_progress(catalog: CaptureCatalog, answers: object) -> tuple[int, int]:
    if not isinstance(answers, dict):
        return 0, len(catalog.required_question_keys)
    completed = sum(
        1
        for key in catalog.required_question_keys
        if isinstance(answers.get(key), str) and answers[key].strip()
    )
    return completed, len(catalog.required_question_keys)
