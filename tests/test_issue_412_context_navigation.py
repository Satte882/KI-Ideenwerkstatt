from types import SimpleNamespace

from django.test import RequestFactory
from django.urls import reverse

from ki_radar.core.templatetags.context_navigation import context_navigation


class _PageObject:
    def __init__(self, url):
        self.url = url

    def get_absolute_url(self):
        return self.url


def _request(path, namespace, url_name):
    request = RequestFactory().get(path)
    request.resolver_match = SimpleNamespace(namespace=namespace, url_name=url_name)
    return request


def _journey(url, label="Weiterarbeiten"):
    return SimpleNamespace(
        next_action=SimpleNamespace(
            url=url,
            action_method="get",
            action_label=label,
            label=label,
        )
    )


def test_use_case_detail_has_parent_navigation_without_duplicate_recommendation():
    request = _request("/use-cases/123/", "use_cases", "detail")
    use_case = _PageObject("/use-cases/123/")

    navigation = context_navigation(
        {
            "request": request,
            "use_case": use_case,
            "journey": _journey("/governance/123/"),
        }
    )

    assert navigation["back"] == {
        "url": reverse("use_cases:list"),
        "label": "Use Cases",
    }
    assert navigation["overview"] is None
    assert navigation["recommendation"] is None


def test_child_workspace_preserves_return_context_and_uses_existing_journey_recommendation():
    request = _request(
        "/use-cases/123/assessment/",
        "use_cases",
        "assessment_create",
    )
    use_case = _PageObject("/use-cases/123/")

    navigation = context_navigation(
        {
            "request": request,
            "use_case": use_case,
            "return_to": "/reporting/",
            "journey": _journey("/governance/use-cases/123/", "Governance öffnen"),
        }
    )

    assert navigation["back"] == {
        "url": "/reporting/",
        "label": "Zum Arbeitskontext",
    }
    assert navigation["overview"] == {
        "url": "/use-cases/123/",
        "label": "Use Case Übersicht",
    }
    assert navigation["recommendation"] == {
        "url": "/governance/use-cases/123/",
        "label": "Governance öffnen",
    }


def test_current_form_action_is_not_repeated_as_recommendation():
    path = "/use-cases/123/assessment/"
    request = _request(path, "use_cases", "assessment_create")

    navigation = context_navigation(
        {
            "request": request,
            "use_case": _PageObject("/use-cases/123/"),
            "journey": _journey(path, "Bewertung bearbeiten"),
        }
    )

    assert navigation["recommendation"] is None
