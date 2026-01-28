"""Atlassian Document Format (ADF) utilities.

This module provides functions to convert plain text and markdown to ADF,
which is the rich text format used by JIRA Cloud API v3.

Supported markdown features:
- Bullet lists (- item or * item)
- Numbered lists (1. item)
- Checklists ([] unchecked, [x] checked)
- Code blocks (```code```)
- Inline code (`code`)
- Bold (**text**)
- Italic (*text* or _text_)
- Headings (# ## ###)
"""

import re
from typing import Any


def _create_text_node(text: str, marks: list[dict] | None = None) -> dict[str, Any]:
    """Create an ADF text node."""
    node: dict[str, Any] = {"type": "text", "text": text}
    if marks:
        node["marks"] = marks
    return node


def _create_paragraph(content: list[dict]) -> dict[str, Any]:
    """Create an ADF paragraph node."""
    return {"type": "paragraph", "content": content}


def _create_bullet_list(items: list[dict]) -> dict[str, Any]:
    """Create an ADF bullet list node."""
    return {"type": "bulletList", "content": items}


def _create_ordered_list(items: list[dict]) -> dict[str, Any]:
    """Create an ADF ordered list node."""
    return {"type": "orderedList", "content": items}


def _create_list_item(content: list[dict]) -> dict[str, Any]:
    """Create an ADF list item node."""
    return {"type": "listItem", "content": content}


def _create_task_list(items: list[dict]) -> dict[str, Any]:
    """Create an ADF task list (checklist) node."""
    return {"type": "taskList", "attrs": {"localId": ""}, "content": items}


def _create_task_item(content: list[dict], checked: bool = False) -> dict[str, Any]:
    """Create an ADF task item (checkbox) node."""
    return {
        "type": "taskItem",
        "attrs": {"localId": "", "state": "DONE" if checked else "TODO"},
        "content": content,
    }


def _create_code_block(text: str, language: str | None = None) -> dict[str, Any]:
    """Create an ADF code block node."""
    node: dict[str, Any] = {
        "type": "codeBlock",
        "content": [_create_text_node(text)],
    }
    if language:
        node["attrs"] = {"language": language}
    return node


def _create_heading(level: int, content: list[dict]) -> dict[str, Any]:
    """Create an ADF heading node."""
    return {"type": "heading", "attrs": {"level": level}, "content": content}


def _parse_inline_formatting(text: str) -> list[dict]:
    """Parse inline formatting (bold, italic, code) in text.

    Returns a list of ADF text nodes with appropriate marks.
    """
    if not text:
        return []

    nodes: list[dict] = []
    current_pos = 0

    # Pattern for inline formatting
    # Matches: `code`, **bold**, *italic*, _italic_
    pattern = re.compile(
        r"(`[^`]+`)|"  # inline code
        r"(\*\*[^*]+\*\*)|"  # bold
        r"(\*[^*]+\*)|"  # italic with *
        r"(_[^_]+_)"  # italic with _
    )

    for match in pattern.finditer(text):
        # Add any text before the match
        if match.start() > current_pos:
            plain_text = text[current_pos : match.start()]
            if plain_text:
                nodes.append(_create_text_node(plain_text))

        matched = match.group()

        if matched.startswith("`") and matched.endswith("`"):
            # Inline code
            code_text = matched[1:-1]
            nodes.append(_create_text_node(code_text, [{"type": "code"}]))
        elif matched.startswith("**") and matched.endswith("**"):
            # Bold
            bold_text = matched[2:-2]
            nodes.append(_create_text_node(bold_text, [{"type": "strong"}]))
        elif matched.startswith("*") and matched.endswith("*"):
            # Italic with *
            italic_text = matched[1:-1]
            nodes.append(_create_text_node(italic_text, [{"type": "em"}]))
        elif matched.startswith("_") and matched.endswith("_"):
            # Italic with _
            italic_text = matched[1:-1]
            nodes.append(_create_text_node(italic_text, [{"type": "em"}]))

        current_pos = match.end()

    # Add any remaining text
    if current_pos < len(text):
        remaining = text[current_pos:]
        if remaining:
            nodes.append(_create_text_node(remaining))

    # If no formatting found, return single text node
    if not nodes and text:
        return [_create_text_node(text)]

    return nodes


def markdown_to_adf(text: str) -> dict[str, Any]:
    """Convert markdown text to Atlassian Document Format (ADF).

    Supported markdown:
    - Bullet lists: - item or * item
    - Numbered lists: 1. item
    - Checklists: [] unchecked, [x] checked
    - Code blocks: ```language\\ncode\\n```
    - Inline code: `code`
    - Bold: **text**
    - Italic: *text* or _text_
    - Headings: # H1, ## H2, ### H3

    Args:
        text: Markdown text to convert

    Returns:
        ADF document structure
    """
    if not text:
        return {
            "type": "doc",
            "version": 1,
            "content": [_create_paragraph([_create_text_node("")])],
        }

    content: list[dict] = []
    lines = text.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Code block
        if line.startswith("```"):
            language = line[3:].strip() or None
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                code_lines.append(lines[i])
                i += 1
            content.append(_create_code_block("\n".join(code_lines), language))
            i += 1
            continue

        # Heading
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2)
            content.append(_create_heading(level, _parse_inline_formatting(heading_text)))
            i += 1
            continue

        # Checklist item
        checklist_match = re.match(r"^\s*\[([ xX])\]\s*(.*)$", line)
        if checklist_match:
            # Collect all consecutive checklist items
            task_items = []
            while i < len(lines):
                match = re.match(r"^\s*\[([ xX])\]\s*(.*)$", lines[i])
                if not match:
                    break
                checked = match.group(1).lower() == "x"
                item_text = match.group(2)
                task_items.append(
                    _create_task_item(
                        [_create_paragraph(_parse_inline_formatting(item_text))],
                        checked=checked,
                    )
                )
                i += 1
            content.append(_create_task_list(task_items))
            continue

        # Bullet list item
        bullet_match = re.match(r"^\s*[-*]\s+(.+)$", line)
        if bullet_match:
            # Collect all consecutive bullet items
            list_items = []
            while i < len(lines):
                match = re.match(r"^\s*[-*]\s+(.+)$", lines[i])
                if not match:
                    break
                item_text = match.group(1)
                list_items.append(
                    _create_list_item([_create_paragraph(_parse_inline_formatting(item_text))])
                )
                i += 1
            content.append(_create_bullet_list(list_items))
            continue

        # Numbered list item
        numbered_match = re.match(r"^\s*\d+\.\s+(.+)$", line)
        if numbered_match:
            # Collect all consecutive numbered items
            list_items = []
            while i < len(lines):
                match = re.match(r"^\s*\d+\.\s+(.+)$", lines[i])
                if not match:
                    break
                item_text = match.group(1)
                list_items.append(
                    _create_list_item([_create_paragraph(_parse_inline_formatting(item_text))])
                )
                i += 1
            content.append(_create_ordered_list(list_items))
            continue

        # Regular paragraph (skip empty lines)
        if line.strip():
            content.append(_create_paragraph(_parse_inline_formatting(line)))

        i += 1

    # Ensure at least one content node
    if not content:
        content = [_create_paragraph([_create_text_node("")])]

    return {"type": "doc", "version": 1, "content": content}


def build_adf_text(text: str) -> dict[str, Any]:
    """Build simple ADF structure for plain text content.

    This is a simple wrapper that creates a basic ADF document with
    a single paragraph. For markdown support, use markdown_to_adf().

    Args:
        text: Plain text content

    Returns:
        ADF document structure
    """
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}] if text else [],
            }
        ],
    }


def extract_text_from_adf(adf: dict[str, Any] | None) -> str:
    """Extract plain text from an ADF document.

    Args:
        adf: ADF document structure

    Returns:
        Plain text content
    """
    if not adf:
        return ""

    def extract_from_node(node: dict[str, Any]) -> str:
        if node.get("type") == "text":
            return node.get("text", "")

        content = node.get("content", [])
        texts = [extract_from_node(child) for child in content]

        # Add newlines for block-level elements
        node_type = node.get("type", "")
        if node_type in ("paragraph", "heading", "listItem", "taskItem", "codeBlock"):
            return "".join(texts) + "\n"

        return "".join(texts)

    return extract_from_node(adf).strip()
