from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from ki_radar.accelerator.models import SolutionGenerationRun
from ki_radar.accelerator.solution_generation_adoption import (
    SolutionGenerationAdoptionError,
    adopt_solution_generation_bundle,
)
from ki_radar.accelerator.solution_generation_contract import (
    GENERATED_OPTION_FIELDS,
    GENERATION_PROMPT_VERSION,
    GENERATION_SCHEMA_VERSION,
    OPTION_LANES,
)
from ki_radar.accelerator.solution_generation_sources import (
    build_solution_generation_source_context,
)
from ki_radar.architecture.focus import ValueStreamFocus
from ki_radar.architecture.models import (
    ProcessAnalysis,
    ProcessValidation,
    SolutionOption,
    SolutionSelectionDecision,
    ValueStream,
    ValueStreamStage,
)
from ki_radar.core.taxonomy import BusinessDomain, ScreeningLevel

LANE_NAMES = {
    "organizational": "Organisatorischer Entwurf",
    "rule_automation": "Regelbasierter Entwurf",
    "assistant": "Assistenzentwurf",
}
LANE_TYPES = {
    "organizational": SolutionOption.OptionType.ORGANIZATIONAL,
    "rule_automation": SolutionOption.OptionType.RULE_AUTOMATION,
    "assistant": SolutionOption.OptionType.ASSISTANT,
}


def make_process(owner, business_unit):
    stream = ValueStream.objects.create(
        name="Beschaffung bis Zahlung",
        business_unit=business_unit,
        owner=owner,
        created_by=owner,
        trigger="Freigegebener Bedarf",
        outcome="Bestellung ausgelöst",
        scope_in="Bedarf bis Bestellung",
        strategic_objective="Durchlaufzeit reduzieren",
        constraints="EU-Datenhaltung und menschliche Freigabe",
    )
    stage = ValueStreamStage.objects.create(
        value_stream=stream,
        sequence=2,
        name="Angebote vergleichen",
        description="Angebote fachlich vergleichen",
        actors="Einkauf",
        systems="ERP",
        documents="Angebote",
        pain_points="Manueller Vergleich",
        baseline_metrics="Elf Minuten pro Vergleich",
    )
    return ProcessAnalysis.objects.create(
        stage=stage,
        name="Angebotsvergleich",
        scope_start="Angebote liegen vor",
        scope_end="Auswahl ist dokumentiert",
        trigger="Angebotsfrist endet",
        outcome="Nachvollziehbare Auswahl",
        current_flow="Angebote werden manuell gegenübergestellt.",
        roles="Einkauf und Fachbereich",
        systems="ERP und Dateiablage",
        data_objects="Angebote und Kriterienkatalog",
        business_rules="Vier-Augen-Prinzip bei Freigabe",
        handoffs="Einkauf übergibt an Fachbereich",
        bottlenecks="Manuelle Übertragung verursacht Wartezeit.",
        exceptions="Fehlende Pflichtangaben werden nachgefordert.",
        baseline_metrics="Elf Minuten pro Vergleich",
        target_state_principles="Nachvollziehbar und assistierend",
        analyzed_by=owner,
    )


def select_focus(process, owner):
    ValueStreamFocus.objects.create(
        value_stream=process.stage.value_stream,
        business_domain=BusinessDomain.PROCUREMENT,
        capability="Supplier Sourcing und Angebotsvergleich",
        strategic_impact=ScreeningLevel.HIGH,
        economic_potential=ScreeningLevel.MEDIUM,
        pain_intensity=ScreeningLevel.HIGH,
        data_accessibility=ScreeningLevel.MEDIUM,
        change_effort=ScreeningLevel.MEDIUM,
        status=ValueStreamFocus.Status.SELECTED,
        rationale="Der Angebotsvergleich wurde fachlich für den Deep Dive ausgewählt.",
        updated_by=owner,
    )


def statement(text):
    return {
        "text": text,
        "source_ids": ["process.current_flow"],
        "assumptions": [],
        "open_evidence": [],
        "uncertainty": {
            "level": "low",
            "reason": "Direkt aus dem dokumentierten Ist-Ablauf abgeleitet.",
        },
    }


def preview_payload(process):
    context = build_solution_generation_source_context(process)
    options = {}
    for lane in OPTION_LANES:
        options[lane] = {
            field_name: statement(f"{LANE_NAMES[lane]} - {field_name}")
            for field_name in GENERATED_OPTION_FIELDS
        }
    return {
        "schema_version": GENERATION_SCHEMA_VERSION,
        "prompt_version": GENERATION_PROMPT_VERSION,
        "source_context": context.provider_payload(),
        "options": options,
        "edits": {},
    }


def make_run(owner, process):
    context = build_solution_generation_source_context(process)
    return SolutionGenerationRun.objects.create(
        process_analysis=process,
        process_version=process.version,
        source_hash=context.source_hash,
        requested_by=owner,
        status=SolutionGenerationRun.Status.SUCCESS,
        prompt_version=GENERATION_PROMPT_VERSION,
        generation_schema_version=GENERATION_SCHEMA_VERSION,
        finished_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=1),
        preview_payload=preview_payload(process),
    )


@pytest.mark.django_db
def test_atomic_adoption_creates_exactly_three_neutral_regular_options(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    response = client.post(reverse("accelerator:solution_generation_adopt", args=[run.pk]))

    assert response.status_code == 302
    assert response.url == reverse("architecture:solution_option_compare", args=[process.pk])
    options = list(SolutionOption.objects.filter(process_analysis=process).order_by("option_type"))
    assert len(options) == 3
    assert {option.option_type for option in options} == set(LANE_TYPES.values())
    assert all(
        option.recommendation == SolutionOption.Recommendation.CANDIDATE for option in options
    )
    assert all(
        option.evaluation_status == SolutionOption.EvaluationStatus.DRAFT for option in options
    )
    assert all(option.feasibility == SolutionOption.Effort.NOT_ASSESSED for option in options)
    assert all(
        option.integration_effort == SolutionOption.Effort.NOT_ASSESSED for option in options
    )
    assert all(option.created_by == owner for option in options)
    assert not ProcessValidation.objects.filter(process_analysis=process).exists()
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()

    run.refresh_from_db()
    adoption = run.preview_payload["adoption"]
    assert adoption["status"] == "adopted"
    assert len(adoption["option_ids"]) == 3


@pytest.mark.django_db
def test_adoption_uses_saved_preview_edits_and_options_remain_editable(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    select_focus(process, owner)
    run = make_run(owner, process)
    payload = dict(run.preview_payload)
    payload["edits"] = {"assistant": {"description": "Vom Menschen präzisierter Assistenzentwurf."}}
    run.preview_payload = payload
    run.save(update_fields=["preview_payload", "updated_at"])

    result = adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert result.created is True
    assistant = SolutionOption.objects.get(
        process_analysis=process,
        option_type=SolutionOption.OptionType.ASSISTANT,
    )
    assert assistant.description == "Vom Menschen präzisierter Assistenzentwurf."

    client.force_login(owner)
    response = client.get(reverse("architecture:solution_option_update", args=[assistant.pk]))
    assert response.status_code == 200
    assert "Lösungsoption bearbeiten" in response.content.decode()


@pytest.mark.django_db
def test_stale_source_blocks_whole_adoption(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    process.current_flow = "Der Ist-Ablauf wurde nach der Generierung geändert."
    process.save(update_fields=["current_flow", "updated_at"])

    with pytest.raises(SolutionGenerationAdoptionError) as exc_info:
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert exc_info.value.code == "preview_stale"
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_tampered_preview_edit_is_rejected_before_domain_write(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    payload = dict(run.preview_payload)
    payload["edits"] = {"assistant": {"feasibility": "high"}}
    run.preview_payload = payload
    run.save(update_fields=["preview_payload", "updated_at"])

    with pytest.raises(SolutionGenerationAdoptionError) as exc_info:
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert exc_info.value.code == "invalid_preview"
    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_regular_form_failure_rolls_back_entire_bundle(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    payload = dict(run.preview_payload)
    payload["options"] = dict(payload["options"])
    payload["options"]["assistant"] = dict(payload["options"]["assistant"])
    payload["options"]["assistant"]["name"] = dict(payload["options"]["assistant"]["name"])
    payload["options"]["assistant"]["name"]["text"] = "x" * 201
    run.preview_payload = payload
    run.save(update_fields=["preview_payload", "updated_at"])

    with pytest.raises(SolutionGenerationAdoptionError) as exc_info:
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert exc_info.value.code == "option_form_invalid"
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    run.refresh_from_db()
    assert "adoption" not in run.preview_payload


@pytest.mark.django_db
def test_persistence_failure_rolls_back_first_created_option(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    original_save = SolutionOption.save
    calls = {"count": 0}

    def flaky_save(instance, *args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            raise RuntimeError("simulated persistence failure")
        return original_save(instance, *args, **kwargs)

    with (
        patch.object(SolutionOption, "save", new=flaky_save),
        pytest.raises(RuntimeError, match="simulated persistence failure"),
    ):
        adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    run.refresh_from_db()
    assert "adoption" not in run.preview_payload


@pytest.mark.django_db
def test_duplicate_adoption_is_idempotent(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)

    first = adopt_solution_generation_bundle(actor=owner, run_id=run.pk)
    second = adopt_solution_generation_bundle(actor=owner, run_id=run.pk)

    assert first.created is True
    assert second.created is False
    assert [option.pk for option in first.options] == [option.pk for option in second.options]
    assert SolutionOption.objects.filter(process_analysis=process).count() == 3


@pytest.mark.django_db
def test_adoption_permission_is_rechecked_inside_service(owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    outsider = owner.__class__.objects.create_user(username="block7-outsider", password="secret")

    with pytest.raises(PermissionDenied):
        adopt_solution_generation_bundle(actor=outsider, run_id=run.pk)

    assert not SolutionOption.objects.filter(process_analysis=process).exists()


@pytest.mark.django_db
def test_adopted_preview_is_locked_and_cannot_be_adopted_twice_via_ui(
    client,
    owner,
    business_unit,
):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    first = client.post(reverse("accelerator:solution_generation_adopt", args=[run.pk]))
    second = client.post(reverse("accelerator:solution_generation_adopt", args=[run.pk]))
    preview = client.get(reverse("accelerator:solution_generation_preview", args=[run.pk]))

    assert first.status_code == 302
    assert second.status_code == 302
    assert SolutionOption.objects.filter(process_analysis=process).count() == 3
    content = preview.content.decode()
    assert "Bereits übernommen" in content
    assert "Alle drei Lösungsoptionen übernehmen" not in content
    assert "Bearbeitungen speichern" not in content


@pytest.mark.django_db
def test_preview_offers_one_adoption_choice_per_generated_option(client, owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    content = client.get(
        reverse("accelerator:solution_generation_preview", args=[run.pk])
    ).content.decode()

    assert content.count('name="selected_lanes"') == 3
    assert content.count("Diesen KI-Vorschlag übernehmen") == 3
    assert content.count("Vorschlag verwerfen") == 3
    assert "Ausgewählte KI-Lösungsoptionen hinzufügen" in content
    assert 'name="selection_mode" value="explicit"' in content


@pytest.mark.django_db
def test_explicit_subset_adoption_creates_only_selected_options(client, owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:solution_generation_adopt", args=[run.pk]),
        data={
            "selection_mode": "explicit",
            "selected_lanes": ["organizational", "assistant"],
        },
    )

    assert response.status_code == 302
    options = SolutionOption.objects.filter(process_analysis=process)
    assert options.count() == 2
    assert set(options.values_list("option_type", flat=True)) == {
        SolutionOption.OptionType.ORGANIZATIONAL,
        SolutionOption.OptionType.ASSISTANT,
    }
    assert not SolutionSelectionDecision.objects.filter(process_analysis=process).exists()

    run.refresh_from_db()
    assert run.preview_payload["adoption"]["lanes"] == ["organizational", "assistant"]
    assert len(run.preview_payload["adoption"]["option_ids"]) == 2


@pytest.mark.django_db
def test_explicit_empty_adoption_is_rejected_without_domain_write(client, owner, business_unit):
    process = make_process(owner, business_unit)
    run = make_run(owner, process)
    client.force_login(owner)

    response = client.post(
        reverse("accelerator:solution_generation_adopt", args=[run.pk]),
        data={"selection_mode": "explicit"},
    )

    preview_url = reverse("accelerator:solution_generation_preview", args=[run.pk])
    assert response.status_code == 302
    assert response.url == f"{preview_url}#solution-generation-adoption"
    assert not SolutionOption.objects.filter(process_analysis=process).exists()
    run.refresh_from_db()
    assert "adoption" not in run.preview_payload
