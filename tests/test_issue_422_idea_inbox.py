from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from ki_radar.core.taxonomy import BusinessDomain
from ki_radar.use_cases.idea_models import IdeaCandidate
from ki_radar.use_cases.models import DecisionAssessment, UseCase


def complete_intake_data(business_unit, business_owner, **overrides):
    data = {
        "title": "Wissenssuche verbessern",
        "business_unit": business_unit.pk,
        "business_owner": business_owner.pk,
        "problem_statement": (
            "Mitarbeitende benötigen zu viel Zeit, um verbindliche Informationen zu finden."
        ),
        "affected_process": "Interne Wissenssuche",
        "business_domain": BusinessDomain.CORPORATE_SERVICES,
        "business_capability": "Knowledge Management",
        "summary": "Eine Anfrage löst heute eine manuelle Suche aus.",
        "target_users": "Mitarbeitende im Kundenservice",
        "source_systems": "SharePoint und PDF-Richtlinien",
        "intended_users": "Mitarbeitende im Kundenservice",
        "intended_purpose": "Relevante Textstellen mit Quellenhinweis auffinden",
        "privacy_review_required": False,
        "security_review_required": False,
        "legal_review_required": False,
        "expected_benefit": "Suchzeit je Anfrage reduzieren",
        "metric_name": "Suchzeit je Anfrage",
        "metric_type": UseCase.MetricType.DURATION,
        "metric_direction": UseCase.MetricDirection.LOWER,
        "metric_unit": "Minuten",
        "metric_baseline": "20",
        "metric_target": "8",
        "metric_measurement_method": "Vierwöchige Stichprobe über 100 Anfragen",
        "data_sources": "Freigegebene Richtlinien und Arbeitsanweisungen",
        "solution_type": UseCase.SolutionType.ASSISTANT,
        "hosting_type": UseCase.HostingType.INTERNAL,
    }
    data.update(overrides)
    return data


def set_intake_session(client, business_unit, business_owner, idea=None, **overrides):
    session = client.session
    session["use_case_intake"] = complete_intake_data(
        business_unit,
        business_owner,
        **overrides,
    )
    if idea is not None:
        session["use_case_intake_idea_candidate"] = str(idea.pk)
    session.save()


@pytest.mark.django_db
def test_authenticated_user_can_capture_minimal_idea(client, reader):
    client.force_login(reader)

    response = client.post(
        reverse("use_cases:idea_create"),
        {
            "title": "Angebote schneller vergleichen",
            "description": "Einkauf benötigt zu viel Zeit für den manuellen Angebotsvergleich.",
            "business_unit": "",
            "source_note": "Workshop Einkauf",
        },
    )

    assert response.status_code == 302
    idea = IdeaCandidate.objects.get()
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.submitted_by == reader
    assert idea.business_unit is None
    assert UseCase.objects.count() == 0


@pytest.mark.django_db
def test_list_defaults_to_open_and_filters_by_state_and_business_unit(
    client,
    reader,
    business_unit,
):
    open_idea = IdeaCandidate.objects.create(
        title="Offene Idee",
        description="Noch zu prüfen",
        business_unit=business_unit,
        submitted_by=reader,
    )
    IdeaCandidate.objects.create(
        title="Verworfene Idee",
        description="Nicht weiter verfolgen",
        business_unit=business_unit,
        submitted_by=reader,
        state=IdeaCandidate.State.DISMISSED,
        decision_note="Kein relevanter Nutzen.",
    )
    client.force_login(reader)

    response = client.get(reverse("use_cases:idea_list"))
    assert response.status_code == 200
    assert open_idea.title in response.content.decode()
    assert "Verworfene Idee" not in response.content.decode()

    response = client.get(
        reverse("use_cases:idea_list"),
        {"state": "dismissed", "business_unit": str(business_unit.pk)},
    )
    assert "Verworfene Idee" in response.content.decode()
    assert open_idea.title not in response.content.decode()


@pytest.mark.django_db
def test_quick_triage_is_role_guarded_and_score_is_derived(
    client,
    reader,
    owner,
    business_unit,
):
    idea = IdeaCandidate.objects.create(
        title="Voice Bot testen",
        description="Wiederkehrende Standardanfragen automatisieren.",
        business_unit=business_unit,
        submitted_by=reader,
    )

    client.force_login(reader)
    response = client.post(
        reverse("use_cases:idea_triage", args=[idea.pk]),
        {"impact": 5, "confidence": 2, "ease": 4},
    )
    assert response.status_code == 403

    client.force_login(owner)
    response = client.post(
        reverse("use_cases:idea_triage", args=[idea.pk]),
        {"impact": 5, "confidence": 2, "ease": 4},
    )
    assert response.status_code == 302

    idea.refresh_from_db()
    assert idea.triage_complete is True
    assert idea.quick_score == 3.7
    assert idea.triaged_by == owner
    assert DecisionAssessment.objects.count() == 0


@pytest.mark.django_db
def test_triage_rejects_values_outside_one_to_five(client, owner, reader, business_unit):
    idea = IdeaCandidate.objects.create(
        title="Idee",
        description="Beschreibung",
        business_unit=business_unit,
        submitted_by=reader,
    )
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:idea_triage", args=[idea.pk]),
        {"impact": 6, "confidence": 3, "ease": 3},
    )

    assert response.status_code == 302
    idea.refresh_from_db()
    assert idea.impact is None
    assert idea.quick_score is None


@pytest.mark.django_db
def test_dismiss_requires_reason(client, owner, reader, business_unit):
    idea = IdeaCandidate.objects.create(
        title="Idee",
        description="Beschreibung",
        business_unit=business_unit,
        submitted_by=reader,
    )
    client.force_login(owner)

    client.post(reverse("use_cases:idea_dismiss", args=[idea.pk]), {"decision_note": ""})
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN

    client.post(
        reverse("use_cases:idea_dismiss", args=[idea.pk]),
        {"decision_note": "Nutzen ist aktuell zu gering."},
    )
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.DISMISSED
    assert idea.decision_note == "Nutzen ist aktuell zu gering."


@pytest.mark.django_db
def test_promotion_prefills_existing_intake_without_creating_use_case(
    client,
    owner,
    business_unit,
):
    idea = IdeaCandidate.objects.create(
        title="Angebotsvergleich",
        description="Vergleich dauert heute mehrere Tage.",
        business_unit=business_unit,
        submitted_by=owner,
        impact=5,
        confidence=2,
        ease=5,
    )
    client.force_login(owner)

    response = client.post(reverse("use_cases:idea_promote", args=[idea.pk]))

    assert response.status_code == 302
    session = client.session
    assert session["use_case_intake"]["title"] == idea.title
    assert session["use_case_intake"]["problem_statement"] == idea.description
    assert session["use_case_intake"]["business_unit"] == business_unit.pk
    assert session["use_case_intake_idea_candidate"] == str(idea.pk)
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.promoted_use_case is None
    assert UseCase.objects.count() == 0
    assert DecisionAssessment.objects.count() == 0


@pytest.mark.django_db
def test_promotion_never_overwrites_existing_intake_draft(
    client,
    owner,
    business_unit,
):
    idea = IdeaCandidate.objects.create(
        title="Neue Idee",
        description="Soll später geprüft werden.",
        submitted_by=owner,
    )
    client.force_login(owner)
    session = client.session
    session["use_case_intake"] = {"title": "Bestehender Draft", "business_unit": business_unit.pk}
    session.save()

    response = client.post(reverse("use_cases:idea_promote", args=[idea.pk]))

    assert response.status_code == 302
    session = client.session
    assert session["use_case_intake"] == {
        "title": "Bestehender Draft",
        "business_unit": business_unit.pk,
    }
    assert "use_case_intake_idea_candidate" not in session
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN


@pytest.mark.django_db
def test_discarded_candidate_intake_leaves_candidate_open(client, owner, business_unit):
    idea = IdeaCandidate.objects.create(
        title="Idee",
        description="Beschreibung",
        business_unit=business_unit,
        submitted_by=owner,
    )
    client.force_login(owner)
    client.post(reverse("use_cases:idea_promote", args=[idea.pk]))

    response = client.post(reverse("use_cases:intake_discard"))

    assert response.status_code == 302
    session = client.session
    assert "use_case_intake" not in session
    assert "use_case_intake_idea_candidate" not in session
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.promoted_use_case is None


@pytest.mark.django_db
def test_successful_intake_atomically_promotes_exactly_one_use_case(
    client,
    owner,
    business_unit,
):
    idea = IdeaCandidate.objects.create(
        title="Wissenssuche verbessern",
        description="Mitarbeitende suchen zu lange.",
        business_unit=business_unit,
        submitted_by=owner,
        impact=5,
        confidence=1,
        ease=5,
    )
    client.force_login(owner)
    set_intake_session(client, business_unit, owner, idea=idea)

    response = client.post(reverse("use_cases:intake_step", args=[6]))

    assert response.status_code == 302
    assert UseCase.objects.count() == 1
    use_case = UseCase.objects.get()
    idea.refresh_from_db()
    assert idea.state == IdeaCandidate.State.PROMOTED
    assert idea.promoted_use_case == use_case
    assert use_case.origin_idea_candidate == idea
    assert DecisionAssessment.objects.count() == 0

    set_intake_session(client, business_unit, owner, idea=idea)
    response = client.post(reverse("use_cases:intake_step", args=[6]))

    assert response.status_code == 200
    assert UseCase.objects.count() == 1
    idea.refresh_from_db()
    assert idea.promoted_use_case == use_case


@pytest.mark.django_db
def test_long_open_idea_is_marked_without_new_state(reader):
    idea = IdeaCandidate.objects.create(
        title="Alte Idee",
        description="Noch offen",
        submitted_by=reader,
    )
    IdeaCandidate.objects.filter(pk=idea.pk).update(created_at=timezone.now() - timedelta(days=31))
    idea.refresh_from_db()

    assert idea.state == IdeaCandidate.State.OPEN
    assert idea.is_stale is True
    assert idea.age_days >= 30
