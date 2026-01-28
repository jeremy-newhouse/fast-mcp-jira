"""Atlassian Document Format (ADF) utilities.

This module provides functions to convert between markdown and ADF,
which is the rich text format used by JIRA Cloud API v3.

Functions:
- markdown_to_adf(): Convert markdown text to ADF for creating/updating issues
- adf_to_markdown(): Convert ADF from API responses back to readable markdown
- extract_text_from_adf(): Extract plain text from ADF (no formatting)
- build_adf_text(): Create simple ADF from plain text

Supported markdown features (bidirectional):
- Bullet lists (- item or * item)
- Numbered lists (1. item)
- Checklists ([] unchecked, [x] checked)
- Code blocks (```language code```)
- Inline code (`code`)
- Bold (**text**)
- Italic (*text* or _text_)
- Strikethrough (~~text~~)
- Links ([text](url))
- Headings (# ## ### up to h6)
- Blockquotes (> text)
- Horizontal rules (---)
- Tables (| col | col |)
- Panels/callouts (info, warning, error, note)
- Mentions (@user)
- Images (![alt](url))
"""

import re
from typing import Any

# Allowed code block languages (JIRA-supported languages)
ALLOWED_CODE_LANGUAGES: set[str | None] = {
    None,  # No language specified
    "abap",
    "actionscript",
    "ada",
    "arduino",
    "autoit",
    "bash",
    "c",
    "clojure",
    "coffeescript",
    "cpp",
    "csharp",
    "css",
    "cuda",
    "d",
    "dart",
    "delphi",
    "diff",
    "elixir",
    "erlang",
    "fortran",
    "foxpro",
    "go",
    "graphql",
    "groovy",
    "haskell",
    "haxe",
    "html",
    "java",
    "javascript",
    "json",
    "julia",
    "kotlin",
    "latex",
    "livescript",
    "lua",
    "mathematica",
    "matlab",
    "objectivec",
    "objectivej",
    "ocaml",
    "octave",
    "pascal",
    "perl",
    "php",
    "plaintext",
    "powershell",
    "prolog",
    "puppet",
    "python",
    "qml",
    "r",
    "racket",
    "restructuredtext",
    "ruby",
    "rust",
    "sass",
    "scala",
    "scheme",
    "shell",
    "smalltalk",
    "sql",
    "standardml",
    "swift",
    "tcl",
    "tex",
    "text",
    "typescript",
    "vala",
    "vbnet",
    "verilog",
    "vhdl",
    "xml",
    "xquery",
    "yaml",
}


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
    """Create an ADF code block node.

    Args:
        text: Code content.
        language: Optional language for syntax highlighting.
            If the language is not in ALLOWED_CODE_LANGUAGES, it defaults to None.
    """
    # Validate and sanitize language
    if language:
        language = language.lower().strip()
        if language not in ALLOWED_CODE_LANGUAGES:
            language = None  # Fall back to no syntax highlighting

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

    # Map of prefix/suffix to (strip_length, mark_type)
    format_map = {
        "`": (1, "code"),
        "**": (2, "strong"),
        "*": (1, "em"),
        "_": (1, "em"),
    }

    for match in pattern.finditer(text):
        # Add any text before the match
        if match.start() > current_pos:
            plain_text = text[current_pos : match.start()]
            if plain_text:
                nodes.append(_create_text_node(plain_text))

        matched = match.group()

        # Determine format type and extract inner text
        for prefix, (strip_len, mark_type) in format_map.items():
            if matched.startswith(prefix) and matched.endswith(prefix):
                inner_text = matched[strip_len:-strip_len]
                nodes.append(_create_text_node(inner_text, [{"type": mark_type}]))
                break

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

    # Normalize escaped newlines to actual newlines
    # Handle multiple levels of escaping that can occur during JSON transmission:
    # - "\\\\n" (4 chars: double-escaped) -> "\n" (actual newline)
    # - "\\n" (2 chars: single-escaped) -> "\n" (actual newline)
    text = text.replace("\\\\n", "\n")  # Double-escaped first
    text = text.replace("\\n", "\n")  # Then single-escaped

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


def adf_to_markdown(adf: dict[str, Any] | None) -> str:
    """Convert ADF document to Markdown string.

    Supports converting most ADF node types back to their markdown equivalents:
    - Text with marks (bold, italic, code, links, strikethrough)
    - Paragraphs, headings (1-6)
    - Bullet lists, ordered lists, task lists
    - Code blocks with language
    - Blockquotes, horizontal rules
    - Tables, panels, mentions, images, emoji

    Unknown node types fall back to extracting plain text.

    Args:
        adf: ADF document structure from JIRA API

    Returns:
        Markdown-formatted string
    """
    if not adf:
        return ""

    def process_marks(text: str, marks: list[dict]) -> str:
        """Apply marks (formatting) to text in correct order."""
        for mark in marks:
            mark_type = mark.get("type", "")
            attrs = mark.get("attrs", {})

            if mark_type == "strong":
                text = f"**{text}**"
            elif mark_type == "em":
                text = f"*{text}*"
            elif mark_type == "code":
                text = f"`{text}`"
            elif mark_type == "strike":
                text = f"~~{text}~~"
            elif mark_type == "link":
                href = attrs.get("href", "")
                text = f"[{text}]({href})"
            elif mark_type == "underline":
                # No standard markdown, use HTML
                text = f"<u>{text}</u>"

        return text

    def process_node(node: dict[str, Any], indent: int = 0) -> str:
        """Recursively process an ADF node to markdown."""
        node_type = node.get("type", "")
        content = node.get("content", [])
        attrs = node.get("attrs", {})
        marks = node.get("marks", [])

        # Document root
        if node_type == "doc":
            return "".join(process_node(c) for c in content).strip()

        # Text node with optional marks
        if node_type == "text":
            text = node.get("text", "")
            return process_marks(text, marks)

        # Paragraph
        if node_type == "paragraph":
            text = "".join(process_node(c) for c in content)
            return f"{text}\n\n"

        # Heading
        if node_type == "heading":
            level = attrs.get("level", 1)
            text = "".join(process_node(c) for c in content)
            return f"{'#' * level} {text}\n\n"

        # Code block
        if node_type == "codeBlock":
            language = attrs.get("language", "")
            code = "".join(process_node(c) for c in content)
            return f"```{language}\n{code}\n```\n\n"

        # Bullet list
        if node_type == "bulletList":
            items = []
            for item in content:
                item_text = process_list_item(item, indent)
                items.append(f"{'  ' * indent}- {item_text}")
            return "\n".join(items) + "\n\n"

        # Ordered list
        if node_type == "orderedList":
            items = []
            for i, item in enumerate(content, 1):
                item_text = process_list_item(item, indent)
                items.append(f"{'  ' * indent}{i}. {item_text}")
            return "\n".join(items) + "\n\n"

        # Task list (checklist)
        if node_type == "taskList":
            items = []
            for item in content:
                state = item.get("attrs", {}).get("state", "TODO")
                checkbox = "[x]" if state == "DONE" else "[]"
                item_text = process_list_item(item, indent)
                items.append(f"{'  ' * indent}{checkbox} {item_text}")
            return "\n".join(items) + "\n\n"

        # List item / Task item - just return inner content
        if node_type in ("listItem", "taskItem"):
            return "".join(process_node(c) for c in content).strip()

        # Blockquote
        if node_type == "blockquote":
            inner = "".join(process_node(c) for c in content).strip()
            lines = inner.split("\n")
            return "\n".join(f"> {line}" for line in lines) + "\n\n"

        # Horizontal rule
        if node_type == "rule":
            return "---\n\n"

        # Hard break
        if node_type == "hardBreak":
            return "\n"

        # Table
        if node_type == "table":
            return process_table(node)

        # Panel (info/warning/error/note boxes)
        if node_type == "panel":
            panel_type = attrs.get("panelType", "info").capitalize()
            inner = "".join(process_node(c) for c in content).strip()
            lines = inner.split("\n")
            result = f"> **{panel_type}:**\n"
            result += "\n".join(f"> {line}" for line in lines)
            return result + "\n\n"

        # Mention (@user)
        if node_type == "mention":
            # Try to get display text, fall back to account ID
            display = attrs.get("text", attrs.get("id", "user"))
            return f"@{display}"

        # Emoji
        if node_type == "emoji":
            short_name = attrs.get("shortName", "")
            if short_name:
                return short_name  # Already in :emoji: format
            # Fall back to text representation
            return attrs.get("text", "")

        # Image
        if node_type == "media" or node_type == "mediaInline":
            # Media nodes have complex structure, try to get URL
            media_type = attrs.get("type", "")
            if media_type == "external":
                url = attrs.get("url", "")
                alt = attrs.get("alt", "image")
                return f"![{alt}]({url})"
            # For file attachments, just note the filename
            file_id = attrs.get("id", "attachment")
            return f"[attachment: {file_id}]"

        if node_type == "mediaSingle":
            # Container for media, process children
            return "".join(process_node(c) for c in content)

        # Inline card (smart links)
        if node_type == "inlineCard":
            url = attrs.get("url", "")
            return f"[{url}]({url})" if url else ""

        # Date
        if node_type == "date":
            timestamp = attrs.get("timestamp", "")
            return f"[date: {timestamp}]" if timestamp else ""

        # Status badge
        if node_type == "status":
            text = attrs.get("text", "")
            return f"[{text}]" if text else ""

        # Expand/collapse section
        if node_type == "expand":
            title = attrs.get("title", "Details")
            inner = "".join(process_node(c) for c in content).strip()
            return f"<details>\n<summary>{title}</summary>\n\n{inner}\n</details>\n\n"

        # Unknown node - try to extract text from children
        if content:
            return "".join(process_node(c) for c in content)

        return ""

    def process_list_item(item: dict[str, Any], indent: int) -> str:
        """Process a list item, handling nested lists."""
        result_parts = []
        for child in item.get("content", []):
            child_type = child.get("type", "")
            if child_type in ("bulletList", "orderedList", "taskList"):
                # Nested list - process with increased indent
                nested = process_node(child, indent + 1).strip()
                result_parts.append(f"\n{nested}")
            elif child_type == "paragraph":
                # Regular paragraph content
                text = "".join(process_node(c) for c in child.get("content", []))
                result_parts.append(text)
            else:
                result_parts.append(process_node(child, indent))
        return "".join(result_parts).strip()

    def process_table(table: dict[str, Any]) -> str:
        """Convert ADF table to markdown table."""
        rows = table.get("content", [])
        if not rows:
            return ""

        result_lines = []
        header_done = False

        for row in rows:
            if row.get("type") != "tableRow":
                continue

            cells = row.get("content", [])
            cell_texts = []

            for cell in cells:
                cell_type = cell.get("type", "")
                # Extract text from cell content
                cell_content = "".join(
                    process_node(c) for c in cell.get("content", [])
                ).strip()
                # Replace newlines with spaces for table cells
                cell_content = cell_content.replace("\n", " ")
                cell_texts.append(cell_content)

                # Check if this is a header cell
                if cell_type == "tableHeader" and not header_done:
                    pass  # Will add separator after first row

            result_lines.append("| " + " | ".join(cell_texts) + " |")

            # Add separator after header row
            if not header_done and any(
                c.get("type") == "tableHeader" for c in cells
            ):
                separator = "| " + " | ".join("---" for _ in cell_texts) + " |"
                result_lines.append(separator)
                header_done = True

        # If no header was found, add separator after first row
        if not header_done and result_lines:
            first_row = result_lines[0]
            col_count = first_row.count("|") - 1
            separator = "| " + " | ".join("---" for _ in range(col_count)) + " |"
            result_lines.insert(1, separator)

        return "\n".join(result_lines) + "\n\n"

    return process_node(adf)
