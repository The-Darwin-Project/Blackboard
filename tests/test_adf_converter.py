# tests/test_adf_converter.py
# @ai-rules:
# 1. [Pattern]: Validate shared ADF-to-markdown converter behavior with pure dict fixtures.
# 2. [Constraint]: No network, filesystem, or Jira API calls.
"""Unit tests for src.utils.adf.adf_to_markdown."""

from src.utils.adf import adf_to_markdown


def test_simple_paragraph_text():
    adf = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello world"}]}]}
    assert adf_to_markdown(adf) == "hello world"


def test_heading_levels_h1_through_h6():
    for level in range(1, 7):
        adf = {"type": "doc", "content": [{"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": "Title"}]}]}
        assert adf_to_markdown(adf) == f"{'#' * level} Title"


def test_nested_bullet_and_ordered_lists():
    adf = {
        "type": "doc",
        "content": [{
            "type": "bulletList",
            "content": [{
                "type": "listItem",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Parent"}]},
                    {
                        "type": "orderedList",
                        "attrs": {"order": 3},
                        "content": [
                            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Child A"}]}]},
                            {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Child B"}]}]},
                        ],
                    },
                ],
            }],
        }],
    }
    rendered = adf_to_markdown(adf)
    assert rendered == "- Parent\n  3. Child A\n  4. Child B"


def test_nested_list_first_child_is_nested_list():
    """R2-01: listItem whose only content is a nested list (no leading paragraph)."""
    adf = {
        "type": "doc",
        "content": [{
            "type": "bulletList",
            "content": [{
                "type": "listItem",
                "content": [{
                    "type": "bulletList",
                    "content": [{
                        "type": "listItem",
                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "nested only"}]}],
                    }],
                }],
            }],
        }],
    }
    rendered = adf_to_markdown(adf)
    assert rendered == "-\n  - nested only"


def test_three_level_nesting_indentation():
    """R2-02: each nesting level indents by exactly 2 spaces relative to its parent."""
    adf = {
        "type": "doc",
        "content": [{
            "type": "bulletList",
            "content": [{
                "type": "listItem",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "Level 1"}]},
                    {
                        "type": "bulletList",
                        "content": [{
                            "type": "listItem",
                            "content": [
                                {"type": "paragraph", "content": [{"type": "text", "text": "Level 2"}]},
                                {
                                    "type": "bulletList",
                                    "content": [{
                                        "type": "listItem",
                                        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Level 3"}]}],
                                    }],
                                },
                            ],
                        }],
                    },
                ],
            }],
        }],
    }
    rendered = adf_to_markdown(adf)
    lines = rendered.splitlines()
    assert lines == ["- Level 1", "  - Level 2", "    - Level 3"]

    def leading_spaces(line: str) -> int:
        return len(line) - len(line.lstrip(" "))

    assert leading_spaces(lines[0]) == 0
    assert leading_spaces(lines[1]) == 2
    assert leading_spaces(lines[2]) == 4


def test_recursion_depth_guard():
    """R2-03: cyclic/pathological ADF depth fails soft instead of raising RecursionError."""
    node: dict = {"type": "paragraph", "content": [{"type": "text", "text": "leaf"}]}
    for _ in range(100):
        node = {"type": "blockquote", "content": [node]}
    adf = {"type": "doc", "content": [node]}

    assert adf_to_markdown(adf) == ""


def test_ordered_list_respects_start_order():
    adf = {
        "type": "doc",
        "content": [{
            "type": "orderedList",
            "attrs": {"order": 7},
            "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Only item"}]}]}],
        }],
    }
    assert adf_to_markdown(adf).startswith("7. Only item")


def test_text_marks_and_stacked_marks():
    marked = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "text", "text": "bold", "marks": [{"type": "strong"}]},
        {"type": "text", "text": " italic", "marks": [{"type": "em"}]},
        {"type": "text", "text": " code", "marks": [{"type": "code"}]},
        {"type": "text", "text": " strike", "marks": [{"type": "strike"}]},
    ]}]}
    rendered = adf_to_markdown(marked)
    assert "**bold**" in rendered
    assert ("* italic*" in rendered) or ("_ italic_" in rendered)
    assert "` code`" in rendered
    assert "~~ strike~~" in rendered

    stacked = {"type": "text", "text": "stack", "marks": [{"type": "strong"}, {"type": "em"}]}
    stacked_rendered = adf_to_markdown({"type": "doc", "content": [{"type": "paragraph", "content": [stacked]}]})
    assert "stack" in stacked_rendered
    assert "**" in stacked_rendered
    assert ("*" in stacked_rendered) or ("_" in stacked_rendered)


def test_link_mark_and_inline_card():
    adf = {"type": "doc", "content": [
        {"type": "paragraph", "content": [{"type": "text", "text": "Docs", "marks": [{"type": "link", "attrs": {"href": "https://example.com/docs"}}]}]},
        {"type": "paragraph", "content": [{"type": "inlineCard", "attrs": {"url": "https://example.com/card"}}]},
    ]}
    rendered = adf_to_markdown(adf)
    assert "[Docs](https://example.com/docs)" in rendered
    assert "[link](https://example.com/card)" in rendered


def test_mention_node_single_prefix():
    adf = {"type": "doc", "content": [{"type": "paragraph", "content": [
        {"type": "mention", "attrs": {"text": "@alice"}},
        {"type": "text", "text": " ping"},
    ]}]}
    rendered = adf_to_markdown(adf)
    assert "@@alice" not in rendered
    assert "@alice ping" in rendered


def test_codeblock_blockquote_hardbreak_rule_panel_table_media():
    adf = {
        "type": "doc",
        "content": [
            {"type": "codeBlock", "attrs": {"language": "python"}, "content": [{"type": "text", "text": "print('x')"}]},
            {"type": "codeBlock", "content": [{"type": "text", "text": "echo ok"}]},
            {"type": "blockquote", "content": [{"type": "paragraph", "content": [
                {"type": "text", "text": "line1"},
                {"type": "hardBreak"},
                {"type": "text", "text": "line2"},
            ]}]},
            {"type": "rule"},
            {"type": "panel", "attrs": {"panelType": "note"}, "content": [{"type": "paragraph", "content": [{"type": "text", "text": "inside panel"}]}]},
            {"type": "table", "content": [{"type": "tableRow", "content": [
                {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "H1"}]}]},
                {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "C1"}]}]},
            ]}]},
            {"type": "mediaSingle", "attrs": {"id": "m1"}, "content": [{"type": "media", "attrs": {"id": "m2"}}]},
        ],
    }
    rendered = adf_to_markdown(adf)
    assert "```python" in rendered
    assert "```\necho ok\n```" in rendered
    assert "> line1" in rendered and "> line2" in rendered
    assert "---" in rendered
    assert "inside panel" in rendered
    assert "**NOTE:**" in rendered
    assert "H1" in rendered and "C1" in rendered
    assert "m1" not in rendered and "m2" not in rendered


def test_unknown_nodes_and_malformed_input_fail_soft():
    unknown_with_content = {
        "type": "mysteryNode",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "child text"}]}],
    }
    unknown_without_content = {"type": "mysteryLeaf"}
    malformed = {"type": "doc", "content": ["not-a-dict", None, {"type": "paragraph", "content": "not-a-list"}]}

    assert adf_to_markdown(unknown_with_content) == "child text"
    assert adf_to_markdown(unknown_without_content) == ""
    assert adf_to_markdown({}) == ""
    assert adf_to_markdown(None) == ""
    assert adf_to_markdown(malformed) == ""


def test_real_worldish_fixture():
    adf = {
        "type": "doc",
        "version": 1,
        "content": [
            {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "Bug Summary"}]},
            {"type": "paragraph", "content": [
                {"type": "text", "text": "Observed "},
                {"type": "text", "text": "critical", "marks": [{"type": "strong"}]},
                {"type": "text", "text": " failure in "},
                {"type": "text", "text": "logs", "marks": [{"type": "link", "attrs": {"href": "https://example.com/logs"}}]},
            ]},
            {"type": "bulletList", "content": [
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Repro step 1"}]}]},
                {"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Repro step 2"}]}]},
            ]},
            {"type": "codeBlock", "attrs": {"language": "bash"}, "content": [{"type": "text", "text": "oc get pods -n cnv-fbc-konflux"}]},
        ],
    }
    rendered = adf_to_markdown(adf)
    assert "# Bug Summary" in rendered
    assert "**critical**" in rendered
    assert "[logs](https://example.com/logs)" in rendered
    assert "- Repro step 1" in rendered
    assert "```bash" in rendered
