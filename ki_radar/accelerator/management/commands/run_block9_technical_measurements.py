# fmt: off
from __future__ import annotations

import json
import secrets
from pathlib import Path
from time import perf_counter

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.test import override_settings
from django.utils import timezone

from ki_radar.accelerator.benchmark_measurement import (
    append_raw_record,
    build_raw_record,
)
from ki_radar.core.scenario_blueprint import load_blueprint_json
from ki_radar.core.scenario_blueprint_run import run_blueprint
from ki_radar.delivery.mapping_refresh import BLOCK8_MAPPING_MANIFEST_KEY
from ki_radar.delivery.services import create_delivery_package
from ki_radar.use_cases.models import ApprovalDecision, DecisionAssessment, UseCase

BLUEPRINT_PATH = (
    Path(__file__).resolve().parents[3]
    / "core"
    / "scenario_blueprints"
    / "real_demo.v1.json"
)
REAL_DEMO_USE_CASE_KEY = "real-demo-assisted-offer-comparison"
INTERACTIVE_RUN_IDS = (
    "manual-A-1",
    "accelerator-A-1",
    "accelerator-A-2",
    "manual-A-2",
    "manual-A-3",
    "accelerator-A-3",
)


def _elapsed_seconds(started):
    return round(perf_counter() - started, 6)


def _empty_quality():
    return {}


def _mapping_counts(package):
    fields = {}
    for review in package.section_reviews.all():
        mapping = review.source_manifest.get(BLOCK8_MAPPING_MANIFEST_KEY, {})
        fields.update(mapping.get("fields", {}))
    statuses = [str(item.get("status", "")) for item in fields.values()]
    return {
        "deterministic_fields": statuses.count("mapped"),
        "llm_fields": 0,
        "open_gaps": statuses.count("gap"),
        "conflicts": statuses.count("conflict") + statuses.count("stale"),
        "manually_corrected_fields": 0,
    }


def _prepare_final_approval(use_case):
    actor = use_case.coordinator or use_case.technical_owner or use_case.business_owner
    if actor is None:
        raise CommandError("Real-DEMO Use Case has no actor for the Delivery benchmark")
    use_case.decision_status = UseCase.DecisionStatus.APPROVED
    use_case.save(update_fields=["decision_status", "updated_at"])
    assessment = DecisionAssessment.objects.create(
        use_case=use_case,
        version=1,
        assessed_by=actor,
        business_value=UseCase.Level.HIGH,
        strategic_fit=UseCase.Level.HIGH,
        technical_feasibility=UseCase.Level.HIGH,
        data_readiness=UseCase.Level.MEDIUM,
        risk_complexity=UseCase.Level.MEDIUM,
        evidence_quality=DecisionAssessment.EvidenceQuality.REPRESENTATIVE,
        evidence_recency=DecisionAssessment.ConfidenceFactor.SOLID,
        evidence_coverage=DecisionAssessment.ConfidenceFactor.SOLID,
        independent_review=DecisionAssessment.ConfidenceFactor.SOLID,
        assumptions_resolved=DecisionAssessment.ConfidenceFactor.SOLID,
        rationale="Block-9 technical benchmark approval snapshot.",
        governance_precheck_completed=True,
        recommendation=UseCase.DecisionStatus.APPROVED,
    )
    decision = ApprovalDecision.objects.create(
        use_case=use_case,
        assessment=assessment,
        decision_status=UseCase.DecisionStatus.APPROVED,
        rationale="Block-9 technical benchmark only.",
        decided_by=actor,
        governance_confirmed=True,
        finalized_at=timezone.now(),
    )
    return actor, decision


def _write_interactive_manifest(path):
    payload = {
        "benchmark_version": "block9-v1",
        "status": "operator_measurement_required",
        "runs": [
            {
                "run_id": run_id,
                "status": "not_executed",
                "reason": (
                    "This execution environment has no human operator/browser session; "
                    "automated timings are not valid substitutes for the frozen interactive run."
                ),
            }
            for run_id in INTERACTIVE_RUN_IDS
        ],
        "quality_case_B": {
            "status": "not_executed",
            "reason": (
                "Requires the same controlled human review path as the interactive benchmark."
            ),
        },
    }
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


class Command(BaseCommand):
    help = "Run only the technically executable Block-9 benchmark controls."

    def add_arguments(self, parser):
        parser.add_argument("--output", required=True)
        parser.add_argument("--interactive-manifest", required=True)

    def handle(self, *args, **options):
        output = Path(options["output"])
        if output.exists():
            raise CommandError(f"Raw output already exists: {output}")

        with override_settings(DEBUG=True):
            call_command(
                "seed_demo_data",
                demo_user_password=secrets.token_urlsafe(18),
                verbosity=0,
            )

        payload = load_blueprint_json(BLUEPRINT_PATH)
        started = perf_counter()
        blueprint_result = run_blueprint(payload, apply=True)
        blueprint_elapsed = _elapsed_seconds(started)
        if blueprint_result.summary.get("result") != "CREATE":
            raise CommandError("Blueprint control did not start from an empty target graph")

        blueprint_record = build_raw_record(
            run_id="blueprint-A-control-1",
            path="blueprint",
            case_key="A",
            status="completed",
            times={
                "system_wait_seconds": blueprint_elapsed,
                "end_to_end_seconds": blueprint_elapsed,
            },
            quality=_empty_quality(),
            notes="Technical control only; not an interactive productivity measurement.",
        )
        blueprint_record["technical_control"] = {
            "result": blueprint_result.summary["result"],
            "created_counts": blueprint_result.summary["created_counts"],
            "checksum": blueprint_result.summary["checksum"],
        }
        append_raw_record(output, blueprint_record)

        use_case = UseCase.objects.get(demo_key=REAL_DEMO_USE_CASE_KEY)
        actor, _decision = _prepare_final_approval(use_case)
        for run_number in range(1, 4):
            with transaction.atomic():
                started = perf_counter()
                package = create_delivery_package(
                    use_case=use_case,
                    actor=actor,
                    use_evidence_mapper=True,
                )
                elapsed = _elapsed_seconds(started)
                delivery = _mapping_counts(package)
                record = build_raw_record(
                    run_id=f"delivery-A-{run_number}",
                    path="delivery",
                    case_key="A",
                    status="completed",
                    times={
                        "system_wait_seconds": elapsed,
                        "end_to_end_seconds": elapsed,
                    },
                    quality=_empty_quality(),
                    delivery=delivery,
                    notes=(
                        "Secondary Block-8 mapper control; transaction rolled back after capture."
                    ),
                )
                append_raw_record(output, record)
                transaction.set_rollback(True)

        _write_interactive_manifest(options["interactive_manifest"])
        self.stdout.write(self.style.SUCCESS(f"Technical raw data written to {output}"))
# fmt: on
