from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.http import HttpRequest
from django.utils.http import url_has_allowed_host_and_scheme


def safe_internal_url(request: HttpRequest, value: str | None, fallback: str) -> str:
    candidate = (value or "").strip()
    if not candidate:
        return fallback
    if not candidate.startswith("/"):
        return fallback
    if not url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return fallback
    return candidate


def requested_return_to(request: HttpRequest, fallback: str) -> str:
    return safe_internal_url(
        request,
        request.POST.get("return_to") or request.GET.get("return_to"),
        fallback,
    )


def with_return_to(url: str, return_to: str | None) -> str:
    if not url or not return_to or not url.startswith("/") or not return_to.startswith("/"):
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["return_to"] = return_to
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))
