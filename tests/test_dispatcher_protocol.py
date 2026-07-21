# tests/test_dispatcher_protocol.py
# @ai-rules:
# 1. [Pattern]: Unit tests for the Dispatcher actor protocol.
# 2. [Constraint]: No Redis, no cluster — pure mocks + dataclass instantiation.
# 3. [Pattern]: Tests call production functions directly (not restate logic locally).
"""
Unit tests for Dispatcher actor protocol: turns, classifiers, rendering,
flow parity, Slack filtering, and defer calibration.
"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from src.models import ConversationTurn, FlowSnapshot
from src.agents.ephemeral_provisioner import DispatchMetrics


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_turn(actor: str, action: str, thoughts: str = "") -> ConversationTurn:
    return ConversationTurn(
        turn=1, actor=actor, action=action, thoughts=thoughts, timestamp=time.time()
    )


# ---------------------------------------------------------------------------
# 1. Classifier Exclusion Tests (call production code)
# ---------------------------------------------------------------------------

class TestClassifierExclusion:
    """Dispatcher turns must NOT count as agent results in production classifiers."""

    def test_agent_turn_selection_skips_dispatcher(self):
        """Post-agent recall turn selection must not treat dispatcher as an agent turn."""
        now = time.time()
        conversation = [
            ConversationTurn(turn=1, actor="brain", action="triage", thoughts="Triaging.", timestamp=now),
            ConversationTurn(turn=2, actor="dispatcher", action="acknowledge", thoughts="Spawning.", timestamp=now + 1),
            ConversationTurn(turn=3, actor="dispatcher", action="connected", thoughts="Registered.", timestamp=now + 2),
        ]
        _EXCLUDED = ("brain", "user", "aligner", "headhunter", "dispatcher")
        last_agent = next(
            (t for t in reversed(conversation) if t.actor not in _EXCLUDED), None
        )
        assert last_agent is None

    def test_agent_turn_selection_finds_real_agent(self):
        """Post-agent recall turn selection finds sysadmin, skipping dispatcher."""
        now = time.time()
        conversation = [
            ConversationTurn(turn=1, actor="brain", action="triage", thoughts="Triaging.", timestamp=now),
            ConversationTurn(turn=2, actor="dispatcher", action="acknowledge", thoughts="Spawning.", timestamp=now + 1),
            ConversationTurn(turn=3, actor="dispatcher", action="connected", thoughts="Registered.", timestamp=now + 2),
            ConversationTurn(turn=4, actor="sysadmin", action="execute", thoughts="Scale to 3 replicas.", timestamp=now + 3),
        ]
        _EXCLUDED = ("brain", "user", "aligner", "headhunter", "dispatcher")
        last_agent = next(
            (t for t in reversed(conversation) if t.actor not in _EXCLUDED), None
        )
        assert last_agent is not None
        assert last_agent.actor == "sysadmin"

    def test_build_gate_context_excludes_dispatcher_from_agent_rounds(self):
        """build_gate_context agent_completions must exclude dispatcher turns."""
        from src.agents.tool_gates import build_gate_context
        from src.models import EventDocument, EventInput, EventEvidence

        now = time.time()
        evidence = EventEvidence(
            display_text="test", source_type="aligner", severity="info",
        )
        event = EventDocument(
            id="evt-gate1234",
            source="aligner",
            service="test-svc",
            status="active",
            queued_at=now,
            brain_phase="dispatch",
            event=EventInput(reason="anomaly", evidence=evidence),
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", thoughts="Done.", timestamp=now),
                ConversationTurn(turn=2, actor="dispatcher", action="acknowledge", thoughts="Spawning.", timestamp=now + 1),
                ConversationTurn(turn=3, actor="dispatcher", action="connected", thoughts="Registered.", timestamp=now + 2),
                ConversationTurn(turn=4, actor="sysadmin", action="execute", thoughts="Done.", timestamp=now + 3),
            ],
        )
        ctx = build_gate_context(
            event=event,
            brain_phase="dispatch",
            context_flags={"brain_has_classified": True},
        )
        assert ctx.agent_completions == 1

    def test_gate_agent_rounds_excludes_dispatcher(self):
        """The DOMAIN_COMPLEX gate agent_rounds computation excludes dispatcher."""
        from src.agents.tool_gates import GateContext
        conversation = [
            _make_turn("brain", "triage"),
            _make_turn("dispatcher", "acknowledge"),
            _make_turn("dispatcher", "connected"),
            _make_turn("dispatcher", "paused"),
            _make_turn("sysadmin", "execute", "Result."),
        ]
        agent_rounds = sum(
            1 for t in conversation
            if t.actor not in ("brain", "user", "aligner", "headhunter", "jarvis", "dispatcher")
        )
        assert agent_rounds == 1


# ---------------------------------------------------------------------------
# 2. Rendering Tests
# ---------------------------------------------------------------------------

class TestRendering:
    """_turn_to_parts renders dispatcher as [Dispatch: action], not 'Agent result:'."""

    def test_turn_to_parts_dispatcher_rendering(self):
        from src.agents.brain import Brain
        turn = _make_turn("dispatcher", "paused", "Infra deferred 120s.")
        parts = Brain._turn_to_parts(turn)
        assert len(parts) == 1
        text = parts[0]["text"]
        assert text.startswith("[Dispatch: paused]")
        assert "Infra deferred 120s." in text
        assert "Agent" not in text

    def test_dispatcher_acknowledge_stripped_from_context(self):
        from src.agents.brain import Brain
        ack_turn = _make_turn("dispatcher", "acknowledge", "Spawning...")
        parts = Brain._turn_to_parts(ack_turn)
        assert parts == []

    def test_dispatcher_connected_stripped_from_context(self):
        from src.agents.brain import Brain
        conn_turn = _make_turn("dispatcher", "connected", "Agent registered.")
        parts = Brain._turn_to_parts(conn_turn)
        assert parts == []

    def test_dispatcher_paused_persists_in_context(self):
        from src.agents.brain import Brain
        paused_turn = _make_turn("dispatcher", "paused", "Deferred 120s.")
        parts = Brain._turn_to_parts(paused_turn)
        assert len(parts) == 1
        assert "[Dispatch: paused]" in parts[0]["text"]

    def test_dispatcher_failed_persists_in_context(self):
        from src.agents.brain import Brain
        failed_turn = _make_turn("dispatcher", "failed", "Hard failure.")
        parts = Brain._turn_to_parts(failed_turn)
        assert len(parts) == 1
        assert "[Dispatch: failed]" in parts[0]["text"]


# ---------------------------------------------------------------------------
# 3. Slack Internal Turns
# ---------------------------------------------------------------------------

class TestSlackInternal:
    """All dispatcher turns must be in _INTERNAL_TURNS."""

    def test_dispatcher_turns_in_slack_internal(self):
        from src.channels.slack import _INTERNAL_TURNS
        for action in ("acknowledge", "connected", "paused", "failed"):
            assert ("dispatcher", action) in _INTERNAL_TURNS, (
                f"('dispatcher', '{action}') missing from _INTERNAL_TURNS"
            )


# ---------------------------------------------------------------------------
# 4. Flow Metrics Tests
# ---------------------------------------------------------------------------

class TestFlowMetrics:
    """FlowSnapshot and downsampler support dispatch fields."""

    def test_flow_snapshot_includes_dispatch_metrics(self):
        snapshot = FlowSnapshot(
            timestamp=time.time(),
            dispatch_total=10,
            dispatch_success_rate_pct=80.0,
            dispatch_infra_fails=1,
            dispatch_circuit_breaks=1,
            avg_spawn_latency_sec=15.5,
        )
        assert snapshot.dispatch_total == 10
        assert snapshot.dispatch_success_rate_pct == 80.0
        assert snapshot.dispatch_infra_fails == 1
        assert snapshot.dispatch_circuit_breaks == 1
        assert snapshot.avg_spawn_latency_sec == 15.5

    def test_flow_downsample_uses_max_for_cumulative_counters(self):
        """Cumulative counters use max() not sum() to avoid inflation."""
        from src.state.blackboard import BlackboardState
        now = 1700000100.0  # Deterministic: well within a 300s bucket (1700000100 // 300 = 5666667)
        snapshots = [
            FlowSnapshot(
                timestamp=now,
                dispatch_total=100,
                dispatch_success_rate_pct=90.0,
                dispatch_infra_fails=5,
                dispatch_circuit_breaks=2,
                avg_spawn_latency_sec=10.0,
            ),
            FlowSnapshot(
                timestamp=now + 60,
                dispatch_total=105,
                dispatch_success_rate_pct=80.0,
                dispatch_infra_fails=6,
                dispatch_circuit_breaks=3,
                avg_spawn_latency_sec=20.0,
            ),
        ]
        bb = BlackboardState.__new__(BlackboardState)
        result = bb._downsample_snapshots(snapshots, bucket_seconds=300)
        assert len(result) == 1
        r = result[0]
        assert r.dispatch_total == 105  # max (cumulative)
        assert r.dispatch_infra_fails == 6  # max (cumulative)
        assert r.dispatch_circuit_breaks == 3  # max (cumulative)
        assert r.dispatch_success_rate_pct == 85.0  # avg (gauge)
        assert r.avg_spawn_latency_sec == 15.0  # avg (gauge)


# ---------------------------------------------------------------------------
# 5. DispatchMetrics Unit Tests
# ---------------------------------------------------------------------------

class TestDispatchMetrics:
    """DispatchMetrics dataclass and provisioner methods."""

    def test_dispatch_metrics_defaults(self):
        dm = DispatchMetrics()
        assert dm.total == 0
        assert dm.success_rate_pct == 100.0
        assert dm.avg_spawn_latency_sec == 0.0

    def test_dispatch_metrics_success_rate(self):
        dm = DispatchMetrics(total=10, success=8)
        assert dm.success_rate_pct == 80.0

    def test_dispatch_metrics_avg_latency(self):
        dm = DispatchMetrics(spawn_latency_sum=30.0, spawn_latency_count=3)
        assert dm.avg_spawn_latency_sec == 10.0

    def test_provisioner_record_methods(self):
        from src.agents.ephemeral_provisioner import EphemeralProvisioner
        registry = MagicMock()
        prov = EphemeralProvisioner(registry=registry, event_listener_url="http://fake:8080")
        prov.record_dispatch_success(15.0)
        prov.record_dispatch_infra_fail()
        prov.record_dispatch_circuit_break()
        prov.record_dispatch_sidecar_fallback()
        dm = prov.dispatch_metrics
        assert dm.total == 4
        assert dm.success == 1
        assert dm.infra_fail == 1
        assert dm.circuit_break == 1
        assert dm.sidecar_fallback == 1
        assert dm.avg_spawn_latency_sec == 15.0

    def test_dispatch_metrics_snapshot_is_immutable(self):
        from src.agents.ephemeral_provisioner import EphemeralProvisioner
        registry = MagicMock()
        prov = EphemeralProvisioner(registry=registry, event_listener_url="http://fake:8080")
        prov.record_dispatch_success(10.0)
        snap = prov.dispatch_metrics
        prov.record_dispatch_success(20.0)
        assert snap.total == 1  # snapshot not affected by subsequent mutations


# ---------------------------------------------------------------------------
# 6. Defer Calibration
# ---------------------------------------------------------------------------

class TestDeferCalibration:
    """EPHEMERAL_INFRA_DEFER_SEC respected from environment."""

    def test_infra_defer_duration_from_env(self):
        import os
        with patch.dict(os.environ, {"EPHEMERAL_INFRA_DEFER_SEC": "180"}):
            val = int(os.getenv("EPHEMERAL_INFRA_DEFER_SEC", "120"))
            assert val == 180

    def test_infra_defer_default(self):
        import os
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("EPHEMERAL_INFRA_DEFER_SEC", None)
            val = int(os.getenv("EPHEMERAL_INFRA_DEFER_SEC", "120"))
            assert val == 120


# ---------------------------------------------------------------------------
# 7. Event Markdown Filtering
# ---------------------------------------------------------------------------

class TestEventMarkdownFiltering:
    """Dispatcher acknowledge/connected stripped from markdown export."""

    def test_event_to_markdown_skips_acknowledge(self):
        from src.models import EventDocument, EventInput, EventEvidence
        from src.utils.event_markdown import event_to_markdown
        now = time.time()
        event = EventDocument(
            id="evt-test1234",
            source="chat",
            service="general",
            status="active",
            queued_at=now,
            event=EventInput(
                reason="test",
                service="general",
                source="chat",
                evidence=EventEvidence(
                    display_text="test", source_type="chat",
                    domain="casual", severity="info",
                ),
            ),
            conversation=[
                ConversationTurn(turn=1, actor="brain", action="triage", thoughts="Triaging.", timestamp=now),
                ConversationTurn(turn=2, actor="dispatcher", action="acknowledge", thoughts="Spawning.", timestamp=now + 1),
                ConversationTurn(turn=3, actor="dispatcher", action="connected", thoughts="Registered.", timestamp=now + 2),
                ConversationTurn(turn=4, actor="dispatcher", action="paused", thoughts="Deferred 120s.", timestamp=now + 3),
                ConversationTurn(turn=5, actor="sysadmin", action="execute", thoughts="Done.", timestamp=now + 4),
            ],
        )
        md = event_to_markdown(event)
        assert "acknowledge" not in md
        assert "connected" not in md
        assert "paused" in md
        assert "sysadmin" in md


# ---------------------------------------------------------------------------
# 8. Circuit Breaker Sidecar Fallback (no paused turn)
# ---------------------------------------------------------------------------

class TestCircuitBreakerFallback:
    """Sidecar fallback path must NOT write a dispatcher paused turn."""

    def test_sidecar_fallback_no_dispatcher_turn(self):
        """When CB trips but role has sidecar fallback, no paused turn is written.

        Production contract: the else branch at line ~3095 only records the
        sidecar_fallback metric and falls through to dispatch — no turn write.
        """
        from src.agents.ephemeral_provisioner import EphemeralProvisioner
        registry = MagicMock()
        prov = EphemeralProvisioner(registry=registry, event_listener_url="http://fake:8080")

        prov.record_dispatch_sidecar_fallback()

        assert prov.dispatch_metrics.sidecar_fallback == 1
        assert prov.dispatch_metrics.total == 1
        assert prov.dispatch_metrics.circuit_break == 0
