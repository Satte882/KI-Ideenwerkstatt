from __future__ import annotations

import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ki_radar.accelerator.ap4_evidence import source_pack_hash
from ki_radar.accelerator.investigation_models import InvestigationSourceFolder
from ki_radar.accelerator.investigation_tools import SnapshotRequest, create_source_snapshot
from ki_radar.accelerator.issue106_baseline import golden_case_specs
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

CONTRACT_PATH = "tests/fixtures/issue117_package3_contract_v1.json"
STREAM_NAME = "Issue #117 Package 3"
STAGE_NAME = "Structured Mapping Provider Evidence"
FALLBACK_BUSINESS_UNIT = "Issue #117 Evidence"


def _contract() -> dict[str, object]:
    path = Path(settings.BASE_DIR) / CONTRACT_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CommandError(f"Could not load {CONTRACT_PATH}: {exc}") from exc
    if payload.get("schema_version") != "issue117-package3-contract-v1":
        raise CommandError("Unexpected Issue #117 Package 3 contract version.")
    slots = payload.get("slots")
    if not isinstance(slots, list) or len(slots) != 4:
        raise CommandError("Issue #117 Package 3 requires exactly four planned slots.")
    slot_ids = [str(item.get("slot_id") or "") for item in slots if isinstance(item, dict)]
    if len(slot_ids) != 4 or len(set(slot_ids)) != 4 or not all(slot_ids):
        raise CommandError("Issue #117 Package 3 slot IDs are invalid.")
    return payload


def _process_name(slot_id: str) -> str:
    return f"Issue #117 Package 3 {slot_id}"


class Command(BaseCommand):
    help = "Prepare the four isolated Issue #117 Package 3 provider-evidence slots."

    def add_arguments(self, parser):
        parser.add_argument(
            "--inspect-only",
            action="store_true",
            help="Report prepared Package 3 state without mutating data.",
        )

    def handle(self, *args, **options):
        owner_name = (
            os.getenv("ISSUE117_OWNER_USERNAME", "").strip()
            or os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
            or "Satinder"
        )
        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=owner_name, is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError(
                f"Issue #117 Package 3 owner {owner_name!r} not found or inactive."
            ) from exc

        contract = _contract()
        slots = contract["slots"]
        existing = ProcessAnalysis.objects.filter(name__startswith="Issue #117 Package 3 ").count()
        self.stdout.write(
            "ISSUE117_P3_PREFLIGHT "
            + json.dumps(
                {
                    "owner": owner.username,
                    "expected_slots": len(slots),
                    "existing_processes": existing,
                },
                separators=(",", ":"),
            )
        )
        if options["inspect_only"]:
            return

        golden = golden_case_specs()
        with transaction.atomic():
            _stream, stage = self._ensure_stream(owner)
            prepared = []
            for slot in slots:
                case_id = str(slot["case_id"])
                if case_id not in {"AP4-02", "AP4-04"}:
                    raise CommandError(f"Unsupported Package 3 case: {case_id}")
                case = golden[case_id]
                self._assert_source_pack(case_id, case)

                process = self._ensure_process(
                    owner=owner,
                    stage=stage,
                    slot_id=str(slot["slot_id"]),
                    problem_statement=str(case["problem_statement"]),
                )
                root = (Path(settings.BASE_DIR) / str(case["source_pack"])).resolve()
                folder, _created = InvestigationSourceFolder.objects.get_or_create(
                    process_analysis=process,
                    root_path=str(root),
                    defaults={
                        "name": f"#117 Package 3 {slot['slot_id']}",
                        "registered_by": owner,
                    },
                )
                if not folder.is_active:
                    raise CommandError(f"{slot['slot_id']}: source folder is inactive.")

                snapshots = list(
                    folder.snapshots.filter(process_version=process.version).order_by("-revision")
                )
                if len(snapshots) > 1:
                    raise CommandError(
                        f"{slot['slot_id']}: multiple current snapshots exist; inspect manually."
                    )
                if snapshots:
                    snapshot = snapshots[0]
                    self._assert_snapshot_contract(snapshot, slot)
                else:
                    result = create_source_snapshot(
                        actor=owner,
                        request=SnapshotRequest(
                            process_analysis_id=process.pk,
                            folder_id=folder.pk,
                            decision_question=str(case["problem_statement"]),
                            run_limits={},
                            structured_mapping_specs=(self._mapping_spec(slot),),
                        ),
                    )
                    snapshot = folder.snapshots.get(pk=result.snapshot_id)
                    self._assert_snapshot_contract(snapshot, slot)

                prepared.append(
                    {
                        "slot_id": slot["slot_id"],
                        "case_id": case_id,
                        "process_analysis_id": str(process.pk),
                        "snapshot_id": str(snapshot.pk),
                        "manifest_hash": snapshot.manifest_hash,
                        "mapping_spec": snapshot.process_context["structured_mapping_specs"][0],
                        "existing_runs": process.investigation_runs.count(),
                    }
                )

        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE117_P3_PREPARED "
                + json.dumps({"slots": prepared}, ensure_ascii=False, separators=(",", ":"))
            )
        )

    def _ensure_stream(self, owner):
        business_unit = owner.business_unit
        if business_unit is None or not business_unit.is_active:
            business_unit, _created = BusinessUnit.objects.get_or_create(
                name=FALLBACK_BUSINESS_UNIT,
                defaults={
                    "description": "Technische Organisationseinheit für #117/Paket-3-Evidence.",
                    "is_active": True,
                },
            )
            if not business_unit.is_active:
                raise CommandError(f"Fallback business unit {FALLBACK_BUSINESS_UNIT!r} is inactive.")

        streams = list(ValueStream.objects.select_for_update().filter(name=STREAM_NAME))
        if len(streams) > 1:
            raise CommandError("Multiple Issue #117 Package 3 ValueStreams exist.")
        if streams:
            stream = streams[0]
            if (
                stream.owner_id != owner.pk
                or stream.business_unit_id != business_unit.pk
                or stream.status != ValueStream.Status.ACTIVE
            ):
                raise CommandError("Existing Issue #117 Package 3 ValueStream conflicts with setup.")
        else:
            stream = ValueStream.objects.create(
                name=STREAM_NAME,
                business_unit=business_unit,
                owner=owner,
                created_by=owner,
                trigger="Ein gegateter #117-Paket-3-Nachweis wird gestartet.",
                outcome="Provider- und Human-Review-Evidence für Structured Mapping liegt vor.",
                scope_in="Nur die vier vorab definierten Paket-3-Prüffälle.",
                scope_out="Performance-, Reliability- und Modellvergleich.",
                constraints="Keine Wiederholung bis zum Wunschresultat.",
                status=ValueStream.Status.ACTIVE,
            )

        stages = list(stream.stages.select_for_update().filter(sequence=1))
        if len(stages) > 1:
            raise CommandError("Multiple Package 3 stages exist.")
        if stages:
            stage = stages[0]
            if stage.name != STAGE_NAME:
                raise CommandError("Existing Package 3 stage conflicts with setup.")
        else:
            stage = ValueStreamStage.objects.create(
                value_stream=stream,
                sequence=1,
                name=STAGE_NAME,
                description="Gezielter Integrationsnachweis des #117 Structured-Mapping-Contracts.",
                actors="Benchmark-Operator und Human Reviewer",
                systems="KI-Ideenwerkstatt Investigation",
                documents="AP4 Source Packs und #117 Paket-3-Vertrag",
                pain_points="Mapping-Verlust, Repair und semantische Verifier-Erkennung",
                baseline_metrics="Kein Performanceziel in Paket 3.",
            )
        return stream, stage

    def _ensure_process(self, *, owner, stage, slot_id: str, problem_statement: str):
        name = _process_name(slot_id)
        expected = {
            "scope_start": "Ein eingefrorener Paket-3-Fall liegt zur Investigation vor.",
            "scope_end": "Der vorab definierte Paket-3-Nachweis ist erreicht oder sicher blockiert.",
            "trigger": "Der Paket-3-Slot wird explizit gestartet.",
            "outcome": "Auditierbare Provider- und Human-Review-Evidence.",
            "current_flow": "Evidenz untersuchen, Mapping erzeugen, prüfen und gegebenenfalls reparieren.",
            "roles": "Benchmark-Operator; Human Reviewer bleibt semantische Autorität.",
            "systems": "KI-Ideenwerkstatt Investigation",
            "data_objects": "Immutable Source Snapshot und Structured-Mapping-Contract.",
            "business_rules": "Nur der vorab deklarierte #117-Paket-3-Testtyp ist zulässig.",
            "handoffs": "",
            "bottlenecks": "Structured-Mapping-Vollständigkeit und semantische Verifier-Prüfung.",
            "diagnostic_observations": problem_statement,
            "cause_hypotheses": "",
            "confirmed_causes": "",
            "constraints": "Maximal vier geplante Runs; keine Post-hoc-Auswahl.",
            "exceptions": "",
            "baseline_metrics": "Nicht Gegenstand dieses Bugfix-Gates.",
        }
        matches = list(ProcessAnalysis.objects.select_for_update().filter(stage=stage, name=name))
        if len(matches) > 1:
            raise CommandError(f"{slot_id}: multiple ProcessAnalysis records exist.")
        if matches:
            process = matches[0]
            if process.status != ProcessAnalysis.Status.DRAFT or process.analyzed_by_id != owner.pk:
                raise CommandError(f"{slot_id}: existing ProcessAnalysis conflicts with setup.")
            for field, value in expected.items():
                if getattr(process, field) != value:
                    raise CommandError(
                        f"{slot_id}: existing ProcessAnalysis differs in {field}; refusing overwrite."
                    )
            return process
        return ProcessAnalysis.objects.create(
            stage=stage,
            name=name,
            status=ProcessAnalysis.Status.DRAFT,
            analyzed_by=owner,
            **expected,
        )

    def _mapping_spec(self, slot):
        return {
            "source_filename": str(slot["source_filename"]),
            "case_key_column": str(slot["case_key_column"]),
            "case_keys": list(slot["case_keys"]),
            "mapping_dimension": str(slot["mapping_dimension"]),
            "exhaustive": True,
        }

    def _assert_snapshot_contract(self, snapshot, slot) -> None:
        specs = snapshot.process_context.get("structured_mapping_specs")
        if not isinstance(specs, list) or len(specs) != 1:
            raise CommandError(f"{slot['slot_id']}: snapshot has no single frozen mapping spec.")
        spec = specs[0]
        expected = self._mapping_spec(slot)
        for field in ("source_filename", "case_key_column", "case_keys", "mapping_dimension", "exhaustive"):
            if spec.get(field) != expected[field]:
                raise CommandError(
                    f"{slot['slot_id']}: frozen snapshot mapping contract differs in {field}."
                )
        source = snapshot.sources.filter(filename=expected["source_filename"]).first()
        if source is None or spec.get("source_content_sha256") != source.content_sha256:
            raise CommandError(f"{slot['slot_id']}: frozen mapping source hash differs.")

    def _assert_source_pack(self, case_id: str, case) -> None:
        root = (Path(settings.BASE_DIR) / str(case["source_pack"])).resolve()
        filenames = tuple(str(item) for item in case["files"])
        if not root.is_dir():
            raise CommandError(f"{case_id}: frozen source pack is missing.")
        actual = tuple(sorted(item.name for item in root.iterdir() if item.is_file()))
        if actual != tuple(sorted(filenames)):
            raise CommandError(f"{case_id}: source pack file signature differs.")
        current_hash = source_pack_hash(root, filenames)
        allowed = set(case["quality_contract"]["source_pack_hashes"])
        if current_hash not in allowed:
            raise CommandError(f"{case_id}: source pack hash differs from frozen AP0 evidence.")
