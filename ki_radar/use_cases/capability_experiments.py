"""Record early capability tests without changing approvals, pilot gates or business value."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .capability_models import CapabilityExperiment, CapabilityExperimentCorrection
from .initiative_models import ImprovementInitiative
from .initiatives import can_edit_initiative

CAPABILITY_FIELDS = (
    "title",
    "ai_vision",
    "first_viable_step",
    "capability_hypothesis",
    "tested_configuration",
    "test_case_ids",
    "holdout_case_ids",
    "holdout_unseen_confirmed",
    "failure_modes",
    "assumptions",
    "effort",
    "finding",
    "evidence_reference",
    "learning_value",
    "data_kind",
    "governance_reference",
    "retest_of",
)


def _case_ids(value):
    """One opaque case identifier per line; never parse or store case payloads."""
    ids = [item.strip() for item in (value or "").splitlines() if item.strip()]
    if len(ids) != len(set(ids)):
        raise ValidationError("Fall-Referenzen dürfen nicht doppelt vorkommen.")
    return set(ids)


def _check_evidence(experiment):
    if not all(
        getattr(experiment, field).strip()
        for field in (
            "ai_vision",
            "first_viable_step",
            "capability_hypothesis",
            "tested_configuration",
            "assumptions",
            "effort",
            "evidence_reference",
            "learning_value",
        )
    ):
        raise ValidationError(
            "Für den geprüften Capability-Nachweis fehlen Zielhypothese, erste Ausbaustufe, "
            "prüfbare Fähigkeit, Konfiguration, Annahmen, Aufwand, Nachweis oder Learning Value. "
            "Der Entwurf bleibt jederzeit speicherbar."
        )
    tested = _case_ids(experiment.test_case_ids)
    holdout = _case_ids(experiment.holdout_case_ids)
    if not tested or not holdout:
        raise ValidationError(
            "Für einen geprüften Capability-Test sind dokumentierte Beispiele und "
            "separat unverbrauchte Testfälle erforderlich."
        )
    if tested & holdout:
        raise ValidationError("Testfälle und unverbrauchte Holdout-Fälle müssen verschieden sein.")
    if not experiment.holdout_unseen_confirmed:
        raise ValidationError(
            "Bitte fachlich bestätigen, dass die Holdout-Fälle zuvor nicht zur Anpassung "
            "verwendet wurden. Die Anwendung kann dies nicht automatisch verifizieren."
        )
    if experiment.finding == CapabilityExperiment.Finding.OPEN:
        raise ValidationError("Ergebnis als gestützt, teilweise oder nicht bestätigt einordnen.")
    if (
        experiment.data_kind == CapabilityExperiment.DataKind.REAL
        and not experiment.governance_reference.strip()
    ):
        raise ValidationError(
            "Bei Real-Daten fehlt die dokumentierte Datenschutz-/Governance-Referenz. "
            "Dieser Nachweis erteilt selbst keine Datenschutzfreigabe."
        )
    previous = experiment.retest_of
    while previous:
        if previous.initiative_id != experiment.initiative_id or not previous.is_reviewed:
            raise ValidationError(
                "Ein Nachtest braucht einen geprüften früheren Test desselben Vorhabens."
            )
        consumed = _case_ids(previous.test_case_ids) | _case_ids(previous.holdout_case_ids)
        if holdout & consumed:
            raise ValidationError(
                "Der Nachtest muss neue, noch nicht verwendete Holdout-Fälle dokumentieren."
            )
        previous = previous.retest_of


@transaction.atomic
def save_capability_experiment(
    *, initiative, actor, data, experiment=None, expected_revision=None, finalize=False
):
    """Save a loose draft or human-attested evidence. Never changes Outcome or decision state."""
    initiative = ImprovementInitiative.objects.select_for_update().get(pk=initiative.pk)
    if not can_edit_initiative(actor, initiative):
        raise PermissionDenied
    if set(data) - set(CAPABILITY_FIELDS):
        raise ValidationError("Serververwaltete Experimentfelder dürfen nicht geändert werden.")
    if experiment is not None:
        experiment = CapabilityExperiment.objects.select_for_update().get(pk=experiment.pk)
        if experiment.initiative_id != initiative.pk:
            raise PermissionDenied
        if experiment.is_reviewed:
            raise ValidationError("Geprüfter Nachweis ist unveränderlich; einen Nachtest erfassen.")
        if expected_revision != experiment.revision:
            raise ValidationError("Der Experimententwurf wurde zwischenzeitlich geändert.")
        experiment.revision += 1
    else:
        experiment = CapabilityExperiment(initiative=initiative, created_by=actor)
    for name in CAPABILITY_FIELDS:
        if name in data:
            setattr(experiment, name, data[name])
    if finalize:
        _check_evidence(experiment)
        experiment.reviewed_by = actor
        experiment.reviewed_at = timezone.now()
    experiment.save()
    return experiment


@transaction.atomic
def add_capability_correction(*, experiment, actor, note):
    """Append a factual correction without editing the reviewed record or faking a retest."""
    experiment = CapabilityExperiment.objects.select_for_update().select_related(
        "initiative"
    ).get(pk=experiment.pk)
    if not can_edit_initiative(actor, experiment.initiative):
        raise PermissionDenied
    if not experiment.is_reviewed:
        raise ValidationError("Entwürfe können direkt bearbeitet werden.")
    note = (note or "").strip()
    if not note:
        raise ValidationError("Bitte den falschen und den korrigierten Stand begründen.")
    return CapabilityExperimentCorrection.objects.create(
        experiment=experiment,
        note=note,
        created_by=actor,
    )
