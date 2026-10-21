"""Explicitly authorized real Discovery run using unchanged app views and transport.

Each case has its own SQLite database and source directory under work/issue133-live.
No domain materialization, scope confirmation, approval or lifecycle action is performed.
Existing results are reused; one factual clarification revision is allowed per case.
"""

import argparse
import json
import os
import re
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list("ABCD"), required=True)
    parser.add_argument("--confirm-real-provider", action="store_true", required=True)
    parser.add_argument("--correction-file", type=Path)
    args = parser.parse_args()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    os.environ["USE_SQLITE_FOR_TESTS"] = "1"
    os.environ["SENTRY_DSN"] = ""
    os.environ["SENTRY_DSN_FILE"] = ""

    from django.conf import settings

    private = ROOT / "work" / "issue133-live" / args.case
    private.mkdir(parents=True, exist_ok=True)
    settings.DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": private / "case.sqlite3"}
    }
    settings.INVESTIGATION_SOURCE_UPLOAD_ROOT = private / "sources"
    settings.ANONYMIZATION_LEDGER_PATH = private / "anonymization.jsonl"
    settings.ALLOWED_HOSTS = ["testserver"]
    if not settings.OPENROUTER_API_KEY:
        raise SystemExit("Configured provider key is missing; no run started")

    import django

    django.setup()
    from django.contrib.auth.models import Group
    from django.contrib.messages import get_messages
    from django.core.management import call_command
    from django.test import Client
    from django.test.utils import setup_test_environment
    from django.urls import reverse

    from ki_radar.accelerator import architect_service
    from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
    from ki_radar.accounts.models import BusinessUnit, User
    from ki_radar.architecture.models import ValueStream
    from ki_radar.core.openrouter import OpenRouterUnavailable
    from ki_radar.use_cases.idea_models import IdeaCandidate

    setup_test_environment()
    call_command("migrate", interactive=False, verbosity=0)
    unit, _ = BusinessUnit.objects.get_or_create(name=f"[SYNTHETISCH #133 {args.case}] Touristik")
    owner, _ = User.objects.get_or_create(
        username="issue133_test_owner", defaults={"business_unit": unit}
    )
    group, _ = Group.objects.get_or_create(name="Business Owner")
    owner.groups.add(group)
    client = Client()
    client.force_login(owner)
    evidence = ROOT / "artifacts" / "issue133" / "live"
    ledger_path = evidence / "provider-ledger.json"
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.exists()
        else {
            "budget_usd": "5",
            "authorization": "User: du hast die freigabe",
            "pricing_reservation": (
                "10x catalog pricing; UTF-8 request bytes as input token ceiling"
            ),
            "calls": [],
        }
    )
    metadata_path = ROOT / "work" / "issue133-model-metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    configured_model = settings.ACCELERATOR_DISCOVERY_MODEL or settings.OPENROUTER_MODEL
    if metadata["id"] != configured_model:
        raise SystemExit("Pricing snapshot does not match configured model")
    write_json(evidence / "model-metadata.json", metadata)
    original = architect_service.request_openrouter

    def observed_provider(**kwargs):
        encoded = json.dumps(kwargs, ensure_ascii=False, default=str).encode("utf-8")
        reserve = Decimal(10) * (
            Decimal(len(encoded)) * Decimal(metadata["pricing"]["prompt"])
            + Decimal(kwargs["max_tokens"]) * Decimal(metadata["pricing"]["completion"])
        )
        accounted = sum(Decimal(c["accounted_usd"]) for c in ledger["calls"])
        if accounted + reserve > Decimal(ledger["budget_usd"]) or len(ledger["calls"]) >= 48:
            raise OpenRouterUnavailable("Issue133 test budget exhausted", code="test_budget")
        entry = {
            "case": args.case,
            "sequence": len(ledger["calls"]) + 1,
            "schema": kwargs.get("response_format", {}).get("json_schema", {}).get("name"),
            "reserved_usd": str(reserve),
            "accounted_usd": str(reserve),
            "status": "started",
            "request": kwargs,
        }
        entry["call_id"] = f"{args.case}:{entry['sequence']}:{entry['schema']}"
        ledger["calls"].append(entry)
        write_json(ledger_path, ledger)
        started = time.monotonic()
        print(f"CASE {args.case}: provider call {entry['sequence']} {entry['schema']}", flush=True)
        try:
            result = original(**kwargs)
        except OpenRouterUnavailable as exc:
            entry.update(status="failed", error_code=exc.code, message=str(exc))
            raise
        else:
            entry.update(
                status="completed",
                model=result.model,
                usage=result.usage,
                content=result.content,
                finish_reason=result.finish_reason,
            )
            if result.usage.get("cost") is not None:
                entry["accounted_usd"] = str(result.usage["cost"])
            return result
        finally:
            entry["seconds"] = round(time.monotonic() - started, 3)
            write_json(ledger_path, ledger)

    architect_service.request_openrouter = observed_provider
    scenario_doc = (ROOT / "docs/planning/ISSUE_133_RSD_SCENARIOS.md").read_text(encoding="utf-8")
    section = scenario_doc.split(f"## {args.case} \u2013 ", 1)[1].split("### Später", 1)[0]
    initial = " ".join(re.findall(r"^> (.*)$", section, re.MULTILINE))
    idea = IdeaCandidate.objects.first()
    if idea is None:
        response = client.post(
            reverse("use_cases:idea_create"),
            {
                "title": f"[SYNTHETISCH #133 {args.case}] Touristik-Problem",
                "description": initial,
                "business_unit": unit.pk,
                "source_note": "Synthetische Testperson; keine realen RSD-Unternehmensdaten",
            },
        )
        if response.status_code != 302:
            raise RuntimeError("Inbox rejected test input")
        idea = IdeaCandidate.objects.get()
    if idea.description != initial:
        raise SystemExit("Original input differs from existing case; no run started")
    session = CaptureSession.objects.first()
    http = None
    operator_action = "reused existing result, no provider call"
    if session is None:
        response = client.post(
            reverse("accelerator:autonomous_discovery_start"),
            {
                "idea_candidate": str(idea.pk),
                "business_unit": unit.pk,
                "problem_statement": initial,
                "business_context": "",
            },
        )
        http = {
            "status": response.status_code,
            "messages": [str(m) for m in get_messages(response.wsgi_request)],
        }
        session = CaptureSession.objects.get()
        operator_action = "enter initial statement and explicitly start Discovery"
    elif args.correction_file:
        correction = args.correction_file.read_text(encoding="utf-8")
        if session.revision >= 1:
            raise SystemExit("One clarification revision already used; no repeat allowed")
        response = client.post(
            reverse("accelerator:autonomous_discovery_review", args=[session.pk]),
            {
                "action": "correct",
                "revision": session.revision,
                "correction": correction,
            },
        )
        http = {
            "status": response.status_code,
            "messages": [str(m) for m in get_messages(response.wsgi_request)],
        }
        session.refresh_from_db()
        operator_action = "answer model clarification with documented synthetic card information"
    analyses = list(
        CaptureAnalysis.objects.order_by("created_at").values(
            "id",
            "status",
            "error_code",
            "source_revision",
            "source_hash",
            "prompt_version",
            "extraction_schema_version",
            "duration_ms",
            "model_name",
            "cost",
            "prompt_tokens",
            "completion_tokens",
            "result_payload",
            "verification_payload",
            "open_questions",
            "contradictions",
        )
    )
    output = {
        "case": args.case,
        "synthetic": True,
        "initial": initial,
        "source": "scenario document; no K1-K3 cards in initial request",
        "operator_action": operator_action,
        "http": http,
        "session_id": session.pk,
        "session_revision": session.revision,
        "session_answers": session.answers,
        "analyses": analyses,
        "materialized_value_stream_count": ValueStream.objects.count(),
        "scope_confirmation_submitted": False,
        "human_time_measured": False,
    }
    write_json(evidence / f"{args.case}.json", output)
    print(
        json.dumps(
            {
                "case": args.case,
                "analyses": [
                    {"status": a["status"], "error_code": a["error_code"], "cost": a["cost"]}
                    for a in analyses
                ],
                "http": http,
            },
            ensure_ascii=False,
            default=str,
        ),
        flush=True,
    )


if __name__ == "__main__":
    lock_path = ROOT / "work" / "issue133-live" / "active.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_handle = lock_path.open("x", encoding="utf-8")
    except FileExistsError:
        raise SystemExit("Another run or unresolved interrupted run holds the test lock") from None
    try:
        with lock_handle:
            lock_handle.write(str(os.getpid()))
        main()
    finally:
        lock_path.unlink()
