"""Execute the production JS guard against a minimal form/event contract."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_busy_guard_preserves_clicked_action_and_prevents_duplicate_submission():
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js required for submit-guard behavioral regression")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(  # noqa: S603
        [node, "tests/submit_guard_runtime.cjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
