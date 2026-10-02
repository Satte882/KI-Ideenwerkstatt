from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ki_radar.accelerator.issue118_execution import build_record, experiment_runs
from ki_radar.accelerator.issue118_experiment import (
    EXPERIMENT_ID,
    aggregate_experiment,
    experiment_review_template,
    experiment_reviews,
    historical_reference,
    read_plan,
    slot_key,
    slots,
)
from ki_radar.accelerator.issue118_fixtures import fixture_evidence


class Command(BaseCommand):
    help = "Export all 25 frozen #118 slots, raw evidence, authoritative review and AP0 gates."

    def add_arguments(self, parser):
        parser.add_argument("--plan", required=True)
        parser.add_argument("--output", default="artifacts/issue106/exp118/experiment.json")
        parser.add_argument("--review-template", default="artifacts/issue106/exp118/review.json")
        parser.add_argument("--assessments")
        parser.add_argument("--require-complete", action="store_true")

    def handle(self, *args, **options):
        plan = read_plan(options["plan"])
        if Path(settings.BASE_DIR).resolve() != Path(plan["variant_root"]).resolve():
            raise CommandError("Export must use the frozen variant checkout")
        records = [build_record(run) for run in experiment_runs().order_by("started_at")]
        try:
            reference = historical_reference()
            if reference["hashes"] != plan["ap1_hashes"]:
                raise ValueError("AP1 reference hash mismatch")
            # Validate embedded fixture proof again, rather than trust caller booleans.
            import tempfile

            with tempfile.TemporaryDirectory(prefix="issue118-proof-") as folder:
                proof = Path(folder) / "fixture.json"
                proof.write_text(json.dumps(plan["fixture_evidence"]), encoding="utf-8")
                fixture_evidence(proof, plan["variant_root"], plan["variant_commit"])
            reviews = None
            if options["assessments"]:
                payload = json.loads(Path(options["assessments"]).read_text(encoding="utf-8"))
                reviews = experiment_reviews(payload, records, plan)
            summary = aggregate_experiment(records, plan, reference, reviews)
        except (ValueError, OSError, KeyError) as exc:
            raise CommandError(f"Invalid experiment evidence: {exc}") from exc
        by_slot = {
            slot_key({key: r[key] for key in ("arm", "case_id", "repetition")}): r for r in records
        }
        payload = {
            "schema_version": EXPERIMENT_ID,
            "experiment_id": EXPERIMENT_ID,
            "plan_hash": plan["plan_hash"],
            "generated_at": timezone.now().isoformat(),
            "slots": [
                {
                    **slot,
                    "run_id": by_slot.get(slot_key(slot), {}).get("run_id"),
                    "observed": slot_key(slot) in by_slot,
                }
                for slot in slots()
            ],
            "runs": records,
            "summary": summary,
            "ap1_reference_hashes": reference["hashes"],
        }
        if reviews is not None:
            payload["reviews"] = list(reviews.values())
        output = self._resolve(options["output"])
        review_path = self._resolve(options["review_template"])
        protected = {(Path(settings.BASE_DIR) / name).resolve() for name in reference["hashes"]}
        if output in protected or review_path in protected or output == review_path:
            raise CommandError("Cannot overwrite AP1 artifacts or mix output/review paths")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if reviews is None and not review_path.exists():
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(
                json.dumps(experiment_review_template(records, plan), indent=2) + "\n",
                encoding="utf-8",
            )
        if options["require_complete"] and (
            not summary["population_complete"]
            or not summary["quality_complete"]
            or summary["observed_hard_fail_count"]
        ):
            raise CommandError(
                "Incomplete population/review or human-confirmed hard fail; adoption blocked"
            )
        self.stdout.write("ISSUE118_EXPORTED " + str(output))

    def _resolve(self, value):
        path = Path(value)
        return (path if path.is_absolute() else Path(settings.BASE_DIR) / path).resolve()
