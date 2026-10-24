from copy import deepcopy

import pytest
from django.urls import reverse
from test_solution_option_comparison import (
    assessed_form_data,
    make_option,
)
from test_solution_selection_ux import make_process

from ki_radar.architecture.forms import SolutionOptionForm
from ki_radar.architecture.models import SolutionOption
from ki_radar.architecture.solution_selection import comparison_blockers, select_preferred_solution

pytestmark = pytest.mark.django_db


@pytest.fixture
def comparison_process(owner, business_unit):
    return make_process(owner, business_unit)


@pytest.mark.parametrize("option_type", ["assistant", "organizational"])
def test_hypothesis_has_prominent_evidence_without_changing_assessment(
    client, owner, comparison_process, option_type
):
    option = make_option(
        comparison_process,
        owner,
        name="Unbelegte Option",
        option_type=option_type,
        feasibility="medium",
        architecture_fit="unknown",
        risks="unknown \u2013 Quelle fehlt",
    )
    make_option(comparison_process, owner, name="Gegenprobe", option_type="no_tech")
    before = deepcopy(SolutionOption.objects.values().get(pk=option.pk))
    client.force_login(owner)
    response = client.get(
        reverse("architecture:solution_option_compare", args=[comparison_process.pk])
    )
    html = response.content.decode()
    assert "Kriterien erfasst (Bewertet)" in html
    assert html.index("Nicht belegt: Machbarkeit und Nutzen sind Annahmen.") < html.index(
        "Lösungsbeschreibung</th>"
    )
    assert "Mittel<span" in html and "Nicht belegt \u2013 Hypothese" in html
    assert "Unbekannt / noch zu klären \u2013 Quelle fehlt" in html
    assert "stets" not in html
    assert "werden absichtlich zunächst" not in html
    assert not response.context["selection_blocked"]
    assert SolutionOption.objects.values().get(pk=option.pk) == before
    assert not comparison_process.solution_selection_decisions.exists()


@pytest.mark.parametrize(
    "evidence,label",
    [("indicative", "Indiz / qualitativ belegt"), ("measured", "Gemessen / nachgewiesen")],
)
def test_mixed_evidence_and_draft_remain_separate(
    client, owner, comparison_process, evidence, label
):
    make_option(
        comparison_process,
        owner,
        name="Belegte Option",
        option_type="rule_automation",
        evidence_basis=evidence,
    )
    make_option(
        comparison_process,
        owner,
        name="Offener Entwurf",
        option_type="assistant",
        status="draft",
        feasibility="not_assessed",
    )
    client.force_login(owner)
    response = client.get(
        reverse("architecture:solution_option_compare", args=[comparison_process.pk])
    )
    html = response.content.decode()
    assert label in html
    assert "Entwurf \u2013 Erfassung nicht abgeschlossen" in html
    assert response.context["selection_blocked"]
    assert "Auswahl noch gesperrt" in html
    assert comparison_blockers(list(comparison_process.solution_options.all()))


def test_form_keeps_raw_values_and_validation_contract(client, owner, comparison_process):
    option = make_option(
        comparison_process,
        owner,
        name="Prüfen",
        option_type="assistant",
        architecture_fit="unknown",
        feasibility="medium",
    )
    client.force_login(owner)
    url = reverse("architecture:solution_option_update", args=[option.pk]) + "?return_to=comparison"
    response = client.get(url)
    form = response.context["form"]
    assert form["architecture_fit"].value() == "unknown"
    assert form["feasibility"].value() == "medium"
    assert (
        dict(form.fields["evaluation_status"].choices)["assessed"] == "Kriterien erfasst (Bewertet)"
    )
    assert "kein Nachweis" in form.fields["feasibility"].help_text
    invalid = SolutionOptionForm(
        assessed_form_data(feasibility="not_assessed"), process_analysis=comparison_process
    )
    assert not invalid.is_valid() and "feasibility" in invalid.errors
    result = client.post(
        url,
        assessed_form_data(
            name=option.name, architecture_fit="Bewusst korrigierte Begründung", feasibility="low"
        ),
    )
    assert result.status_code == 302
    option.refresh_from_db()
    assert option.feasibility == "low" and option.evidence_basis == "hypothesis"
    assert option.architecture_fit == "Bewusst korrigierte Begründung"
    assert not comparison_process.solution_selection_decisions.exists()


def test_read_only_reader_does_not_gain_edit_or_selection_rights(
    client, reader, owner, comparison_process
):
    option = make_option(
        comparison_process, owner, name="Lesbare Hypothese", option_type="organizational"
    )
    make_option(comparison_process, owner, name="Alternative", option_type="assistant")
    client.force_login(reader)
    url = reverse("architecture:solution_option_compare", args=[comparison_process.pk])
    response = client.get(url)
    assert "Nicht belegt: Machbarkeit und Nutzen sind Annahmen." in response.content.decode()
    assert not response.context["can_select"]
    assert (
        client.post(
            url, {"selected_option": option.pk, "rationale": "Nicht berechtigt"}
        ).status_code
        == 403
    )
    assert (
        client.get(reverse("architecture:solution_option_update", args=[option.pk])).status_code
        == 403
    )


def test_historical_decision_and_snapshot_stay_unchanged(client, owner, comparison_process):
    first = make_option(
        comparison_process,
        owner,
        name="Gewählte Non-KI-Lösung",
        option_type="organizational",
        architecture_fit="unknown",
        feasibility="medium",
    )
    make_option(comparison_process, owner, name="KI-Alternative", option_type="assistant")
    decision = select_preferred_solution(
        process_analysis=comparison_process,
        selected_option=first,
        actor=owner,
        rationale="Historische bewusste Wahl einer Hypothese",
    )
    before = deepcopy(type(decision).objects.values().get(pk=decision.pk))
    client.force_login(owner)
    response = client.get(
        reverse("architecture:solution_option_compare", args=[comparison_process.pk])
    )
    html = response.content.decode()
    assert "Aktuell bevorzugt: Gewählte Non-KI-Lösung" in html
    assert "Historisch nicht gebunden" in html
    assert "Nicht belegt: Machbarkeit und Nutzen sind Annahmen." in html
    assert type(decision).objects.values().get(pk=decision.pk) == before
    assert before["comparison_snapshot"][0]["architecture_fit"] == "unknown"
