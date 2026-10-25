"""Explicitly human-scoped exploration, isolated from historical discovery contracts."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone

CATALOG = "3.0"
ANSWER_SCHEMA = "1.1"
SCHEMA = "ap1-discovery-v3"
PROMPT = "ap1-methodology-v15"
VERIFIER_SCHEMA = "ap1-discovery-verifier-v2"
VERIFIER_PROMPT = "ap1-ver-method-v14"
INPUT_SCHEMA = "ap1-discovery-input-v1"
SCOPE_FIELDS = ("scope_start", "scope_end", "scope_out", "reason", "validation_step")
REQUIRED_SCOPE_FIELDS = ("scope_start", "scope_end", "reason", "validation_step")
STAGE_RATINGS = (
    "impact",
    "pain_intensity",
    "improvement_potential",
    "data_accessibility",
    "change_effort",
)
FOCUS_RATINGS = (
    "strategic_impact",
    "economic_potential",
    "pain_intensity",
    "data_accessibility",
    "change_effort",
)

RULES = """
Dies ist ausschließlich eine ausdrücklich strategische, menschlich abgegrenzte Exploration.
human_scope ist eine vom Server eingefrorene menschliche Untersuchungsanweisung, KEIN
Ist-Prozessbeleg. Kopiere ihre fünf Scopefelder exakt nach scope_basis, auch leere Werte.
process_analysis.scope_start/scope_end müssen exakt diesen menschlichen Grenzen entsprechen.
Fehlt eine Grenze, benenne einen offenen Scopeentscheid; erfinde keine menschliche Zustimmung.
Beschreibe Phasen ausdrücklich als vorläufigen Untersuchungsrahmen (hypothesis), nicht als
beobachtete Prozessfolge. current_flow: Ist-Ablauf unbekannt, sofern keine Quelle ihn berichtet.
Keine Ursache, Rollen, Systeme, Zahlen, Verfügbarkeit oder wirtschaftliche Wirkung erfinden.
Alle qualitativen Screening-Ratings bleiben in dieser explorativen Route leer ("");
time_to_value bleibt unknown. Keine low/medium/high-Schätzwerte als Ersatz für Unbekanntes.
Der menschlich begründete Bereich entscheidet den vorläufigen Fokus, keine Fokusüberlegenheit.
clarifications erhalten kind=scope_decision oder evidence_collection. Nur eine tatsächlich
offene verantwortbare Scope-/Fokusentscheidung darf blocking=true sein. Fehlende Baseline,
Ist-Abläufe und Rollen innerhalb eines verantwortbar abgegrenzten Untersuchungsbereichs sind
spätere Evidenzerhebung (evidence_collection, blocking=false); Unknowns bleiben sichtbar.
Ist der Bereich selbst nicht verantwortbar abgrenzbar, waiting_human mit präziser Scopefrage.
Ein gefülltes human_scope allein heilt keine echte Scope-Unklarheit oder Quellenerfindung.
Verifier: approved gilt nur für den Untersuchungsentwurf, niemals für Diagnose oder Freigabe.
Die spätere Datenerhebung darf nicht als Voraussetzung ihrer eigenen Untersuchung blockieren.
Repair: entferne Erfindungen, erhalte menschliche Grenzen und Unknowns; keine neuen Tatsachen.
"""


def human_scope_record(*, actor, values):
    if set(values) - set(SCOPE_FIELDS):
        raise ValidationError("Unbekannte Felder im menschlichen Untersuchungsrahmen.")
    scope = {name: str(values.get(name) or "").strip() for name in SCOPE_FIELDS}
    if any(len(value) > 2000 for value in scope.values()):
        raise ValidationError("Der Untersuchungsrahmen ist zu lang.")
    return {
        "input_schema": INPUT_SCHEMA,
        "actor_id": actor.pk,
        "recorded_at": timezone.now().isoformat(),
        "explicit_strategic": True,
        **scope,
    }


def frozen_human_scope(session, snapshot):
    scope = snapshot.process_context.get("human_scope")
    if (
        session.catalog_version != CATALOG
        or session.schema_version != ANSWER_SCHEMA
        or not isinstance(scope, dict)
        or scope != session.answers.get("human_scope")
        or scope.get("actor_id") != session.owner_id
        or snapshot.captured_by_id != session.owner_id
        or scope.get("explicit_strategic") is not True
        or scope.get("input_schema") != INPUT_SCHEMA
    ):
        raise ValidationError("Der menschliche Untersuchungsrahmen ist nicht quellengebunden.")
    return scope


def scope_basis(scope):
    return {name: str((scope or {}).get(name) or "") for name in SCOPE_FIELDS}


def scope_findings(draft, scope):
    if draft.get("scope_basis") != scope_basis(scope):
        return ["scope_basis: Menschliche Scopeangaben müssen unverändert erhalten bleiben."]
    process = draft.get("process_analysis") or {}
    return [
        f"process_analysis.{field}: Grenze widerspricht der menschlichen Scopeentscheidung."
        for field in ("scope_start", "scope_end")
        if process.get(field) != (scope or {}).get(field, "")
    ]


def missing_scope_question(scope):
    if any(not str((scope or {}).get(name) or "").strip() for name in REQUIRED_SCOPE_FIELDS):
        return (
            "Welchen vorläufigen Bereich (Beginn/Ende) untersuchen Sie aus welchem Grund, "
            "und welcher konkrete Schritt validiert ihn?"
        )
    return ""


def assert_enabled():
    if not settings.ACCELERATOR_STRATEGIC_DISCOVERY_ENABLED:
        raise ValidationError(
            "Neue strategische Untersuchungen sind vorübergehend ausgesetzt; "
            "gespeicherte Stände bleiben lesbar."
        )
