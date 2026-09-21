# ruff: noqa: E402, E501, I001, S105, S310
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
os.environ.setdefault("USE_SQLITE_FOR_TESTS", "1")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
os.environ.setdefault("ACCELERATOR_FIELD_ADOPTION_ENABLED", "1")

import django


django.setup()

from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import Page, sync_playwright

from ki_radar.accelerator.adoption_service import adopt_field_candidate
from ki_radar.accelerator.candidate_snapshot import create_adoption_candidates
from ki_radar.accelerator.catalogs import ANSWER_SCHEMA_VERSION, CATALOG_VERSION_V1
from ki_radar.accelerator.extraction_contract import (
    EXTRACTION_PROMPT_VERSION,
    EXTRACTION_SCHEMA_VERSION,
)
from ki_radar.accelerator.models import (
    CaptureAnalysis,
    CaptureFieldSuggestion,
    CaptureSession,
    FieldAdoptionAudit,
)
from ki_radar.accelerator.services import create_capture_session
from ki_radar.accelerator.target_binding import bind_capture_target
from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER
from ki_radar.architecture.models import ValueStream
from ki_radar.use_cases.models import UseCase

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path("artifacts/block5-ui-verification")
USERNAME = "block5-ui-owner"
PASSWORD = "Block5UiVerification!123"
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000, "is_mobile": False},
    "mobile": {"width": 390, "height": 844, "is_mobile": True},
}


def _session(*, actor: User, target, capture_type: str) -> CaptureSession:
    session = create_capture_session(
        actor=actor,
        capture_type=capture_type,
        working_title=f"[Real-DEMO] {target}",
    )
    bind_capture_target(actor=actor, session_id=session.pk, target_id=target.pk)
    session.status = CaptureSession.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])
    return session


def _analysis(session: CaptureSession, actor: User, source_hash: str) -> CaptureAnalysis:
    now = timezone.now()
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=actor,
        status=CaptureAnalysis.Status.SUCCESS,
        source_revision=session.revision,
        source_hash=source_hash,
        capture_type=session.capture_type,
        catalog_version=CATALOG_VERSION_V1,
        answer_schema_version=ANSWER_SCHEMA_VERSION,
        provider="openrouter",
        model_name="openai/gpt-5-mini-ui-proof",
        prompt_version=EXTRACTION_PROMPT_VERSION,
        extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
        started_at=now,
        finished_at=now,
        duration_ms=900,
        total_tokens=900,
    )


def _suggestion(
    *,
    analysis: CaptureAnalysis,
    field_name: str,
    value: str,
    uncertainty: str,
) -> None:
    CaptureFieldSuggestion.objects.create(
        analysis=analysis,
        target_object_type=analysis.capture_type,
        target_field=field_name,
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=value,
        source_question="real_demo_source",
        source_excerpt=f"[Real-DEMO] {value}",
        uncertainty=uncertainty,
        uncertainty_reason="Gezielter Block-5-UI-Nachweis.",
    )


def prepare_data() -> dict[str, object]:
    old_user = User.objects.filter(username=USERNAME).first()
    if old_user is not None:
        FieldAdoptionAudit.objects.filter(actor=old_user).delete()
        CaptureSession.objects.filter(owner=old_user).delete()
    UseCase.objects.filter(demo_key="block5-ui-use-case").delete()
    ValueStream.objects.filter(demo_key="block5-ui-value-stream").delete()
    User.objects.filter(username=USERNAME).delete()

    business_unit, _ = BusinessUnit.objects.get_or_create(name="Block-5-UI-Prüfung")
    group, _ = Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)
    user = User.objects.create_user(
        username=USERNAME,
        password=PASSWORD,
        business_unit=business_unit,
    )
    user.groups.add(group)

    value_stream = ValueStream.objects.create(
        demo_key="block5-ui-value-stream",
        name="[Real-DEMO] Beschaffung bis Bestellung",
        description="Bestehende Beschreibung",
        business_unit=business_unit,
        owner=user,
        trigger="Bestehender Auslöser",
        outcome="Bestehendes Ergebnis",
        scope_in="Bedarf bis Bestellung",
        status=ValueStream.Status.ACTIVE,
        created_by=user,
    )
    use_case = UseCase.objects.create(
        demo_key="block5-ui-use-case",
        title="[Real-DEMO] KI-Assistenz Angebotsvergleich",
        summary="Bestehende Kurzbeschreibung",
        problem_statement="Der Vergleich dauert zu lange.",
        business_unit=business_unit,
        affected_process="Beschaffung",
        target_users="Einkauf",
        business_owner=user,
        expected_benefit="Bearbeitungszeit reduzieren",
        submitter=user,
    )

    value_stream_session = _session(
        actor=user,
        target=value_stream,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
    )
    value_stream_analysis = _analysis(value_stream_session, user, "e" * 64)
    _suggestion(
        analysis=value_stream_analysis,
        field_name="description",
        value="Angebote werden strukturiert und nachvollziehbar verglichen.",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    _suggestion(
        analysis=value_stream_analysis,
        field_name="trigger",
        value="Ein fachlich freigegebener Bedarf liegt vor.",
        uncertainty=CaptureFieldSuggestion.Uncertainty.MEDIUM,
    )
    _suggestion(
        analysis=value_stream_analysis,
        field_name="outcome",
        value="Eine belastbar dokumentierte Bestellung ist ausgelöst.",
        uncertainty=CaptureFieldSuggestion.Uncertainty.HIGH,
    )
    value_stream_candidates = {
        candidate.target_field: candidate
        for candidate in create_adoption_candidates(analysis_id=value_stream_analysis.pk)
    }

    use_case_session = _session(
        actor=user,
        target=use_case,
        capture_type=CaptureSession.CaptureType.USE_CASE,
    )
    use_case_analysis = _analysis(use_case_session, user, "f" * 64)
    _suggestion(
        analysis=use_case_analysis,
        field_name="summary",
        value="KI unterstützt den nachvollziehbaren Angebotsvergleich.",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
    )
    conflict_candidate = create_adoption_candidates(analysis_id=use_case_analysis.pk)[0]
    use_case.summary = "Die Fachseite hat die Kurzbeschreibung inzwischen geändert."
    use_case.save(update_fields=["summary", "updated_at"])
    adopt_field_candidate(candidate_id=conflict_candidate.pk, actor=user)

    return {
        "value_stream_analysis": value_stream_analysis,
        "use_case_analysis": use_case_analysis,
        "low_candidate": value_stream_candidates["description"],
        "medium_candidate": value_stream_candidates["trigger"],
        "high_candidate": value_stream_candidates["outcome"],
        "conflict_candidate": conflict_candidate,
    }


def wait_for_server(timeout_seconds: int = 30) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(
                f"{BASE_URL}{reverse('accounts:login')}", timeout=1
            ) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError("Django-Server wurde nicht rechtzeitig erreichbar.")


def login(page: Page) -> None:
    page.goto(f"{BASE_URL}{reverse('accounts:login')}", wait_until="networkidle")
    page.locator('input[name="username"]').fill(USERNAME)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    if reverse("accounts:login") in page.url:
        raise AssertionError("Browser-Login ist fehlgeschlagen.")


def _layout_metrics(page: Page) -> dict[str, object]:
    return page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const body = document.body;
          const interactive = [...document.querySelectorAll('main a, main button, main textarea')];
          const offViewport = interactive.filter((element) => {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            return rect.left < -1 || rect.right > window.innerWidth + 1;
          });
          return {
            viewportWidth: window.innerWidth,
            documentScrollWidth: root.scrollWidth,
            bodyScrollWidth: body.scrollWidth,
            horizontalOverflow: Math.max(root.scrollWidth, body.scrollWidth) > window.innerWidth + 1,
            offViewportInteractiveCount: offViewport.length,
          };
        }
        """
    )


def _candidate_text(page: Page, candidate_id) -> str:
    return page.locator(f'[data-adoption-candidate="{candidate_id}"]').inner_text()


def inspect_review_page(page: Page, data: dict[str, object], viewport_name: str) -> dict:
    path = reverse(
        "accelerator:analysis_detail",
        kwargs={"analysis_id": data["value_stream_analysis"].pk},
    )
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    if response is None or response.status != 200:
        raise AssertionError("Die Feldprüfung ist nicht erreichbar.")

    low = _candidate_text(page, data["low_candidate"].pk)
    medium = _candidate_text(page, data["medium_candidate"].pk)
    high = _candidate_text(page, data["high_candidate"].pk)
    if "Direkt übernehmen" not in low or "Bearbeitet übernehmen" not in low:
        raise AssertionError("Low-Unsicherheit bietet nicht beide Übernahmewege.")
    if "Direkt übernehmen" in medium or "Bearbeitet übernehmen" not in medium:
        raise AssertionError("Medium-Unsicherheit verletzt die Policy-Matrix.")
    if "Direkt übernehmen" in high or "Bearbeitet übernehmen" in high:
        raise AssertionError("High-Unsicherheit darf keine Übernahme anbieten.")
    if "Hohe Unsicherheit" not in high or "Verwerfen" not in high:
        raise AssertionError("High-Unsicherheit ist nicht als Vorschau mit Verwerfen sichtbar.")

    metrics = _layout_metrics(page)
    if metrics["horizontalOverflow"] or metrics["offViewportInteractiveCount"]:
        raise AssertionError("Die Feldprüfung erzeugt horizontalen Überlauf.")
    screenshot = OUTPUT_DIR / f"{viewport_name}-field-review.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return {"page": "field-review", "path": path, "screenshot": str(screenshot), **metrics}


def inspect_conflict_page(page: Page, data: dict[str, object], viewport_name: str) -> dict:
    path = reverse(
        "accelerator:analysis_detail",
        kwargs={"analysis_id": data["use_case_analysis"].pk},
    )
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    if response is None or response.status != 200:
        raise AssertionError("Die Konfliktprüfung ist nicht erreichbar.")

    conflict = _candidate_text(page, data["conflict_candidate"].pk)
    for expected in (
        "Damals",
        "Aktuell",
        "Vorschlag",
        "Neu analysieren",
        "Regulär bearbeiten",
        "Verwerfen",
    ):
        if expected not in conflict:
            raise AssertionError(f"Konfliktaktion oder Vergleich fehlt: {expected}")
    if "Direkt übernehmen" in conflict or "Bearbeitet übernehmen" in conflict:
        raise AssertionError("Die Konfliktkarte bietet eine unzulässige Übernahme an.")

    metrics = _layout_metrics(page)
    if metrics["horizontalOverflow"] or metrics["offViewportInteractiveCount"]:
        raise AssertionError("Die Konfliktprüfung erzeugt horizontalen Überlauf.")
    screenshot = OUTPUT_DIR / f"{viewport_name}-conflict-review.png"
    page.screenshot(path=str(screenshot), full_page=True)
    return {"page": "conflict-review", "path": path, "screenshot": str(screenshot), **metrics}


def run_verification() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    data = prepare_data()
    server_log = (OUTPUT_DIR / "django-server.log").open("w", encoding="utf-8")
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
        wait_for_server()
        report = {"marker": "[Real-DEMO]", "pages": [], "visualReviewRequired": True}
        with sync_playwright() as playwright:
            for viewport_name, viewport in VIEWPORTS.items():
                browser = playwright.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": viewport["width"], "height": viewport["height"]},
                    is_mobile=viewport["is_mobile"],
                )
                page = context.new_page()
                login(page)
                report["pages"].append(inspect_review_page(page, data, viewport_name))
                report["pages"].append(inspect_conflict_page(page, data, viewport_name))
                context.close()
                browser.close()
        (OUTPUT_DIR / "manifest.json").write_text(
            f"{json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)}\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()


if __name__ == "__main__":
    run_verification()
