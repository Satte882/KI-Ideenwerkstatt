"""External bridge: import all product/runtime modules from the verified v19 checkout.

Run with the variant venv Python. No files are copied into the historical checkout.
Only the new experiment modules/commands fall back to the variant package path.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess  # nosec B404 -- fixed git argv
import sys
from pathlib import Path

CONTROL_COMMIT = "b37e25b6508a6e5769785c72c2fc35ac1177fae2"
HARNESS_MODULES = {
    "ki_radar.accelerator.issue118_execution",
    "ki_radar.accelerator.issue118_experiment",
    "ki_radar.accelerator.issue118_fixtures",
    "ki_radar.accelerator.management.commands.run_issue118_control",
}


def verify(root, commit):
    executable = shutil.which("git")
    if not executable:
        raise SystemExit("Git required")
    for args, expected in (
        (["status", "--porcelain", "--untracked-files=all"], ""),
        (["rev-parse", "HEAD"], commit),
    ):
        actual = subprocess.run(  # noqa: S603 # nosec B603 -- shell=False, git only
            [executable, *args],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if actual != expected:
            raise SystemExit("Wrong/dirty runtime checkout; control bridge refused")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--inspect-runtime", action="store_true")
    parser.add_argument("--confirm-real-provider", action="store_true")
    options = parser.parse_args()
    plan = json.loads(Path(options.plan).read_text(encoding="utf-8"))
    root = Path(plan["control_root"]).resolve()
    harness = Path(__file__).resolve().parents[1]
    if plan["control_commit"] != CONTROL_COMMIT or Path(plan["variant_root"]).resolve() != harness:
        raise SystemExit("Wrong historical commit/harness checkout")
    verify(root, CONTROL_COMMIT)
    verify(harness, plan["variant_commit"])
    sys.path.insert(0, str(root))
    os.chdir(root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    os.environ["GIT_COMMIT"] = CONTROL_COMMIT
    import django

    django.setup()
    import ki_radar.accelerator
    import ki_radar.accelerator.management.commands

    ki_radar.accelerator.__path__.append(str(harness / "ki_radar/accelerator"))
    ki_radar.accelerator.management.commands.__path__.append(
        str(harness / "ki_radar/accelerator/management/commands")
    )
    from ki_radar.accelerator.issue118_experiment import read_plan
    from ki_radar.accelerator.management.commands.run_issue118_control import Command

    read_plan(options.plan)

    # These runtime modules must have loaded from the historical package first.
    for name, module in list(sys.modules.items()):
        if name.startswith("ki_radar.") and getattr(module, "__file__", None):
            relative = Path(module.__file__).resolve()
            if not relative.is_relative_to(root) and name not in HARNESS_MODULES:
                raise SystemExit(f"Mixed runtime import refused: {name}")
    if options.inspect_runtime:
        from ki_radar.accelerator import investigation_loop, investigation_runtime

        print(
            json.dumps(
                {
                    "tested_commit": CONTROL_COMMIT,
                    "loop_version": investigation_runtime.LOOP_VERSION,
                    "runtime_module": investigation_runtime.__file__,
                    "loop_module": investigation_loop.__file__,
                    "real_provider_runs": 0,
                }
            )
        )
        return
    args = [
        "issue118_control.py",
        "run_issue118_control",
        "--plan",
        options.plan,
        "--case",
        options.case,
        "--repeat",
        str(options.repeat),
    ]
    if options.check_only:
        args.append("--check-only")
    if options.confirm_real_provider:
        args.append("--confirm-real-provider")
    Command().run_from_argv(args)


if __name__ == "__main__":
    main()
