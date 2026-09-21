from datetime import timedelta

import pytest
from django import forms
from django.urls import reverse
from django.utils import timezone

from ki_radar.use_cases.forms import UseCaseForm
from ki_radar.use_cases.models import UseCase


@pytest.fixture
def use_case(owner, business_unit):
    return UseCase.objects.create(
        title="Dokumente klassifizieren",
        problem_statement="Manuelle Klassifizierung kostet Zeit.",
        business_unit=business_unit,
        affected_process="Dokumentenbearbeitung",
        submitter=owner,
        business_owner=owner,
        expected_benefit="Bearbeitungszeit reduzieren",
    )


def _edit_payload(use_case, **overrides):
    form = UseCaseForm(instance=use_case)
    payload = {}
    for name, field in form.fields.items():
        value = form.initial.get(name)
        if isinstance(field, forms.BooleanField):
            if value:
                payload[name] = "on"
        elif value is not None:
            payload[name] = getattr(value, "pk", value)
    payload.update(
        {
            "business_domain": "other",
            "business_capability": "Allgemeine Prozessunterstützung",
            "process_area": use_case.affected_process,
            **overrides,
        }
    )
    return payload


@pytest.mark.django_db
def test_owner_can_edit_own_use_case(client, owner, use_case):
    client.force_login(owner)
    response = client.get(reverse("use_cases:edit", args=[use_case.pk]))
    assert response.status_code == 200


@pytest.mark.django_db
def test_owner_cannot_edit_foreign_use_case(client, other_owner, use_case):
    client.force_login(other_owner)
    response = client.get(reverse("use_cases:edit", args=[use_case.pk]))
    assert response.status_code == 403


@pytest.mark.django_db
def test_reader_cannot_create(client, reader):
    client.force_login(reader)
    assert client.get(reverse("use_cases:create")).status_code == 403


@pytest.mark.django_db
def test_use_case_form_uses_german_decision_labels():
    form = UseCaseForm()

    assert form.fields["problem_statement"].label == "Problemstellung"
    assert form.fields["next_review_date"].label == "Nächster Entscheidungstermin"
    assert form.fields["planned_pilot_end"].label == "Geplantes Pilotende"
    assert form.fields["technical_owner"].label == "Technischer Owner"
    assert "pilot_start" not in form.fields


@pytest.mark.django_db
def test_use_case_form_renders_date_inputs_in_browser_format(use_case):
    localized_today = timezone.localdate().strftime("%d.%m.%Y")
    use_case.next_review_date = timezone.localdate()
    form = UseCaseForm(instance=use_case)

    assert f'value="{timezone.localdate().isoformat()}"' in form.as_p()
    assert localized_today not in form.as_p()


@pytest.mark.django_db
def test_general_edit_ignores_injected_pilot_start_and_keeps_existing_value(
    client, owner, use_case
):
    existing_start = timezone.localdate() - timedelta(days=2)
    use_case.pilot_start = existing_start
    use_case.planned_pilot_end = existing_start + timedelta(days=5)
    use_case.save(update_fields=["pilot_start", "planned_pilot_end", "updated_at"])
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:edit", args=[use_case.pk]),
        _edit_payload(
            use_case,
            title="Gewöhnlich bearbeitet",
            pilot_start=timezone.localdate().isoformat(),
        ),
    )

    assert response.status_code == 302
    use_case.refresh_from_db()
    assert use_case.title == "Gewöhnlich bearbeitet"
    assert use_case.pilot_start == existing_start


@pytest.mark.django_db
def test_general_edit_does_not_run_delivery_handover_validation(client, owner, use_case):
    client.force_login(owner)

    response = client.post(
        reverse("use_cases:edit", args=[use_case.pk]),
        _edit_payload(use_case, title="Ohne Delivery bearbeitet"),
        follow=True,
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Ohne Delivery bearbeitet" in content
    assert "verbindlichen Übergabe" not in content


@pytest.mark.django_db
def test_planned_pilot_end_still_cannot_precede_existing_pilot_start(use_case):
    use_case.pilot_start = timezone.localdate()
    use_case.save(update_fields=["pilot_start", "updated_at"])
    form = UseCaseForm(
        data=_edit_payload(
            use_case,
            planned_pilot_end=(use_case.pilot_start - timedelta(days=1)).isoformat(),
        ),
        instance=use_case,
    )

    assert form.is_valid() is False
    assert "darf nicht vor dem Pilotbeginn" in form.errors["planned_pilot_end"][0]


@pytest.mark.django_db
def test_history_tracks_user(client, owner, use_case):
    client.force_login(owner)
    use_case.title = "Geänderter Titel"
    use_case.save()
    latest = use_case.history.first()
    assert latest.title == "Geänderter Titel"


@pytest.mark.django_db
def test_csv_export_is_authenticated(client, owner, use_case):
    client.force_login(owner)
    response = client.get(reverse("use_cases:export_csv"))
    assert response.status_code == 200
    assert use_case.short_id in response.content.decode("utf-8-sig")
