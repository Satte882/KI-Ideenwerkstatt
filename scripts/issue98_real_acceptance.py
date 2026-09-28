# ruff: noqa: E402, E501, S105, S310
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("USE_SQLITE_FOR_TESTS", "1")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")

import django

django.setup()

from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from playwright.sync_api import sync_playwright

from ki_radar.accelerator.architect_service import execute_autonomous_business_discovery
from ki_radar.accelerator.investigation_ingestion import create_managed_discovery_source_folder
from ki_radar.accelerator.investigation_tools import (
    DiscoverySnapshotRequest,
    create_discovery_source_snapshot,
)
from ki_radar.accelerator.models import CaptureAnalysis, CaptureSession
from ki_radar.accelerator.services import (
    add_autonomous_discovery_correction,
    create_autonomous_capture_session,
)
from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER
from ki_radar.architecture.discovery_materialization import (
    materialize_discovery_and_start_investigation,
)

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path("artifacts/issue98-real-acceptance")
USERNAME = "issue98-real-owner"
PASSWORD = "Issue98RealAcceptance!123"


def _upload(name: str, content: str, content_type: str = "text/plain"):
    return SimpleUploadedFile(name, content.encode(), content_type=content_type)


def _prepare_owner() -> User:
    CaptureSession.objects.filter(owner__username=USERNAME).delete()
    User.objects.filter(username=USERNAME).delete()
    unit, _ = BusinessUnit.objects.get_or_create(name="Issue-98-Real-Acceptance")
    group, _ = Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)
    user = User.objects.create_user(
        username=USERNAME,
        password=PASSWORD,
        business_unit=unit,
    )
    user.groups.add(group)
    return user


def _case(
    *,
    owner: User,
    source_root: Path,
    key: str,
    problem: str,
    context: str,
    sources: list[SimpleUploadedFile],
):
    session = create_autonomous_capture_session(
        actor=owner,
        problem_statement=problem,
        business_context=context,
    )
    with override_settings(INVESTIGATION_SOURCE_UPLOAD_ROOT=source_root):
        folder = create_managed_discovery_source_folder(
            actor=owner,
            capture_session_id=session.pk,
            name=f"AP1 Real {key}",
            uploads=sources,
        )
        snapshot_result = create_discovery_source_snapshot(
            actor=owner,
            request=DiscoverySnapshotRequest(
                capture_session_id=session.pk,
                folder_id=folder.pk,
            ),
        )
    snapshot = session.discovery_source_snapshots.get(pk=snapshot_result.snapshot_id)
    analysis = execute_autonomous_business_discovery(
        actor=owner,
        session_id=session.pk,
        snapshot_id=snapshot.pk,
    )
    return session, snapshot, analysis


def _summary(analysis: CaptureAnalysis) -> dict:
    draft = dict((analysis.result_payload or {}).get("draft") or {})
    verifier = dict(analysis.verification_payload or {})
    return {
        "analysis_id": str(analysis.pk),
        "status": analysis.status,
        "model": analysis.model_name,
        "prompt_tokens": analysis.prompt_tokens,
        "completion_tokens": analysis.completion_tokens,
        "total_tokens": analysis.total_tokens,
        "cost_usd": str(analysis.cost or ""),
        "focus_stage": (draft.get("focus") or {}).get("recommended_stage_key"),
        "stage_count": len(draft.get("stages") or []),
        "clarification_count": len(draft.get("clarifications") or []),
        "contradiction_count": len(draft.get("contradictions") or []),
        "human_question": verifier.get("human_question", ""),
        "verifier_status": verifier.get("status", ""),
        "verifier_checks": verifier.get("checks", {}),
    }


def _wait_for_server() -> None:
    deadline = time.time() + 30
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{BASE_URL}{reverse('accounts:login')}",
                timeout=1,
            ) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Django-Server wurde nicht rechtzeitig erreichbar.")


def _capture_browser(owner: User, sessions: dict[str, CaptureSession], *, label: str) -> dict:
    server_log = (OUTPUT_DIR / f"django-{label}.log").open("w", encoding="utf-8")
    server = subprocess.Popen(
        [
            sys.executable,
            "manage.py",
            "runserver",
            "127.0.0.1:8000",
            "--noreload",
            "--insecure",
        ],
        stdout=server_log,
        stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )
    try:
        _wait_for_server()
        report = {}
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000},
                    locale="de-DE",
                )
                page = context.new_page()
                response = page.goto(
                    f"{BASE_URL}{reverse('accounts:login')}",
                    wait_until="networkidle",
                )
                if response is None or response.status != 200:
                    raise AssertionError("Login-Seite ist nicht erreichbar.")
                page.locator('input[name="username"]').fill(owner.username)
                page.locator('input[name="password"]').fill(PASSWORD)
                page.locator('button[type="submit"]').click()
                page.wait_for_load_state("networkidle")

                for key, session in sessions.items():
                    path = reverse(
                        "accelerator:autonomous_discovery_review",
                        kwargs={"session_id": session.pk},
                    )
                    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
                    if response is None or response.status != 200:
                        raise AssertionError(f"{key}: Review-Surface nicht erreichbar.")
                    body = page.locator("body").inner_text()
                    metrics = page.evaluate(
                        """
                        () => ({
                          viewportWidth: window.innerWidth,
                          scrollWidth: Math.max(
                            document.documentElement.scrollWidth,
                            document.body.scrollWidth
                          ),
                          h1: document.querySelector('h1')?.innerText?.trim() || '',
                          radioCount: document.querySelectorAll(
                            'input[name="selected_stage_key"]'
                          ).length,
                        })
                        """
                    )
                    if metrics["scrollWidth"] > metrics["viewportWidth"] + 1:
                        raise AssertionError(f"{key}: horizontaler Overflow.")
                    if "Scope-/Fokus-Review" not in body:
                        raise AssertionError(f"{key}: Scope-/Fokus-Review fehlt.")
                    if (
                        key == "B"
                        and label == "waiting"
                        and "Fachliche Klärung erforderlich" not in body
                    ):
                        raise AssertionError("B: WAITING_HUMAN ist im Browser nicht sichtbar.")
                    if key == "C" and "Widersprüche" not in body:
                        raise AssertionError(
                            "C: Widerspruchsbereich ist im Browser nicht sichtbar."
                        )
                    screenshot = OUTPUT_DIR / f"{label}-{key}.png"
                    page.screenshot(path=str(screenshot), full_page=True)
                    report[key] = {
                        **metrics,
                        "url": page.url,
                        "screenshot": str(screenshot),
                    }
                context.close()
            finally:
                browser.close()
        return report
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()


def run() -> None:
    if not os.getenv("OPENROUTER_API_KEY"):
        raise RuntimeError(
            "OPENROUTER_API_KEY fehlt. Der reale AP1-Nachweis darf nicht als Mock ausgegeben werden."
        )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    owner = _prepare_owner()

    with tempfile.TemporaryDirectory(prefix="issue98-real-") as temp:
        root = Path(temp)

        a_session, a_snapshot, a_analysis = _case(
            owner=owner,
            source_root=root / "a",
            key="A",
            problem=(
                "Der manuelle Vergleich von Lieferantenangeboten dauert zu lange. "
                "Gesucht ist zunächst eine belastbare fachliche Abgrenzung des "
                "betroffenen End-to-End-Value-Streams und des Process Scopes."
            ),
            context=(
                "Der Einkauf verantwortet die Lieferantenauswahl. "
                "Es soll noch keine technische Lösung festgelegt werden."
            ),
            sources=[
                _upload(
                    "interview.md",
                    (
                        "# Fachinterview\n"
                        "Ein freigegebener Beschaffungsbedarf startet den Value Stream.\n"
                        "Der Einkauf fordert Angebote an.\n"
                        "Wenn alle Angebote vorliegen, vergleicht der Einkauf gemeinsam "
                        "mit dem Fachbereich die Inhalte und bereitet die "
                        "Lieferantenentscheidung vor.\n"
                        "Der manuelle Angebotsvergleich ist der aktuell benannte Engpass.\n"
                        "Die Entscheidungsvorbereitung beendet den betrachteten Value Stream.\n"
                    ),
                    "text/markdown",
                )
            ],
        )

        b_session, b_snapshot, b_waiting = _case(
            owner=owner,
            source_root=root / "b",
            key="B",
            problem=(
                "Die Lieferantenauswahl soll untersucht werden. "
                "Die vorliegenden Aussagen lassen die verantwortete Prozessgrenze offen."
            ),
            context=(
                "Die Entscheidung über den Process Scope soll nicht durch das Modell "
                "erfunden werden."
            ),
            sources=[
                _upload(
                    "einkauf.md",
                    (
                        "# Einkauf\n"
                        "Aus Sicht Einkauf beginnt die verantwortete Arbeit mit dem "
                        "freigegebenen Beschaffungsbedarf. Der Einkauf fordert Angebote an "
                        "und vergleicht sie anschließend.\n"
                    ),
                    "text/markdown",
                ),
                _upload(
                    "fachbereich.md",
                    (
                        "# Fachbereich\n"
                        "Für den zu analysierenden Verantwortungsbereich ist nicht geklärt, "
                        "ob die Angebotseinholung dazugehört oder ob die Prozessanalyse erst "
                        "beginnen soll, wenn alle Lieferantenangebote vollständig vorliegen.\n"
                    ),
                    "text/markdown",
                ),
            ],
        )

        c_session, _c_snapshot, c_analysis = _case(
            owner=owner,
            source_root=root / "c",
            key="C",
            problem=(
                "Der manuelle Angebotsvergleich ist der klare Engpass. "
                "Widersprüchliche Aussagen zur Rollenfolge sollen sichtbar bleiben."
            ),
            context="Der Process Scope beginnt nach vollständigem Angebotseingang.",
            sources=[
                _upload(
                    "interview.md",
                    (
                        "# Interview\n"
                        "Nach vollständigem Angebotseingang vergleicht der Einkauf die "
                        "Angebote gemeinsam mit dem Fachbereich. Danach wird die "
                        "Lieferantenentscheidung vorbereitet.\n"
                    ),
                    "text/markdown",
                ),
                _upload(
                    "prozessnotiz.txt",
                    (
                        "Nach vollständigem Angebotseingang bereitet ausschließlich der "
                        "Fachbereich den Vergleich vor; der Einkauf prüft das Ergebnis erst "
                        "danach. Die Lieferantenentscheidung folgt anschließend.\n"
                    ),
                ),
            ],
        )

        report = {
            "A": _summary(a_analysis),
            "B_waiting": _summary(b_waiting),
            "C": _summary(c_analysis),
        }

        if a_analysis.status != CaptureAnalysis.Status.SUCCESS:
            raise AssertionError(f"A muss SUCCESS sein, ist {a_analysis.status}.")
        if b_waiting.status != CaptureAnalysis.Status.WAITING_HUMAN:
            raise AssertionError(f"B muss zunächst WAITING_HUMAN sein, ist {b_waiting.status}.")
        human_question = str(b_waiting.verification_payload.get("human_question") or "").strip()
        if not human_question:
            raise AssertionError("B benötigt eine präzise menschliche Klärungsfrage.")
        contradictions = list(
            ((c_analysis.result_payload or {}).get("draft") or {}).get("contradictions") or []
        )
        if not contradictions:
            raise AssertionError("C muss mindestens einen Widerspruch sichtbar erhalten.")
        if not any(len(set(item.get("evidence_refs") or [])) >= 2 for item in contradictions):
            raise AssertionError("C-Widerspruch muss auf mindestens zwei Quellen verweisen.")

        report["browser_waiting"] = _capture_browser(
            owner,
            {"A": a_session, "B": b_session, "C": c_session},
            label="waiting",
        )

        b_session = add_autonomous_discovery_correction(
            actor=owner,
            session_id=b_session.pk,
            expected_revision=b_session.revision,
            correction=(
                "Fachliche Klärung: Der zu analysierende Process Scope beginnt erst, "
                "wenn alle Lieferantenangebote vollständig vorliegen. Die vorgelagerte "
                "Angebotseinholung bleibt Teil des breiteren Value Streams."
            ),
        )
        b_resolved = execute_autonomous_business_discovery(
            actor=owner,
            session_id=b_session.pk,
            snapshot_id=b_snapshot.pk,
        )
        report["B_resolved"] = _summary(b_resolved)
        if b_resolved.status != CaptureAnalysis.Status.SUCCESS:
            raise AssertionError(
                f"B muss nach menschlicher Klärung SUCCESS sein, ist {b_resolved.status}."
            )
        if b_resolved.result_payload["discovery_snapshot_id"] != str(b_snapshot.pk):
            raise AssertionError("B muss auf demselben autorisierten Snapshot fortsetzen.")

        report["browser_resolved"] = _capture_browser(
            owner,
            {"B": b_session},
            label="resolved",
        )

        a_focus_key = a_analysis.result_payload["draft"]["focus"]["recommended_stage_key"]
        a_handoff = materialize_discovery_and_start_investigation(
            actor=owner,
            session_id=a_session.pk,
            analysis_id=a_analysis.pk,
            selected_stage_key=a_focus_key,
            expected_revision=a_session.revision,
        )
        b_focus_key = b_resolved.result_payload["draft"]["focus"]["recommended_stage_key"]
        b_handoff = materialize_discovery_and_start_investigation(
            actor=owner,
            session_id=b_session.pk,
            analysis_id=b_resolved.pk,
            selected_stage_key=b_focus_key,
            expected_revision=b_session.revision,
        )
        report["handoff"] = {
            "A": {
                "run_id": str(a_handoff.investigation_run_id),
                "manifest_hash": a_snapshot.manifest_hash,
            },
            "B": {
                "run_id": str(b_handoff.investigation_run_id),
                "manifest_hash": b_snapshot.manifest_hash,
            },
        }

        (OUTPUT_DIR / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", 8000)) == 0:
            raise RuntimeError("Port 8000 ist bereits belegt.")
    run()
