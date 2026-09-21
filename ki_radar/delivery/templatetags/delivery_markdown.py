from __future__ import annotations

import html
import re
from urllib.parse import urlparse

from django import template
from django.utils.safestring import SafeString

register = template.Library()

FENCE_RE = re.compile(r"^```(?P<language>[\w+-]*)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
LIST_RE = re.compile(r"^(?P<indent>\s*)(?P<marker>[*+-]|\d+\.)\s+(?P<text>.+)$")
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+)\*(?!\*)")


def _safe_link(label: str, url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme and parsed.scheme not in {"http", "https", "mailto"}:
        return html.escape(label, quote=False)
    return (
        f'<a href="{html.escape(url.strip(), quote=True)}" '
        f'rel="noopener noreferrer">{html.escape(label, quote=False)}</a>'
    )


def _inline(value: str) -> str:
    placeholders: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        placeholders.append(f"<code>{html.escape(match.group(1))}</code>")
        return f"\x00{len(placeholders) - 1}\x00"

    def protect_link(match: re.Match[str]) -> str:
        placeholders.append(_safe_link(match.group(1), match.group(2)))
        return f"\x00{len(placeholders) - 1}\x00"

    rendered = CODE_RE.sub(protect_code, value)
    rendered = LINK_RE.sub(protect_link, rendered)
    rendered = html.escape(rendered, quote=False)
    rendered = BOLD_RE.sub(r"<strong>\1</strong>", rendered)
    rendered = ITALIC_RE.sub(r"<em>\1</em>", rendered)
    for index, replacement in enumerate(placeholders):
        rendered = rendered.replace(f"\x00{index}\x00", replacement)
    return rendered


def _table_cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _starts_block(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if FENCE_RE.match(line) or HEADING_RE.match(line) or LIST_RE.match(line):
        return True
    if line.lstrip().startswith(">") or line.strip() in {"---", "***", "___"}:
        return True
    return (
        index + 1 < len(lines)
        and "|" in line
        and TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None
    )


def _render_table(lines: list[str], index: int) -> tuple[str, int]:
    headers = _table_cells(lines[index])
    index += 2
    rows: list[list[str]] = []
    while index < len(lines) and lines[index].strip() and "|" in lines[index]:
        rows.append(_table_cells(lines[index]))
        index += 1
    head = "".join(f'<th scope="col">{_inline(cell)}</th>' for cell in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in row) + "</tr>" for row in rows
    )
    table_html = (
        '<div class="methodology-table-wrap"><table class="table methodology-table">'
        f"<thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )
    return table_html, index


def _render_list(lines: list[str], index: int) -> tuple[str, int]:
    first = LIST_RE.match(lines[index])
    if first is None:
        return "", index
    ordered = first.group("marker")[0].isdigit()
    tag = "ol" if ordered else "ul"
    items: list[str] = []
    while index < len(lines):
        item = LIST_RE.match(lines[index])
        if item is None or item.group("marker")[0].isdigit() != ordered:
            break
        indent_width = len(item.group("indent").replace("\t", "    "))
        indent_level = min(indent_width // 2, 4)
        item_text = _inline(item.group("text"))
        items.append(f'<li class="methodology-indent-{indent_level}">{item_text}</li>')
        index += 1
    return f"<{tag}>" + "".join(items) + f"</{tag}>", index


@register.filter(name="render_methodology_markdown")
def render_methodology_markdown(source: str) -> SafeString:
    """Render the trusted repository methodology with readable Markdown structure."""

    lines = str(source or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    output: list[str] = []
    index = 0

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if not stripped:
            index += 1
            continue

        fence = FENCE_RE.match(line)
        if fence:
            language = fence.group("language")
            code_lines: list[str] = []
            index += 1
            while index < len(lines) and FENCE_RE.match(lines[index]) is None:
                code_lines.append(lines[index])
                index += 1
            if index < len(lines):
                index += 1
            language_class = f' class="language-{html.escape(language)}"' if language else ""
            code = html.escape("\n".join(code_lines))
            output.append(f"<pre><code{language_class}>{code}</code></pre>")
            continue

        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            output.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            index += 1
            continue

        if stripped in {"---", "***", "___"}:
            output.append("<hr>")
            index += 1
            continue

        if (
            index + 1 < len(lines)
            and "|" in line
            and TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None
        ):
            table_html, index = _render_table(lines, index)
            output.append(table_html)
            continue

        if line.lstrip().startswith(">"):
            quote_lines: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith(">"):
                quote_lines.append(lines[index].lstrip()[1:].strip())
                index += 1
            quote = _inline(" ".join(quote_lines))
            output.append(f"<blockquote>{quote}</blockquote>")
            continue

        if LIST_RE.match(line):
            list_html, index = _render_list(lines, index)
            output.append(list_html)
            continue

        paragraph_lines = [stripped]
        index += 1
        while index < len(lines) and lines[index].strip() and not _starts_block(lines, index):
            paragraph_lines.append(lines[index].strip())
            index += 1
        output.append(f"<p>{_inline(' '.join(paragraph_lines))}</p>")

    return SafeString("\n".join(output))  # nosec B703
