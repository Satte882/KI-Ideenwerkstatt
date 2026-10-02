"""Verify the fixed, provider-blocked C1 state replay test evidence."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET  # nosec B405 -- DTD/entity input is rejected below
from pathlib import Path

from django.core.management.base import CommandError

from .issue118_experiment import AFFECTED_CASES, FIXTURE_TEST

IDS = ("AP4-02-R4-state-pattern", "AP4-04-R5-state-pattern")
SOURCE = "tests/test_issue_118_planner_source_coverage.py"


def fixture_evidence(path, root, commit):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload["tested_commit"] != commit or payload["test_selector"] != FIXTURE_TEST:
            raise ValueError("Fixture commit/test selection mismatch")
        expected_hash = hashlib.sha256((Path(root) / SOURCE).read_bytes()).hexdigest()
        if payload["test_source_sha256"] != expected_hash:
            raise ValueError("Fixture source changed")
        xml = payload["junit_xml"]
        if "<!DOCTYPE" in xml.upper() or "<!ENTITY" in xml.upper():
            raise ValueError("Unsafe JUnit XML")
        document = ET.fromstring(xml)  # noqa: S314 # nosec B314 -- DTD/entity rejected
        cases = list(document.iter("testcase"))
        if len(cases) != 2 or any(list(case) for case in cases):
            raise ValueError("Exactly two passed fixture tests, no skips/failures, required")
        if {case.get("name") for case in cases} != {
            f"test_historical_early_read_survives_six_later_steps[{name}]" for name in IDS
        }:
            raise ValueError("Wrong replay test IDs")
        if payload["passed_cases"] != list(AFFECTED_CASES):
            raise ValueError("Wrong affected fixtures")
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError) as exc:
        raise CommandError(f"Invalid deterministic fixture evidence: {exc}") from exc
    return payload
