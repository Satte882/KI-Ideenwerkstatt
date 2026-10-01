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
            "--overwrite-review-template",
            action="store_true",
            help="Explicitly replace an existing review template when no assessments are supplied.",
        )
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
            if review_path.exists() and not options["overwrite_review_template"]:
                self.stdout.write(
                    self.style.WARNING(
                        f"Existing review file preserved: {review_path}. "
                        "Use --overwrite-review-template to replace it deliberately."
                    )
                )
            else:
                review_path.write_text(
                    json.dumps(review_template(records), ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

        if options["require_complete"]:
            if not summary["population_complete"]:
                details = []
                if not summary["complete_slots"]:
                    details.append(
                        "slot set incomplete/duplicated: "
                        + ", ".join(
                            [*summary["missing_slots"], *summary["duplicate_slots"]]
                        )
                    )
                if not summary["all_runs_at_system_boundary"]:
                    details.append("one or more runs are still RUNNING/no stored system boundary")
                if not summary["all_tested_commits_present_and_valid"]:
                    details.append("one or more tested_commit values are missing/invalid")
                elif not summary["single_tested_commit"]:
                    details.append("baseline uses more than one tested commit")
                raise CommandError(
                    "Baseline population is incomplete: " + "; ".join(details)
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
                        "population_complete": summary["population_complete"],
                        "quality_complete": summary["quality_complete"],
                        "total_actual_cost_usd": summary["total_actual_cost_usd"],
                        "total_budget_accounted_cost_usd": (
                            summary["total_budget_accounted_cost_usd"]
                        ),
                        "uncertain_provider_attempts": (summary["uncertain_provider_attempts"]),
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
