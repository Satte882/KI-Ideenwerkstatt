"""Authorized, bounded methodological acceptance. Never collected as a pytest test.

Use --case A --phase replay|fresh|sources|solutions --confirm-real-provider.
Historical provider text is reused only as explicitly marked replay input.
All new model responses pass through the unchanged application transport.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.request
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "issue133" / "methodology"
PRIVATE = ROOT / "work" / "issue133-methodology"
FIXTURES = ROOT / "tests" / "fixtures" / "issue133_methodology"


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", choices=list("ABCD"), required=True)
    parser.add_argument(
        "--phase", choices=["replay", "fresh", "sources", "revalidate", "solutions"], required=True
    )
    parser.add_argument("--confirm-real-provider", action="store_true", required=True)
    parser.add_argument("--resume-technical", action="store_true")
    args = parser.parse_args()
    case, phase = args.case, args.phase
    version = "v7" if phase in {"replay", "revalidate", "solutions"} else "v4"
    target = OUT / f"{case}-{phase}-{version}.json"
    prior = json.loads(target.read_text(encoding="utf-8")) if target.exists() else None
    if prior and args.resume_technical:
        if prior.get("error", {}).get("code") not in {
            "provider_unavailable",
            "test_budget",
            "empty_response",
        }:
            raise SystemExit("Resume is limited to incomplete technical attempts")
        archive = target.with_suffix(".technical-attempt.json")
        if archive.exists():
            raise SystemExit("A technical retry has already been attempted")
        save(archive, prior)
    elif target.exists():
        print(f"Existing {case}/{phase} evidence reused; no model call")
        return
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))
    os.environ.update(
        DJANGO_SETTINGS_MODULE="config.settings.test",
        USE_SQLITE_FOR_TESTS="1",
        SENTRY_DSN="",
        SENTRY_DSN_FILE="",
    )
    from django.conf import settings

    private = PRIVATE / case
    private.mkdir(parents=True, exist_ok=True)
    settings.DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": private / "db.sqlite3"}
    }
    settings.INVESTIGATION_SOURCE_UPLOAD_ROOT = private / "sources"
    settings.ANONYMIZATION_LEDGER_PATH = private / "ledger.jsonl"
    settings.ALLOWED_HOSTS = ["testserver"]
    # Isolated acceptance campaign: retain quota enforcement, but permit the
    # authorized bounded matrix rather than the ordinary per-person day limit.
    # The shared 3 USD ledger remains the tighter campaign-wide hard boundary.
    settings.ACCELERATOR_LLM_MAX_CALLS_PER_USER_DAY = 80
    settings.ACCELERATOR_LLM_MAX_CALLS_GLOBAL_DAY = 100
    import django

    django.setup()
    from django.contrib.auth.models import Group
    from django.core.files.uploadedfile import SimpleUploadedFile
    from django.core.management import call_command
    from django.test import Client
    from django.test.utils import setup_test_environment
    from django.urls import reverse

    from ki_radar.accelerator import architect_service, architect_views
    from ki_radar.accelerator.architect_contract import (
        build_discovery_verifier_schema,
        validate_verifier_payload,
    )
    from ki_radar.accelerator.investigation_ingestion import create_managed_discovery_source_folder
    from ki_radar.accelerator.investigation_models import InvestigationSourceSnapshot
    from ki_radar.accelerator.investigation_tools import (
        DiscoverySnapshotRequest,
        create_discovery_source_snapshot,
    )
    from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
    from ki_radar.accelerator.services import add_autonomous_discovery_correction
    from ki_radar.accounts.models import BusinessUnit, User
    from ki_radar.core.openrouter import OpenRouterResult, OpenRouterUnavailable, request_openrouter
    from ki_radar.use_cases.idea_models import IdeaCandidate

    setup_test_environment()
    call_command("migrate", interactive=False, verbosity=0)
    unit, _ = BusinessUnit.objects.get_or_create(name=f"[SYNTHETISCH #133] Methodik {case}")
    owner, _ = User.objects.get_or_create(
        username="methodology_owner", defaults={"business_unit": unit}
    )
    owner.groups.add(Group.objects.get_or_create(name="Business Owner")[0])
    ledger_path = OUT / "provider-ledger.json"
    ledger = (
        json.loads(ledger_path.read_text(encoding="utf-8"))
        if ledger_path.exists()
        else {
            "budget_usd": "3",
            "authorization": "User: targeted final validation up to 3 USD",
            "calls": [],
        }
    )
    metadata_path = OUT / "model-metadata.json"
    if not metadata_path.exists():
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
            catalog = json.load(response)["data"]
        names = {
            settings.OPENROUTER_MODEL,
            settings.ACCELERATOR_DISCOVERY_MODEL or settings.OPENROUTER_MODEL,
        }
        save(
            metadata_path,
            {
                m["id"]: {k: m.get(k) for k in ("id", "pricing", "supported_parameters")}
                for m in catalog
                if m["id"] in names
            },
        )
    bounds = json.loads((OUT / "endpoint-price-bounds.json").read_text(encoding="utf-8"))

    def reservation(request):
        model = request.get("model_override") or settings.OPENROUTER_MODEL
        pricing = bounds[model]["max_endpoint_pricing"]
        # UTF-8 bytes conservatively bound input tokens; include framing overhead.
        return Decimal(len(json.dumps(request, ensure_ascii=False).encode()) + 1024) * Decimal(
            pricing["prompt"]
        ) + Decimal(request["max_tokens"]) * Decimal(pricing["completion"])

    for call in ledger["calls"]:
        if call["status"] != "completed" and "prior_reservation_usd" not in call:
            call["prior_reservation_usd"] = call["accounted_usd"]
            call["accounted_usd"] = str(reservation(call["request"]))
            call["reservation_basis"] = (
                "Maximum published endpoint rates, input bytes + 1024, maximum output; "
                "charge remains unknown"
            )
    save(ledger_path, ledger)
    seed = None

    def observed(**kwargs):
        nonlocal seed
        schema = kwargs.get("response_format", {}).get("json_schema", {}).get("name", "")
        if seed is not None and schema == "autonomous_business_discovery_v1":
            content = seed["content"]
            save(
                OUT / f"{case}-{phase}-{version}-reused-generator.json",
                {
                    "origin": "unchanged saved real provider text; no new generation",
                    "historical_call_id": seed["call_id"],
                    "sha256": hashlib.sha256(content.encode()).hexdigest(),
                    "content": content,
                },
            )
            seed = None
            return OpenRouterResult(
                content=content,
                model="historical-provider-evidence",
                usage={},
                output_chars=len(content),
                finish_reason="stop",
            )
        reserve = reservation(kwargs)
        accounted = sum(Decimal(c["accounted_usd"]) for c in ledger["calls"])
        if accounted + reserve > Decimal(ledger["budget_usd"]):
            raise OpenRouterUnavailable("Methodology test budget exhausted", code="test_budget")
        entry = {
            "case": case,
            "phase": phase,
            "call_id": len(ledger["calls"]) + 1,
            "schema": schema,
            "status": "started",
            "accounted_usd": str(reserve),
            "request": kwargs,
        }
        ledger["calls"].append(entry)
        save(ledger_path, ledger)
        print(f"{case}/{phase} real call {entry['call_id']} {schema}", flush=True)
        try:
            result = request_openrouter(**kwargs)
        except OpenRouterUnavailable as exc:
            entry.update(status="failed", error_code=exc.code, message=str(exc))
            raise
        else:
            entry.update(
                status="completed",
                model=result.model,
                content=result.content,
                usage=result.usage,
                finish_reason=result.finish_reason,
            )
            if result.usage.get("cost") is not None:
                entry["accounted_usd"] = str(result.usage["cost"])
            return result
        finally:
            save(ledger_path, ledger)

    architect_service.request_openrouter = observed
    client = Client()
    client.force_login(owner)
    state_path = private / "sessions.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    identity = "replay" if phase == "replay" else "fresh"
    if phase in {"sources", "revalidate", "solutions"} and "fresh-recovery" in state:
        identity = "fresh-recovery"
    if phase == "fresh" and prior and args.resume_technical:
        # A failed later source attempt may already have advanced the original session.
        # Restart the exact natural input in a separate session; never remove sources.
        identity = "fresh-recovery"
    if identity not in state:
        if phase in {"sources", "revalidate", "solutions"}:
            raise SystemExit("Run the natural fresh initial input first")
        doc = (ROOT / "docs/planning/ISSUE_133_RSD_SCENARIOS.md").read_text(encoding="utf-8")
        section = doc.split(f"## {case} \u2013 ", 1)[1].split("### Später", 1)[0]
        initial = " ".join(re.findall(r"^> (.*)$", section, re.MULTILINE))
        title = f"[SYNTHETISCH #133 {case}/{identity}] Methodische Probe"
        client.post(
            reverse("use_cases:idea_create"),
            {
                "title": title,
                "description": initial,
                "business_unit": unit.pk,
                "source_note": "Synthetische Testperson; keine RSD-Unternehmensdaten",
            },
        )
        idea = IdeaCandidate.objects.get(title=title)
        session, snapshot, _process, error = architect_views._prepare_discovery_start(
            actor=owner,
            data={"problem_statement": initial, "business_context": "", "business_unit": unit},
            uploads=[],
            idea=idea,
        )
        if error:
            raise RuntimeError(error)
        state[identity] = {"session_id": str(session.pk), "snapshot_id": str(snapshot.pk)}
        save(state_path, state)
    session = CaptureSession.objects.get(pk=state[identity]["session_id"])
    snapshot = InvestigationSourceSnapshot.objects.get(pk=state[identity]["snapshot_id"])
    output = {
        "case": case,
        "phase": phase,
        "synthetic": True,
        "isolated_test_limits": {"user_day": 80, "global_day": 100, "campaign_usd": "3"},
        "criteria_sha256": hashlib.sha256((FIXTURES / "criteria.json").read_bytes()).hexdigest(),
    }
    if prior and args.resume_technical:
        output["technical_retry_of"] = target.with_suffix(".technical-attempt.json").name
    if phase == "fresh" and prior and case == "C":
        seed = next(
            c
            for c in ledger["calls"]
            if c["case"] == "C" and c["phase"] == "fresh" and c["status"] == "completed"
        )
    if phase == "revalidate":
        previous = session.analyses.order_by("-created_at").first()
        draft = previous.result_payload["draft"]
        seed = next(
            call
            for call in reversed(ledger["calls"])
            if call["case"] == case
            and call["status"] == "completed"
            and call.get("schema")
            in {"autonomous_business_discovery_v1", "autonomous_business_discovery_repair_v1"}
            and json.loads(call["content"]) == draft
        )
        output["revalidated_analysis_id"] = str(previous.pk)
        output["reused_real_call_id"] = seed["call_id"]
    output["implementation_sha256"] = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "ki_radar/accelerator/architect_service.py",
            "ki_radar/accelerator/architect_contract.py",
        )
    }
    if phase == "replay":
        historical = json.loads(
            (ROOT / "artifacts/issue133/live/provider-ledger.json").read_text(encoding="utf-8")
        )
        original = next(
            c
            for c in historical["calls"]
            if c["case"] == case and c["schema"] == "autonomous_business_discovery_v1"
        )
        draft = json.loads(original["content"])
        document, _refs, _text = architect_service._source_document(
            session=session, snapshot=snapshot
        )
        review = architect_service._provider_call(
            actor=owner,
            session=session,
            policy=architect_service.get_accelerator_llm_policy(),
            messages=architect_service._prompt_payload(
                architect_service.VERIFIER_SYSTEM_PROMPT, {"input": document, "draft": draft}
            ),
            schema_name="autonomous_business_discovery_verifier_v1",
            schema=build_discovery_verifier_schema(),
        )
        output["historical_draft_review"] = validate_verifier_payload(json.loads(review.content))
        seed = original
    if phase == "sources" and prior and args.resume_technical and identity == "fresh":
        output["preceding_model_questions"] = prior.get("preceding_model_questions", [])
        output["released_sources"] = prior.get("released_sources", [])
        output["source_release_reused"] = True
    elif phase == "sources":
        questions = list(session.analyses.order_by("-created_at").first().open_questions)
        output["preceding_model_questions"] = questions
        session = add_autonomous_discovery_correction(
            actor=owner,
            session_id=session.pk,
            expected_revision=session.revision,
            correction="Für die fachliche Klärung liegen nun die ausdrücklich synthetischen "
            "Fallunterlagen vor. Unbekannte Angaben bleiben unbekannt.",
        )
        files = sorted((FIXTURES / case).glob("*.md"))
        output["released_sources"] = [
            {"filename": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files
        ]
        folder = create_managed_discovery_source_folder(
            actor=owner,
            capture_session_id=session.pk,
            name="Synthetische Klärungsunterlagen",
            uploads=[
                SimpleUploadedFile(p.name, p.read_bytes(), content_type="text/markdown")
                for p in files
            ],
        )
        bound = create_discovery_source_snapshot(
            actor=owner,
            request=DiscoverySnapshotRequest(capture_session_id=session.pk, folder_id=folder.pk),
        )
        snapshot = InvestigationSourceSnapshot.objects.get(pk=bound.snapshot_id)
        state[identity]["snapshot_id"] = str(snapshot.pk)
        save(state_path, state)
    if phase == "solutions":
        from ki_radar.accelerator import (
            solution_critic_service,
            solution_generation_service,
            solution_repair_service,
        )
        from ki_radar.accelerator.models import SolutionQualityRun
        from ki_radar.architecture.models import ProcessAnalysis, ValueStream, ValueStreamStage

        for module in (
            solution_critic_service,
            solution_generation_service,
            solution_repair_service,
        ):
            module.request_openrouter = observed
        analysis = session.analyses.order_by("-created_at").first()
        draft = analysis.result_payload["draft"]
        stream = ValueStream.objects.create(
            name=f"[SYNTHETISCH {case}] Explorationsentwurf",
            business_unit=unit,
            owner=owner,
            created_by=owner,
            status="draft",
            trigger=draft["value_stream"]["trigger"],
            outcome=draft["value_stream"]["outcome"],
            scope_in=draft["value_stream"]["scope_in"],
        )
        stage = ValueStreamStage.objects.create(
            value_stream=stream, sequence=1, name="Exploration ohne Scopefreigabe"
        )
        data = draft["process_analysis"]
        fields = {
            name: data.get(name) or "Unbekannt; nicht bestätigt."
            for name in (
                "name",
                "scope_start",
                "scope_end",
                "trigger",
                "outcome",
                "current_flow",
                "roles",
                "systems",
                "data_objects",
                "bottlenecks",
                "baseline_metrics",
            )
        }
        process = ProcessAnalysis.objects.create(
            stage=stage,
            analyzed_by=owner,
            status="draft",
            confirmed_causes="",
            diagnostic_observations=data.get("observations", ""),
            cause_hypotheses=data.get("cause_hypotheses", ""),
            business_rules=data.get("business_rules", ""),
            exceptions=data.get("exceptions", ""),
            **fields,
        )
        output["test_setup"] = (
            "Canonical DRAFT ProcessAnalysis populated from generated source-stage draft; "
            "explicit test setup, not autonomous materialization or human scope/cause approval."
        )
        output["source_analysis_id"] = str(analysis.pk)
        try:
            run = solution_generation_service.generate_solution_preview(
                actor=owner, process_analysis_id=process.pk
            )
            critic = solution_critic_service.run_initial_solution_critic(
                solution_generation_run_id=run.pk
            )
            if critic.status == "success" and any(
                finding.get("repairable") for finding in critic.result_payload.get("findings", [])
            ):
                repaired = solution_repair_service.run_targeted_solution_repair(
                    solution_generation_run_id=run.pk, actor=owner
                )
                if repaired.status == "success":
                    solution_critic_service.run_final_solution_critic(
                        solution_generation_run_id=run.pk
                    )
            run.refresh_from_db()
            output["solution_preview"] = run.preview_payload
            output["quality_runs"] = list(
                SolutionQualityRun.objects.filter(solution_generation_run=run).values(
                    "status", "step_type", "error_code", "result_payload"
                )
            )
        except Exception as exc:
            output["error"] = {
                "type": type(exc).__name__,
                "code": getattr(exc, "code", ""),
                "message": str(exc),
            }
        output["scope_confirmed"] = False
        output["cause_confirmed"] = False
        save(target, output)
        print(
            f"{case}/solutions saved: "
            + str(
                output.get("error")
                or [
                    {
                        "step": item["step_type"],
                        "status": item["status"],
                        "error": item["error_code"],
                    }
                    for item in output.get("quality_runs", [])
                ]
            ),
            flush=True,
        )
        return
    try:
        analysis = architect_service.execute_autonomous_business_discovery(
            actor=owner, session_id=session.pk, snapshot_id=snapshot.pk
        )
        output["status"] = analysis.status
    except architect_service.DiscoveryAnalysisError as exc:
        output["error"] = {"code": exc.code, "message": str(exc)}
    output["session_answers"] = session.answers
    output["analyses"] = list(
        CaptureAnalysis.objects.filter(session=session)
        .order_by("created_at")
        .values(
            "id",
            "status",
            "error_code",
            "source_revision",
            "source_hash",
            "prompt_version",
            "result_payload",
            "verification_payload",
            "open_questions",
            "cost",
        )
    )
    output["scope_confirmed"] = False
    save(target, output)
    print(f"{case}/{phase}: {output.get('status', output.get('error'))}", flush=True)


if __name__ == "__main__":
    PRIVATE.mkdir(parents=True, exist_ok=True)
    lock = PRIVATE / "active.lock"
    try:
        handle = lock.open("x", encoding="utf-8")
    except FileExistsError:
        raise SystemExit("Acceptance run already active; no concurrent provider calls") from None
    try:
        with handle:
            handle.write(str(os.getpid()))
        main()
    finally:
        lock.unlink()
