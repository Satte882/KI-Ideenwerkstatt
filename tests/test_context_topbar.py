from pathlib import Path
from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template.loader import render_to_string
from django.test import RequestFactory

from ki_radar.use_cases.journey import JourneyState, JourneyStep

ROOT = Path(__file__).resolve().parents[1]


def test_base_uses_contextual_topbar_instead_of_static_status():
    base = (ROOT / "templates" / "base.html").read_text(encoding="utf-8")

    assert "includes/context_topbar.html" in base
    assert "css/context-topbar.css" in base
    assert "css/sidebar-journey.css" in base
    assert "sidebar-local-depth" in base
    assert "Discovery · Portfolio · Governance · Delivery" not in base
    assert "System bereit" not in base


def test_context_topbar_contains_permanent_workflow_and_next_action():
    topbar = (ROOT / "templates" / "includes" / "context_topbar.html").read_text(encoding="utf-8")
    tags = (ROOT / "ki_radar" / "core" / "templatetags" / "workflow_tags.py").read_text(
        encoding="utf-8"
    )
    stylesheet = (ROOT / "static" / "css" / "context-topbar.css").read_text(encoding="utf-8")

    assert 'aria-label="Arbeitsfortschritt"' in topbar
    assert "workflow_steps journey request" in topbar
    assert "End-to-End-Arbeitsmodell" in topbar
    assert "journey.next_action" in topbar
    assert "Nächster Schritt" in topbar
    for label in [
        "Discovery",
        "Fokus & Priorisierung",
        "Use Cases",
        "Bewertung",
        "Freigabe",
        "Delivery",
    ]:
        assert label in tags
    assert "journey-progress-current" in stylesheet
    assert "journey-progress-blocked" in stylesheet
    assert "journey-topbar-next" in stylesheet


def test_outcome_workspace_yields_topbar_ownership_to_local_lifecycle():
    request = RequestFactory().get("/wirkung-betrieb/?stage=pilot")
    request.user = AnonymousUser()
    request.resolver_match = SimpleNamespace(
        namespace="reporting",
        url_name="outcome_workspace",
    )
    action = JourneyStep(
        key="pilot",
        label="Pilot",
        state="current",
        url="/wirkung-betrieb/?stage=pilot",
        action_label="Pilotübersicht öffnen",
        reason="Der Pilot läuft im externen Delivery-System.",
    )
    journey = JourneyState(
        path_label="KI-0001 · Wirkung & Betrieb",
        steps=(action,),
        next_action=action,
    )

    rendered = render_to_string(
        "includes/context_topbar.html",
        {"journey": journey, "request": request},
        request=request,
    )

    assert rendered.strip() == ""
    assert "Pilotübersicht öffnen" not in rendered
    assert "journey-topbar" not in rendered
