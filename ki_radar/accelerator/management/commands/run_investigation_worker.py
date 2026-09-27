from __future__ import annotations

import logging
import signal
import subprocess  # nosec B404
import sys
import time
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections
from django.utils import timezone

from ki_radar.accelerator.investigation_execution import (
    HEARTBEAT_SECONDS,
    MAX_EXECUTIONS,
    claim_execution,
    fail_execution,
    reap_executions,
    renew_execution,
)
from ki_radar.accelerator.investigation_loop import run_until_boundary
from ki_radar.accelerator.investigation_models import InvestigationRun

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run durable product investigations independently of web requests."

    def add_arguments(self, parser):
        parser.add_argument("--run-id")
        parser.add_argument("--generation", type=int)
        parser.add_argument("--worker-id")
        parser.add_argument("--once", action="store_true")

    def handle(self, *args, **options):
        if options["run_id"]:
            if not options["generation"] or not options["worker_id"]:
                raise CommandError("Child execution requires generation and worker identity.")
            self.execute_run(options)
            return
        self.supervise(once=options["once"])

    def execute_run(self, options):
        run_id, generation = options["run_id"], options["generation"]
        worker_id = uuid.UUID(options["worker_id"])
        run = InvestigationRun.objects.select_related("execution_requested_by").get(pk=run_id)
        if (
            run.status != "running"
            or run.evidence_campaign_id is not None
            or run.execution_mode != "adaptive"
            or run.executor_generation != generation
            or run.execution_generation != generation
            or run.execution_worker_id != worker_id
            or run.execution_lease_until is None
            or run.execution_lease_until <= timezone.now()
        ):
            return
        try:
            actor = run.execution_requested_by
            if actor is None or not actor.is_active:
                raise CommandError("Execution actor is unavailable.")
            run_until_boundary(actor=actor, run_id=run.pk, executor_token=run.executor_token)
        except Exception:
            logger.exception("Product investigation execution failed: %s", run_id)
            fail_execution(run_id, generation, worker_id, "execution_error")
        finally:
            close_old_connections()

    def supervise(self, *, once=False):
        worker_id = uuid.uuid4()
        children = {}
        stopping = False

        def stop(_signum, _frame):
            nonlocal stopping
            stopping = True

        for name in ("SIGINT", "SIGTERM"):
            signal.signal(getattr(signal, name), stop)
        last_heartbeat = 0.0
        try:
            while True:
                close_old_connections()
                reap_executions()
                for run_id, (process, generation) in list(children.items()):
                    run = InvestigationRun.objects.get(pk=run_id)
                    ended = process.poll() is not None
                    superseded = run.status != "running" or run.executor_generation != generation
                    expired = (timezone.now() - run.started_at).total_seconds() > (
                        run.budget_limits["max_runtime_seconds"] + HEARTBEAT_SECONDS
                    )
                    if ended or superseded or expired:
                        if not ended:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=5)
                        if not superseded:
                            fail_execution(
                                run_id,
                                generation,
                                worker_id,
                                "runtime_exhausted" if expired else "execution_interrupted",
                            )
                        del children[run_id]
                if time.monotonic() - last_heartbeat >= HEARTBEAT_SECONDS:
                    for run_id, (process, generation) in list(children.items()):
                        if not renew_execution(run_id, generation, worker_id):
                            process.terminate()
                    last_heartbeat = time.monotonic()
                if not stopping:
                    while len(children) < MAX_EXECUTIONS:
                        claimed = claim_execution(worker_id)
                        if claimed is None:
                            break
                        run_id, generation = claimed
                        try:
                            # Fixed command and UUID/integer arguments; never uses a shell.
                            process = subprocess.Popen(  # noqa: S603 # nosec B603
                                [
                                    sys.executable,
                                    str(settings.BASE_DIR / "manage.py"),
                                    "run_investigation_worker",
                                    "--run-id",
                                    str(run_id),
                                    "--generation",
                                    str(generation),
                                    "--worker-id",
                                    str(worker_id),
                                ],
                                cwd=settings.BASE_DIR,
                                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                            )
                        except OSError:
                            fail_execution(run_id, generation, worker_id, "execution_spawn_failed")
                            logger.exception("Could not launch investigation %s", run_id)
                        else:
                            children[run_id] = process, generation
                if once or (stopping and not children):
                    break
                time.sleep(1)
        finally:
            # A forced supervisor exit fences all still-owned generations.
            for run_id, (process, generation) in children.items():
                try:
                    fail_execution(run_id, generation, worker_id)
                except Exception:
                    logger.exception("Could not fence investigation %s during shutdown", run_id)
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
