from __future__ import annotations

import re

URL_RE = re.compile(r"https?://[^\s`<>\"']+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.IGNORECASE,
)


def sanitize_external_markdown(content: str) -> str:
    """Apply a final deterministic privacy fence to the exported Markdown.

    Field-level policy already omits known private URL/identity fields. This final pass covers
    URLs, e-mail addresses and raw UUIDs that users may have embedded in otherwise free text.
    """

    content = URL_RE.sub("[URL redacted]", content)
    content = EMAIL_RE.sub("[email redacted]", content)
    return UUID_RE.sub("[internal-id redacted]", content)
