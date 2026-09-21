from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from ki_radar.core.scenario_blueprint import (
    BlueprintCanonicalizationError,
    load_blueprint_json,
)
from ki_radar.core.scenario_blueprint_apply import (
    BlueprintApplyError,
    BlueprintConflictError,
)
from ki_radar.core.scenario_blueprint_run import run_blueprint
from ki_radar.core.scenario_blueprint_validation import BlueprintValidationError

BLUEPRINT_DIRECTORY = Path(__file__).resolve().parents[2] / "scenario_blueprints"
KNOWN_SCENARIOS = {
    "real-demo": BLUEPRINT_DIRECTORY / "real_demo.v1.json",
}


class Command(BaseCommand):
    help = (
        "Validate and inspect a deterministic KI-Radar scenario blueprint. "
        "Execution is a dry run unless --apply is supplied explicitly."
    )

    def add_arguments(self, parser):
        source = parser.add_mutually_exclusive_group()
        source.add_argument(
            "--scenario",
            choices=sorted(KNOWN_SCENARIOS),
            help="Known repository scenario. Defaults to real-demo.",
        )
        source.add_argument(
            "--path",
            type=Path,
            help="Path to a JSON blueprint that follows the repository contract.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Apply the fully validated graph atomically. Without this flag no graph is changed."
            ),
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Write the complete result as machine-readable JSON.",
        )

    def handle(self, *args, **options):
        path = self._resolve_path(options["scenario"], options["path"])
        try:
            payload = load_blueprint_json(path)
            execution = run_blueprint(payload, apply=options["apply"])
        except BlueprintCanonicalizationError as exc:
            raise CommandError(str(exc), returncode=2) from exc
        except BlueprintValidationError as exc:
            raise CommandError(str(exc), returncode=2) from exc
        except BlueprintConflictError as exc:
            self._write_conflict(exc, json_output=options["json_output"])
            raise CommandError(
                "Blueprint-Apply wegen graphweitem Konflikt abgebrochen.",
                returncode=3,
            ) from exc
        except BlueprintApplyError as exc:
            raise CommandError(str(exc), returncode=4) from exc

        result = execution.as_dict()
        if options["json_output"]:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        else:
            self._write_human_result(result)

        summary = result["summary"]
        if not options["apply"] and summary["graph_status"] == "CONFLICT":
            raise CommandError(
                "Dry Run abgeschlossen: Der vollständige Graph ist nicht anwendbar.",
                returncode=3,
            )

    def _resolve_path(self, scenario: str | None, path: Path | None) -> Path:
        if path is None:
            return KNOWN_SCENARIOS[scenario or "real-demo"]
        resolved = path.expanduser().resolve()
        if resolved.suffix.lower() != ".json":
            raise CommandError("Blueprint-Dateien müssen die Endung .json besitzen.", returncode=2)
        if not resolved.is_file():
            message = f"Blueprint-Datei wurde nicht gefunden: {resolved}"
            raise CommandError(message, returncode=2)
        return resolved

    def _write_conflict(
        self,
        exc: BlueprintConflictError,
        *,
        json_output: bool,
    ) -> None:
        result = exc.diff.as_dict()
        if json_output:
            self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            return
        self.stdout.write(self.style.ERROR("Graphstatus: CONFLICT"))
        self._write_objects(result["objects"])

    def _write_human_result(self, result: dict[str, Any]) -> None:
        summary = result["summary"]
        self.stdout.write(f"Modus: {result['mode']}")
        self.stdout.write(f"Job-ID: {result['job_run_id']}")
        self.stdout.write(f"Szenario: {summary['scenario_key']}")
        self.stdout.write(f"Schema-Version: {summary['schema_version']}")
        self.stdout.write(f"Prüfsumme: {summary['checksum']}")
        status = summary.get("result") or summary.get("graph_status")
        self.stdout.write(f"Ergebnis: {status}")
        if result["mode"] == "dry_run":
            self.stdout.write("Daten geändert: nein")
            for key, value in sorted(summary["object_counts"].items()):
                self.stdout.write(f"{key}: {value}")
            self._write_objects(summary["objects"])
        else:
            for key, value in sorted(summary["created_counts"].items()):
                self.stdout.write(f"{key}: {value}")
            for key, value in sorted(summary["object_ids"].items()):
                self.stdout.write(f"{key}_id: {value}")

    def _write_objects(self, objects: list[dict[str, Any]]) -> None:
        for item in objects:
            self.stdout.write(f"- {item['object_type']}:{item['key']} — {item['status']}")
            for difference in item["differences"]:
                self.stdout.write(
                    "  "
                    f"{difference['field']}: "
                    f"aktuell={difference['current']!r}; "
                    f"erwartet={difference['expected']!r}"
                )
