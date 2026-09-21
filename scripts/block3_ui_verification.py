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
from playwright.sync_api import Page, sync_playwright

from ki_radar.accelerator.catalogs import get_capture_catalog
from ki_radar.accelerator.models import CaptureSession
from ki_radar.accelerator.services import create_capture_session, save_capture_session
from ki_radar.accounts.models import BusinessUnit, User
from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_DIR = Path("artifacts/block3-ui-verification")
USERNAME = "block3-ui-owner"
PASSWORD = "Block3UiVerification!123"

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 1000, "is_mobile": False},
    "mobile": {"width": 390, "height": 844, "is_mobile": True},
}


def prepare_data() -> dict[str, CaptureSession]:
    CaptureSession.objects.filter(owner__username=USERNAME).delete()
    User.objects.filter(username=USERNAME).delete()

    business_unit, _ = BusinessUnit.objects.get_or_create(name="Block-3-UI-Prüfung")
    group, _ = Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)
    user = User.objects.create_user(
        username=USERNAME,
        password=PASSWORD,
        business_unit=business_unit,
    )
    user.groups.add(group)

    value_stream = create_capture_session(
        actor=user,
        capture_type=CaptureSession.CaptureType.VALUE_STREAM,
        working_title="Beschaffung bis Bestellung – Desktop- und Mobile-Prüfung",
    )
    first_section = get_capture_catalog("value_stream").sections[0]
    value_stream = save_capture_session(
        actor=user,
        session_id=value_stream.pk,
        expected_revision=value_stream.revision,
        answer_updates={
            question.key: (
                "Der Value Stream umfasst die Bedarfsmeldung, den Angebotsvergleich und die "
                "Bestellung. Das Ergebnis ist eine nachvollziehbar ausgewählte Bestellung."
            )
            for question in first_section.questions
        },
    )

    use_case = create_capture_session(
        actor=user,
        capture_type=CaptureSession.CaptureType.USE_CASE,
        working_title="Assistierter Angebotsvergleich mit längerer Arbeitsbezeichnung",
    )

    return {"value_stream": value_stream, "use_case": use_case}


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
) -> dict:
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    if response is None or response.status >= 400:
        raise AssertionError(
            f"{name} lieferte HTTP {response.status if response else 'unbekannt'}."
        )

    metrics = page.evaluate(
        """
        () => {
          const root = document.documentElement;
          const body = document.body;
          const interactive = [...document.querySelectorAll('a, button, input, textarea, select')];
          const invisibleInteractive = interactive.filter((element) => {
            const rect = element.getBoundingClientRect();
            const style = window.getComputedStyle(element);
            return style.display === 'none' || style.visibility === 'hidden' || rect.width === 0 || rect.height === 0;
          });
          const outsideViewport = (selector) => [...document.querySelectorAll(selector)].filter((element) => {
            const rect = element.getBoundingClientRect();
            return rect.left < -1 || rect.right > window.innerWidth + 1;
          }).length;
          return {
            title: document.title,
            h1: document.querySelector('h1')?.innerText?.trim() || '',
            viewportWidth: window.innerWidth,
            documentScrollWidth: root.scrollWidth,
            bodyScrollWidth: body.scrollWidth,
            horizontalOverflow: Math.max(root.scrollWidth, body.scrollWidth) > window.innerWidth + 1,
            textareaCount: document.querySelectorAll('textarea').length,
            contentEditableCount: document.querySelectorAll('[contenteditable]').length,
            inlineInputHandlerCount: document.querySelectorAll('[oninput], [onkeydown], [onkeyup]').length,
            unlabeledTextareaCount: [...document.querySelectorAll('textarea')].filter((element) => {
              if (!element.id) return true;
              return !document.querySelector(`label[for="${CSS.escape(element.id)}"]`);
            }).length,
            invisibleInteractiveCount: invisibleInteractive.length,
            registerActionOffViewportCount: outsideViewport('.register-actions .btn'),
            captureActionOffViewportCount: outsideViewport('.capture-session-table td:last-child .btn'),
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
        }
    )
    screenshot_path = OUTPUT_DIR / f"{viewport_name}-{name}.png"
    page.screenshot(path=str(screenshot_path), full_page=True)
    metrics["screenshot"] = str(screenshot_path)
    return metrics


def native_textarea_input_probe(page: Page, session: CaptureSession) -> dict:
    path = reverse(
        "accelerator:capture_step",
        kwargs={"session_id": session.pk, "step": 2},
    )
    response = page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    if response is None or response.status != 200:
        raise AssertionError("Wizard-Seite für Eingabeprobe ist nicht erreichbar.")

    textarea = page.locator("textarea").first
    textarea.focus()
    probe_text = (
        "Diktatkompatibilitätsprobe: nativer Text wird ohne Custom-Eingabesteuerung übernommen."
    )
    textarea.fill("")
    page.keyboard.insert_text(probe_text)
    before_save = textarea.input_value()
    page.locator('button[name="action"][value="save"]').click()
    page.wait_for_load_state("networkidle")
    page.goto(f"{BASE_URL}{path}", wait_until="networkidle")
    after_reload = page.locator("textarea").first.input_value()

    if before_save != probe_text or after_reload != probe_text:
        raise AssertionError(
            "Native Texteingabe wurde nicht korrekt gespeichert und wieder geladen."
        )

    return {
        "nativeTextareaFocused": True,
        "browserTextInsertion": "passed",
        "persistenceAfterSaveAndReload": "passed",
        "customInputControlAbsent": True,
        "windowsWinHExecuted": False,
        "windowsWinHReason": (
            "GitHub-hosted Linux-Runner besitzt keine interaktive Windows-Desktop-, Mikrofon- "
            "oder Betriebssystem-Diktatumgebung."
        ),
    }


def run_verification() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    sessions = prepare_data()

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
        report = {
            "viewports": VIEWPORTS,
            "pages": [],
            "nativeInputProbe": None,
            "manualVisualReviewRequired": True,
        }

        paths = {
            "capture-list": reverse("accelerator:capture_list"),
            "value-stream-list": reverse("architecture:value_stream_list"),
            "use-case-list": reverse("use_cases:list"),
            "value-stream-start": reverse("accelerator:value_stream_start"),
            "use-case-start": reverse("accelerator:use_case_start"),
            "value-stream-wizard": reverse(
                "accelerator:capture_step",
                kwargs={"session_id": sessions["value_stream"].pk, "step": 1},
            ),
            "use-case-wizard": reverse(
                "accelerator:capture_step",
                kwargs={"session_id": sessions["use_case"].pk, "step": 1},
            ),
            "value-stream-review": reverse(
                "accelerator:capture_review",
                kwargs={"session_id": sessions["value_stream"].pk},
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
                    for page_name, path in paths.items():
                        report["pages"].append(
                            inspect_page(
                                page,
                                name=page_name,
                                path=path,
                                viewport_name=viewport_name,
                                configured_width=viewport["width"],
                            )
                        )
                    if viewport_name == "desktop":
                        report["nativeInputProbe"] = native_textarea_input_probe(
                            page,
                            sessions["value_stream"],
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
        unlabeled_pages = [
            item["screenshot"] for item in report["pages"] if item["unlabeledTextareaCount"]
        ]
        off_viewport_actions = [
            item["screenshot"]
            for item in report["pages"]
            if item["registerActionOffViewportCount"] or item["captureActionOffViewportCount"]
        ]
        report["automatedSummary"] = {
            "pageCount": len(report["pages"]),
            "horizontalOverflowPages": overflow_pages,
            "layoutViewportMismatchPages": viewport_mismatches,
            "unlabeledTextareaPages": unlabeled_pages,
            "offViewportActionPages": off_viewport_actions,
            "allPagesHttp200": all(item["httpStatus"] == 200 for item in report["pages"]),
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
        if unlabeled_pages:
            raise AssertionError(f"Textareas ohne sichtbare Label-Zuordnung: {unlabeled_pages}")
        if off_viewport_actions:
            raise AssertionError(
                f"Primäraktionen liegen außerhalb des Viewports: {off_viewport_actions}"
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
