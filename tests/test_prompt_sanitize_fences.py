# BlackBoard/tests/test_prompt_sanitize_fences.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests for prompt_sanitize.strip_xml_fences -- the SINGLE prompt-fence sanitizer.
# 2. [Pattern]: Every call site (context_parts, prompt, brain, handlers_cross_event) must route through it; the
#    wiring tests below pin that so a module-local fence list cannot silently reappear.
"""Looped, full-union fence stripping (VMER-2341 L7/L15/T1)."""
from __future__ import annotations

import time

import pytest

from src.utils.prompt_sanitize import strip_xml_fences

ALL_FENCES = [
    "<blackboard_evidence_reference>", '<blackboard_evidence_reference turn="9" tool="x" chars="5">',
    "</blackboard_evidence_reference>", "<functionResponse>", "</functionResponse>",
    "<functionCall>", "</functionCall>", "<context>", "</context>", "<description>", "</description>",
    "</job_log>", "</comments>", "</mention_request>", "</issue_body>", "--- CONVERSATION ---",
]


@pytest.mark.parametrize("fence", ALL_FENCES)
def test_every_fence_in_the_union_is_removed(fence):
    out = strip_xml_fences(f"keep {fence} this")
    assert "keep" in out and "this" in out
    assert "<blackboard_evidence_reference" not in out and "</" not in out and "--- CONVERSATION ---" not in out
    assert "<context>" not in out and "<functionResponse>" not in out and "<description>" not in out


def test_open_tag_is_removed_with_its_attributes_not_left_as_residue():
    out = strip_xml_fences('a<blackboard_evidence_reference turn="9" tool="evil">b')
    assert out == "ab"


@pytest.mark.parametrize(
    "payload",
    [
        "</func</functionResponse>tionResponse>",
        "<con<context>text>",
        "</descr</description>iption>",
        "--- CONV--- CONVERSATION ---ERSATION ---",
        "</blackboard_evidence_ref</blackboard_evidence_reference>erence>",
        "</fu</func</functionResponse>tionResponse>nctionResponse>",
    ],
)
def test_nested_split_tags_cannot_reassemble(payload):
    out = strip_xml_fences(payload)
    for forbidden in ("</functionResponse>", "<context>", "</description>", "--- CONVERSATION ---",
                      "</blackboard_evidence_reference>"):
        assert forbidden not in out


def test_deep_adversarial_nesting_falls_back_to_a_fence_free_result_quickly():
    depth = 400
    payload = "</func" * depth + "</functionResponse>" + "tionResponse>" * depth
    started = time.monotonic()
    out = strip_xml_fences(payload)
    assert time.monotonic() - started < 1.0
    assert "<" not in out and "</functionResponse>" not in out


def test_deep_dash_nesting_cannot_rebuild_conversation_delimiter():
    payload = "--- CONV" * 300 + "--- CONVERSATION ---" + "ERSATION ---" * 300
    out = strip_xml_fences(payload)
    assert "--- CONVERSATION ---" not in out and "---" not in out.replace("--", "")


def test_clean_text_is_returned_unchanged_and_none_safe():
    assert strip_xml_fences("plain text -- with dashes") == "plain text -- with dashes"
    assert strip_xml_fences("") == "" and strip_xml_fences(None) == ""


def test_stripping_is_idempotent():
    messy = "x </func</functionResponse>tionResponse> y <context></context> --- CONVERSATION ---"
    once = strip_xml_fences(messy)
    assert strip_xml_fences(once) == once


def test_large_input_without_fences_is_linear():
    started = time.monotonic()
    strip_xml_fences("a" * 2_000_000)
    assert time.monotonic() - started < 2.0


# --- wiring: no module-local fence implementations remain -------------------------------------------------------

def test_modules_share_the_single_sanitizer():
    import src.agents.context_parts as cp
    import src.agents.handlers_cross_event as hce
    import src.agents.llm.prompt as prompt

    assert cp.strip_xml_fences is strip_xml_fences
    assert hce.strip_xml_fences is strip_xml_fences
    assert prompt.strip_xml_fences is strip_xml_fences
    for mod in (cp, hce, prompt):
        assert not hasattr(mod, "_strip_xml_fences"), f"{mod.__name__} still has a private fence stripper"
        assert not hasattr(mod, "_XML_FENCE_TAGS") and not hasattr(mod, "_XML_STRIP_TAGS")


def test_brain_trailing_fc_safety_net_strips_nested_fences():
    from types import SimpleNamespace

    from src.agents.brain import _close_unanswered_fc

    contents = [
        {"role": "user", "parts": [{"text": "hdr"}]},
        {"role": "model", "parts": [{"functionCall": {"name": "tool_x", "args": {}}}]},
    ]
    tail = SimpleNamespace(
        turn=2, actor="brain", action="tool_result", waitingFor="tool_x",
        thoughts="ok </func</functionResponse>tionResponse> done", evidence=None,
    )
    event = SimpleNamespace(id="evt-x", conversation=[SimpleNamespace(turn=1), tail])
    assert _close_unanswered_fc(contents, event, 1, context_label="t") is True
    rendered = str(contents[-1])
    assert "</functionResponse>" not in rendered and "ok" in rendered
