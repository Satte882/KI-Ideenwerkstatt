from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import UUID

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from ki_radar.architecture.models import ValueStream

ISSUE_NUMBER = 106
TARGET_NAME = "[Real-DEMO] Beschaffungsbedarf bis Bestellung"
REAL_DEMO_PREFIX = "[Real-DEMO]"


class Command(BaseCommand):
    help = "Inspect or apply the explicit, audited data correction for Issue #106."

    def add_arguments(self, parser):
        parser.add_argument(
            "--inspect",
            action="store_true",
            help="Read the target and all Real-DEMO value streams without changing data.",
        )
        parser.add_argument(
            "--plan",
            type=Path,
            help="Absolute container path to the private JSON correction plan.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply the plan. Without this flag, execution is a dry run.",
        )
        parser.add_argument(
            "--audit-path",
            type=Path,
            help="Absolute container path for the private Markdown audit record.",
        )

    def handle(self, *args, **options):
        inspect = options["inspect"]
        plan_path = options["plan"]
        apply = options["apply"]
        audit_path = options["audit_path"]

        if inspect:
            if plan_path or apply or audit_path:
                raise CommandError(
                    "--inspect cannot be combined with --plan, --apply or --audit-path."
                )
            self._inspect()
            return

        if plan_path is None:
            raise CommandError("Use --inspect or provide --plan.")
        if audit_path is not None and not apply:
            raise CommandError("--audit-path is only valid together with --apply.")
        if apply and audit_path is None:
            raise CommandError("--apply requires --audit-path.")

        plan = self._validate_plan(self._read_plan(self._absolute_path(plan_path, "Plan")))
        resolved_audit = (
            self._absolute_path(audit_path, "Audit") if audit_path is not None else None
        )
        self._execute(plan, apply=apply, audit_path=resolved_audit)

    def _inspect(self) -> None:
        matches = list(ValueStream.objects.filter(name=TARGET_NAME).order_by("id"))
        if not matches:
            raise CommandError(f'No value stream named "{TARGET_NAME}" exists.')
        if len(matches) > 1:
            ids = ", ".join(str(item.pk) for item in matches)
            raise CommandError(f"Target name is not unique. Matching IDs: {ids}")

        payload = {
            "issue": ISSUE_NUMBER,
            "mode": "inspection",
            "target": self._serialize(matches[0]),
            "real_demo_value_streams": self._inventory(),
            "next_step": (
                "Review every listed Real-DEMO stream and create a plan with exact values. "
                "No text is inferred or split automatically."
            ),
        }
        self.stdout.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))

    def _execute(
        self,
        plan: dict[str, Any],
        *,
        apply: bool,
        audit_path: Path | None,
    ) -> None:
        target_plan = plan["target"]
        expected_updated_at = target_plan["expected_updated_at_parsed"]
        final_audit: dict[str, Any] | None = None

        with transaction.atomic():
            rows = list(
                ValueStream.objects.select_for_update()
                .filter(name__startswith=REAL_DEMO_PREFIX)
                .order_by("name", "id")
            )
            self._validate_inventory(rows, plan)
            target = self._find_target(rows, target_plan["id"])
            self._validate_current_values(target, target_plan, expected_updated_at)

            before = self._serialize(target)
            planned_after = {
                **before,
                "scope_in": target_plan["new_scope_in"],
                "scope_out": target_plan["new_scope_out"],
            }
            if not apply:
                self.stdout.write(
                    json.dumps(
                        self._public_summary(plan, before, planned_after, "validated_no_change"),
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True,
                    )
                )
                return

            if audit_path is None:
                raise CommandError("Internal error: audit path missing in apply mode.")
            if audit_path.exists():
                raise CommandError(
                    f"Audit path already exists and will not be overwritten: {audit_path}"
                )

            prepared = self._audit_payload(
                plan,
                status="PREPARED",
                before=before,
                after=planned_after,
                inventory=[self._serialize(item) for item in rows],
                changed_rows=0,
            )
            self._write_new_audit(audit_path, prepared)

            changed_rows = ValueStream.objects.filter(
                pk=target.pk,
                name=TARGET_NAME,
                scope_in=target_plan["expected_scope_in"],
                scope_out=target_plan["expected_scope_out"],
                updated_at=expected_updated_at,
            ).update(
                scope_in=target_plan["new_scope_in"],
                scope_out=target_plan["new_scope_out"],
                updated_at=timezone.now(),
            )
            if changed_rows != 1:
                raise CommandError(
                    f"Expected exactly one changed row, but the database reported {changed_rows}."
                )

            target.refresh_from_db()
            if target.scope_in != target_plan["new_scope_in"]:
                raise CommandError("Post-update verification failed for scope_in.")
            if target.scope_out != target_plan["new_scope_out"]:
                raise CommandError("Post-update verification failed for scope_out.")

            final_audit = self._audit_payload(
                plan,
                status="APPLIED",
                before=before,
                after=self._serialize(target),
                inventory=self._inventory(),
                changed_rows=changed_rows,
            )

        if audit_path is None or final_audit is None:
            raise CommandError("Internal error: applied correction has no audit payload.")
        self._replace_audit(audit_path, final_audit)
        audit_hash = hashlib.sha256(audit_path.read_bytes()).hexdigest()
        result = self._public_summary(
            plan,
            final_audit["target"]["before"],
            final_audit["target"]["after"],
            "applied",
        )
        result.update(
            {
                "changed_rows": 1,
                "audit_path": str(audit_path),
                "audit_sha256": audit_hash,
            }
        )
        self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))

    def _validate_inventory(self, rows: list[ValueStream], plan: dict[str, Any]) -> None:
        current_ids = {str(item.pk) for item in rows}
        reviewed_ids = set(plan["real_demo_review"]["reviewed_ids"])
        if current_ids == reviewed_ids:
            return
        unreviewed = sorted(current_ids - reviewed_ids)
        missing = sorted(reviewed_ids - current_ids)
        raise CommandError(
            "Real-DEMO inventory changed or was not fully reviewed. "
            f"Unreviewed IDs: {unreviewed}; missing IDs: {missing}."
        )

    @staticmethod
    def _find_target(rows: list[ValueStream], target_id: str) -> ValueStream:
        matches = [item for item in rows if str(item.pk) == target_id and item.name == TARGET_NAME]
        if len(matches) != 1:
            raise CommandError("The exact target UUID and name do not match one current record.")
        return matches[0]

    @staticmethod
    def _validate_current_values(target, target_plan, expected_updated_at) -> None:
        mismatches = []
        if target.scope_in != target_plan["expected_scope_in"]:
            mismatches.append("scope_in")
        if target.scope_out != target_plan["expected_scope_out"]:
            mismatches.append("scope_out")
        if target.updated_at != expected_updated_at:
            mismatches.append("updated_at")
        if mismatches:
            raise CommandError(
                "Optimistic lock failed for: "
                + ", ".join(mismatches)
                + ". Run --inspect again before changing data."
            )

    def _validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        if plan.get("issue") != ISSUE_NUMBER:
            raise CommandError(f"Plan field 'issue' must be {ISSUE_NUMBER}.")
        for field in (
            "environment",
            "operator",
            "backup_reference",
            "repository_check_reference",
        ):
            self._required_text(plan, field)

        target = plan.get("target")
        if not isinstance(target, dict):
            raise CommandError("Plan field 'target' must be an object.")
        if target.get("name") != TARGET_NAME:
            raise CommandError(f"Plan target name must be exactly: {TARGET_NAME}")
        target_id = self._uuid(self._required_text(target, "id"), "target.id")

        expected_text = self._required_text(target, "expected_updated_at")
        expected_updated_at = parse_datetime(expected_text)
        if expected_updated_at is None:
            raise CommandError("target.expected_updated_at must be an ISO-8601 datetime.")
        if timezone.is_naive(expected_updated_at):
            expected_updated_at = timezone.make_aware(expected_updated_at)

        for field in (
            "expected_scope_in",
            "expected_scope_out",
            "new_scope_in",
            "new_scope_out",
        ):
            if not isinstance(target.get(field), str):
                raise CommandError(f"target.{field} must be a string.")
        if not target["new_scope_in"].strip() or not target["new_scope_out"].strip():
            raise CommandError("new_scope_in and new_scope_out must not be empty.")
        if (
            target["expected_scope_in"] == target["new_scope_in"]
            and target["expected_scope_out"] == target["new_scope_out"]
        ):
            raise CommandError("The plan does not change scope_in or scope_out.")

        review = plan.get("real_demo_review")
        if not isinstance(review, dict):
            raise CommandError("Plan field 'real_demo_review' must be an object.")
        raw_ids = review.get("reviewed_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            raise CommandError("real_demo_review.reviewed_ids must be a non-empty list.")
        reviewed_ids = [self._uuid(str(value), "reviewed_ids") for value in raw_ids]
        if len(reviewed_ids) != len(set(reviewed_ids)):
            raise CommandError("real_demo_review.reviewed_ids contains duplicates.")
        if target_id not in reviewed_ids:
            raise CommandError("The target UUID must be included in reviewed_ids.")
        self._required_text(review, "conclusion")

        return {
            **plan,
            "target": {
                **target,
                "id": target_id,
                "expected_updated_at_parsed": expected_updated_at,
            },
            "real_demo_review": {**review, "reviewed_ids": reviewed_ids},
        }

    @staticmethod
    def _absolute_path(path: Path | None, label: str) -> Path:
        if path is None or not path.is_absolute():
            raise CommandError(f"{label} path must be absolute inside the container.")
        return path.resolve()

    @staticmethod
    def _read_plan(path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise CommandError(f"Plan file does not exist: {path}")
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CommandError(f"Cannot read valid JSON plan {path}: {exc}") from exc
        if not isinstance(value, dict):
            raise CommandError("The correction plan must be a JSON object.")
        return value

    def _inventory(self) -> list[dict[str, Any]]:
        rows = ValueStream.objects.filter(name__startswith=REAL_DEMO_PREFIX).order_by("name", "id")
        return [self._serialize(item) for item in rows]

    @staticmethod
    def _serialize(stream: ValueStream) -> dict[str, Any]:
        return {
            "id": str(stream.pk),
            "name": stream.name,
            "scope_in": stream.scope_in,
            "scope_out": stream.scope_out,
            "updated_at": stream.updated_at.isoformat(),
        }

    @staticmethod
    def _required_text(mapping: dict[str, Any], field: str) -> str:
        value = mapping.get(field)
        if not isinstance(value, str) or not value.strip():
            raise CommandError(f"Plan field '{field}' must be a non-empty string.")
        return value

    @staticmethod
    def _uuid(value: str, field: str) -> str:
        try:
            return str(UUID(value))
        except ValueError as exc:
            raise CommandError(f"{field} must contain a valid UUID.") from exc

    def _public_summary(self, plan, before, after, status) -> dict[str, Any]:
        return {
            "issue": ISSUE_NUMBER,
            "status": status,
            "environment": plan["environment"],
            "target_id": plan["target"]["id"],
            "target_name": TARGET_NAME,
            "before": self._hashed_scope(before),
            "after": self._hashed_scope(after),
            "reviewed_real_demo_ids": plan["real_demo_review"]["reviewed_ids"],
            "review_conclusion": plan["real_demo_review"]["conclusion"],
        }

    @staticmethod
    def _hashed_scope(value: dict[str, Any]) -> dict[str, str]:
        return {
            "scope_in_sha256": hashlib.sha256(value["scope_in"].encode()).hexdigest(),
            "scope_out_sha256": hashlib.sha256(value["scope_out"].encode()).hexdigest(),
            "updated_at": value["updated_at"],
        }

    @staticmethod
    def _audit_payload(plan, *, status, before, after, inventory, changed_rows):
        return {
            "issue": ISSUE_NUMBER,
            "status": status,
            "environment": plan["environment"],
            "operator": plan["operator"],
            "backup_reference": plan["backup_reference"],
            "repository_check_reference": plan["repository_check_reference"],
            "recorded_at": timezone.now().isoformat(),
            "target": {"before": before, "after": after},
            "changed_rows": changed_rows,
            "real_demo_review": {
                **plan["real_demo_review"],
                "inventory_after_operation": inventory,
            },
        }

    def _write_new_audit(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with path.open("x", encoding="utf-8", newline="\n") as handle:
                handle.write(self._audit_markdown(payload))
        except OSError as exc:
            raise CommandError(f"Cannot create private audit file {path}: {exc}") from exc

    def _replace_audit(self, path: Path, payload: dict[str, Any]) -> None:
        temporary_path = None
        try:
            with NamedTemporaryFile(
                "w",
                encoding="utf-8",
                newline="\n",
                dir=path.parent,
                delete=False,
            ) as handle:
                handle.write(self._audit_markdown(payload))
                temporary_path = Path(handle.name)
            os.replace(temporary_path, path)
        except OSError as exc:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise CommandError(
                "Database correction committed, but the final audit could not be written. "
                f"The PREPARED audit remains at {path}: {exc}"
            ) from exc

    @staticmethod
    def _audit_markdown(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        return (
            "# Datenkorrektur Issue #106\n\n"
            "Diese Datei enthält fachliche Daten und muss privat aufbewahrt werden. "
            "Sie darf nicht committed werden.\n\n"
            f"```json\n{serialized}\n```\n"
        )
