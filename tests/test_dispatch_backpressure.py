# tests/test_dispatch_backpressure.py
# @ai-rules:
# 1. [Pattern]: Pure unit tests for brain.compute_dispatch_backpressure -- no Redis, no async.
# 2. [Constraint]: The signal is the dispatcher's structured `action` (paused/connected), NEVER turn text.
"""Dispatch backpressure signal tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.brain import compute_dispatch_backpressure


def _t(actor: str, action: str, thoughts: str = "") -> SimpleNamespace:
    return SimpleNamespace(actor=actor, action=action, thoughts=thoughts)


def test_empty_conversation_below_threshold_is_not_backpressure():
    assert compute_dispatch_backpressure([], 0, 10) is False


def test_dispatcher_paused_is_backpressure_regardless_of_wording():
    conv = [_t("dispatcher", "paused", "Agents unavailable.")]
    assert compute_dispatch_backpressure(conv, 0, 10) is True
    conv = [_t("dispatcher", "paused", "xyzzy")]  # wording change must not flip the gate
    assert compute_dispatch_backpressure(conv, 0, 10) is True


def test_keywords_in_non_paused_dispatcher_turn_do_not_trigger():
    """The old implementation matched 'busy'/'queue'/'full' in ANY dispatcher thoughts."""
    conv = [_t("dispatcher", "acknowledge", "Spawning agent; queue is full of busy work.")]
    assert compute_dispatch_backpressure(conv, 0, 10) is False


def test_keywords_in_other_actors_do_not_trigger():
    conv = [_t("brain", "paused", "busy"), _t("developer", "message", "queue full")]
    assert compute_dispatch_backpressure(conv, 0, 10) is False


def test_connected_after_paused_clears_backpressure():
    conv = [_t("dispatcher", "paused"), _t("dispatcher", "acknowledge"), _t("dispatcher", "connected")]
    assert compute_dispatch_backpressure(conv, 0, 10) is False


def test_paused_after_connected_sets_backpressure():
    conv = [_t("dispatcher", "connected"), _t("dispatcher", "paused")]
    assert compute_dispatch_backpressure(conv, 0, 10) is True


def test_signal_does_not_expire_after_five_unrelated_turns():
    conv = [_t("dispatcher", "paused")] + [_t("brain", "think") for _ in range(20)]
    assert compute_dispatch_backpressure(conv, 0, 10) is True


@pytest.mark.parametrize("active,expected", [(9, False), (10, True), (11, True)])
def test_active_event_count_threshold_boundary(active, expected):
    assert compute_dispatch_backpressure([], active, 10) is expected


def test_connected_does_not_mask_load_threshold():
    conv = [_t("dispatcher", "connected")]
    assert compute_dispatch_backpressure(conv, 12, 10) is True


def test_dict_shaped_turns_are_supported():
    conv = [{"actor": "dispatcher", "action": "paused"}]
    assert compute_dispatch_backpressure(conv, 0, 10) is True

    conv = [{"actor": "dispatcher", "action": "paused"}, {"actor": "dispatcher", "action": "connected"}]
    assert compute_dispatch_backpressure(conv, 0, 10) is False
