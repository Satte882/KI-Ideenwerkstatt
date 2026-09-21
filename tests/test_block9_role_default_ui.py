import pytest
from django.contrib.auth.models import Group
from django.urls import reverse

from ki_radar.accounts.models import User
from ki_radar.accounts.permissions import GROUP_COORDINATOR
from ki_radar.architecture.models import ValueStream, ValueStreamStage
from ki_radar.use_cases.decision_forms import ApprovalDecisionForm
from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.intake import ProblemStepForm
from ki_radar.use_cases.intake_views import SESSION_KEY
from ki_radar.use_cases.models import UseCase

pytestmark = pytest.mark.django_db


def _use_case(*, business_unit, owner, coordinator=None, technical_owner=None):
    return UseCase.objects.create(
        title="Block-9-UI-Testfall",
        problem_statement="Ein klarer fachlicher Testfall benötigt eine nachvollziehbare Rolle.",
        business_unit=business_unit,
        affected_process="Testprozess",
        business_owner=owner,
        coordinator=coordinator,
        technical_owner=technical_owner,
        expected_benefit="Weniger manuelle Bearbeitung",
    )


def _coordinator_user(*, username, business_unit):
    user = User.objects.create_user(
        username=username,
        password="VerySecureTestPassword!123",
        business_unit=business_unit,
    )
    group, _ = Group.objects.get_or_create(name=GROUP_COORDINATOR)
    user.groups.add(group)
    return user


def _value_stream(*, business_unit, owner):
    return ValueStream.objects.create(
        name="Beschaffung",
        business_unit=business_unit,
        owner=owner,
        trigger="Bedarf entsteht",
        outcome="Bestellung ist ausgelöst",
        scope_in="Bedarf bis Bestellung",
    )


def test_new_use_case_form_has_no_request_user_business_owner_default(owner, reader):
    form = UseCaseForm(current_user=owner)

    assert form.fields["business_owner"].initial is None
    assert form.fields["business_owner"].role_default.state == "open"
    assert "Offen" in str(form.fields["business_owner"].help_text)
    assert owner in form.fields["business_owner"].queryset
    assert reader not in form.fields["business_owner"].queryset


def test_existing_use_case_role_fields_show_source_provenance(
    business_unit,
    owner,
    coordinator,
    reader,
):
    use_case = _use_case(
        business_unit=business_unit,
        owner=owner,
        coordinator=coordinator,
        technical_owner=reader,
    )

    form = UseCaseForm(instance=use_case, current_user=coordinator)

    assert "Bestehende Zuordnung" in str(form.fields["business_owner"].help_text)
    assert "Quelle: Business Owner des Use Cases" in str(form.fields["business_owner"].help_text)
    assert "Quelle: KI-Koordinator des Use Cases" in str(form.fields["coordinator"].help_text)
    assert "Quelle: Technical Owner des Use Cases" in str(form.fields["technical_owner"].help_text)


def test_value_stream_owner_is_visible_cross_role_suggestion(business_unit, owner):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)

    form = ProblemStepForm(value_stream=value_stream)

    assert form.fields["business_owner"].initial is None
    assert form.fields["business_owner"].role_default.state == "suggestion"
    help_text = str(form.fields["business_owner"].help_text)
    assert f"Vorschlag: {owner.get_display_name()}" in help_text
    assert "Quelle: Owner des zugehörigen Value Streams" in help_text
    assert "Cross-Role-Vorschlag" in help_text


def test_architecture_intake_renders_business_owner_provenance(
    client,
    owner,
    business_unit,
):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)
    stage = ValueStreamStage.objects.create(
        value_stream=value_stream,
        sequence=1,
        name="Lieferantenauswahl",
        description="Angebote vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Vergleich ist manuell und langsam.",
        baseline_metrics="Fünf Tage",
    )
    session = client.session
    session[SESSION_KEY] = {"source_stage_id": str(stage.pk)}
    session.save()
    client.force_login(owner)

    response = client.get(reverse("use_cases:create"))
    body = response.content.decode()

    assert response.status_code == 200
    assert "Vorschlag:" in body
    assert "Quelle: Owner des zugehörigen Value Streams" in body
    assert "Cross-Role-Vorschlag" in body


def test_stale_value_stream_suggestion_is_rejected_fail_closed(
    business_unit,
    owner,
    other_owner,
):
    value_stream = _value_stream(business_unit=business_unit, owner=owner)
    form = ProblemStepForm(
        data={
            "title": "Lieferantenauswahl beschleunigen",
            "business_unit": business_unit.pk,
            "business_owner": owner.pk,
            "problem_statement": (
                "Der manuelle Angebotsvergleich verursacht heute unnötig lange Durchlaufzeiten."
            ),
        },
        value_stream=value_stream,
    )

    value_stream.owner = other_owner
    value_stream.save(update_fields=["owner", "updated_at"])

    assert form.is_valid() is False
    assert "entspricht nicht dem aktuell zulässigen Vorschlag" in form.errors["business_owner"][0]


def test_unique_second_approver_is_visible_suggestion_without_initial_assignment(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    candidate = _coordinator_user(username="block9-second", business_unit=business_unit)

    form = ApprovalDecisionForm(actor=coordinator, use_case=use_case)

    assert form.fields["second_approval_assignee"].initial is None
    assert form.fields["second_approval_assignee"].role_default.state == "suggestion"
    help_text = str(form.fields["second_approval_assignee"].help_text)
    assert candidate.get_display_name() in help_text
    assert "Quelle: Einzige aktuell zulässige unabhängige Zweitprüfung" in help_text
    assert form.fields["condition_owner"].role_default.state == "open"
    assert "Offen" in str(form.fields["condition_owner"].help_text)


def test_second_approver_suggestion_is_revalidated_before_form_acceptance(
    business_unit,
    owner,
    coordinator,
):
    use_case = _use_case(business_unit=business_unit, owner=owner)
    candidate = _coordinator_user(username="block9-second-a", business_unit=business_unit)
    form = ApprovalDecisionForm(
        data={
            "decision_status": UseCase.DecisionStatus.APPROVED_WITH_CONDITIONS,
            "rationale": "Die Freigabe ist fachlich begründet und nachvollziehbar dokumentiert.",
            "governance_confirmed": "on",
            "conditions": "Messkonzept vor Pilotstart fachlich bestätigen.",
            "condition_owner": owner.pk,
            "condition_due_date": "2026-08-30",
            "second_approval_assignee": candidate.pk,
        },
        actor=coordinator,
        use_case=use_case,
    )
    _coordinator_user(username="block9-second-b", business_unit=business_unit)

    assert form.is_valid() is False
    assert "aktuell kein zulässiger Personen-Default" in form.errors["second_approval_assignee"][0]
