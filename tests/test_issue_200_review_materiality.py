"""One narrow materiality rule for selection, historical review and completion."""

from copy import deepcopy
from unicodedata import normalize

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from test_issue_146_outcome_contract import bind_process, outcome_process, select
from test_issue_189_measurement_plan import finding, planned, save
from test_issue_199_binding_prerequisites import form_data

from ki_radar.use_cases.initiatives import PLAN_FIELDS, save_initiative
from ki_radar.use_cases.outcome_contract import confirm_initiative, snapshot_is_stale

pytestmark = pytest.mark.django_db
CRITERIA_FIELDS = (*PLAN_FIELDS, "evaluation_criteria")


@pytest.fixture
def reviewed(owner, business_unit):
    process = outcome_process(owner, business_unit)
    initiative = planned(owner)
    # Give every compared field a composed character, including documented unknowns.
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            **{name: getattr(initiative, name) + " für Testfälle" for name in CRITERIA_FIELDS},
            "measurement_change_reason": "Synthetischen Prüfrahmen vor Auswahl präzisiert",
        },
    )
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Synthetischen Prüfrahmen angenommen",
        expected_revision=initiative.revision,
    )
    bind_process(owner, process, initiative=initiative)
    selection = select(owner, process)
    review = save(owner, initiative, finding(selection=selection))
    return process, initiative, selection, review


@pytest.mark.parametrize("field", CRITERIA_FIELDS)
@pytest.mark.parametrize("correction", ["whitespace", "unicode", "full_stop"])
def test_formal_correction_keeps_selection_review_and_confirmed_completion(
    reviewed, owner, field, correction
):
    process, initiative, selection, review = reviewed
    original_selection = deepcopy(selection.outcome_snapshot)
    original_criteria = deepcopy(review.criteria_snapshot)
    original_review_history = list(review.history.values_list("history_id", flat=True))
    original = getattr(initiative, field)
    corrected = {
        "whitespace": "  " + original.replace(" ", "\n  ") + "\t",
        "unicode": normalize("NFD", original),
        "full_stop": original + ".",
    }[correction]
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={field: corrected},
        correction_reason="Nur Leerraum, Unicode-Komposition oder abschließenden Punkt korrigiert",
    )
    selection.refresh_from_db()
    review.refresh_from_db()
    assert not snapshot_is_stale(process, original_selection)
    assert not selection.outcome_review_required
    assert not review.criteria_review_blocker
    assert not review.review_required
    assert review.criteria_snapshot == original_criteria
    assert list(review.history.values_list("history_id", flat=True)) == original_review_history
    assert selection.outcome_snapshot == original_selection
    initiative = save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})
    assert initiative.status == "completed" and initiative.effect_status == "confirmed"
    review.refresh_from_db()
    assert not review.review_required
    assert review.criteria_snapshot == original_criteria
    assert initiative.history.filter(**{field: original}).exists()
    assert getattr(initiative, field) == corrected


@pytest.mark.parametrize("action", ["save_draft", "confirm"])
def test_terminal_full_stop_through_real_preparation_route(reviewed, owner, client, action):
    process, initiative, selection, review = reviewed
    frozen = deepcopy((selection.outcome_snapshot, review.criteria_snapshot))
    client.force_login(owner)
    url = reverse("use_cases:prepare_outcome", args=["process", process.pk])
    data = form_data(client, url)
    data.update({name: getattr(initiative, name) + "." for name in CRITERIA_FIELDS})
    data.update(
        action=action,
        correction_reason="Nur abschließende Satzpunkte ergänzt",
        confirmation_reason="Fachliche Aussage unverändert",
    )
    response = client.post(url, data)
    assert response.status_code == 302, response.context and response.context["form"].errors
    selection.refresh_from_db()
    review.refresh_from_db()
    assert not selection.outcome_review_required
    assert not review.review_required
    assert not review.criteria_review_blocker
    assert (selection.outcome_snapshot, review.criteria_snapshot) == frozen
    # The same original-plan finding can also be explicitly reviewed again.
    review = save(owner, initiative, finding(selection=selection))
    assert not review.review_required
    assert review.criteria_snapshot["original"] == frozen[1]["original"]
    assert review.criteria_snapshot["current"]["evaluation_criteria"].endswith(".")
    assert review.history.filter(criteria_snapshot=frozen[1]).exists()
    initiative.refresh_from_db()
    completed = save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})
    assert completed.effect_status == "confirmed"


@pytest.mark.parametrize(
    "field,value",
    [
        ("evaluation_criteria", "Nur 12 statt 18 von 100 erforderlich"),
        ("measurement_reference", "Absolutes Ziel: mindestens 19 von 100 Abschlüssen"),
        ("measurement_period", "Acht statt vier Wochen nach Beginn"),
        ("measurement_population", "Nur ausgewählte Vorgänge statt aller Testfälle"),
        ("measurement_reference", "Vorher-Nachher-Vergleich statt absolutem Ziel"),
        ("measurement_method", "Keine Prüfung freigegebener Vorgänge"),
        ("measurement_unknowns", "Referenzdaten sind bekannt statt ungeklärt"),
        ("evaluation_criteria", "double_stop"),
    ],
)
def test_correction_label_cannot_hide_material_change(reviewed, owner, field, value):
    process, initiative, selection, review = reviewed
    frozen = deepcopy((selection.outcome_snapshot, review.criteria_snapshot))
    if value == "double_stop":
        value = initiative.evaluation_criteria + ".."
    initiative = save_initiative(
        actor=owner,
        initiative=initiative,
        data={field: value},
        correction_reason="Schreibkorrektur",
    )
    assert initiative.confirmed_revision is None
    selection.refresh_from_db()
    review.refresh_from_db()
    assert selection.outcome_review_required and review.review_required
    assert snapshot_is_stale(process, frozen[0])
    assert "Abweichung" in review.criteria_review_blocker
    with pytest.raises(ValidationError, match="Wirkungsreview"):
        save_initiative(actor=owner, initiative=initiative, data={"status": "completed"})
    initiative = confirm_initiative(
        initiative=initiative,
        actor=owner,
        rationale="Neue materielle Aussage bewusst angenommen",
        expected_revision=initiative.revision,
    )
    renewed = select(owner, process)
    with pytest.raises(ValidationError, match="Abweichung"):
        save(owner, initiative, finding(selection=renewed))
    review.refresh_from_db()
    assert (selection.outcome_snapshot, review.criteria_snapshot) == frozen
    reassessed = save(
        owner,
        initiative,
        finding(
            selection=renewed,
            assessment_basis="retrospective",
            criteria_deviation="Nachträgliche Neubewertung; ursprünglicher Maßstab bleibt erhalten",
        ),
    )
    assert not reassessed.review_required
    assert reassessed.criteria_snapshot["original"] == frozen[1]["original"]
    assert reassessed.criteria_snapshot["current"][field] == value
    assert reassessed.history.filter(criteria_snapshot=frozen[1]).exists()
