# ruff: noqa: E402, E501, I001, RUF001, S105, S310
from __future__ import annotations

import json
import os
import socket
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

import django


django.setup()

from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import Page, sync_playwright

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureAnalysis, CaptureFieldSuggestion, CaptureSession
from ki_radar.accelerator.services import (
    complete_capture_session,
    create_capture_session,
    save_capture_session,
)
from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path("artifacts/block4-ui-verification")
USERNAME = "block4-ui-owner"
PASSWORD = "Block4UiVerification!123"
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000, "is_mobile": False},
    "mobile": {"width": 390, "height": 844, "is_mobile": True},
}


def _complete_session(user: User, capture_type: str, working_title: str) -> CaptureSession:
    session = create_capture_session(
        actor=user,
        capture_type=capture_type,
        working_title=working_title,
    )
    catalog = get_capture_catalog(capture_type, session.catalog_version)
    answers = {
        question.key: (
            f"[UI-Nachweis] {question.label} Fachliche Antwort mit nachvollziehbarer Quelle."
        )
        for question in catalog.questions
    }
    if capture_type == CaptureSession.CaptureType.VALUE_STREAM:
        answers["vs_context"] = (
            "Der Value Stream Beschaffung bis Bestellung liefert eine nachvollziehbar "
            "vorbereitete Bestellung."
        )
        answers["vs_stages"] = (
            "1 Angebot prüfen: Angebote strukturieren. "
            "2 Freigabe dokumentieren: Ergebnis nachvollziehbar freigeben."
        )
    else:
        answers["uc_problem_context"] = (
            "Der Use Case Assistierter Angebotsvergleich reduziert manuelle Übertragung."
        )
    session = save_capture_session(
        actor=user,
        session_id=session.pk,
        expected_revision=session.revision,
        answer_updates=answers,
    )
    return complete_capture_session(
        actor=user,
        session_id=session.pk,
        expected_revision=session.revision,
    )


def _analysis(
    session: CaptureSession,
    user: User,
    *,
    source_hash: str,
    status: str = CaptureAnalysis.Status.SUCCESS,
    error_code: str = "",
    open_questions: list[dict] | None = None,
    contradictions: list[dict] | None = None,
) -> CaptureAnalysis:
    now = timezone.now()
    return CaptureAnalysis.objects.create(
        session=session,
        requested_by=user,
        status=status,
        source_revision=session.revision,
        source_hash=source_hash,
        capture_type=session.capture_type,
        catalog_version=session.catalog_version,
        answer_schema_version=session.schema_version,
        provider="openrouter",
        model_name="openai/gpt-5-mini-ui-proof",
        prompt_version="1.0",
        extraction_schema_version="1.0",
        started_at=now,
        finished_at=now,
        duration_ms=120,
        error_code=error_code,
        input_chars=2400,
        output_chars=800,
        total_tokens=420,
        open_questions=open_questions or [],
        contradictions=contradictions or [],
    )


def prepare_data() -> dict[str, object]:
    CaptureSession.objects.filter(owner__username=USERNAME).delete()
    User.objects.filter(username=USERNAME).delete()

    business_unit, _ = BusinessUnit.objects.get_or_create(name="Block-4-UI-Prüfung")
    group, _ = Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)
    user = User.objects.create_user(
        username=USERNAME,
        password=PASSWORD,
        business_unit=business_unit,
    )
    user.groups.add(group)

    value_stream = _complete_session(
        user,
        CaptureSession.CaptureType.VALUE_STREAM,
        "Beschaffung bis Bestellung – Block-4-Abnahme",
    )
    use_case = _complete_session(
        user,
        CaptureSession.CaptureType.USE_CASE,
        "Assistierter Angebotsvergleich – Block-4-Abnahme",
    )

    grouped = _analysis(
        value_stream,
        user,
        source_hash="1" * 64,
        open_questions=[
            {
                "message": "Die Messmethode muss im nächsten Block bestätigt werden.",
                "source_questions": ["vs_stage_pain_metrics"],
            }
        ],
        contradictions=[
            {
                "message": "Für eine Phase werden zwei Systemquellen genannt.",
                "source_questions": ["vs_stage_operations"],
            }
        ],
    )
    CaptureFieldSuggestion.objects.create(
        analysis=grouped,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="value_stream.name",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Beschaffung bis Bestellung",
        source_question="vs_context",
        source_excerpt="Value Stream Beschaffung bis Bestellung",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Der Name ist ausdrücklich genannt.",
    )
    CaptureFieldSuggestion.objects.create(
        analysis=grouped,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].name",
        target_group_key="angebot-prufen",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Angebot prüfen",
        source_question="vs_stages",
        source_excerpt="Angebot prüfen",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Die Phase ist wörtlich belegt.",
    )
    CaptureFieldSuggestion.objects.create(
        analysis=grouped,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM_STAGE,
        target_field="value_stream.stages[].description",
        target_group_key="angebot-prufen",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Angebote strukturieren.",
        source_question="vs_stages",
        source_excerpt="Angebote strukturieren",
        uncertainty=CaptureFieldSuggestion.Uncertainty.MEDIUM,
        uncertainty_reason="Die Beschreibung ist knapp und muss geprüft werden.",
    )

    empty = _analysis(
        value_stream,
        user,
        source_hash="2" * 64,
        open_questions=[
            {
                "message": "Die Antworten enthalten noch keine belastbare Feldzuordnung.",
                "source_questions": ["vs_open_questions"],
            }
        ],
    )

    long_preview = _analysis(value_stream, user, source_hash="3" * 64)
    CaptureFieldSuggestion.objects.create(
        analysis=long_preview,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.VALUE_STREAM,
        target_field="value_stream.description",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value=(
            "Eine bewusst lange, mehrzeilige Beschreibung prüft die responsive Darstellung "
            "umfangreicher Feldvorschläge. Sie enthält mehrere vollständige Sätze, damit "
            "Zeilenumbrüche, Quellnachweis und Unsicherheitsbegründung auch auf einem mobilen "
            "Viewport ohne horizontales Scrollen lesbar bleiben."
        ),
        source_question="vs_context",
        source_excerpt="nachvollziehbar vorbereitete Bestellung",
        uncertainty=CaptureFieldSuggestion.Uncertainty.HIGH,
        uncertainty_reason=(
            "Der Vorschlag fasst mehrere Aspekte zusammen und benötigt deshalb eine besonders "
            "sorgfältige fachliche Prüfung."
        ),
    )

    failed = _analysis(
        value_stream,
        user,
        source_hash="4" * 64,
        status=CaptureAnalysis.Status.FAILED,
        error_code="timeout",
    )

    use_case_preview = _analysis(use_case, user, source_hash="5" * 64)
    CaptureFieldSuggestion.objects.create(
        analysis=use_case_preview,
        target_object_type=CaptureFieldSuggestion.TargetObjectType.USE_CASE,
        target_field="use_case.title",
        field_type=CaptureFieldSuggestion.FieldType.TEXT,
        suggested_value="Assistierter Angebotsvergleich",
        source_question="uc_problem_context",
        source_excerpt="Use Case Assistierter Angebotsvergleich",
        uncertainty=CaptureFieldSuggestion.Uncertainty.LOW,
        uncertainty_reason="Der Titel ist wörtlich belegt.",
    )

    return {
        "value_stream": value_stream,
        "use_case": use_case,
        "grouped": grouped,
        "empty": empty,
        "long": long_preview,
        "failed": failed,
        "use_case_preview": use_case_preview,
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
    response = page.goto(f"{BASE_URL}{reverse('accounts:login')}", wait_until="networkidle")
    if response is None or response.status != 200:
        raise AssertionError("Login-Seite ist nicht erreichbar.")
    page.locator('input[name="username"]').fill(USERNAME)
    page.locator('input[name="password"]').fill(PASSWORD)
    page.locator('button[type="submit"]').click()
    page.wait_for_load_state("networkidle")
    if reverse("accounts:login") in page.url:
        raise AssertionError("Browser-Login ist fehlgeschlagen.")


def inspect_page(
    page: Page,
    *,
    name: str,
    path: str,
    viewport_name: str,
    configured_width: int,
    expected_text: tuple[str, ...],
) -> dict:
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    if response is None or response.status >= 400:
        raise AssertionError(
            f"{name} lieferte HTTP {response.status if response else 'unbekannt'}."
        )

    content = page.locator("body").inner_text()
    missing_text = [text for text in expected_text if text not in content]
    if missing_text:
        raise AssertionError(f"{name}: Erwartete Inhalte fehlen: {missing_text}")
    forbidden_actions = [
        action for action in ("Übernehmen", "Verwerfen", "Sammelübernahme") if action in content
    ]
    if forbidden_actions:
        raise AssertionError(f"{name}: Block-5-Aktionen sichtbar: {forbidden_actions}")

    metrics = page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const body = document.body;
          const interactive = [...document.querySelectorAll('main a, main button, main input, main select, main textarea')];
          const isInsideHorizontalScroller = (element) => {
            let ancestor = element.parentElement;
            while (ancestor && ancestor !== document.body) {
              const ancestorStyle = window.getComputedStyle(ancestor);
              const overflowX = ancestorStyle.overflowX;
              if (
                (overflowX === 'auto' || overflowX === 'scroll') &&
                ancestor.scrollWidth > ancestor.clientWidth + 1
              ) {
                return true;
              }
              ancestor = ancestor.parentElement;
            }
            return false;
          };
          const offViewport = interactive.filter((element) => {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            if (style.display === 'none' || style.visibility === 'hidden') return false;
            const outsideViewport = rect.left < -1 || rect.right > window.innerWidth + 1;
            return outsideViewport && !isInsideHorizontalScroller(element);
          });
          return {
            title: document.title,
            h1: document.querySelector('h1')?.innerText?.trim() || '',
            viewportWidth: window.innerWidth,
            documentScrollWidth: root.scrollWidth,
            bodyScrollWidth: body.scrollWidth,
            horizontalOverflow: Math.max(root.scrollWidth, body.scrollWidth) > window.innerWidth + 1,
            offViewportInteractiveCount: offViewport.length,
            formCount: document.querySelectorAll('form').length,
            analysisActionCount: [...document.querySelectorAll('button')].filter(
              (button) => button.innerText.includes('analysieren')
            ).length,
          };
        }
        """
    )
    metrics.update(
        {
            "name": name,
            "path": path,
            "httpStatus": response.status,
            "configuredViewportWidth": configured_width,
            "layoutViewportMismatch": metrics["viewportWidth"] != configured_width,
            "missingExpectedText": missing_text,
            "forbiddenActions": forbidden_actions,
        }
    )
    screenshot_path = OUTPUT_DIR / f"{viewport_name}-{name}.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    metrics["screenshot"] = str(screenshot_path)
    return metrics


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
        report = {"viewports": VIEWPORTS, "pages": [], "manualVisualReviewRequired": True}
        pages = {
            "value-stream-review": (
                reverse(
                    "accelerator:capture_review",
                    kwargs={"session_id": data["value_stream"].pk},
                ),
                ("Antworten analysieren", "Bisherige Analyseläufe"),
            ),
            "use-case-review": (
                reverse(
                    "accelerator:capture_review",
                    kwargs={"session_id": data["use_case"].pk},
                ),
                ("Antworten analysieren", "Assistierter Angebotsvergleich – Block-4-Abnahme"),
            ),
            "grouped-preview": (
                reverse(
                    "accelerator:analysis_detail",
                    kwargs={"analysis_id": data["grouped"].pk},
                ),
                ("Feldvorschläge", "Angebot prüfen", "Offene Fragen", "Widersprüche"),
            ),
            "empty-preview": (
                reverse(
                    "accelerator:analysis_detail",
                    kwargs={"analysis_id": data["empty"].pk},
                ),
                ("keine gültigen Feldvorschläge", "Offene Fragen"),
            ),
            "long-preview": (
                reverse(
                    "accelerator:analysis_detail",
                    kwargs={"analysis_id": data["long"].pk},
                ),
                ("bewusst lange", "Unsicherheit: Hoch"),
            ),
            "failed-preview": (
                reverse(
                    "accelerator:analysis_detail",
                    kwargs={"analysis_id": data["failed"].pk},
                ),
                ("konnte nicht abgeschlossen werden", "timeout"),
            ),
            "use-case-preview": (
                reverse(
                    "accelerator:analysis_detail",
                    kwargs={"analysis_id": data["use_case_preview"].pk},
                ),
                ("Assistierter Angebotsvergleich", "use_case.title"),
            ),
        }

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                for viewport_name, viewport in VIEWPORTS.items():
                    context = browser.new_context(
                        viewport={"width": viewport["width"], "height": viewport["height"]},
                        is_mobile=viewport["is_mobile"],
                        has_touch=viewport["is_mobile"],
                        locale="de-DE",
                    )
                    page = context.new_page()
                    login(page)
                    for page_name, (path, expected_text) in pages.items():
                        report["pages"].append(
                            inspect_page(
                                page,
                                name=page_name,
                                path=path,
                                viewport_name=viewport_name,
                                configured_width=viewport["width"],
                                expected_text=expected_text,
                            )
                        )
                    context.close()
            finally:
                browser.close()

        overflow_pages = [
            item["screenshot"] for item in report["pages"] if item["horizontalOverflow"]
        ]
        viewport_mismatches = [
            item["screenshot"] for item in report["pages"] if item["layoutViewportMismatch"]
        ]
        off_viewport_actions = [
            item["screenshot"] for item in report["pages"] if item["offViewportInteractiveCount"]
        ]
        report["automatedSummary"] = {
            "pageCount": len(report["pages"]),
            "allPagesHttp200": all(item["httpStatus"] == 200 for item in report["pages"]),
            "horizontalOverflowPages": overflow_pages,
            "layoutViewportMismatchPages": viewport_mismatches,
            "offViewportInteractivePages": off_viewport_actions,
            "block5ActionsAbsent": all(not item["forbiddenActions"] for item in report["pages"]),
        }
        (OUTPUT_DIR / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        if overflow_pages:
            raise AssertionError(f"Dokumentweiter horizontaler Überlauf: {overflow_pages}")
        if viewport_mismatches:
            raise AssertionError(
                f"Layout vergrößert den konfigurierten Viewport: {viewport_mismatches}"
            )
        if off_viewport_actions:
            raise AssertionError(
                f"Interaktive Elemente liegen außerhalb des Viewports: {off_viewport_actions}"
            )
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
        server_log.close()


if __name__ == "__main__":
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", 8000)) == 0:
            raise RuntimeError("Port 8000 ist bereits belegt.")
    run_verification()
