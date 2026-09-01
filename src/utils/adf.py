# BlackBoard/src/utils/adf.py
# @ai-rules:
# 1. [Constraint]: Pure function, no I/O, no imports beyond stdlib. Shared by multiple hexagonal layers.
# 2. [Pattern]: Recursive tree walker over Atlassian Document Format (ADF) dicts.
# 3. [Gotcha]: ADF from Jira API can have unexpected node types -- always fall through to content recursion.
# 4. [Constraint]: Output is LLM-optimized markdown, not round-trip-faithful ADF reproduction.
# 5. [Gotcha]: Nested lists render at relative indent "" and are indented ONLY by the parent
#    _render_list's continuation-line prefix. Never pass a non-empty `indent` into a nested
#    _render_list call -- that double-counts indentation (see R2-02).
# 6. [Constraint]: Every mutually-recursive render function threads a `depth` counter and bails
#    to "" past `_MAX_DEPTH` -- required to fail soft on cyclic/pathological ADF (see R2-03).
"""Shared Atlassian Document Format (ADF) to markdown converter."""

from __future__ import annotations

import re
from typing import Any

_MAX_DEPTH = 64

# Matches a rendered line that is itself a list marker ("- " or "12. "), used to detect
# when a listItem's first rendered content is a nested list rather than its own text.
_LIST_MARKER_RE = re.compile(r"^(?:-\s|\d+\.\s)")


def adf_to_markdown(adf: dict) -> str:
    """Render an ADF document tree into markdown, failing soft on malformed or pathological input."""
    if not isinstance(adf, dict) or not adf:
        return ""

    def _children(node: dict) -> list[dict]:
        content = node.get("content", [])
        if not isinstance(content, list):
            return []
        return [item for item in content if isinstance(item, dict)]

    def _apply_marks(text: str, marks: Any) -> str:
        if not text or not isinstance(marks, list):
            return text

        rendered = text
        for mark in marks:
            if not isinstance(mark, dict):
                continue
            mark_type = mark.get("type", "")
            attrs = mark.get("attrs", {})
            if mark_type == "strong":
                rendered = f"**{rendered}**"
            elif mark_type == "em":
                rendered = f"*{rendered}*"
            elif mark_type == "code":
                rendered = f"`{rendered}`"
            elif mark_type == "strike":
                rendered = f"~~{rendered}~~"
            elif mark_type == "link":
                href = attrs.get("href") if isinstance(attrs, dict) else ""
                if href:
                    rendered = f"[{rendered}]({href})"
        return rendered

    def _render_list(node: dict, ordered: bool, indent: str = "", depth: int = 0) -> str:
        if depth > _MAX_DEPTH:
            return ""

        items = []
        start = 1
        attrs = node.get("attrs", {})
        if ordered and isinstance(attrs, dict):
            raw_start = attrs.get("order", 1)
            if isinstance(raw_start, int):
                start = raw_start

        for index, item in enumerate(_children(node)):
            if item.get("type") != "listItem":
                continue

            marker = f"{start + index}. " if ordered else "- "
            # Nested lists always render at relative indent "" -- this function's own
            # `indent` prefix is the ONLY indentation applied, on the way back up.
            body = _render_list_item(item, depth + 1).strip("\n")
            lines = body.splitlines() if body else [""]

            if lines[0] and _LIST_MARKER_RE.match(lines[0]):
                # The item has no text of its own -- its first (and only unindented)
                # rendered line is already a nested list's marker line. Keep the
                # parent marker on its own line instead of collapsing them together.
                items.append(f"{indent}{marker}".rstrip())
                for line in lines:
                    items.append(f"{indent}  {line}" if line else "")
            else:
                first_line = lines[0].strip()
                items.append(f"{indent}{marker}{first_line}".rstrip())
                for line in lines[1:]:
                    items.append(f"{indent}  {line}" if line else "")
        return ("\n".join(items) + "\n\n") if items else ""

    def _render_list_item(node: dict, depth: int = 0) -> str:
        if depth > _MAX_DEPTH:
            return ""

        chunks: list[str] = []
        for child in _children(node):
            child_type = child.get("type", "")
            if child_type == "bulletList":
                chunks.append(_render_list(child, ordered=False, depth=depth + 1).rstrip())
            elif child_type == "orderedList":
                chunks.append(_render_list(child, ordered=True, depth=depth + 1).rstrip())
            else:
                chunks.append(_render(child, depth + 1).rstrip())
        return "\n".join(part for part in chunks if part)

    def _render_table_like(node: dict, node_type: str, depth: int = 0) -> str:
        if depth > _MAX_DEPTH:
            return ""

        parts = []
        for child in _children(node):
            parts.append(_render(child, depth + 1).strip())
        if node_type == "table":
            return "\n".join(part for part in parts if part) + ("\n\n" if parts else "")
        return " ".join(part for part in parts if part)

    def _render(node: Any, depth: int = 0) -> str:
        if not isinstance(node, dict):
            return ""
        if depth > _MAX_DEPTH:
            return ""

        node_type = node.get("type", "")
        attrs = node.get("attrs", {})

        if node_type == "doc":
            return "".join(_render(child, depth + 1) for child in _children(node))
        if node_type == "paragraph":
            text = "".join(_render(child, depth + 1) for child in _children(node)).strip()
            return f"{text}\n\n" if text else ""
        if node_type == "heading":
            level = attrs.get("level", 1) if isinstance(attrs, dict) else 1
            if not isinstance(level, int) or level < 1:
                level = 1
            level = min(level, 6)
            text = "".join(_render(child, depth + 1) for child in _children(node)).strip()
            return f"{'#' * level} {text}\n\n" if text else ""
        if node_type == "text":
            text = node.get("text", "")
            if not isinstance(text, str):
                text = ""
            return _apply_marks(text, node.get("marks"))
        if node_type == "bulletList":
            return _render_list(node, ordered=False, depth=depth)
        if node_type == "orderedList":
            return _render_list(node, ordered=True, depth=depth)
        if node_type == "listItem":
            return _render_list_item(node, depth)
        if node_type == "codeBlock":
            language = ""
            if isinstance(attrs, dict):
                raw_language = attrs.get("language", "")
                language = raw_language if isinstance(raw_language, str) else ""
            body = "".join(_render(child, depth + 1) for child in _children(node)).rstrip("\n")
            return f"```{language}\n{body}\n```\n\n"
        if node_type == "blockquote":
            content = "".join(_render(child, depth + 1) for child in _children(node)).strip()
            if not content:
                return ""
            lines = content.splitlines()
            return "\n".join(f"> {line}" if line else ">" for line in lines) + "\n\n"
        if node_type == "mention":
            mention_text = ""
            if isinstance(attrs, dict):
                raw = attrs.get("text", "")
                mention_text = raw if isinstance(raw, str) else ""
            mention_text = mention_text.lstrip("@")
            return f"@{mention_text}" if mention_text else ""
        if node_type == "hardBreak":
            return "\n"
        if node_type == "rule":
            return "---\n\n"
        if node_type == "inlineCard":
            url = attrs.get("url", "") if isinstance(attrs, dict) else ""
            return f"[link]({url})" if isinstance(url, str) and url else ""
        if node_type in ("table", "tableRow", "tableHeader", "tableCell"):
            return _render_table_like(node, node_type, depth)
        if node_type == "panel":
            panel_type = attrs.get("panelType", "") if isinstance(attrs, dict) else ""
            panel_body = "".join(_render(child, depth + 1) for child in _children(node)).strip()
            if not panel_body:
                return ""
            if isinstance(panel_type, str) and panel_type:
                return f"**{panel_type.upper()}:**\n{panel_body}\n\n"
            return f"{panel_body}\n\n"
        if node_type in ("mediaSingle", "media"):
            return ""

        return "".join(_render(child, depth + 1) for child in _children(node))

    return _render(adf, 0).strip()
