# ruff: noqa: S101, S105, S310, S603
"""Desktop browser evidence against an isolated database and deterministic provider."""

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
OUTPUT = Path(
    os.environ.get("IDEA_UI_OUTPUT", ROOT / "artifacts" / "idea-discovery-ui-verification")
)
BASE = "http://127.0.0.1:8765"
PASSWORD = "IsolatedUiVerification123!"


def serve():
    os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings.test"
    os.environ["USE_SQLITE_FOR_TESTS"] = "1"
    from config.settings import test as settings

    scratch = Path(os.environ["IDEA_UI_SCRATCH"])
    settings.DATABASES["default"]["NAME"] = scratch / "ui.sqlite3"
    settings.ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
    settings.INVESTIGATION_SOURCE_UPLOAD_ROOT = scratch / "sources"
    import django

    django.setup()
    from django.contrib.auth.models import Group
    from django.core.management import call_command
    from django.urls import reverse
    from test_issue_98_autonomous_business_discovery import _draft, _result, _verifier

    from ki_radar.accelerator import architect_service
    from ki_radar.accounts.models import BusinessUnit, User
    from ki_radar.accounts.permissions import GROUP_BUSINESS_OWNER
    from ki_radar.use_cases.idea_models import IdeaCandidate

    call_command("migrate", verbosity=0)
    unit = BusinessUnit.objects.create(name="Isolierte UI-Abnahme")
    user = User.objects.create_user(username="idea-ui-owner", password=PASSWORD, business_unit=unit)
    user.groups.add(Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)[0])
    unassigned = User.objects.create_user(username="unassigned-ui-owner", password=PASSWORD)
    unassigned.groups.add(Group.objects.get_or_create(name=GROUP_BUSINESS_OWNER)[0])
    BusinessUnit.objects.create(name="Anderer Untersuchungsbereich")
    inactive = BusinessUnit.objects.create(name="Inaktive Idee-Einheit", is_active=False)
    urls = {}
    for key in ["discovery", "discard", "intake"]:
        idea = IdeaCandidate.objects.create(
            title=f"Angebote vergleichen ({key})",
            description=(
                "Ein freigegebener Beschaffungsbedarf startet die Lieferantenauswahl. "
                "Angebote werden per E-Mail eingeholt und manuell verglichen. "
                "Einkauf und Fachbereich bereiten die Entscheidung vor."
            ),
            business_unit=unit,
            submitted_by=user,
            source_note="Synthetischer UI-Test, keine produktive Evidenz",
        )
        urls[key] = idea.get_absolute_url()
    for key, idea_unit in [("unassigned", unit), ("inactive", inactive)]:
        idea = IdeaCandidate.objects.create(
            title=f"Angebote vergleichen ({key})",
            description=idea.description,
            business_unit=idea_unit,
            submitted_by=unassigned,
        )
        urls[key] = idea.get_absolute_url()
    urls["generic"] = reverse("accelerator:autonomous_discovery_start")
    urls["login"] = reverse("accounts:login")
    (scratch / "urls.json").write_text(json.dumps(urls), encoding="utf-8")

    def provider(**kwargs):
        if "verifier" in kwargs["schema_name"]:
            return _result(_verifier())
        draft = _draft()
        for item in [
            draft["value_stream"],
            draft["focus"],
            draft["process_analysis"],
            *draft["stages"],
            *draft["facts"],
            *draft["hypotheses"],
        ]:
            item["evidence_refs"] = ["U0"]
        return _result(draft)

    architect_service._provider_call = provider
    call_command("runserver", "127.0.0.1:8765", use_reloader=False, insecure=True)


def verify():
    from playwright.sync_api import expect, sync_playwright

    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="idea-ui-") as directory:
        scratch = Path(directory)
        with (scratch / "server.log").open("w", encoding="utf-8") as log:
            server = subprocess.Popen(
                [sys.executable, __file__, "--serve"],
                cwd=ROOT,
                env={**os.environ, "IDEA_UI_SCRATCH": directory},
                stdout=log,
                stderr=log,
            )
            report = {
                "viewport": "1440x1000 desktop",
                "provider": "deterministic fixture",
                "checks": [],
                "pages": [],
                "findings": [],
            }
            try:
                for _ in range(120):
                    if server.poll() is not None:
                        raise RuntimeError((scratch / "server.log").read_text())
                    try:
                        urllib.request.urlopen(BASE, timeout=1).close()
                        break
                    except OSError:
                        time.sleep(1)
                urls = json.loads((scratch / "urls.json").read_text())
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch()
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    errors = []
                    page.on("pageerror", lambda error: errors.append(str(error)))

                    def capture(name):
                        active = page.locator(".app-sidebar .sidebar-link.active")
                        expect(active).to_have_count(1)
                        active_label = active.inner_text().strip()
                        if name == "02-start" or name.startswith("03-review"):
                            expect(
                                page.locator('.app-sidebar [aria-current="page"]')
                            ).to_contain_text("Business Discovery")
                        if name == "04-investigation":
                            expect(
                                page.locator('.app-sidebar [aria-current="page"]')
                            ).to_contain_text("Untersuchung")
                        if name in {"05-process", "09-process-edit"}:
                            expect(
                                page.locator('.app-sidebar [aria-current="page"]')
                            ).to_contain_text("Prozessanalyse")
                        page.screenshot(path=str(OUTPUT / f"{name}.png"), full_page=True)
                        overflow = page.evaluate(
                            "document.documentElement.scrollWidth > window.innerWidth"
                        )
                        assert not overflow, f"Horizontal overflow: {name}"
                        report["pages"].append(
                            {
                                "name": name,
                                "horizontalOverflow": overflow,
                                "activeSidebar": active_label,
                            }
                        )

                    page.goto(BASE + urls["login"])
                    page.locator('[name="username"]').fill("unassigned-ui-owner")
                    page.locator('[name="password"]').fill(PASSWORD)
                    page.locator('button[type="submit"]').click()
                    page.goto(BASE + urls["unassigned"])
                    page.get_by_role("link", name="Geschäftsproblem untersuchen").click()
                    expect(
                        page.get_by_text("Ihre persönliche Zuordnung: Nicht zugeordnet")
                    ).to_be_visible()
                    expect(page.locator('[name="business_unit"] option:checked')).to_have_text(
                        "Isolierte UI-Abnahme"
                    )
                    page.locator('[name="business_unit"]').select_option(
                        label="Anderer Untersuchungsbereich"
                    )
                    capture("unit-01-unassigned-start")
                    page.get_by_role("button", name="Analyse starten", exact=True).click()
                    expect(page.locator('[aria-labelledby="decision-heading"]')).to_contain_text(
                        "Wird angelegt in: Anderer Untersuchungsbereich"
                    )
                    capture("unit-02-cross-unit-review")
                    page.get_by_role("button", name="Scope & Fokus übernehmen").click()
                    expect(
                        page.get_by_role("link", name="Zur Prozessanalyse", exact=True)
                    ).to_be_visible()
                    report["checks"].append(
                        "Owner without profile unit starts cross-unit idea discovery "
                        "and confirms result"
                    )
                    page.goto(BASE + urls["inactive"])
                    page.get_by_role("link", name="Geschäftsproblem untersuchen").click()
                    expect(page.locator('[name="business_unit"]')).to_have_value("")
                    expect(
                        page.get_by_text(
                            "Organisationseinheit der Idee: Inaktive Idee-Einheit (inaktiv)"
                        )
                    ).to_be_visible()
                    expect(
                        page.locator('[name="business_unit"] option').filter(
                            has_text="Inaktive Idee-Einheit"
                        )
                    ).to_have_count(0)
                    page.locator('[name="business_unit"]').select_option(
                        label="Isolierte UI-Abnahme"
                    )
                    page.get_by_role("button", name="Analyse starten", exact=True).click()
                    page.get_by_role("button", name="Discovery verwerfen").click()
                    page.get_by_role("link", name="Neue Untersuchung starten").click()
                    expect(page.locator('[name="business_unit"]')).to_have_value("")
                    report["checks"].append(
                        "Inactive idea unit can be replaced; discard and direct restart"
                    )
                    page.goto(BASE + urls["generic"])
                    expect(page.locator('[name="business_unit"]')).to_have_value("")
                    page.locator('[name="problem_statement"]').fill(
                        "Angebote werden manuell verglichen."
                    )
                    page.locator('[name="business_unit"]').select_option(
                        label="Isolierte UI-Abnahme"
                    )
                    page.locator('[name="sources"]').set_input_files(
                        {
                            "name": "generic-source.md",
                            "mimeType": "text/markdown",
                            "buffer": b"Synthetic source: Einkauf vergleicht Angebote.",
                        }
                    )
                    page.get_by_role("button", name="Analyse starten", exact=True).click()
                    expect(page.locator('[aria-labelledby="decision-heading"]')).to_contain_text(
                        "Wird angelegt in: Isolierte UI-Abnahme"
                    )
                    page.get_by_role("button", name="Discovery verwerfen").click()
                    page.get_by_role("link", name="Neue Untersuchung starten").click()
                    expect(page.locator('[name="business_unit"]')).to_have_value("")
                    report["checks"].append(
                        "Generic discovery without profile unit; discard and restart"
                    )
                    page.get_by_role("button", name="Benutzermenü öffnen").click()
                    page.get_by_role("button", name="Abmelden").click()
                    page.goto(BASE + urls["login"])
                    page.locator('[name="username"]').fill("idea-ui-owner")
                    page.locator('[name="password"]').fill(PASSWORD)
                    page.locator('button[type="submit"]').click()
                    page.goto(BASE + urls["discovery"])
                    page.get_by_role("link", name="Idee korrigieren").click()
                    expect(page.locator('[name="description"]')).not_to_be_empty()
                    page.get_by_role("link", name="Abbrechen", exact=True).click()
                    assert page.url == BASE + urls["discovery"]
                    page.get_by_role("link", name="Idee korrigieren").click()
                    page.locator('[name="source_note"]').fill("Synthetischer UI-Test korrigiert")
                    page.get_by_role("button", name="Änderungen speichern").click()
                    expect(
                        page.get_by_text("Synthetischer UI-Test korrigiert", exact=True)
                    ).to_be_visible()
                    report["checks"].append("Idea edit, save and cancel return to origin")
                    capture("01-idea")
                    page.get_by_role("link", name="Geschäftsproblem untersuchen").click()
                    expect(page.locator('[name="problem_statement"]')).not_to_be_empty()
                    capture("02-start")
                    expect(page.get_by_role("link", name="Zur Ursprungsidee")).to_have_attribute(
                        "href", urls["discovery"]
                    )
                    page.go_back()
                    expect(
                        page.get_by_role("link", name="Geschäftsproblem untersuchen")
                    ).to_be_visible()
                    page.go_forward()
                    page.get_by_role("button", name="Analyse starten", exact=True).click()
                    expect(
                        page.get_by_role("button", name="Scope & Fokus übernehmen")
                    ).to_be_visible()
                    review_url = page.url
                    capture("03-review")
                    for width, height in [(1280, 900), (1920, 1080)]:
                        page.set_viewport_size({"width": width, "height": height})
                        capture(f"03-review-desktop-{width}")
                    page.set_viewport_size({"width": 1440, "height": 1000})
                    page.get_by_text(
                        "Evidenz, Hypothesen, Unknowns und Widersprüche prüfen", exact=True
                    ).click()
                    expect(page.get_by_role("heading", name="Unknowns", exact=True)).to_be_visible()
                    page.get_by_text(
                        "Evidenz, Hypothesen, Unknowns und Widersprüche prüfen", exact=True
                    ).click()
                    for heading in ["value-stream-heading", "stages-heading", "process-heading"]:
                        section = page.locator(f'section[aria-labelledby="{heading}"]')
                        link = section.get_by_role("link", name="korrigieren")
                        expect(link).to_have_count(1)
                        link.click()
                        assert page.url.endswith("#id_correction")
                        expect(page.locator('[name="correction"]')).to_be_in_viewport()
                    page.locator('[name="correction"]').evaluate(
                        "el => el.removeAttribute('maxlength')"
                    )
                    page.locator('[name="correction"]').fill("x" * 4001)
                    page.locator('[name="correction"]').evaluate("el => el.form.noValidate = true")
                    page.get_by_role("button", name="Mit Korrektur neu analysieren").click()
                    expect(page.locator('[name="correction"]')).to_have_value("x" * 4001)
                    expect(page.locator(".field-attention-message")).to_be_visible()
                    report["checks"].append(
                        "Contextual correction links and visible server validation preserve input"
                    )
                    page.locator('[name="correction"]').fill("Rollen: Einkauf und Fachbereich.")
                    page.get_by_role("button", name="Mit Korrektur neu analysieren").click()
                    expect(
                        page.get_by_role("button", name="Scope & Fokus übernehmen")
                    ).to_be_visible()
                    report["checks"].append("Discovery start, history back/forward, correction")
                    page.goto(BASE + urls["discovery"])
                    page.get_by_role("link", name="Discovery fortsetzen").click()
                    assert page.url == review_url
                    page.get_by_role("button", name="Scope & Fokus übernehmen").click()
                    capture("04-investigation")
                    activity_url = page.url
                    page.get_by_role("link", name="Status aktualisieren").click()
                    assert page.url == activity_url
                    page.get_by_text("Autorisierte Quellen prüfen", exact=True).click()
                    expect(page.locator(".activity-sources li")).to_have_count(1)
                    page.get_by_role("link", name="Zur Prozessanalyse", exact=True).click()
                    page.get_by_role("link", name="Zur Ursprungsidee").click()
                    assert page.url == BASE + urls["discovery"]
                    page.get_by_role("link", name="Analyse fortsetzen").click()
                    capture("05-process")
                    expect(page.locator(".process-investigation-panel")).not_to_contain_text(
                        "läuft im Hintergrund"
                    )
                    process_url = page.url
                    page.get_by_role("link", name="Bearbeiten", exact=True).click()
                    expect(page.locator('[name="scope_start"]')).not_to_be_empty()
                    expect(page.locator('[name="scope_end"]')).not_to_be_empty()
                    capture("09-process-edit")
                    page.get_by_role("link", name="Abbrechen", exact=True).click()
                    assert page.url == process_url
                    report["checks"].append("Process edit fields and cancel navigation")
                    page.goto(BASE + urls["discovery"])
                    expect(page.get_by_role("link", name="Analyse fortsetzen")).to_be_visible()
                    report["checks"].append(
                        "Resume, materialize, investigation, process, durable idea link"
                    )
                    page.goto(BASE + urls["discard"])
                    page.get_by_role("link", name="Geschäftsproblem untersuchen").click()
                    page.locator('[name="sources"]').set_input_files(
                        {
                            "name": "ui-source.md",
                            "mimeType": "text/markdown",
                            "buffer": b"Synthetic UI source: Einkauf vergleicht Angebote.",
                        }
                    )
                    expect(page.locator("[data-file-staging-list]")).to_contain_text("ui-source.md")
                    page.get_by_role("button", name="Analyse starten", exact=True).click()
                    page.get_by_role("button", name="Discovery verwerfen").click()
                    page.goto(BASE + urls["discard"])
                    expect(
                        page.get_by_role("link", name="Geschäftsproblem untersuchen")
                    ).to_be_visible()
                    report["checks"].append("Discard releases idea")
                    page.goto(BASE + urls["intake"])
                    page.get_by_role("button", name="Direkt als Use Case übernehmen").click()
                    capture("06-intake")
                    page.locator('[name="business_owner"]').select_option(label="idea-ui-owner")
                    page.get_by_role("button", name="Weiter", exact=True).click()
                    page.get_by_role("link", name="Zurück", exact=True).click()
                    expect(page.locator('[name="title"]')).to_have_value(
                        "Angebote vergleichen (intake)"
                    )
                    page.get_by_role("button", name="Weiter", exact=True).click()
                    for step in range(2, 6):
                        expect(page.locator(".eyebrow").first).to_contain_text(f"Schritt {step}")
                        page.get_by_role("button", name="Weiter", exact=True).click()
                    capture("07-intake-review")
                    for label, step in [
                        ("Problem", 1),
                        ("Prozess", 2),
                        ("Nutzen", 4),
                        ("Kennzahl", 4),
                        ("Daten", 5),
                        ("Prüfungen", 3),
                    ]:
                        page.get_by_role("link", name=f"{label} bearbeiten", exact=True).click()
                        expect(page.locator(".eyebrow").first).to_contain_text(f"Schritt {step}")
                        page.locator('.wizard-stepper a[href="/use-cases/new/step/6/"]').click()
                    page.get_by_role(
                        "button", name="Use Case anlegen und zur Bewertung bereitstellen"
                    ).click()
                    page.goto(BASE + urls["intake"])
                    expect(
                        page.get_by_role("heading", name="Als Use Case übernommen")
                    ).to_be_visible()
                    capture("08-promoted-idea")
                    report["checks"].append("Direct intake prefill and backwards navigation")
                    assert not errors, errors
                    report["browserErrors"] = errors
                    browser.close()
                report["status"] = "passed"
            finally:
                server.terminate()
                server.wait(timeout=30)
                (OUTPUT / "report.json").write_text(
                    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            print(json.dumps(report, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    serve() if "--serve" in sys.argv else verify()
