"""Explicit reuse of existing evidence in the regular intake and outcome forms."""

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.analysis_service import canonical_answer_hash
from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.extraction_contract import (
    current_extraction_prompt_version,
    extraction_prompt_version,
)
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.structured_metric_adoption import METRIC_TARGET_TO_FIELD

from .outcome_contract import _process

CAPTURE_SOURCE_KEY = "_capture_source"
OUTCOME_LABELS = {
    "title": "Vorhaben",
    "contribution": "Abgegrenzter Vorhabensbeitrag",
    "origin_basis": "Dokumentierte Herkunft / Ausgangslage",
    "evidence_note": "Evidenz / Quelle",
    "impact_hypothesis": "Wirkannahme",
    "target_group": "Betroffene Empfängergruppe",
    "evaluation_criteria": "Prüfkriterien",
}
_SALT = "outcome-context-v1"
_TEXT_FIELDS = (
    "title",
    "summary",
    "problem_statement",
    "affected_process",
    "target_users",
    "source_systems",
    "data_sources",
    "intended_users",
    "intended_purpose",
    "expected_benefit",
    "benefit_category",
    "human_oversight",
    "solution_type",
    "hosting_type",
)
CAPTURE_FIELDS = {f"use_case.{name}": name for name in _TEXT_FIELDS} | METRIC_TARGET_TO_FIELD


def capture_context(*, actor, analysis_id, lock=False):
    try:
        analysis = CaptureAnalysis.objects.select_related("session").get(pk=analysis_id)
    except CaptureAnalysis.DoesNotExist as exc:
        raise ValidationError("Die Analysequelle ist nicht mehr verfügbar.") from exc
    session = CaptureSession.objects
    if lock:
        session = session.select_for_update()
    session = session.get(pk=analysis.session_id)
    if session.owner_id != actor.pk or analysis.requested_by_id != actor.pk:
        raise PermissionDenied
    try:
        catalog = get_capture_catalog(session.capture_type, session.catalog_version)
    except ValueError as exc:
        raise ValidationError("Der Katalog dieser Quelle wird nicht unterstützt.") from exc
    from .lean_intake import WIZARD_STEPS

    labels = {
        key: field.label
        for config in WIZARD_STEPS.values()
        if config["form"]
        for key, field in config["form"].base_fields.items()
    }
    if (
        session.capture_type != "use_case"
        or session.mode != CaptureSession.Mode.GUIDED
        or session.status != CaptureSession.Status.COMPLETED
        or session.expires_at <= timezone.now()
        or analysis.status != CaptureAnalysis.Status.SUCCESS
        or analysis.capture_type != session.capture_type
        or analysis.catalog_version != session.catalog_version
        or analysis.answer_schema_version != session.schema_version
        or analysis.extraction_schema_version != "1.0"
        or analysis.prompt_version
        not in {extraction_prompt_version(catalog), current_extraction_prompt_version(catalog)}
        or analysis.source_revision != session.revision
        or analysis.source_hash != canonical_answer_hash(session.answers)
    ):
        raise ValidationError("Die Analysequelle ist nicht mehr aktuell oder nicht verfügbar.")
    items = []
    for suggestion in analysis.suggestions.filter(
        target_object_type="use_case", target_group_key="", uncertainty__in=("low", "medium")
    ):
        field = CAPTURE_FIELDS.get(suggestion.target_field)
        value = suggestion.suggested_value
        if isinstance(value, dict) and field in {"metric_baseline", "metric_target"}:
            value = value.get("value")
        if field and isinstance(value, str) and value.strip():
            items.append(
                {
                    "field": field,
                    "value": value,
                    "source_field": suggestion.target_field,
                    "excerpt": suggestion.source_excerpt,
                    "uncertainty": suggestion.get_uncertainty_display(),
                    "suggestion_id": str(suggestion.pk),
                    "source_question": suggestion.source_question,
                    "label": labels.get(field, field),
                }
            )
    if not items:
        raise ValidationError("Die Analyse enthält keine übernehmbaren Angaben.")
    context = {
        "kind": "capture_analysis",
        "id": str(analysis.pk),
        "label": session.working_title or "KI-Erfassung",
        "url": reverse("accelerator:analysis_detail", args=[analysis.pk]),
        "revision": analysis.source_revision,
        "hash": analysis.source_hash,
        "prompt_version": analysis.prompt_version,
        "model": analysis.model_name,
        "catalog_version": analysis.catalog_version,
        "answer_schema_version": analysis.answer_schema_version,
        "extraction_schema_version": analysis.extraction_schema_version,
        "items": items,
    }
    context["content_hash"] = canonical_answer_hash(context)
    return session, context


def outcome_context(artifact):
    """Map only semantic equivalents; never turn process output into business outcome."""
    process = _process(artifact)
    values = {}
    source_fields = {}
    sources = []
    if process:
        stream = process.stage.value_stream
        sources = [
            {
                "kind": "process",
                "id": str(process.pk),
                "revision": process.version,
                "updated_at": process.updated_at.isoformat(),
                "source_snapshot": process.source_snapshot,
            },
            {
                "kind": "value_stream",
                "id": str(stream.pk),
                "updated_at": stream.updated_at.isoformat(),
            },
        ]
        values = {
            "title": process.name,
            "contribution": f"Zu prüfender Prozessbeitrag: {process.outcome}"
            if process.outcome
            else "",
            "origin_basis": process.diagnostic_observations,
            "evidence_note": "\n\n".join(
                filter(
                    None,
                    [
                        f"Beobachtung: {process.diagnostic_observations}"
                        if process.diagnostic_observations
                        else "",
                        f"Ursachenhypothesen (keine bestätigte Wirkung): {process.cause_hypotheses}"
                        if process.cause_hypotheses
                        else "",
                        (
                            "Strategischer Kontext (Geschäftsergebnis noch abzugrenzen): "
                            f"{stream.strategic_objective}"
                        )
                        if stream.strategic_objective
                        else "",
                    ],
                )
            ),
        }
        source_fields.update(
            {
                "title": "process.name",
                "contribution": "process.outcome",
                "origin_basis": "process.diagnostic_observations",
                "evidence_note": (
                    "process.diagnostic_observations / process.cause_hypotheses / "
                    "value_stream.strategic_objective"
                ),
            }
        )
        for run in process.investigation_runs.filter(
            materializations__outcome="applied"
        ).distinct()[:10]:
            sources.append(
                {
                    "kind": "investigation",
                    "id": str(run.pk),
                    "brief_hash": run.brief_hash,
                    "manifest_hash": run.manifest_hash,
                    "url": reverse("accelerator:investigation_detail", args=[run.pk]),
                }
            )
    if artifact._meta.model_name == "usecase":
        sources.append(
            {
                "kind": "use_case",
                "id": str(artifact.pk),
                "updated_at": artifact.updated_at.isoformat(),
            }
        )
        values.update(
            {
                "title": artifact.title,
                "contribution": artifact.summary,
                "impact_hypothesis": (
                    "Zu prüfende Nutzenhypothese; Geschäftswirkung noch offen: "
                    f"{artifact.expected_benefit}"
                )
                if artifact.expected_benefit
                else "",
                "target_group": artifact.target_users,
                "evaluation_criteria": (
                    "Prozessmessung; Geschäftswirkung getrennt prüfen: "
                    f"{artifact.metric_measurement_method}"
                )
                if artifact.metric_measurement_method
                else "",
            }
        )
        source_fields.update(
            {
                "title": "use_case.title",
                "contribution": "use_case.summary",
                "impact_hypothesis": "use_case.expected_benefit",
                "target_group": "use_case.target_users",
                "evaluation_criteria": "use_case.metric_measurement_method",
            }
        )
    items = [
        {
            "field": key,
            "label": OUTCOME_LABELS[key],
            "value": value,
            "source_field": source_fields[key],
        }
        for key, value in values.items()
        if value
    ]
    return {
        "kind": "outcome_context",
        "id": str(artifact.pk),
        "label": str(artifact),
        "url": artifact.get_absolute_url(),
        "items": items,
        "sources": sources,
        "hash": canonical_answer_hash({"sources": sources, "values": values}),
    }


def lock_outcome_source(*, actor, artifact, expected_hash):
    from ki_radar.architecture.permissions import can_edit_value_stream

    from .permissions import can_edit_use_case

    current = type(artifact).objects.select_for_update().get(pk=artifact.pk)
    process = _process(current)
    if process:
        process = type(process).objects.select_for_update().get(pk=process.pk)
        stage = type(process.stage).objects.select_for_update().get(pk=process.stage_id)
        stream = stage.value_stream
        stage.value_stream = type(stream).objects.select_for_update().get(pk=stream.pk)
        process.stage = stage
        if current._meta.model_name == "processanalysis":
            current = process
        else:
            current.architecture_origin.process_analysis = process
    allowed = (
        can_edit_value_stream(actor, process.stage.value_stream)
        if current._meta.model_name == "processanalysis"
        else can_edit_use_case(actor, current)
    )
    if not allowed:
        raise PermissionDenied
    context = outcome_context(current)
    if context["hash"] != expected_hash:
        raise ValidationError("Die Quelle wurde inzwischen geändert. Bitte erneut prüfen.")
    return context


def fill_empty(data, context):
    result = data.copy()
    used = []
    for item in context["items"]:
        if result.get(item["field"]) is None or not str(result[item["field"]]).strip():
            result[item["field"]] = item["value"]
            used.append(item["field"])
    return result, used


def context_ticket(*, actor, context, fields):
    return signing.dumps(
        {"actor": actor.pk, "id": context["id"], "hash": context["hash"], "fields": fields},
        salt=_SALT,
    )


def checked_ticket(token, *, actor, context):
    try:
        payload = signing.loads(token, salt=_SALT, max_age=86400)
    except signing.BadSignature as exc:
        raise ValidationError("Die Quellenübernahme ist abgelaufen. Bitte erneut prüfen.") from exc
    if (
        payload["actor"] != actor.pk
        or payload["id"] != context["id"]
        or payload["hash"] != context["hash"]
    ):
        raise ValidationError(
            "Die Quelle wurde inzwischen geändert. Ihre Eingaben bleiben erhalten; "
            "bitte Quelle erneut prüfen."
        )
    return payload["fields"]


def provenance_record(context, *, actor, fields, final_values):
    # Keep the accepted draft values, not a second copy of raw capture answers.
    return {
        "kind": context["kind"],
        "source_id": context["id"],
        "source_url": context["url"],
        "source_hash": context["hash"],
        "source_revision": context.get("revision"),
        "source_contract": {
            key: context[key]
            for key in (
                "prompt_version",
                "catalog_version",
                "answer_schema_version",
                "extraction_schema_version",
                "model",
            )
            if key in context
        },
        "content_hash": context.get("content_hash", context["hash"]),
        "source_chain": [
            {key: value for key, value in source.items() if key != "source_snapshot"}
            for source in context.get("sources", [])
        ],
        "actor_id": actor.pk,
        "at": timezone.now().isoformat(),
        "fields": [
            {
                "field": item["field"],
                "source_field": item["source_field"],
                "label": item.get("label", item["field"]),
                "proposed": item["value"],
                "saved": str(final_values[item["field"]])
                if final_values.get(item["field"]) is not None
                else "",
                "excerpt_hash": canonical_answer_hash({"excerpt": item.get("excerpt", "")}),
                "source_question": item.get("source_question", ""),
                "suggestion_id": item.get("suggestion_id", ""),
            }
            for item in context["items"]
            if item["field"] in fields
        ],
    }
