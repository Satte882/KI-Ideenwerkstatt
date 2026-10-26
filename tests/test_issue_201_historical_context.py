"""Synthetic historical statements, never proof of real business effects."""

from copy import deepcopy

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from test_issue_146_outcome_contract import direct
from test_issue_189_measurement_plan import approve, delivery_and_pilot, finding, planned, save

from ki_radar.delivery.models import DeliveryPackage
from ki_radar.delivery.services import create_delivery_package
from ki_radar.reviews.services import create_review
from ki_radar.use_cases.initiatives import bind_initiative, save_initiative
from ki_radar.use_cases.measurement_plan import business_context, business_context_review_label

pytestmark = pytest.mark.django_db


@pytest.fixture
def context_case(owner, coordinator, technical_admin, business_unit):
    initiative = planned(owner)
    case = direct(owner, coordinator, business_unit)
    bind_initiative(initiative=initiative, artifact=case, actor=owner)
    case.refresh_from_db()
    case.technical_owner = coordinator
    case.save()
    approve(case, coordinator, technical_admin)
    case.refresh_from_db()
    return case, initiative


def record_finding(owner, case, initiative, *, finalize):
    return save(
        owner,
        initiative,
        finding(
            use_case=case,
            attribution="confirmed",
            attribution_reason="Synthetische Attribution mit begrenztem Vergleich",
            measurement_difference="Geschäftsabschlüsse statt Prozessdurchlaufzeit",
        ),
        finalize=finalize,
    )


def handover(client, coordinator, case):
    package = create_delivery_package(use_case=case, actor=coordinator)
    client.force_login(coordinator)
    assert client.post(reverse("delivery:package_mark_ready", args=[package.pk])).status_code == 302
    assert client.post(reverse("delivery:package_handover", args=[package.pk])).status_code == 302
    package.refresh_from_db()
    assert package.status == "handed_over"
    return package


@pytest.mark.parametrize(
    ("state", "label"),
    [
        ("draft", "Ungeprüft - Wirkungsprüfung offen"),
        ("reviewed", "Geprüft"),
        ("stale", "Erneute Prüfung erforderlich"),
    ],
)
def test_handover_route_freezes_and_exports_review_quality(
    context_case, owner, coordinator, client, state, label
):
    case, initiative = context_case
    record_finding(owner, case, initiative, finalize=state != "draft")
    if state == "stale":
        initiative.refresh_from_db()
        save_initiative(actor=owner, initiative=initiative, data={"effect_reason": "Neue Aussage"})
    case.refresh_from_db()
    package = handover(client, coordinator, case)
    frozen = deepcopy(package.business_context_snapshot)
    assert business_context_review_label(frozen) == label
    export_url = reverse("delivery:package_export_markdown", args=[package.pk])
    exported = client.get(export_url)
    assert exported.status_code == 200
    assert exported["Content-Type"] == "text/markdown; charset=utf-8"
    markdown = exported.content.decode()
    assert f"**Prüfstatus damals:** {label}" in markdown
    assert "**Gespeicherte Wirkungsaussage:** Bestätigt" in markdown
    assert "**Attribution:** Bestätigt" in markdown
    for field in (
        "business_outcome",
        "contribution",
        "evaluation_criteria",
        "measurement_method",
        "measurement_period",
        "measurement_population",
        "measurement_reference",
    ):
        assert frozen["current"][field] in markdown
    page = client.get(package.get_absolute_url()).content.decode()
    historical = page.split("Bei Übergabe betrachteter Wirkungskontext</summary>", 1)[1]
    historical = historical.split("</details>", 1)[0]
    assert label in historical
    assert "Gespeicherte Wirkungsaussage</dt><dd>Bestätigt" in historical
    assert "Attribution</dt><dd>Bestätigt" in historical
    initiative.refresh_from_db()
    save_initiative(
        actor=owner,
        initiative=initiative,
        data={
            "business_outcome": "Neues aktuelles Geschäftsziel",
            "measurement_method": "Andere aktuelle Messmethode",
            "measurement_change_reason": "Neue Folgephase",
            "effect_reason": "Andere aktuelle Aussage",
        },
    )
    assert client.get(export_url).content == exported.content
    page = client.get(package.get_absolute_url()).content.decode()
    assert "Neues aktuelles Geschäftsziel" in page
    assert frozen["current"]["business_outcome"] in page
    package.refresh_from_db()
    assert package.business_context_snapshot == frozen


@pytest.mark.parametrize("state", ["draft", "reviewed", "stale", "legacy"])
def test_real_scale_snapshot_preserves_review_qualification(
    context_case, owner, coordinator, client, state
):
    case, initiative = context_case
    delivery_and_pilot(case, coordinator, client)
    record_finding(owner, case, initiative, finalize=state != "draft")
    if state == "stale":
        initiative.refresh_from_db()
        save_initiative(actor=owner, initiative=initiative, data={"effect_reason": "Neue Aussage"})
    review = create_review(
        use_case=case,
        actor=coordinator,
        data={
            "review_date": timezone.localdate(),
            "decision": "continue",
            "new_status": "pilot",
            "rationale": "Synthetischen Pilot weiter beobachten",
        },
    )
    if state == "legacy":
        review.scale_readiness_snapshot["business_context"].pop("review_required")
        review.scale_readiness_snapshot["business_context"].pop("reviewed_at")
        review.save()
    frozen = deepcopy(review.scale_readiness_snapshot)
    label = {
        "draft": "Ungeprüft - Wirkungsprüfung offen",
        "reviewed": "Geprüft",
        "stale": "Erneute Prüfung erforderlich",
        "legacy": "Historisch nicht erfasst",
    }[state]
    assert business_context_review_label(frozen["business_context"]) == label
    client.force_login(owner)
    page = client.get(case.get_absolute_url())
    assert page.status_code == 200
    historical = page.content.decode().split("Wirkungskontext zum damaligen Review:", 1)[1]
    assert f"Prüfstatus damals:</strong> {label}" in historical
    assert "Gespeicherte Wirkungsaussage</dt><dd>Bestätigt" in historical
    assert "Attribution</dt><dd>Bestätigt" in historical
    initiative.refresh_from_db()
    save_initiative(actor=owner, initiative=initiative, data={"effect_reason": "Spätere Aussage"})
    review.refresh_from_db()
    assert review.scale_readiness_snapshot == frozen
    assert (
        label
        in client.get(case.get_absolute_url())
        .content.decode()
        .split("Wirkungskontext zum damaligen Review:", 1)[1]
    )


@pytest.mark.parametrize(
    ("snapshot", "label"),
    [
        ({}, "Historischer Wirkungskontext nicht vorhanden"),
        ({"current": {"business_outcome": "Altes Ziel"}}, "Historisch nicht erfasst"),
        (
            {
                "effect_label": "Bestätigt",
                "attribution_label": "Bestätigt",
                "review_required": True,
            },
            "Wirkungsprüfung offen / erneut erforderlich",
        ),
        ({"review_required": False}, "Geprüft"),
    ],
)
def test_legacy_snapshot_never_infers_or_backfills_context(
    context_case, coordinator, client, snapshot, label
):
    case, _ = context_case
    package = create_delivery_package(use_case=case, actor=coordinator)
    # Existing historical storage shapes, with no migration/backfill.
    package.business_context_snapshot = deepcopy(snapshot)
    package.status = "handed_over"
    package.save()
    client.force_login(coordinator)
    for url in (
        package.get_absolute_url(),
        reverse("delivery:package_export_markdown", args=[package.pk]),
    ):
        response = client.get(url)
        assert response.status_code == 200
        assert label in response.content.decode()
    package.refresh_from_db()
    assert package.business_context_snapshot == snapshot


def test_pre_handover_export_has_no_fictional_history(context_case, coordinator, client):
    case, _ = context_case
    package = create_delivery_package(use_case=case, actor=coordinator)
    client.force_login(coordinator)
    response = client.get(reverse("delivery:package_export_markdown", args=[package.pk]))
    assert response.status_code == 200
    assert "Historischer Wirkungskontext nicht vorhanden" in response.content.decode()
    assert not package.business_context_snapshot
    assert business_context(case)["reviewed_at"] is None


def test_access_and_handed_over_immutability(context_case, coordinator, reader, client):
    case, _ = context_case
    package = handover(client, coordinator, case)
    frozen = deepcopy(package.business_context_snapshot)
    client.logout()
    export_url = reverse("delivery:package_export_markdown", args=[package.pk])
    assert client.get(export_url).status_code == 302
    client.force_login(reader)
    assert client.get(export_url).status_code == 200
    assert client.post(reverse("delivery:package_handover", args=[package.pk])).status_code == 403
    client.force_login(coordinator)
    assert client.post(
        reverse("delivery:package_update", args=[package.pk]), {"problem_context": "Manipuliert"}
    ).status_code in {302, 403}
    from ki_radar.delivery.lean_services import hand_over_package, mark_package_ready

    with pytest.raises(ValidationError):
        mark_package_ready(package)
    with pytest.raises(ValidationError):
        hand_over_package(package, coordinator)
    case.is_archived = True
    case.save()
    assert client.get(export_url).status_code == 403
    assert client.get(package.get_absolute_url()).status_code == 403
    package.refresh_from_db()
    assert package.business_context_snapshot == frozen
    assert DeliveryPackage.objects.filter(pk=package.pk).count() == 1
