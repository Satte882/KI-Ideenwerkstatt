from __future__ import annotations

import hashlib
import os
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ki_radar.accelerator.investigation_evidence import create_evidence_campaign
from ki_radar.accelerator.investigation_models import (
    InvestigationEvidenceCampaign,
    InvestigationSourceFolder,
)
from ki_radar.accelerator.investigation_tools import SnapshotRequest, create_source_snapshot
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

PROCESS_NAME = "VS1/#4 Neutral Evidence Case"
STREAM_NAME = "VS1/#4 Evidence Benchmark"
STAGE_NAME = "Evidence Review"
CAMPAIGN_KEY = "issue4-real-evidence-20260922"
DECISION_QUESTION = "Welche Lösungsrichtung ist durch die Evidenz gestützt?"
VARIANT_FILES = {
    "A": ("01_case_note.md", "02_counterevidence.md", "cases.csv"),
    "B": ("01_case_note.md", "02_report.md", "cases.csv"),
    "C": ("01_case_note.md", "02_system_note.md", "cases.csv"),
}
CAMPAIGN_LIMITS = {
    "max_provider_calls": 150,
    "max_input_tokens": 1_000_000,
    "max_output_tokens": 200_000,
    "max_cost_microunits": 5_000_000,
}
NEUTRAL_PROCESS_FIELDS = {
    "scope_start": "Ein Fall liegt zur Prüfung vor.",
    "scope_end": "Eine begründete Richtungsentscheidung ist dokumentiert.",
    "trigger": "Ein Fall wird zur Prüfung eingereicht.",
    "outcome": "Eine nachvollziehbare Richtungsentscheidung liegt vor.",
    "current_flow": "Fall prüfen, Evidenz bewerten und Lösungsrichtung ableiten.",
    "roles": "Fachbereich",
    "systems": "Bestehender Workflow",
    "data_objects": "Fallunterlagen und Messdaten",
    "business_rules": "",
    "handoffs": "",
    "bottlenecks": "Unterschiedliche Bearbeitungs- und Freigabezeiten.",
    "diagnostic_observations": "Bearbeitungs- und Freigabezeiten schwanken.",
    "cause_hypotheses": "",
    "confirmed_causes": "",
    "constraints": "",
    "exceptions": "",
    "baseline_metrics": "Noch nicht abschließend bewertet.",
}


class Command(BaseCommand):
    help = (
        "Prepare the neutral VS1/#4 ProcessAnalysis, frozen A/B/C snapshots and the "
        "authorized EvidenceCampaign. This command never starts an investigation run or "
        "calls a provider."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inspect-only",
            action="store_true",
            help="Report the production preflight state without mutating data.",
        )

    def handle(self, *args, **options):
        owner_name = (
            os.getenv("ISSUE4_OWNER_USERNAME", "").strip()
            or os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
            or "Satinder"
        )
        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=owner_name, is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError(f"Issue #4 owner {owner_name!r} not found or inactive.") from exc

        model = str(getattr(settings, "OPENROUTER_MODEL", "") or "").strip()
        api_key_present = bool(str(getattr(settings, "OPENROUTER_API_KEY", "") or "").strip())
        process_matches = ProcessAnalysis.objects.filter(name=PROCESS_NAME).count()
        campaign_matches = InvestigationEvidenceCampaign.objects.filter(
            campaign_key=CAMPAIGN_KEY
        ).count()
        self.stdout.write(
            "ISSUE4_PREFLIGHT "
            f"owner={owner.username} model={model or '<empty>'} "
            f"api_key_present={str(api_key_present).lower()} "
            f"process_matches={process_matches} campaign_matches={campaign_matches}"
        )
        if options["inspect_only"]:
            return

        if not model or not api_key_present:
            raise CommandError("OPENROUTER_MODEL and OPENROUTER_API_KEY must be configured.")
        expected_model = os.getenv("ISSUE4_EXPECTED_MODEL", "").strip()
        if not expected_model or expected_model != model:
            raise CommandError(
                "ISSUE4_EXPECTED_MODEL must exactly match the configured OPENROUTER_MODEL."
            )

        pricing = self._pricing_from_env()
        currency = os.getenv("ISSUE4_PRICING_CURRENCY", "USD").strip().upper()
        pricing_version = os.getenv("ISSUE4_PRICING_VERSION", "").strip()
        if currency != "USD" or not pricing_version:
            raise CommandError("Issue #4 pricing requires USD and a non-empty pricing version.")

        with transaction.atomic():
            process = self._ensure_neutral_process(owner)
            if process.investigation_runs.exists():
                raise CommandError(
                    "Neutral Issue #4 ProcessAnalysis already has InvestigationRuns; "
                    "refusing setup."
                )
            snapshot_ids: dict[str, str] = {}
            for variant, filenames in VARIANT_FILES.items():
                root = (
                    Path(settings.BASE_DIR)
                    / "tests"
                    / "fixtures"
                    / "investigation_source_packs"
                    / variant
                ).resolve()
                self._assert_fixture(root, filenames)
                folder, _created = InvestigationSourceFolder.objects.get_or_create(
                    process_analysis=process,
                    root_path=str(root),
                    defaults={
                        "name": f"VS1/#4 Variant {variant}",
                        "registered_by": owner,
                    },
                )
                if not folder.is_active:
                    raise CommandError(f"Variant {variant} source folder is inactive.")
                snapshot = self._matching_snapshot(folder, process, root, filenames)
                if snapshot is None:
                    result = create_source_snapshot(
                        actor=owner,
                        request=SnapshotRequest(
                            process_analysis_id=process.pk,
                            folder_id=folder.pk,
                            decision_question=DECISION_QUESTION,
                            run_limits={},
                        ),
                    )
                    snapshot = folder.snapshots.get(pk=result.snapshot_id)
                snapshot_ids[variant] = str(snapshot.pk)

            campaign = InvestigationEvidenceCampaign.objects.filter(
                campaign_key=CAMPAIGN_KEY
            ).first()
            if campaign is None:
                campaign = create_evidence_campaign(
                    actor=owner,
                    process_analysis_id=process.pk,
                    campaign_key=CAMPAIGN_KEY,
                    limits=CAMPAIGN_LIMITS,
                    pricing=pricing,
                    currency=currency,
                    pricing_version=pricing_version,
                )
            else:
                self._assert_campaign(
                    campaign=campaign,
                    process=process,
                    pricing=pricing,
                    currency=currency,
                    pricing_version=pricing_version,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE4_PREPARED "
                f"process_analysis={process.pk} campaign={campaign.pk} "
                f"campaign_revision={campaign.revision} usage={campaign.usage} "
                f"snapshot_A={snapshot_ids['A']} snapshot_B={snapshot_ids['B']} "
                f"snapshot_C={snapshot_ids['C']} provider_runs_started=0"
            )
        )

    def _pricing_from_env(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for env_name, key in (
            ("ISSUE4_PRICE_INPUT_PER_MILLION", "input_per_million"),
            ("ISSUE4_PRICE_OUTPUT_PER_MILLION", "output_per_million"),
        ):
            raw = os.getenv(env_name, "").strip()
            try:
                value = Decimal(raw)
            except (InvalidOperation, ValueError) as exc:
                raise CommandError(f"{env_name} must be a non-negative decimal.") from exc
            if value < 0:
                raise CommandError(f"{env_name} must be a non-negative decimal.")
            values[key] = str(value)
        return values

    def _ensure_neutral_process(self, owner):
        matches = list(
            ProcessAnalysis.objects.select_for_update()
            .select_related("stage__value_stream")
            .filter(name=PROCESS_NAME)
        )
        if len(matches) > 1:
            raise CommandError("Multiple neutral Issue #4 ProcessAnalysis records exist.")
        if matches:
            process = matches[0]
            if process.status != ProcessAnalysis.Status.DRAFT:
                raise CommandError("Existing neutral Issue #4 ProcessAnalysis is not DRAFT.")
            if process.stage.value_stream.owner_id != owner.pk:
                raise CommandError("Existing neutral Issue #4 ValueStream has a different owner.")
            for field, expected in NEUTRAL_PROCESS_FIELDS.items():
                if getattr(process, field) != expected:
                    raise CommandError(
                        f"Existing neutral ProcessAnalysis differs in field {field}; "
                        "refusing overwrite."
                    )
            if process.solution_options.exists() or process.validations.exists():
                raise CommandError(
                    "Existing neutral ProcessAnalysis is no longer neutral; refusing reuse."
                )
            return process

        business_unit = owner.business_unit
        if business_unit is None or not business_unit.is_active:
            business_unit, _ = BusinessUnit.objects.get_or_create(
                name="VS1 Evidence",
                defaults={
                    "description": (
                        "Technische Organisationseinheit für den kontrollierten VS1/#4-Nachweis."
                    ),
                    "is_active": True,
                },
            )
            if not business_unit.is_active:
                raise CommandError("Fallback business unit 'VS1 Evidence' is inactive.")

        streams = list(ValueStream.objects.select_for_update().filter(name=STREAM_NAME))
        if len(streams) > 1:
            raise CommandError("Multiple Issue #4 benchmark ValueStreams exist.")
        if streams:
            stream = streams[0]
            if (
                stream.owner_id != owner.pk
                or stream.business_unit_id != business_unit.pk
                or stream.status != ValueStream.Status.ACTIVE
            ):
                raise CommandError("Existing Issue #4 ValueStream conflicts with neutral setup.")
        else:
            stream = ValueStream.objects.create(
                name=STREAM_NAME,
                business_unit=business_unit,
                owner=owner,
                created_by=owner,
                trigger="Ein Fall benötigt eine Richtungsentscheidung.",
                outcome="Die Richtungsentscheidung ist nachvollziehbar dokumentiert.",
                scope_in="Prüfung des eingefrorenen Evidenzraums bis zur Richtungsentscheidung.",
                scope_out="Umsetzung, Pilot und Go-live.",
                constraints="Nur der eingefrorene VS1/#4-Evidenzraum.",
                status=ValueStream.Status.ACTIVE,
            )

        stages = list(stream.stages.select_for_update().filter(sequence=1))
        if len(stages) > 1:
            raise CommandError("Multiple sequence-1 stages exist on Issue #4 ValueStream.")
        if stages:
            stage = stages[0]
            if stage.name != STAGE_NAME:
                raise CommandError("Existing Issue #4 stage conflicts with neutral setup.")
        else:
            stage = ValueStreamStage.objects.create(
                value_stream=stream,
                sequence=1,
                name=STAGE_NAME,
                description="Fall und Evidenz prüfen; keine Ursache oder Lösung vorgeben.",
                actors="Fachbereich",
                systems="Bestehender Workflow",
                documents="Fallunterlagen und Messdaten",
                pain_points="Schwankende Bearbeitungs- und Freigabezeiten",
                baseline_metrics="Noch nicht abschließend bewertet",
            )

        return ProcessAnalysis.objects.create(
            stage=stage,
            name=PROCESS_NAME,
            status=ProcessAnalysis.Status.DRAFT,
            analyzed_by=owner,
            **NEUTRAL_PROCESS_FIELDS,
        )

    def _assert_fixture(self, root: Path, filenames: tuple[str, ...]) -> None:
        if not root.is_dir():
            raise CommandError(f"Frozen Issue #4 source pack missing: {root}")
        actual = tuple(sorted(item.name for item in root.iterdir() if item.is_file()))
        if actual != filenames:
            raise CommandError(
                f"Frozen source pack signature mismatch for {root.name}: "
                f"{actual!r} != {filenames!r}"
            )

    def _matching_snapshot(self, folder, process, root: Path, filenames: tuple[str, ...]):
        expected_hashes = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in filenames
        }
        for snapshot in folder.snapshots.filter(process_version=process.version).order_by(
            "-revision"
        ):
            if snapshot.decision_question != DECISION_QUESTION or snapshot.run_limits != {}:
                continue
            sources = {item.filename: item for item in snapshot.sources.all()}
            if tuple(sorted(sources)) != filenames:
                continue
            if all(sources[name].content_sha256 == expected_hashes[name] for name in filenames):
                return snapshot
        return None

    def _assert_campaign(self, *, campaign, process, pricing, currency, pricing_version):
        if campaign.process_analysis_id != process.pk:
            raise CommandError(
                "Existing Issue #4 campaign belongs to a different ProcessAnalysis."
            )
        if campaign.limits != CAMPAIGN_LIMITS:
            raise CommandError("Existing Issue #4 campaign limits differ; refusing overwrite.")
        if campaign.pricing != pricing or campaign.currency != currency:
            raise CommandError("Existing Issue #4 campaign pricing differs; refusing overwrite.")
        if campaign.pricing_version != pricing_version:
            raise CommandError(
                "Existing Issue #4 campaign pricing version differs; refusing overwrite."
            )
        if campaign.investigation_runs.exists() or campaign.provider_reservations.exists():
            raise CommandError(
                "Existing Issue #4 campaign already has runs or provider reservations."
            )
        if any(int(value or 0) != 0 for value in campaign.usage.values()):
            raise CommandError("Existing Issue #4 campaign usage is not zero.")
