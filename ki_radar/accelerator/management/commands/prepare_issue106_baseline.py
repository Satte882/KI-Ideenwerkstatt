from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ki_radar.accelerator.investigation_models import InvestigationSourceFolder
from ki_radar.accelerator.investigation_tools import SnapshotRequest, create_source_snapshot
from ki_radar.accelerator.issue106_baseline import (
    baseline_slots,
    golden_case_specs,
    slot_process_name,
)
from ki_radar.accounts.models import BusinessUnit
from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

STREAM_NAME = "Issue #106 AP1 Baseline"
STAGE_NAME = "Investigation Baseline"
FALLBACK_BUSINESS_UNIT = "Issue #106 Evidence"


class Command(BaseCommand):
    help = (
        "Prepare the 25 isolated Issue #106 AP1 baseline slots. "
        "This command never starts provider calls."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--inspect-only",
            action="store_true",
            help="Report the current AP1 slot state without mutating data.",
        )

    def handle(self, *args, **options):
        owner_name = (
            os.getenv("ISSUE106_OWNER_USERNAME", "").strip()
            or os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
            or "Satinder"
        )
        user_model = get_user_model()
        try:
            owner = user_model.objects.get(username=owner_name, is_active=True)
        except user_model.DoesNotExist as exc:
            raise CommandError(
                f"Issue #106 baseline owner {owner_name!r} not found or inactive."
            ) from exc

        specs = golden_case_specs()
        existing = ProcessAnalysis.objects.filter(name__startswith="Issue #106 AP1 AP4-").count()
        self.stdout.write(
            "ISSUE106_AP1_PREFLIGHT "
            f"owner={owner.username} expected_slots={len(baseline_slots())} "
            f"existing_processes={existing}"
        )
        if options["inspect_only"]:
            return

        with transaction.atomic():
            _stream, stage = self._ensure_stream(owner)
            prepared: list[dict[str, object]] = []
            for case_id, repetition in baseline_slots():
                spec = specs[case_id]
                process = self._ensure_process(
                    owner=owner,
                    stage=stage,
                    case_id=case_id,
                    repetition=repetition,
                    problem_statement=str(spec["problem_statement"]),
                )
                root = (Path(settings.BASE_DIR) / str(spec["source_pack"])).resolve()
                filenames = tuple(str(item) for item in spec["files"])
                self._assert_fixture(root, filenames)
                folder, _created = InvestigationSourceFolder.objects.get_or_create(
                    process_analysis=process,
                    root_path=str(root),
                    defaults={
                        "name": f"#106 AP1 {case_id} R{repetition}",
                        "registered_by": owner,
                    },
                )
                if not folder.is_active:
                    raise CommandError(f"{case_id} R{repetition}: source folder is inactive.")
                question = str(spec["problem_statement"])
                snapshot = self._matching_snapshot(
                    folder=folder,
                    process=process,
                    root=root,
                    filenames=filenames,
                    decision_question=question,
                )
                if snapshot is None:
                    if process.investigation_runs.exists():
                        raise CommandError(
                            f"{case_id} R{repetition}: frozen source snapshot changed after "
                            "a baseline run already exists."
                        )
                    result = create_source_snapshot(
                        actor=owner,
                        request=SnapshotRequest(
                            process_analysis_id=process.pk,
                            folder_id=folder.pk,
                            decision_question=question,
                            run_limits={},
                        ),
                    )
                    snapshot = folder.snapshots.get(pk=result.snapshot_id)
                prepared.append(
                    {
                        "case_id": case_id,
                        "repetition": repetition,
                        "process_analysis_id": str(process.pk),
                        "snapshot_id": str(snapshot.pk),
                        "manifest_hash": snapshot.manifest_hash,
                        "existing_runs": process.investigation_runs.count(),
                    }
                )

        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE106_AP1_PREPARED "
                + json.dumps({"slots": prepared}, ensure_ascii=False, separators=(",", ":"))
            )
        )

    def _ensure_stream(self, owner):
        business_unit = owner.business_unit
        if business_unit is None or not business_unit.is_active:
            business_unit, _created = BusinessUnit.objects.update_or_create(
                name=FALLBACK_BUSINESS_UNIT,
                defaults={
                    "description": "Technische Organisationseinheit für #106/AP1-Baselines.",
                    "is_active": True,
                    "catalog_scope": BusinessUnit.CatalogScope.DEMO_TEST,
                },
            )
            if not business_unit.is_active:
                raise CommandError(
                    f"Fallback business unit {FALLBACK_BUSINESS_UNIT!r} is inactive."
                )

        streams = list(ValueStream.objects.select_for_update().filter(name=STREAM_NAME))
        if len(streams) > 1:
            raise CommandError("Multiple Issue #106 AP1 ValueStreams exist.")
        if streams:
            stream = streams[0]
            if (
                stream.owner_id != owner.pk
                or stream.business_unit_id != business_unit.pk
                or stream.status != ValueStream.Status.ACTIVE
            ):
                raise CommandError("Existing Issue #106 AP1 ValueStream conflicts with setup.")
        else:
            stream = ValueStream.objects.create(
                name=STREAM_NAME,
                business_unit=business_unit,
                owner=owner,
                created_by=owner,
                trigger="Ein eingefrorener Golden-Set-Fall benötigt eine Baseline-Messung.",
                outcome="Eine reproduzierbare Investigation-Baseline liegt vor.",
                scope_in="Nur die eingefrorenen #106/AP1-Investigation-Fälle.",
                scope_out="Produktive Materialisierung, Lösungsauswahl, Pilot und Go-live.",
                constraints="Keine Performance-Optimierung in AP1.",
                status=ValueStream.Status.ACTIVE,
            )

        stages = list(stream.stages.select_for_update().filter(sequence=1))
        if len(stages) > 1:
            raise CommandError("Multiple sequence-1 stages exist on Issue #106 AP1 ValueStream.")
        if stages:
            stage = stages[0]
            if stage.name != STAGE_NAME:
                raise CommandError("Existing Issue #106 AP1 stage conflicts with setup.")
        else:
            stage = ValueStreamStage.objects.create(
                value_stream=stream,
                sequence=1,
                name=STAGE_NAME,
                description="Eingefrorene Evidenz untersuchen; keine Lösung vorgeben.",
                actors="Benchmark-Operator",
                systems="KI-Ideenwerkstatt Investigation",
                documents="Golden-Set-Source-Packs",
                pain_points="Laufzeit, Streuung, Repairs, Retries und Kosten",
                baseline_metrics="Werden in #111 gemessen.",
            )
        return stream, stage

    def _ensure_process(
        self,
        *,
        owner,
        stage,
        case_id: str,
        repetition: int,
        problem_statement: str,
    ):
        name = slot_process_name(case_id, repetition)
        expected = {
            "scope_start": "Ein eingefrorener Fall liegt zur Investigation vor.",
            "scope_end": "Ein fachlich korrekter Investigation-Endzustand ist erreicht.",
            "trigger": "Der Baseline-Slot wird explizit gestartet.",
            "outcome": "READY, WAITING_HUMAN oder fachlich korrektes FAILED.",
            "current_flow": (
                "Evidenz untersuchen und Decision Brief bis zur fachlichen Grenze erzeugen."
            ),
            "roles": "Benchmark-Operator; fachliche Entscheidungen bleiben Human Authority.",
            "systems": "KI-Ideenwerkstatt Investigation",
            "data_objects": "Eingefrorener Source-Snapshot und persistierter Investigation-State.",
            "business_rules": "Keine Performance-Optimierung; aktueller #106-Contract ist bindend.",
            "handoffs": "",
            "bottlenecks": "Werden durch die Baseline nicht vorweggenommen.",
            "diagnostic_observations": problem_statement,
            "cause_hypotheses": "",
            "confirmed_causes": "",
            "constraints": "Nur die eingefrorenen Quellen und der aktuelle Execution Contract.",
            "exceptions": "",
            "baseline_metrics": "Noch nicht gemessen.",
        }
        matches = list(ProcessAnalysis.objects.select_for_update().filter(stage=stage, name=name))
        if len(matches) > 1:
            raise CommandError(f"{name}: multiple ProcessAnalysis records exist.")
        if matches:
            process = matches[0]
            if process.status != ProcessAnalysis.Status.DRAFT:
                raise CommandError(f"{name}: existing ProcessAnalysis is not DRAFT.")
            if process.analyzed_by_id != owner.pk:
                raise CommandError(f"{name}: existing ProcessAnalysis has a different owner.")
            for field, value in expected.items():
                if getattr(process, field) != value:
                    raise CommandError(
                        f"{name}: existing ProcessAnalysis differs in {field}; refusing overwrite."
                    )
            if process.solution_options.exists() or process.validations.exists():
                raise CommandError(f"{name}: benchmark ProcessAnalysis is no longer neutral.")
            return process
        return ProcessAnalysis.objects.create(
            stage=stage,
            name=name,
            status=ProcessAnalysis.Status.DRAFT,
            analyzed_by=owner,
            **expected,
        )

    def _assert_fixture(self, root: Path, filenames: tuple[str, ...]) -> None:
        if not root.is_dir():
            raise CommandError(f"Frozen Issue #106 source pack missing: {root}")
        actual = tuple(sorted(item.name for item in root.iterdir() if item.is_file()))
        if actual != tuple(sorted(filenames)):
            raise CommandError(
                f"Frozen source pack signature mismatch for {root.name}: "
                f"{actual!r} != {tuple(sorted(filenames))!r}"
            )

    def _matching_snapshot(
        self,
        *,
        folder,
        process,
        root: Path,
        filenames: tuple[str, ...],
        decision_question: str,
    ):
        expected_hashes = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in filenames
        }
        for snapshot in folder.snapshots.filter(process_version=process.version).order_by(
            "-revision"
        ):
            if snapshot.decision_question != decision_question or snapshot.run_limits != {}:
                continue
            sources = {item.filename: item for item in snapshot.sources.all()}
            if tuple(sorted(sources)) != tuple(sorted(filenames)):
                continue
            if all(sources[name].content_sha256 == expected_hashes[name] for name in filenames):
                return snapshot
        return None
