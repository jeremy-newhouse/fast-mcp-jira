"""Tests for inline formatting in the markdown to ADF converter.

Underscores open or close italics only at word boundaries, so identifiers such as
``APP_ORDERS_PROD_READER`` or ``snake_case_name`` must come through untouched.
"""

import pytest

from fast_mcp_jira.utils.adf import _parse_inline_formatting, markdown_to_adf


def inline_nodes(md: str) -> list[dict]:
    """All text nodes in the converted document, flattened in order."""
    out: list[dict] = []

    def walk(node: dict) -> None:
        if node.get("type") == "text":
            out.append(node)
        for child in node.get("content", []):
            walk(child)

    walk(markdown_to_adf(md))
    return out


def joined(md: str) -> str:
    return "".join(n["text"] for n in inline_nodes(md))


def marked(md: str) -> list[tuple[str, list[str]]]:
    """(text, mark types) for every text node that carries marks."""
    return [
        (n["text"], [m["type"] for m in n["marks"]]) for n in inline_nodes(md) if n.get("marks")
    ]


# ---- identifiers must stay plain (the bug) ----


@pytest.mark.parametrize(
    ("md", "text"),
    [
        ("- Role APP_ORDERS_PROD_READER is working", "Role APP_ORDERS_PROD_READER is working"),
        (
            "ORDER_STATUS and ORDER_ITEMS in DB_MAIN_SCHEMA_ONE.TABLE_TWO",
            "ORDER_STATUS and ORDER_ITEMS in DB_MAIN_SCHEMA_ONE.TABLE_TWO",
        ),
        ("see FOO.BAR_BAZ and QUX_QUUX now", "see FOO.BAR_BAZ and QUX_QUUX now"),
        ("- snake_case_word here", "snake_case_word here"),
        ("1. snake_case_word here", "snake_case_word here"),
        ("## Role APP_ORDERS_PROD_READER", "Role APP_ORDERS_PROD_READER"),
        ("see https://x.example/a_b_c/d_e_f now", "see https://x.example/a_b_c/d_e_f now"),
        ("__init__ runs first", "__init__ runs first"),
        ("a _ b _ c", "a _ b _ c"),
        ("caf\u00e9_x_ ok", "caf\u00e9_x_ ok"),
        ("_x_\u00e9 ok", "_x_\u00e9 ok"),
    ],
    ids=[
        "bullet-identifier",
        "dotted-identifiers",
        "dot-then-underscore",
        "bullet-snake-case",
        "numbered-snake-case",
        "heading-identifier",
        "url-underscores",
        "dunder",
        "loose-underscores",
        "non-ascii-before",
        "non-ascii-after",
    ],
)
def test_underscores_inside_words_stay_literal(md, text):
    """The text keeps its underscores and nothing gets an em mark."""
    assert joined(md) == text
    assert marked(md) == []


def test_parse_inline_identifier_is_one_plain_node():
    assert _parse_inline_formatting("Role APP_ORDERS_PROD_READER is working") == [
        {"type": "text", "text": "Role APP_ORDERS_PROD_READER is working"}
    ]


# ---- real italics at word boundaries keep working ----


@pytest.mark.parametrize(
    ("md", "expected"),
    [
        ("say _italic_ now", "italic"),
        ("_italic_ at the start", "italic"),
        ("at the end _italic_", "italic"),
        ("wrapped (_italic_) in parens", "italic"),
        ("before a period _italic_.", "italic"),
        ("before a comma _italic_, then more", "italic"),
        ("_two words_ together", "two words"),
    ],
)
def test_word_boundary_italic_stays_em(md, expected):
    assert (expected, ["em"]) in marked(md)
    assert joined(md) == md.replace("_", "")


# ---- other inline formatting is untouched ----


def test_bold():
    assert ("bold", ["strong"]) in marked("a **bold** b")


def test_star_italic():
    assert ("it", ["em"]) in marked("a *it* b")


def test_code_with_underscores():
    assert ("snake_case_name", ["code"]) in marked("use `snake_case_name` here")


# ---- mixed content ----


def test_identifier_and_real_italic_in_one_line():
    md = "APP_ORDERS_PROD_READER is _really_ working"
    assert joined(md) == "APP_ORDERS_PROD_READER is really working"
    assert marked(md) == [("really", ["em"])]


def test_mention_next_to_identifier():
    nodes = _parse_inline_formatting("[~accountId:abc123|Pat] owns APP_ORDERS_PROD_READER")
    assert [n["type"] for n in nodes] == ["mention", "text"]
    assert nodes[1] == {"type": "text", "text": " owns APP_ORDERS_PROD_READER"}


def test_mention_display_name_with_underscores_is_one_mention():
    nodes = _parse_inline_formatting("[~accountId:abc123|Pat_Q_Public] hi")
    assert [n["type"] for n in nodes] == ["mention", "text"]
