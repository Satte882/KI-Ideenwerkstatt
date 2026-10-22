"""Issue #148: early learning is neither a decision nor business value."""

import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process
from test_issue_146_outcome_contract import process as process_fixture

from ki_radar.use_cases.capability_experiments import (
    add_capability_correction,
    save_capability_experiment,
)
from ki_radar.use_cases.capability_models import (
    CapabilityExperiment,
    CapabilityExperimentCorrection,
)
from ki_radar.use_cases.initiatives import save_initiative
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db
process = process_fixture


@pytest.fixture
def initiative(owner):
    return save_initiative(actor=owner, data={"title": "KI als mögliche Option"})


def evidence(**changes):
    data = {
        "title": "Angebots-E-Mails extrahieren",
        "ai_vision": "Alle Anfragearten verlässlich bearbeiten",
        "first_viable_step": "Read-only Vorschläge, Prüfung durch Mitarbeiter",
        "capability_hypothesis": "Das Modell extrahiert Beträge und Zeiträume korrekt",
        "tested_configuration": "Lokales Modell A / Prompt-Version 1",
        "test_case_ids": "train-1\ntrain-2",
        "holdout_case_ids": "held-1\nheld-2",
        "holdout_unseen_confirmed": True,
        "failure_modes": "Fehler bei widersprüchlichen Preisen",
        "assumptions": "PDF-Text verfügbar, Datenzugang noch zu klären",
        "effort": "Halber Tag für eine qualitative Probe",
        "finding": "partial",
        "evidence_reference": "Interner Testbericht: E-17",
        "learning_value": "Widersprüche müssen menschlich entschieden werden",
        "data_kind": "synthetic",
    }
    data.update(changes)
    return data


def save(owner, initiative, data, *, experiment=None, finalize=False):
    return save_capability_experiment(
        initiative=initiative,
        actor=owner,
        experiment=experiment,
        expected_revision=experiment.revision if experiment else None,
        data=data,
        finalize=finalize,
    )


def test_draft_remains_free_without_outcome_or_samples(owner, initiative):
    original = (initiative.revision, initiative.outcome_revision)
    experiment = save(owner, initiative, {"title": "Nur eine Frage"})
    assert not experiment.is_reviewed
    assert experiment.learning_value == ""
    assert not UseCase.objects.exists()
    initiative.refresh_from_db()
    assert (initiative.revision, initiative.outcome_revision) == original
    changed = save(
        owner,
        initiative,
        {"ai_vision": "Ambitionierte AI-first-Idee", "first_viable_step": "Kleiner Test"},
        experiment=experiment,
    )
    assert changed.revision == 2
    assert changed.reviewed_at is None


def test_recorded_capability_is_not_business_success_or_approval(owner, initiative):
    result = save(owner, initiative, evidence(), finalize=True)
    assert result.reviewed_by == owner and result.reviewed_at is not None
    assert result.finding == "partial"
    assert result.learning_value and result.evidence_reference
    initiative.refresh_from_db()
    assert initiative.effect_status == "" and initiative.confirmed_by is None
    assert not UseCase.objects.exists()


def test_no_automatic_ki_victory_for_negative_experiment(owner, initiative):
    finding = save(
        owner,
        initiative,
        evidence(finding="not_supported", learning_value="Non-KI-Regeln genügen"),
        finalize=True,
    )
    assert finding.get_finding_display() == "Capability nicht bestätigt"
    initiative.refresh_from_db()
    assert not initiative.confirmed_by_id
    assert not initiative.use_cases.exists()


@pytest.mark.parametrize(
    "missing",
    [
        {"capability_hypothesis": ""},
        {"first_viable_step": ""},
        {"test_case_ids": ""},
        {"holdout_case_ids": ""},
        {"evidence_reference": ""},
        {"learning_value": ""},
        {"finding": "open"},
        {"holdout_unseen_confirmed": False},
    ],
)
def test_incomplete_evidence_may_be_saved_as_draft(owner, initiative, missing):
    payload = evidence(**missing)
    with pytest.raises(ValidationError):
        save(owner, initiative, payload, finalize=True)
    draft = save(owner, initiative, payload)
    assert not draft.is_reviewed


def test_overlap_and_duplicate_case_refs_are_not_proven_holdouts(owner, initiative):
    with pytest.raises(ValidationError, match="verschieden"):
        save(
            owner,
            initiative,
            evidence(holdout_case_ids="train-1\nheld-3"),
            finalize=True,
        )
    with pytest.raises(ValidationError, match="doppelt"):
        save(
            owner,
            initiative,
            evidence(test_case_ids="train-1\ntrain-1"),
            finalize=True,
        )
    assert not CapabilityExperiment.objects.exists()


def test_real_data_governance_reference_is_separate_from_capability(owner, initiative):
    data = evidence(data_kind="real", governance_reference="")
    with pytest.raises(ValidationError, match="Governance"):
        save(owner, initiative, data, finalize=True)
    assert not save(owner, initiative, data).is_reviewed
    reviewed = save(
        owner,
        initiative,
        evidence(data_kind="real", governance_reference="DSB-Prüfung R-12"),
        finalize=True,
    )
    assert reviewed.data_kind == "real"
    assert reviewed.governance_reference == "DSB-Prüfung R-12"
    assert not initiative.confirmed_by_id


def test_retest_needs_new_unconsumed_holdouts(owner, initiative):
    initial = save(owner, initiative, evidence(), finalize=True)
    with pytest.raises(ValidationError, match="neue"):
        save(
            owner,
            initiative,
            evidence(retest_of=initial, holdout_case_ids="held-1\nheld-3"),
            finalize=True,
        )
    later = save(
        owner,
        initiative,
        evidence(
            title="Nachtest nach Änderung",
            retest_of=initial,
            tested_configuration="Modell A / Prompt-Version 2",
            test_case_ids="held-1\nheld-2",
            holdout_case_ids="fresh-1\nfresh-2",
        ),
        finalize=True,
    )
    assert later.retest_of_id == initial.pk and later.is_reviewed
    assert initial.tested_configuration == "Lokales Modell A / Prompt-Version 1"


def test_retest_must_refer_same_initiative(owner, initiative):
    other = save_initiative(actor=owner, data={"title": "Anderes Vorhaben"})
    previous = save(owner, other, evidence(), finalize=True)
    with pytest.raises(ValidationError, match="desselben Vorhabens"):
        save(owner, initiative, evidence(retest_of=previous), finalize=True)


def test_reviewed_record_is_append_only_but_new_drafts_allowed(owner, initiative):
    reviewed = save(owner, initiative, evidence(), finalize=True)
    with pytest.raises(ValidationError, match="unveränderlich"):
        save(owner, initiative, {"title": "Manipuliert"}, experiment=reviewed)
    with pytest.raises(ValidationError):
        CapabilityExperiment.objects.filter(pk=reviewed.pk).update(finding="supported")
    with pytest.raises(ValidationError):
        reviewed.delete()
    reviewed.refresh_from_db()
    assert reviewed.finding == "partial"
    assert not save(owner, initiative, {"title": "Ein neuer Entwurf"}).is_reviewed


def test_permissions_are_not_extended_by_owner_label(
    client, owner, other_owner, reader, initiative
):
    draft = save(owner, initiative, {"title": "Offen"})
    with pytest.raises(PermissionDenied):
        save(other_owner, initiative, {"title": "Fremd"})
    client.force_login(reader)
    url = reverse("use_cases:capability_experiment_create", args=[initiative.pk])
    assert client.get(url).status_code == 403
    detail = reverse("use_cases:capability_experiment_edit", args=[initiative.pk, draft.pk])
    assert client.get(detail).status_code == 200
    assert client.post(detail, {"title": "Fremd"}).status_code == 403


def test_draft_form_and_failed_review_preserve_input(client, owner, initiative):
    client.force_login(owner)
    url = reverse("use_cases:capability_experiment_create", args=[initiative.pk])
    data = {"title": "Erste Idee", "ai_vision": "Noch ungeprüft", "action": "review"}
    response = client.post(url, data)
    assert response.status_code == 200
    assert "Noch ungeprüft" in response.content.decode()
    assert "Als Entwurf sichern" in response.content.decode()
    assert not CapabilityExperiment.objects.exists()
    data["action"] = "draft"
    response = client.post(url, data)
    assert response.status_code == 302
    record = CapabilityExperiment.objects.get()
    assert record.ai_vision == "Noch ungeprüft" and record.reviewed_at is None
    html = client.get(initiative.get_absolute_url()).content.decode()
    assert "AI-first-Erkundung" in html and "Entwurf" in html and "ungeprüft" in html


def test_human_review_view_and_retest_link(client, owner, initiative):
    client.force_login(owner)
    url = reverse("use_cases:capability_experiment_create", args=[initiative.pk])
    data = {
        **evidence(),
        "retest_of": "",
        "action": "review",
    }
    response = client.post(url, data)
    assert response.status_code == 302
    record = CapabilityExperiment.objects.get()
    assert record.is_reviewed
    html = client.get(record.get_absolute_url()).content.decode()
    assert "Nachtest mit neuen Holdout-Fällen" in html
    assert "Learning Value" in html
    assert client.post(record.get_absolute_url(), data).status_code == 403


def test_reviewed_correction_is_append_only_without_fictitious_retest(owner, initiative):
    reviewed = save(owner, initiative, evidence(data_kind="synthetic"), finalize=True)
    comment = add_capability_correction(
        experiment=reviewed,
        actor=owner,
        note="Bisher als synthetisch bezeichnet; tatsächliche Kategorie real. "
        "Governance-Referenz muss separat nachgereicht und geprüft werden.",
    )
    assert comment.created_by == owner
    assert comment.experiment == reviewed
    reviewed.refresh_from_db()
    assert reviewed.data_kind == "synthetic"
    assert reviewed.retests.count() == 0
    with pytest.raises(ValidationError, match="unveränderlich"):
        comment.note = "Alte Aussage ohne Hinweis überschrieben"
        comment.save()
    with pytest.raises(ValidationError):
        CapabilityExperimentCorrection.objects.filter(pk=comment.pk).update(
            note="Manipuliert"
        )


def test_correction_requires_existing_review_and_authorized_actor(
    owner, other_owner, initiative
):
    draft = save(owner, initiative, {"title": "Offen"})
    with pytest.raises(ValidationError, match="Entwürfe"):
        add_capability_correction(experiment=draft, actor=owner, note="Falsch")
    reviewed = save(owner, initiative, evidence(), finalize=True)
    with pytest.raises(PermissionDenied):
        add_capability_correction(
            experiment=reviewed, actor=other_owner, note="Unbefugter Nachtrag"
        )
    with pytest.raises(ValidationError, match="begründen"):
        add_capability_correction(experiment=reviewed, actor=owner, note=" ")
    assert not CapabilityExperimentCorrection.objects.exists()


def test_correction_ui_preserves_original_and_shows_audit(client, owner, initiative):
    reviewed = save(owner, initiative, evidence(), finalize=True)
    client.force_login(owner)
    response = client.post(
        reviewed.get_absolute_url(),
        {
            "action": "correct",
            "correction_note": "Governance-Referenz war falsch: alte Nummer A, richtig B.",
        },
    )
    assert response.status_code == 302
    result = client.get(reviewed.get_absolute_url())
    html = result.content.decode()
    assert "Governance-Referenz war falsch" in html
    assert "Neue Holdout-Fälle" in html
    assert reviewed.retests.count() == 0


def test_reviewed_negative_capability_visible_on_solution_comparison(
    client, owner, process
):
    initiative = bind_process(owner, process)
    finding = save(
        owner,
        initiative,
        evidence(
            title="KI-Extraktion verworfen",
            finding="not_supported",
            learning_value="Regelbasierte Prüfung ist günstiger und nachvollziehbarer.",
        ),
        finalize=True,
    )
    draft = save(owner, initiative, {"title": "Noch ungetestete KI-Idee"})
    client.force_login(owner)
    url = reverse(
        "architecture:solution_option_compare", args=[process.pk]
    )
    response = client.get(url)
    assert response.status_code == 200
    html = response.content.decode()
    assert finding.title in html
    assert "Capability nicht bestätigt" in html
    assert draft.title not in html
    assert "Geschäftsnutzen-Nachweis" in html
