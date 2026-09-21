from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from django.conf import settings

DEFAULT_MAX_OPENROUTER_RESPONSE_BYTES = 8_000_000
MIN_OPENROUTER_RESPONSE_BYTES = 1_000_000
MAX_OPENROUTER_RESPONSE_BYTES = 16_000_000


class OpenRouterUnavailable(RuntimeError):
    def __init__(self, message: str, *, code: str = "unavailable") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class OpenRouterResult:
    content: str
    model: str
    usage: dict[str, object]
    output_chars: int
    finish_reason: str = ""


def _setting(name: str, default: str = "") -> str:
    return str(getattr(settings, name, os.getenv(name, default)) or "")


def max_response_bytes() -> int:
    raw = _setting(
        "OPENROUTER_MAX_RESPONSE_BYTES",
        str(DEFAULT_MAX_OPENROUTER_RESPONSE_BYTES),
    ).strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise OpenRouterUnavailable(
            "OPENROUTER_MAX_RESPONSE_BYTES muss eine ganze Zahl sein.",
            code="invalid_configuration",
        ) from exc
    if not MIN_OPENROUTER_RESPONSE_BYTES <= value <= MAX_OPENROUTER_RESPONSE_BYTES:
        raise OpenRouterUnavailable(
            "OPENROUTER_MAX_RESPONSE_BYTES muss zwischen 1000000 und 16000000 liegen.",
            code="invalid_configuration",
        )
    return value


def reasoning_response_excluded() -> bool:
    return _setting("OPENROUTER_REASONING_EXCLUDE", "true").casefold() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _usage_metadata(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return {}
    allowed = ("prompt_tokens", "completion_tokens", "total_tokens", "cost")
    return {name: usage.get(name) for name in allowed if usage.get(name) is not None}


def _http_error_payload(exc: urllib.error.HTTPError) -> dict[str, Any]:
    response_limit = max_response_bytes()
    try:
        raw = exc.read(response_limit + 1)
    except (AttributeError, OSError):
        return {}
    if not raw or len(raw) > response_limit:
        return {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _requires_json_schema(
    response_format: dict[str, Any] | None,
    provider: dict[str, Any] | None,
) -> bool:
    return bool(
        response_format
        and response_format.get("type") == "json_schema"
        and provider
        and provider.get("require_parameters") is True
    )


def _schema_provider_unavailable(payload: dict[str, Any]) -> bool:
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    message = str(error.get("message") or "").casefold()
    metadata = error.get("metadata")
    error_type = ""
    raw_error = ""
    if isinstance(metadata, dict):
        error_type = str(
            metadata.get("error_type") or metadata.get("provider_error_code") or ""
        ).casefold()
        raw_error = str(metadata.get("raw") or "").casefold()
    markers = (
        "routing requirements",
        "requested parameters",
        "support the requested parameters",
        "structured output",
        "json schema",
        "invalid schema",
        "invalid_json_schema",
        "no endpoints found",
    )
    return error_type in {
        "invalid_json_schema",
        "no_available_provider",
        "provider_routing_error",
    } or any(marker in f"{message}\n{raw_error}" for marker in markers)


def _message_content(message: object) -> str:
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts).strip()


def _api_url() -> str:
    api_url = _setting(
        "OPENROUTER_API_URL",
        "https://openrouter.ai/api/v1/chat/completions",
    )
    parsed_url = urllib.parse.urlparse(api_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise OpenRouterUnavailable(
            "Die OpenRouter API-URL muss eine gültige HTTPS-URL sein.",
            code="invalid_configuration",
        )
    return api_url


def _headers(api_key: str) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-OpenRouter-Title": _setting("OPENROUTER_APP_NAME", "KI-Radar"),
    }
    site_url = _setting("OPENROUTER_SITE_URL")
    if site_url:
        headers["HTTP-Referer"] = site_url
    return headers


def _read_bounded(response) -> bytes:
    response_limit = max_response_bytes()
    payload = response.read(response_limit + 1)
    if len(payload) > response_limit:
        raise OpenRouterUnavailable(
            "OpenRouter hat eine zu große Antwort zurückgegeben.",
            code="response_too_large",
        )
    return payload


def request_openrouter(
    *,
    messages: list[dict[str, str]],
    max_tokens: int,
    timeout_seconds: int,
    temperature: float | None = 0.1,
    response_format: dict[str, Any] | None = None,
    provider: dict[str, Any] | None = None,
    reasoning_effort: str | None = None,
) -> OpenRouterResult:
    api_key = _setting("OPENROUTER_API_KEY")
    if not api_key:
        raise OpenRouterUnavailable(
            "Kein OpenRouter API-Key konfiguriert.",
            code="not_configured",
        )

    model = _setting("OPENROUTER_MODEL")
    body: dict[str, Any] = {"max_tokens": max_tokens, "messages": messages}
    reasoning: dict[str, Any] = {}
    if reasoning_effort is not None:
        reasoning["effort"] = reasoning_effort
    if reasoning_response_excluded():
        reasoning["exclude"] = True
    if reasoning:
        body["reasoning"] = reasoning
    if temperature is not None:
        body["temperature"] = temperature
    if model:
        body["model"] = model
    if response_format is not None:
        body["response_format"] = response_format
    if provider is not None:
        body["provider"] = provider

    request = urllib.request.Request(  # noqa: S310
        _api_url(),
        data=json.dumps(body).encode("utf-8"),
        headers=_headers(api_key),
        method="POST",
    )
    try:
        with urllib.request.urlopen(  # nosec B310  # noqa: S310
            request,
            timeout=timeout_seconds,
        ) as response:
            payload = json.loads(_read_bounded(response).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_payload = _http_error_payload(exc)
        if exc.code == 429:
            code = "rate_limit"
            message = "OpenRouter hat das Aufruflimit erreicht. Bitte später erneut versuchen."
        elif exc.code in {401, 403}:
            code = "unauthorized"
            message = "OpenRouter ist nicht korrekt autorisiert."
        elif (
            exc.code in {400, 422, 503}
            and _requires_json_schema(response_format, provider)
            and _schema_provider_unavailable(error_payload)
        ):
            code = "provider_schema_unsupported"
            message = (
                "Für das konfigurierte Modell steht kein OpenRouter-Provider bereit, "
                "der das erforderliche strukturierte Ausgabeschema unterstützt."
            )
        elif 500 <= exc.code <= 599:
            code = "provider_unavailable"
            message = "OpenRouter ist derzeit nicht verfügbar."
        else:
            code = "provider_error"
            message = "Die OpenRouter-Anfrage wurde abgelehnt."
        raise OpenRouterUnavailable(message, code=code) from exc
    except TimeoutError as exc:
        raise OpenRouterUnavailable(
            "Die OpenRouter-Anfrage hat das Zeitlimit überschritten.",
            code="timeout",
        ) from exc
    except urllib.error.URLError as exc:
        raise OpenRouterUnavailable(
            "OpenRouter ist derzeit nicht erreichbar.",
            code="provider_unavailable",
        ) from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise OpenRouterUnavailable(
            "OpenRouter hat ein ungültiges Antwortformat zurückgegeben.",
            code="invalid_response",
        ) from exc

    usage = _usage_metadata(payload)
    try:
        choice = payload["choices"][0]
        content = _message_content(choice["message"])
        finish_reason = str(choice.get("finish_reason") or "")
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise OpenRouterUnavailable(
            "OpenRouter hat ein unerwartetes Antwortformat zurückgegeben.",
            code="invalid_response",
        ) from exc
    if not content:
        raise OpenRouterUnavailable(
            "OpenRouter hat keine Analyse zurückgegeben.",
            code="empty_response",
        )
    returned_model = payload.get("model") if isinstance(payload, dict) else ""
    return OpenRouterResult(
        content=content,
        model=str(returned_model or model),
        usage=usage,
        output_chars=len(content),
        finish_reason=finish_reason,
    )
