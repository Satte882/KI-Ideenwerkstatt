from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from ki_radar.accelerator.issue106_baseline import (
    EXPERIMENT_ID,
    aggregate_baseline,
    baseline_runs,
    build_baseline_record,
    review_template,
    validate_reviews,
)

DEFAULT_OUTPUT = "artifacts/issue106/ap1/baseline.json"
DEFAULT_REVIEW = "artifacts/issue106/ap1/review.json"


class Command(BaseCommand):
    help = "Export raw #106/AP1 baseline evidence, review template and A/A summary."

    def add_arguments(self, parser):
        parser.add_argument("--output", default=DEFAULT_OUTPUT)
        parser.add_argument("--review-template", default=DEFAULT_REVIEW)
        parser.add_argument("--assessments")
        parser.add_argument(
            "--require-complete",
            action="store_true",
            help="Fail unless all 25 slots exist and authoritative quality review is complete.",
        )

    def handle(self, *args, **options):
        runs = list(baseline_runs().order_by("created_at"))
        records = [build_baseline_record(run) for run in runs]
        records.sort(
            key=lambda item: (
                str(item.get("case_id") or ""),
                int(item.get("repetition") or 0),
            )
        )

        reviews = None
        assessment_path = options.get("assessments")
        if assessment_path:
            path = self._resolve(assessment_path)
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                reviews = validate_reviews(payload, records)
            except (OSError, ValueError, json.JSONDecodeError) as exc:
                raise CommandError(f"Invalid assessment file: {exc}") from exc

        summary = aggregate_baseline(records, reviews=reviews)
        output_payload = {
            "schema_version": "issue106-ap1-baseline-v1",
            "experiment_id": EXPERIMENT_ID,
            "generated_at": timezone.now().isoformat(),
            "summary": summary,
            "runs": records,
        }
        if reviews is not None:
            output_payload["reviews"] = [reviews[str(item["run_id"])] for item in records]

        output = self._resolve(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(output_payload, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )

        review_path = self._resolve(options["review_template"])
        if reviews is None:
            review_path.parent.mkdir(parents=True, exist_ok=True)
            review_path.write_text(
                json.dumps(review_template(records), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        if options["require_complete"]:
            if not summary["complete_slots"]:
                raise CommandError(
                    "Baseline export is incomplete: " + ", ".join(summary["missing_slots"])
                )
            if not summary["quality_complete"]:
                raise CommandError(
                    "Baseline quality review is incomplete; PASS/FAIL/UNASSESSED must be "
                    "authoritatively resolved for every run."
                )
            if summary["observed_hard_fail_count"]:
                raise CommandError(
                    "Baseline contains one or more human-confirmed quality hard fails."
                )

        self.stdout.write(
            self.style.SUCCESS(
                "ISSUE106_AP1_EXPORTED "
                + json.dumps(
                    {
                        "output": str(output),
                        "review": str(review_path),
                        "observed_runs": summary["observed_run_count"],
                        "complete_slots": summary["complete_slots"],
                        "quality_complete": summary["quality_complete"],
                        "total_cost_usd": summary["total_cost_usd"],
                    },
                    separators=(",", ":"),
                )
            )
        )

    def _resolve(self, value: str) -> Path:
        path = Path(value)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / path
        return path.resolve()
