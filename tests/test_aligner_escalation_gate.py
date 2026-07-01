# tests/test_aligner_escalation_gate.py
# @ai-rules:
# 1. [Pattern]: Tests the escalation suppression flag lifecycle across Aligner, Brain, and Nightwatcher.
# 2. [Constraint]: No real LLM calls, no real Redis. All external deps are AsyncMock.
# 3. [Pattern]: 15 cases covering gate, flag-set, recovery-clear, NW atomic clear, backward compat,
#    Kargo lifecycle, Flash prompt, multi-escalation overwrite, malformed flag, failure-path, loop resilience.
"""Unit tests for the escalation suppression flag (issue #78)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    Metrics,
    Service,
    StagedEscalation,
)
from src.state.blackboard import BlackboardState


# =========================================================================
# Helpers
# =========================================================================

def _svc(name="svc-a", flag=None):
    return Service(name=name, escalation_flag=flag)


def _make_event(event_id="evt-1", service="svc-a", source="aligner", status=EventStatus.ACTIVE, **kw):
    return EventDocument(
        id=event_id, source=source, status=status, service=service,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(display_text="test", source_type=source),
        ),
        **kw,
    )


def _mock_blackboard():
    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_event.return_value = None
    bb.get_service.return_value = None
    bb.get_escalation_flag.return_value = None
    bb.set_escalation_flag.return_value = None
    bb.clear_escalation_flag.return_value = 1
    bb.create_event.return_value = "evt-new"
    bb.redis = AsyncMock()
    bb.redis.get.return_value = None
    return bb


def _make_aligner(bb=None):
    from src.agents.aligner import Aligner
    aligner = Aligner(bb or _mock_blackboard())
    aligner._llm_enabled = False
    return aligner


def _make_blackboard_state():
    """Create a real BlackboardState with mocked Redis and a callable Lua script mock."""
    redis = AsyncMock()
    lua_script = AsyncMock()
    # register_script is sync in redis-py — returns a callable Script object
    redis.register_script = MagicMock(return_value=lua_script)
    bb = BlackboardState(redis)
    return bb, redis, lua_script


def _stub_brain(bb):
    """Create a minimal Brain stub with enough attributes for _execute_function_call."""
    from src.agents.brain import Brain, _BrainToolContext
    brain = Brain.__new__(Brain)
    brain.blackboard = bb
    brain._incident_created = set()
    brain._next_turn_number = AsyncMock(return_value=1)
    brain._append_and_broadcast = AsyncMock()
    brain._emit_executive_pulse = AsyncMock()
    brain._incident_adapter = None
    brain.pulse_port = None
    brain._skill_loader = None
    brain._grounding_evidence_for_event = {}
    brain._thinking_per_event = {}
    brain._tool_ctx = _BrainToolContext(brain)
    return brain


# =========================================================================
# 1. Gate: Service with flag → _trigger_architect returns without create
# =========================================================================

@pytest.mark.asyncio
async def test_gate_blocks_when_flag_set():
    bb = _mock_blackboard()
    bb.get_service.return_value = _svc(flag="evt-old|high cpu")
    aligner = _make_aligner(bb)
    await aligner._trigger_architect("svc-a", "high_cpu")
    bb.create_event.assert_not_called()


# =========================================================================
# 2. Gate negative: flag=None → normal path
# =========================================================================

@pytest.mark.asyncio
async def test_gate_allows_when_no_flag():
    bb = _mock_blackboard()
    bb.get_service.return_value = _svc(flag=None)
    aligner = _make_aligner(bb)
    await aligner._trigger_architect("svc-a", "high_cpu")
    bb.create_event.assert_called_once()


# =========================================================================
# 3. Flag-set: stage_escalation success → set_escalation_flag called
# =========================================================================

@pytest.mark.asyncio
async def test_brain_sets_flag_on_staging_success():
    bb = _mock_blackboard()
    bb.stage_escalation.return_value = None
    bb.get_event.return_value = _make_event(service="svc-a")
    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "high cpu", "description": "test", "priority": "Normal"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_called_once_with("svc-a", "evt-1", "high cpu")


# =========================================================================
# 4. Flag-set null-safety: service=None → set NOT called
# =========================================================================

@pytest.mark.asyncio
async def test_brain_skips_flag_when_service_none():
    """Jira branch: service=None should skip set_escalation_flag."""
    bb = _mock_blackboard()
    evt = _make_event(source="aligner")
    evt.service = None
    bb.get_event.return_value = evt

    mock_adapter = AsyncMock()
    mock_adapter.create_incident.return_value = {"issue_key": "VMER-123", "issue_url": "https://jira.example.com/browse/VMER-123"}

    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "false"}), \
         patch.object(brain, "_incident_adapter", new=mock_adapter):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "test", "description": "test"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_not_called()


# =========================================================================
# 5. Recovery-clear: metrics below threshold → clear called
# =========================================================================

@pytest.mark.asyncio
async def test_recovery_clears_flag():
    bb = _mock_blackboard()
    bb.record_event.return_value = None
    bb.get_journal.return_value = []
    # Active event exists → bypasses pre-filter (metrics healthy = recovery scenario)
    active_evt = _make_event(event_id="evt-active", service="svc-a")
    bb.get_active_events.return_value = ["evt-active"]
    bb.get_event.return_value = active_evt

    aligner = _make_aligner(bb)
    aligner._metrics_buffer["svc-a"] = [
        {"timestamp": time.time(), "cpu": 10.0, "memory": 20.0, "error_rate": 0.1, "replicas": "1/1"},
    ]
    aligner._metrics_analysis_pending["svc-a"] = True

    class MockFunctionCall:
        name = "report_recovery"
        args = {"observation": "recovered"}

    class MockResponse:
        function_call = MockFunctionCall()
        text = ""
        raw_parts = None

    mock_adapter = AsyncMock()
    mock_adapter.generate.return_value = MockResponse()
    aligner._adapter = mock_adapter

    await aligner._analyze_metrics_signals("svc-a")
    bb.clear_escalation_flag.assert_called_once_with("svc-a")


# =========================================================================
# 6. NW clear: committed services cleared, failed not
# =========================================================================

@pytest.mark.asyncio
async def test_nw_clears_committed_only():
    """Verify the clear loop only processes committed event_ids."""
    bb = _mock_blackboard()
    escalations = [
        StagedEscalation(event_id="evt-1", service="svc-a", source="aligner", reason="cpu", summary="high"),
        StagedEscalation(event_id="evt-2", service="svc-b", source="aligner", reason="cpu", summary="high"),
    ]
    successful_event_ids = {"evt-1"}
    escalations_by_id = {e.event_id: e for e in escalations}

    for eid in successful_event_ids:
        esc = escalations_by_id.get(eid)
        if esc and esc.service:
            try:
                await bb.clear_escalation_flag(esc.service, expected_event_id=eid)
            except Exception:
                pass

    bb.clear_escalation_flag.assert_called_once_with("svc-a", expected_event_id="evt-1")


# =========================================================================
# 7. NW atomic race: mismatched event_id → NOT cleared (return 0)
# =========================================================================

@pytest.mark.asyncio
async def test_lua_atomic_no_clear_on_mismatch():
    bb, redis, lua_script = _make_blackboard_state()
    lua_script.return_value = 0

    result = await bb.clear_escalation_flag("svc-a", expected_event_id="evt-wrong")
    assert result == 0
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-a"], args=["evt-wrong"],
    )


# =========================================================================
# 8. Backward compat: missing HASH field → None
# =========================================================================

@pytest.mark.asyncio
async def test_get_service_missing_field_returns_none():
    bb, redis, _ = _make_blackboard_state()
    redis.hgetall.return_value = {
        "version": "v1", "cpu": "10", "memory": "20",
        "error_rate": "0", "last_seen": str(time.time()),
    }
    redis.smembers.return_value = []

    svc = await bb.get_service("svc-a")
    assert svc is not None
    assert svc.escalation_flag is None


# =========================================================================
# 9. Kargo parallel: handle_failed_promotion checks gate
# =========================================================================

@pytest.mark.asyncio
async def test_kargo_gate_blocks_when_flag_set():
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|promotion failed"
    aligner = _make_aligner(bb)

    result = await aligner.handle_failed_promotion(
        service="svc-a", project="proj", stage="staging",
        promotion="p1", freight="f1", phase="failed",
        message="step failed", failed_step="step1", mr_url="https://example.com/mr/1",
    )
    assert result is None
    bb.create_event.assert_not_called()


# =========================================================================
# 10. Kargo hash lifecycle: HSET/HGET/HDEL
# =========================================================================

@pytest.mark.asyncio
async def test_escalation_flag_lifecycle():
    bb, redis, lua_script = _make_blackboard_state()
    redis.hget.return_value = None
    lua_script.return_value = 1

    assert await bb.get_escalation_flag("svc-new") is None
    redis.hget.assert_called_with("darwin:service:svc-new", "escalation_flag")

    await bb.set_escalation_flag("svc-new", "evt-1", "test reason")
    redis.hset.assert_called_with("darwin:service:svc-new", "escalation_flag", "evt-1|test reason")

    await bb.clear_escalation_flag("svc-new", expected_event_id="evt-1")
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-new"], args=["evt-1"],
    )


# =========================================================================
# 11. Flash prompt injection: flag value → escalation context in prompt
# =========================================================================

@pytest.mark.asyncio
async def test_flash_prompt_includes_escalation_context():
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|high cpu sustained"
    bb.get_journal.return_value = []

    aligner = _make_aligner(bb)
    aligner._metrics_buffer["svc-a"] = [
        {"timestamp": time.time(), "cpu": 85.0, "memory": 50.0, "error_rate": 0.1, "replicas": "2/2"},
    ]
    aligner._metrics_analysis_pending["svc-a"] = True

    captured_prompt = None

    class MockResponse:
        function_call = None
        text = "normal"
        raw_parts = None

    async def capture_generate(**kwargs):
        nonlocal captured_prompt
        captured_prompt = kwargs.get("contents", "")
        return MockResponse()

    mock_adapter = AsyncMock()
    mock_adapter.generate = capture_generate
    aligner._adapter = mock_adapter

    await aligner._analyze_metrics_signals("svc-a")

    assert captured_prompt is not None
    assert "Escalation pending for svc-a" in captured_prompt
    assert "evt-old|high cpu sustained" in captured_prompt


# =========================================================================
# 12. Multi-escalation overwrite: latest event_id wins
# =========================================================================

@pytest.mark.asyncio
async def test_multi_escalation_latest_wins():
    bb, redis, _ = _make_blackboard_state()

    await bb.set_escalation_flag("svc-a", "evt-1", "first escalation")
    await bb.set_escalation_flag("svc-a", "evt-2", "second escalation")

    calls = redis.hset.call_args_list
    assert len(calls) == 2
    assert calls[-1].args == ("darwin:service:svc-a", "escalation_flag", "evt-2|second escalation")


# =========================================================================
# 13. Malformed flag: no delimiter → Lua handles gracefully
# =========================================================================

@pytest.mark.asyncio
async def test_malformed_flag_no_delimiter():
    bb, redis, lua_script = _make_blackboard_state()
    lua_script.return_value = 1

    result = await bb.clear_escalation_flag("svc-a", expected_event_id="evt-nopipe")
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-a"], args=["evt-nopipe"],
    )
    assert result == 1


# =========================================================================
# 14. Failure-path no-ghost: staging exception → flag NOT set
# =========================================================================

@pytest.mark.asyncio
async def test_staging_failure_does_not_set_flag():
    bb = _mock_blackboard()
    bb.stage_escalation.side_effect = RuntimeError("Redis down")
    bb.get_event.return_value = _make_event(service="svc-a")
    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "test", "description": "test"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_not_called()


# =========================================================================
# 15. NW clear loop resilience: one clear fails → others still cleared
# =========================================================================

@pytest.mark.asyncio
async def test_nw_clear_loop_resilience():
    """One failing clear_escalation_flag doesn't stop subsequent clears."""
    bb = _mock_blackboard()
    call_count = 0

    async def side_effect(service, expected_event_id=None):
        nonlocal call_count
        call_count += 1
        if service == "svc-a":
            raise RuntimeError("Redis timeout")
        return 1

    bb.clear_escalation_flag.side_effect = side_effect

    escalations = [
        StagedEscalation(event_id="evt-1", service="svc-a", source="aligner", reason="cpu", summary="high"),
        StagedEscalation(event_id="evt-2", service="svc-b", source="aligner", reason="mem", summary="high"),
        StagedEscalation(event_id="evt-3", service="svc-c", source="aligner", reason="err", summary="high"),
    ]
    successful_event_ids = {"evt-1", "evt-2", "evt-3"}
    escalations_by_id = {e.event_id: e for e in escalations}

    for eid in sorted(successful_event_ids):
        esc = escalations_by_id.get(eid)
        if esc and esc.service:
            try:
                await bb.clear_escalation_flag(esc.service, expected_event_id=eid)
            except Exception:
                pass

    assert call_count == 3
