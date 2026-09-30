from __future__ import annotations

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.ap4_evidence import (
    AP4EvidenceError,
    append_record,
    load_records,
    render_summary_markdown,
    summarize_records,
    validate_frozen_manifest,
)


class Command(BaseCommand):
    help = "Validate the frozen AP4 evidence contract and summarize append-only run evidence."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            default="tests/fixtures/ap4_case_manifest_v1.json",
            help="Path relative to repository root or absolute path.",
        )
        parser.add_argument(
            "--records",
            default="artifacts/ap4/evidence.jsonl",
            help="Optional JSONL evidence path relative to repository root or absolute path.",
        )
        parser.add_argument("--json", action="store_true", dest="as_json")
        parser.add_argument(
            "--append-record",
            help="Append one JSON record file after contract validation.",
        )
        parser.add_argument(
            "--show-contract",
            action="store_true",
            help="Print frozen case IDs, slots and source hashes.",
        )

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        manifest_path = Path(options["manifest"])
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        records_path = Path(options["records"])
        if not records_path.is_absolute():
            records_path = root / records_path

        try:
            validation = validate_frozen_manifest(manifest_path, repo_root=root)
            if options["append_record"]:
                record_path = Path(options["append_record"])
                if not record_path.is_absolute():
                    record_path = root / record_path
                raw = json.loads(record_path.read_text(encoding="utf-8"))
                if not isinstance(raw, dict):
                    raise AP4EvidenceError("append record file must contain one JSON object")
                append_record(records_path, raw, validation=validation)

            records = load_records(records_path, validation=validation)
            summary = summarize_records(records, validation=validation)
        except (AP4EvidenceError, OSError, json.JSONDecodeError) as exc:
            raise CommandError(str(exc)) from exc

        if options["show_contract"]:
            contract = {
                "contract_version": validation.manifest.contract_version,
                "plan_commit": validation.manifest.plan_commit,
                "versions": dict(validation.manifest.versions),
                "cases": [
                    {
                        "case_id": case.case_id,
                        "run_slot": case.run_slot,
                        "category": case.category,
                        "source_pack": case.source_pack,
                        "source_pack_hash": validation.source_hashes[case.case_id],
                    }
                    for case in validation.manifest.cases
                ],
            }
            self.stdout.write(json.dumps(contract, ensure_ascii=False, indent=2, sort_keys=True))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"AP4 contract valid: {len(validation.manifest.cases)} cases, "
                f"{len(records)} evidence records."
            )
        )
        if options["as_json"]:
            self.stdout.write(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            self.stdout.write(render_summary_markdown(summary))
