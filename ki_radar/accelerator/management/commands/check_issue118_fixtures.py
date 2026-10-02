from __future__ import annotations

import hashlib
import json
import os
import subprocess  # nosec B404 -- fixed local Python argv
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_radar.accelerator.issue118_experiment import (
    AFFECTED_CASES,
    FIXTURE_TEST,
    verify_checkout,
)
from ki_radar.accelerator.issue118_fixtures import SOURCE, fixture_evidence


class Command(BaseCommand):
    help = "Run only the two provider-blocked #118 C1 replay fixtures and save JUnit proof."

    def add_arguments(self, parser):
        parser.add_argument("--expected-variant-commit", required=True)
        parser.add_argument("--output", required=True)

    def handle(self, *args, **options):
        root = Path(settings.BASE_DIR)
        commit = verify_checkout(root, options["expected_variant_commit"])
        env = dict(os.environ)
        env.update(
            OPENROUTER_API_KEY="",
            OPENROUTER_API_KEY_FILE="",
            OPENAI_API_KEY="",
            DJANGO_SETTINGS_MODULE="config.settings.test",
        )
        with tempfile.TemporaryDirectory(prefix="issue118-fixtures-") as folder:
            junit = Path(folder) / "junit.xml"
            result = subprocess.run(  # noqa: S603 # nosec B603 -- fixed test selector, shell=False
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--no-cov",
                    "-q",
                    FIXTURE_TEST,
                    "--junitxml",
                    str(junit),
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            if result.returncode:
                raise CommandError("#118 state fixtures failed:\n" + result.stdout + result.stderr)
            payload = {
                "tested_commit": commit,
                "test_selector": FIXTURE_TEST,
                "test_source_sha256": hashlib.sha256((root / SOURCE).read_bytes()).hexdigest(),
                "passed_cases": list(AFFECTED_CASES),
                "junit_xml": junit.read_text(encoding="utf-8"),
            }
        path = Path(options["output"]).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise CommandError("Fixture output already exists; choose a new path")
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        fixture_evidence(path, root, commit)
        self.stdout.write("ISSUE118_STATE_FIXTURES_GREEN " + str(path))
